import json

import pytest

from deep_research.agents.report import ReportGenerationAgent, _translate_ids
from deep_research.agents.reviewer import EvidenceReviewer
from deep_research.contracts.evidence import ReviewerRequest, UnsupportedClaim
from deep_research.contracts.reporting import ReportRequest
from tests.conftest import FakeGateway
from tests.factories import (
    make_evidence_package,
    make_plan,
    make_report_draft,
    make_review_draft,
)


async def request_with_rejected_claim():
    evidence = make_evidence_package()
    rejected = evidence.claims[0].model_copy(update={
        "claim_id": "C2", "normalized_claim": "Wrong successor model claim.",
    })
    evidence = evidence.model_copy(update={"claims": [rejected, *evidence.claims]})
    draft = make_review_draft().model_copy(update={"unsupported_claims": [
        UnsupportedClaim(claim_id="C2", rationale="Wrong product generation.")
    ]})
    review = await EvidenceReviewer(FakeGateway(draft)).review(
        ReviewerRequest(plan=make_plan(), evidence=evidence)
    )
    return ReportRequest(plan=make_plan(), evidence=evidence, review=review)


@pytest.mark.asyncio
async def test_rejected_claims_are_excluded_from_writer_and_fallback():
    request = await request_with_rejected_claim()
    prompt = ReportGenerationAgent._build_prompt(request, compact_retry=False)
    assert "Wrong successor model claim" not in prompt
    assert "supporting_excerpts" in prompt
    fallback = ReportGenerationAgent._deterministic_fallback(request)
    assert "Wrong successor model claim" not in fallback.markdown
    assert "EV sales increased" in fallback.markdown


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    "Inference: This product is superior without supporting evidence.",
    "Analysis: An unsupported factual claim.",
    "- Supported fact. [S1]\n- Uncited material claim.",
    "| Feature | Result |\n|---|---|\n| Sales | Increased. [S1] |\n| Price | Doubled. |",
])
async def test_one_cited_item_cannot_launder_uncited_list_or_table_rows(content):
    request = await request_with_rejected_claim()
    draft = make_report_draft(content=content).model_copy(
        update={"limitations": request.review.limitations}
    )
    with pytest.raises(ValueError, match="lacks a citation"):
        ReportGenerationAgent._validate_report(draft, request)


@pytest.mark.asyncio
async def test_repair_receives_the_failed_draft():
    request = await request_with_rejected_claim()
    gateway = FakeGateway(make_report_draft(content="Missing citation."), make_report_draft())
    await ReportGenerationAgent(gateway).generate(request)
    assert "Previous draft (untrusted JSON)" in gateway.calls[1]["prompt"]
    assert "Missing citation." in gateway.calls[1]["prompt"]


@pytest.mark.asyncio
async def test_short_citations_preserve_canonical_provenance():
    evidence = make_evidence_package()
    serialized = evidence.model_dump_json().replace('"S1"', '"S987654321"')
    evidence = type(evidence).model_validate_json(serialized)
    review_draft = make_review_draft()
    review_draft = type(review_draft).model_validate_json(
        review_draft.model_dump_json().replace('"S1"', '"S987654321"')
    )
    review = await EvidenceReviewer(FakeGateway(review_draft)).review(
        ReviewerRequest(plan=make_plan(), evidence=evidence)
    )
    request = ReportRequest(plan=make_plan(), evidence=evidence, review=review)
    artifact = await ReportGenerationAgent(FakeGateway(make_report_draft())).generate(request)
    assert "[S1]" in artifact.markdown
    assert "S987654321" not in artifact.markdown
    assert artifact.citation_map == {"S1": "S987654321"}
    assert artifact.cited_source_ids == ["S987654321"]


def test_aliasing_does_not_rewrite_product_names():
    payload = json.dumps({"text": "LG C4 and Samsung S90D", "source_id": "S999"})
    translated = _translate_ids(payload, {"S999": "S1"})
    assert json.loads(translated) == {"text": "LG C4 and Samsung S90D", "source_id": "S1"}


@pytest.mark.asyncio
async def test_missing_model_limitations_are_preserved_by_application_without_repair():
    request = await request_with_rejected_claim()
    gateway = FakeGateway(make_report_draft())
    artifact = await ReportGenerationAgent(gateway).generate(request)
    assert len(gateway.calls) == 1
    assert all(limitation in artifact.markdown for limitation in request.review.limitations)


@pytest.mark.asyncio
async def test_low_authority_claims_cannot_enter_even_a_fallback():
    request = await request_with_rejected_claim()
    review = request.review.model_copy(update={"source_scores": [
        request.review.source_scores[0].model_copy(update={"authority": 0.2})
    ]})
    request = request.model_copy(update={"review": review})
    gateway = FakeGateway()
    with pytest.raises(ValueError, match="No publishable claims"):
        await ReportGenerationAgent(gateway).generate(request)
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_declaring_a_rejected_claim_does_not_allow_cross_section_reuse():
    request = await request_with_rejected_claim()
    draft = make_report_draft()
    draft = draft.model_copy(update={
        "limitations": request.review.limitations,
        "sections": [draft.sections[0].model_copy(update={"supporting_claim_ids": ["C2"]})],
    })
    with pytest.raises(ValueError, match="unaccepted claim"):
        ReportGenerationAgent._validate_report(draft, request)
