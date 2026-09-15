# Case Study: Reliability Boundaries for Multi-Agent Research

## The engineering problem

Long-running research agents combine several failure-prone systems: probabilistic model output,
untrusted web content, browser automation, search APIs, parallel work, user approval, and expensive
provider calls. A convincing prototype can still fail operationally if it invents citations,
continues after a user changes scope, repeats work after a queue redelivery, or loses the entire run
when a process exits.

This project explores a stricter division of responsibility:

> Models propose typed decisions. Deterministic application code decides what may execute and what
> may be published.

The result is a local end-to-end research backend with production-oriented boundaries for
authentication, persistence, queueing, evidence provenance, cancellation, and failure handling.

## Constraints

- No web research may begin before approval of the exact plan version and content hash.
- Search results may discover pages but may not serve as evidence.
- Agents must not receive credentials or direct access to browsers, indexes, or databases.
- Every depth preset must have enforceable ceilings for queries, sources, model calls, time, and
  parallelism.
- Queue redelivery and process replacement must not duplicate completed phases when durable
  adapters are configured.
- A completed report must never contain an unresolved citation.
- Partial evidence and contradictions must remain visible to the reader.

## Architecture choices

### Typed agents behind application-owned adapters

Each role receives a Pydantic request and returns a Pydantic response. The planner can propose a
query, but only the research service can execute it. The researcher can select evidence segment
IDs, but only the application can turn valid selections into stable source, excerpt, and claim
records.

This design trades some agent autonomy for inspectability, deterministic enforcement, and simpler
security reasoning.

### A graph with explicit interrupt and repair boundaries

The workflow separates clarification, planning, approval, research, review, reporting, and
follow-up generation. Research fans out across independent workstreams, while the reviewer may
issue at most two targeted repair rounds within the original budget.

The graph describes allowed transitions; the persisted run record remains canonical business
state. Phase jobs carry the expected revision and, after approval, the plan version and hash.

### Evidence as a first-class data model

Fetched pages become bounded captured materials and then location-bearing evidence segments.
Research claims must select valid segments. The final report may cite a source in a section only
when an accepted claim for that section traces to an excerpt from that source.

This does not prove that every sentence is semantically perfect. It does make provenance explicit
and allows deterministic rejection of invented or misplaced citations.

### Failure-specific recovery

Retries are reserved for failures that may change on another attempt. Invalid structured output,
provider rejection, exhausted budgets, and insufficient evidence are handled differently from
timeouts or transient transport failures. If polished report prose remains invalid after repair,
the system can assemble reviewed claims deterministically instead of publishing unsupported text.

## Live-run evidence

Two completed outputs are stored unchanged:

| Run | Observed profile |
|---|---|
| [Quick report](../reports/Quick%20research%20sample%20report.md) | 6.5 minutes, 2 workstreams, 5 cited sources, 1 repair round |
| [Deep report](../reports/Deep%20research%20sample%20report.md) | 32 minutes, 6 parallel workstreams, 41 searches, 46 fetched pages, 225 reviewed claims, 36 cited sources |

These are raw operational artifacts, not edited writing samples. Both model-authored report drafts
failed a hard citation check and activated the deterministic fallback.

## What worked

- The runs completed through the same CLI, service, worker, and agent boundaries used by the
  deterministic test suite.
- Research remained bounded and produced a traceable source appendix.
- Invalid report citations were not silently published as polished prose.
- Reviewer limitations and contradictions survived finalization.
- The fallback returned a usable artifact rather than discarding all accepted evidence.
- The failures exposed specific improvement areas instead of becoming unobservable quality loss.

## What the artifacts exposed

The fallback optimized for integrity, not editorial quality. The reports are repetitive, their
conclusions are weak, and the follow-up fallback is generic. The deep report additionally shows:

- scope leakage from the requested Samsung S90D into Samsung S90F material;
- later-generation comparison material that is only loosely relevant to the approved topic;
- a comparison-table section rendered as prose;
- an empty planned section represented by a diagnostic sentence;
- an internal validation error that is too verbose and truncated for an end user.

These issues mean the artifacts should not be marketed as state-of-the-art research prose. They
are more valuable as proof that a safety boundary activated and as a concrete evaluation fixture
for subsequent work.

## Changes after the runs

The report pipeline now normalizes unambiguous multi-source citation groups such as `[S1, S2]`
into individually validated citation tokens before final validation. Tests cover that behavior.
The raw reports remain untouched so they continue to document the behavior observed at run time.

The portfolio documentation also distinguishes implemented local behavior from the original AWS
target architecture. This avoids implying that designed components—such as AgentCore deployment,
S3 artifact storage, a Next.js UI, SSE, and production telemetry—already exist.

## What I would measure next

Further live runs are not required to improve the evaluation discipline. The existing artifacts
can seed offline checks for:

- requested-product and time-window adherence;
- presence and shape of required sections and tables;
- repetition across report sections;
- user-safe error and limitation messages;
- citation resolution and section-level provenance;
- conclusion quality and recommendation completeness;
- fallback usefulness when model prose is rejected.

A small versioned evaluation set would make prompt, model, and validator changes reviewable in CI.
New paid live runs could then be reserved for deliberate release checkpoints.

## Takeaway

The central lesson is that reliable AI systems need two quality layers: semantic quality from the
model and non-negotiable integrity rules from the application. Deterministic validation cannot make
weak synthesis compelling, but it can prevent weak or malformed synthesis from being presented as
fully trustworthy. The next iteration should preserve those hard boundaries while evaluating and
improving the editorial layer independently.
