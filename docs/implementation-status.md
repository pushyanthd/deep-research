# Implementation Status

This document separates the original target architecture from what is present in this repository.
The [architecture plan](../arch_plan/deep-research-system-plan.md) is intentionally preserved as the
initial design proposal; it should not be read as a claim that every component has been deployed.

Status labels:

- **Implemented** — present in the repository and covered by deterministic tests.
- **Partial** — an important slice exists, but the end-user or production path is incomplete.
- **Designed** — described in the architecture plan but not implemented here.
- **External verification** — exercised only by opt-in tests or the two committed live-run artifacts.

## Research workflow

| Capability | Status | Evidence and boundary |
|---|---|---|
| Clarification loop | Implemented | Typed questions and answers, bounded rounds, best-interpretation fallback, resume behavior |
| Plan generation | Implemented | Typed questions, workstream DAG, source strategy, report outline, and depth-specific budgets |
| Human plan approval | Implemented | Exact plan version and SHA-256 hash are required before research begins |
| Parallel research | Implemented | Dependency waves, isolated research-agent instances, concurrency ceilings, and shared page cache |
| Evidence review and repair | Implemented | Source scoring, coverage checks, contradictions, unsupported claims, and bounded targeted repairs |
| Report generation | Implemented | Structured draft, outline and citation validation, deterministic fallback, Markdown artifact |
| Follow-up generation | Implemented | Typed, prioritized, section-linked questions; fallback remains intentionally conservative |
| Complete public-web run | External verification | Covered by the opt-in live workflow and two committed raw report artifacts |

## Evidence and safety

| Capability | Status | Evidence and boundary |
|---|---|---|
| Captured-page evidence | Implemented | Search snippets are discovery-only; claims select exact segments from fetched material |
| Stable provenance IDs | Implemented | Sources, excerpts, and claims receive deterministic content-derived identifiers |
| Citation resolution | Implemented | Finalization checks citations against sources available to each report section |
| Prompt-injection boundary | Implemented | Agents have no direct tools; untrusted inputs are labeled as data; the application owns execution |
| Public URL/SSRF controls | Implemented | URL shape, DNS resolution, address space, redirects, ports, and browser subresources are guarded |
| Mermaid validation | Implemented | Unsafe or invalid generated diagrams are omitted with a prose fallback |
| Automated citation entailment evaluation | Designed | Structural provenance is enforced; semantic entailment benchmarking is not yet implemented |

## Runtime and control plane

| Capability | Status | Evidence and boundary |
|---|---|---|
| Local CLI | Implemented | Interactive clarification and approval, unattended approval flag, Markdown output, cancellation |
| FastAPI run API | Implemented | Create, start, inspect, answer, update plan, approve, cancel, poll events, and fetch report |
| Local development runtime | Implemented | API and worker compose in one process with in-memory adapters |
| Checkpointed worker | Implemented | Phase jobs, node checkpoints, bounded redelivery, failure classification, and cancellation checks |
| Replayable event polling | Implemented | Ordered cursor-based event endpoint with safe metadata |
| Server-Sent Events | Designed | The event log exists, but no SSE transport is implemented |
| Plan editing in API | Implemented | Replacement plans receive a new version and hash |
| Plan editing in CLI | Designed | CLI currently approves or cancels the generated plan |
| Run deletion and artifact cleanup | Designed | No public deletion workflow is implemented |

## Persistence, authentication, and uploads

| Capability | Status | Evidence and boundary |
|---|---|---|
| In-memory persistence and queueing | Implemented | Default local mode; state does not survive a process restart |
| DynamoDB repository | Implemented | Tenant/owner-scoped records, conditional transactional writes, events, and idempotency records |
| SQS dispatcher | Implemented | Typed phase-job publishing and worker consumption boundary |
| Deployed DynamoDB/SQS environment | Designed | Adapters exist; deployment infrastructure is not included |
| Development identity | Implemented | Fixed local principal for single-user development |
| Cognito access-token verification | Implemented | JWKS caching, issuer, signature, client, token-use, expiry, scope, and tenant checks |
| Public upload endpoint | Designed | The API does not currently accept browser-originated upload binaries |
| Document quarantine and parsing | Implemented | PDF, DOCX, TXT, and Markdown validation, parsing, and location-preserving chunking |
| ClamAV scanning | Implemented | Fail-closed client boundary; requires an external ClamAV service |
| OpenSearch retrieval | Implemented | Tenant/run filters are injected by the application; requires external OpenSearch |
| S3 artifact storage and lifecycle | Designed | The current artifact path is local; no S3 repository or lifecycle automation is included |

## Models and providers

| Capability | Status | Evidence and boundary |
|---|---|---|
| Amazon Bedrock | Implemented | YAML-routed Strands model target using the AWS credential chain |
| Anthropic direct | Implemented | YAML-routed Strands model target using an API key |
| OpenAI direct | Implemented | YAML-routed Strands model target using an API key |
| Role-specific routing | Implemented | Ordered target lists, environment substitution, retry, and provider fallback |
| Live provider verification | External verification | Opt-in only because it consumes credentials and model budget |
| Provider quality regression suite | Designed | No fixed, versioned output-quality benchmark is included yet |

## Production target

| Capability | Status | Evidence and boundary |
|---|---|---|
| Separate API and worker processes | Partial | Entrypoints and durable adapters exist; no deployment definition is included |
| Next.js research workspace | Designed | No frontend is included in this repository |
| Bedrock AgentCore Runtime/Browser | Designed | The local implementation uses Strands and Playwright directly |
| AWS CDK or other infrastructure as code | Designed | No cloud infrastructure package is included |
| Secrets Manager integration | Designed | Settings currently use environment variables or the AWS credential chain |
| OpenTelemetry, dashboards, and alerts | Designed | Logging exists; production traces, metrics, dashboards, and alerts do not |
| Load and failure-injection testing | Designed | Deterministic failure-path tests exist; no production load-test suite is included |
| CI | Implemented | GitHub Actions runs Ruff and the deterministic test suite on Python 3.13 |

## Known output-quality limitations

The two reports under [`reports/`](../reports/) are unedited outputs from completed runs. Both used
the deterministic fallback because model-authored prose failed a citation validation gate. The
fallback preserved citation integrity, limitations, and contradictions, but it produced repetitive
claim-list prose rather than a polished narrative.

The deep artifact also contains scope leakage from adjacent television generations, a nominal
comparison-table section without an actual table, and an overly verbose validation diagnostic.
These are documented rather than hidden. See the [case study](case-study.md) for the engineering
interpretation and the changes already made after those runs.

## Near-term priorities

1. Add a fixed evaluation corpus for scope adherence, citation entailment, synthesis quality, and
   fallback readability without relying on new live runs for every change.
2. Improve deterministic report composition and sanitize user-facing failure diagnostics.
3. Add artifact storage and deletion abstractions before claiming a deployable multi-user service.
4. Add infrastructure as code, telemetry, load testing, and operational runbooks for a production
   deployment.
5. Build a thin report/plan UI only if product demonstration becomes more valuable than expanding
   backend evaluation coverage.
