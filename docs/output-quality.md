# Research output quality

This iteration treats report usefulness as a separate requirement from citation syntax. The original
quick and deep samples remain unchanged in `reports/` as failure examples. New reports are raw model
outputs, not hand-edited prose. Results and their generation method are recorded alongside them.

## What changed

The original writer received normalized claims without their supporting passages, lost much of the
user's brief, and could still use claims the reviewer had rejected. Its repair request named an error
but omitted the failed draft. Requiring the model to reproduce review limitations literally caused
otherwise usable prose to fall back to repetitive claim lists.

The writer now receives the complete brief, accepted claims, supporting excerpts, and explicit
section-level source permissions. Claims rejected by review, marked overconfident, or linked to a
source rated below 0.5 for authority or relevance are excluded from both the writer and its fallback.
This score threshold is a conservative policy on model judgments, not a calibrated probability.

Sections can reuse accepted evidence by declaring `supporting_claim_ids`. The application validates
those IDs and derives the permitted source set. This allows, for example, an official specification
to support both a feature table and a buying recommendation without discarding section provenance.
`ReportArtifact.section_claim_ids` records the section's eligible claim set; it is not sentence-level
entailment proof. `citation_map` maps readable report references such as `[S1]` back to stable source IDs.

The application inserts reviewer limitations and contradictions with their original provenance.
The writer owns prose, not copying audit records. Repairs receive the failed draft and the precise
validation error. Every factual table row and list item is checked for a citation independently.
Source appendices include cited sources only. Full evidence and review records remain in the run.

Research and review also receive the complete scope, exact entities, geography, time constraints,
and decision criteria. Research prompts expose only the task's permitted question and section IDs.
Report evidence selection balances questions and sources so an early workstream cannot crowd out
the rest. Deep research initially allocates at most six sources per workstream and twenty claims per
workstream; the approved source/search ceilings still bound later targeted repairs.

The fetcher prefers article/main text to page navigation and handles PDF downloads through a bounded
HTTP stream with a public-URL check on every redirect. Explicit `site:` searches are also passed as
Tavily domain filters. These changes address observed failures, including unrelated search results,
marketplace Q&A pages presented as laboratory evidence, and headless-browser PDF download errors.

## Models and budget

OpenAI calls use the Responses API with one forced structured function call per attempt. Closed
schemas use strict decoding. Contracts containing open dictionaries, such as brief definitions, use
non-strict function calling and Pydantic validation; schema failures return field-level feedback on
the bounded retry. Bedrock and Anthropic still use their existing Strands adapters.

The default is GPT-5.4 mini, with low reasoning for clarification, planning, extraction, and follow-up
questions and medium reasoning for review and reporting. GPT-4.1 mini and GPT-4.1 were tried during this
iteration; one GPT-4.1 review accepted stale pricing and an unsupported absence claim which the later
reasoning-model review flagged. This is a small development observation with prompt changes, not a
controlled model ranking. Models remain configurable by role.

Pricing is pinned in `models/spend.py` from the official model pages: [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1), and [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini). Update the table deliberately when rates
change. Cached inputs are charged at the uncached rate in estimates.

`OPENAI_SPEND_LIMIT_USD=17` applies cumulatively to calls sharing
`OPENAI_SPEND_LEDGER_PATH=.data/openai-spend.sqlite`. SQLite transactions reserve a conservative input
byte bound plus the maximum output allowance before sending a request. Reported usage settles the
reservation even if parsing later fails. Timeouts, cancellation, and responses without usage retain
their reservations; unknown model prices fail before a paid request. Concurrent local processes cannot
overbook the same ledger. Do not delete the ledger to restart a run.

This is a local OpenAI cost control, not the account balance or a distributed multi-host quota. It
does not cover Tavily, other providers, or unrelated API clients. Evaluation `usage` and the ledger
contain measured OpenAI tokens and conservative cost estimates; the older run `BudgetUsage` model
token/cost fields are not yet synchronized with this ledger and must not be presented as billing.

## Reproduce and inspect

The versioned cases cover quick OLED buying advice, a deep three-model comparison, and a technical
retrieval architecture decision. Live runs are opt-in and persist `run.json`, `report.md`,
`model-outputs.json`, and `metrics.json` under ignored `research-reports/` directories.

```bash
python -m deep_research.evaluation --case oled-quick --live
python -m deep_research.evaluation --case oled-deep --live
python -m deep_research.evaluation --case retrieval-quick --live

# Re-review and rewrite the same captured evidence without searching/fetching again.
python -m deep_research.evaluation \
  --replay-run research-reports/evals/oled-quick/run.json \
  --output research-reports/replay --live

# Hold evidence AND review constant to isolate report-generation changes.
python -m deep_research.evaluation \
  --report-request research-reports/replay/request.json \
  --output research-reports/writer-comparison --live
```

Use `--model` and `--report-model` for experiments. Replays have exhausted research-repair capacity by
design; their gaps become limitations. They are labeled separately from fresh end-to-end runs. Saved
requests include third-party excerpts and possibly private uploads; keep them local unless reviewed.

Structural metrics report unresolved references, exact repeated paragraphs, cited table rows, empty
sections, fallback use, and word counts. They are not factual accuracy scores. Review the raw report
for actual decision usefulness, entity/year/region fidelity, measurement comparability, and justified
recommendations. The small live sample is a development check, not evidence of broad quality gains or
statistical significance. There is no independent, calibrated entailment benchmark yet.

The remaining limitations are substantive: search and extraction can still miss a key source;
reviewer judgments can be wrong; citations do not prove every sentence is entailed; and reports can
still be repetitive in meaning even when exact duplicate counts are zero. Unverified current prices
must remain unknown. A limited report is preferable to inventing a complete comparison.
