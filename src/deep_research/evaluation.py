"""Opt-in, reproducible live runs and offline report diagnostics. Never runs during pytest."""

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

from deep_research.agents.report import ReportGenerationAgent
from deep_research.agents.reviewer import EvidenceReviewer
from deep_research.auth.cognito import DevelopmentAuthenticator
from deep_research.cli import run_cli
from deep_research.contracts.evidence import ReviewerRequest
from deep_research.contracts.reporting import ReportRequest
from deep_research.contracts.runs import ResearchRun
from deep_research.dev_app import build_local_runtime
from deep_research.models.gateway import ModelGateway
from deep_research.settings import AppSettings


def report_metrics(markdown: str) -> dict[str, object]:
    """Structural diagnostics, explicitly not a factual-correctness or semantic quality score."""
    body, _, sources = markdown.partition("## Sources")
    paragraphs = [
        re.sub(r"\[S\d+\]", "", p).strip().casefold()
        for p in re.split(r"\n\s*\n", body)
        if p.strip() and not p.startswith("#") and not p.startswith("|")
    ]
    cited = set(re.findall(r"\[(S\d+)\]", body))
    listed = set(re.findall(r"\[(S\d+)\]", sources))
    return {
        "words": len(body.split()),
        "cited_sources": len(cited),
        "unresolved_citations": sorted(cited - listed),
        "duplicate_paragraphs": len(paragraphs) - len(set(paragraphs)),
        "table_data_rows": sum(
            line.startswith("|") and bool(re.search(r"\[S\d+\]", line))
            for line in body.splitlines()
        ),
        "fallback": "assembled deterministically" in body,
        "empty_evidence_sections": body.count("No evidence-backed claim was available"),
    }


async def run_case(case: dict, output: Path, settings: AppSettings) -> int:
    runtime = build_local_runtime(settings)
    runtime.gateway.capture_outputs = True
    captured_run_id = None

    def emit(message: str) -> None:
        nonlocal captured_run_id
        if message.startswith("Run ") and " started with " in message:
            captured_run_id = message.split()[1]
        print(message, flush=True)

    def answer(prompt: str) -> str:
        # Cases provide all assumptions up front. Unexpected interaction fails visibly.
        raise EOFError(f"Evaluation case unexpectedly required clarification: {prompt}")

    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    started = time.monotonic()
    status = await run_cli(
        argparse.Namespace(topic=case["topic"], depth=case["depth"],
                           auto_approve_plan=True, output=output / "report.md"),
        runtime, input_fn=answer, output_fn=emit,
    )
    principal = await DevelopmentAuthenticator().authenticate(None)
    if captured_run_id is not None:
        run = await runtime.control.get_run(principal, captured_run_id)
        (output / "run.json").write_text(run.model_dump_json(indent=2))
        checkpoint = run.graph_checkpoint
        if run.plan and checkpoint.evidence and checkpoint.review and checkpoint.report:
            report_request = ReportRequest(
                plan=run.plan, evidence=checkpoint.evidence, review=checkpoint.review,
                budget_usage=run.budget_usage,
            )
            (output / "request.json").write_text(report_request.model_dump_json(indent=2))
        (output / "model-outputs.json").write_text(
            json.dumps(runtime.gateway.captured_outputs, indent=2) + "\n"
        )
        summary = {
            "case_id": case["id"], "state": run.state.value,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "model_routes": {
                role: [target.model_id for _, target in settings.load_models().route_for(role)]
                for role in settings.load_models().roles
            },
            "usage": runtime.gateway.usage_summary(),
            "research_budget_usage": run.budget_usage.model_dump(mode="json"),
            "report_metrics": report_metrics(run.graph_checkpoint.report.markdown)
            if run.graph_checkpoint.report else None,
        }
        (output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    return status


async def replay(
    path: Path, output: Path, settings: AppSettings, *, report_only: bool = False,
) -> int:
    """Re-review frozen evidence and rewrite without paying for discovery/fetch again."""
    gateway = ModelGateway(
        settings.validate_model_credentials(), spend_limit_usd=settings.openai_spend_limit_usd,
        spend_ledger_path=settings.openai_spend_ledger_path,
    )
    gateway.capture_outputs = True
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    raw = await asyncio.to_thread(path.read_text)
    if report_only:
        report_request = ReportRequest.model_validate_json(raw)
    else:
        run = ResearchRun.model_validate_json(raw)
        assert run.plan is not None and run.graph_checkpoint.evidence is not None
        request = ReviewerRequest(
            plan=run.plan, evidence=run.graph_checkpoint.evidence,
            budget_usage=run.budget_usage, repair_round=run.plan.budget.reviewer_retries,
        )
        review = await EvidenceReviewer(gateway).review(request)
        (output / "review.json").write_text(review.model_dump_json(indent=2))
        report_request = ReportRequest(
            plan=run.plan, evidence=request.evidence, review=review, budget_usage=run.budget_usage,
        )
    artifact = await ReportGenerationAgent(gateway).generate(report_request)
    (output / "report.md").write_text(artifact.markdown)
    (output / "artifact.json").write_text(artifact.model_dump_json(indent=2))
    (output / "request.json").write_text(report_request.model_dump_json(indent=2))
    (output / "model-outputs.json").write_text(json.dumps(gateway.captured_outputs, indent=2))
    kind = "frozen-evidence-and-review replay" if report_only else "frozen-evidence replay"
    metrics = {"kind": kind,
               "usage": gateway.usage_summary(),
               "report_metrics": report_metrics(artifact.markdown)}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2), flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("evals/cases.json"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--case")
    mode.add_argument("--replay-run", type=Path)
    mode.add_argument("--report-request", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--report-model")
    parser.add_argument("--output", type=Path, default=Path("research-reports/evals"))
    parser.add_argument("--live", action="store_true", help="Authorize paid API and web calls")
    args = parser.parse_args()
    if not args.live:
        parser.error("Live evaluation requires --live; it consumes configured API budgets.")
    settings = AppSettings(model_provider="openai", **{
        key: value for key, value in {
            "openai_model_id": args.model, "openai_report_model_id": args.report_model,
        }.items() if value
    })
    if args.replay_run or args.report_request:
        raise SystemExit(asyncio.run(replay(
            args.replay_run or args.report_request, args.output, settings,
            report_only=bool(args.report_request),
        )))
    cases = json.loads(args.cases.read_text())
    case = next((item for item in cases if item["id"] == args.case), None)
    if case is None:
        parser.error(f"Unknown case: {args.case}")
    raise SystemExit(asyncio.run(run_case(case, args.output / args.case, settings)))


if __name__ == "__main__":
    main()
