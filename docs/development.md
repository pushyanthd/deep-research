# Development and Operations

## Requirements

- Python 3.13
- A Tavily API key for live public-web research
- Credentials for at least one model provider: Amazon Bedrock, Anthropic, or OpenAI
- Playwright Chromium for live page retrieval

## Installation

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
playwright install chromium
cp .env.example .env
```

The deterministic suite does not require credentials or Chromium:

```bash
pytest
ruff check src tests
```

## CLI

```text
deep-research-run TOPIC [--depth quick|standard|deep] [--provider openai|anthropic|bedrock]
                        [--output PATH] [--auto-approve-plan] [--verbose]
```

- `--depth` defaults to `standard`.
- `--provider` overrides `MODEL_PROVIDER` for one invocation.
- `--output` may be a Markdown filename or a directory. A directory receives `<run_id>.md`.
- `--auto-approve-plan` skips the interactive plan prompt. Non-interactive stdin requires this
  flag; an unanswered clarification still cancels the run safely.
- `--verbose` logs routing, provider fallback, and adapter failures without logging prompts,
  evidence text, or credentials.
- Ctrl-C requests cooperative cancellation.

Example:

```bash
deep-research-run "Summarize current fusion milestones" --depth quick --output research-reports/
```

Reviewing the plan is recommended. Rejecting it cancels the run; the current CLI does not provide
interactive plan editing.

## Local API and worker

Run both in a single process with shared in-memory adapters:

```bash
deep-research-dev
```

The API is served at `http://127.0.0.1:8000`. This mode is intended for local development and loses
run state on restart.

For separate processes, configure `DYNAMODB_RUNS_TABLE` and `SQS_JOBS_QUEUE_URL`, serve
`deep_research.api.app:app`, and run:

```bash
deep-research-worker
```

The repository includes the adapters and entrypoints but not AWS infrastructure definitions.

## Configuration

Settings load from `.env` or the environment through `pydantic-settings`. See
[`../.env.example`](../.env.example) for the complete template.

| Setting | Purpose |
|---|---|
| `MODEL_PROVIDER`, `MODEL_FALLBACK_ORDER` | Primary provider and optional ordered fallbacks |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Direct-provider credentials; Bedrock uses the AWS chain |
| `ANTHROPIC_MODEL_ID`, `OPENAI_MODEL_ID`, `OPENAI_REPORT_MODEL_ID`, `DEFAULT_MODEL_ID`, `AWS_REGION` | Model target substitutions |
| `OPENAI_SPEND_LIMIT_USD`, `OPENAI_SPEND_LEDGER_PATH` | Cumulative local OpenAI budget and SQLite ledger |
| `MODEL_CONFIG_PATH` | YAML model-routing configuration |
| `TAVILY_API_KEY`, `TAVILY_BASE_URL`, `PLAYWRIGHT_HEADLESS` | Public-web adapters |
| `AUTH_MODE`, `COGNITO_*` | Development identity or Cognito access-token verification |
| `DYNAMODB_RUNS_TABLE`, `SQS_JOBS_QUEUE_URL`, `RUN_RETENTION_DAYS` | Durable run state and dispatch |
| `UPLOADS_ENABLED`, `OPENSEARCH_*`, `CLAMAV_*`, `UPLOAD_ARTIFACT_ROOT` | Private-document pipeline |

[`../config/models.yaml`](../config/models.yaml) maps every agent role to ordered provider targets.
Fallback applies to a whole structured operation and never combines partial outputs from different
providers.

## HTTP API

Every mutating run command requires an `Idempotency-Key` header between 8 and 200 characters.
Reusing a key for the same command replays its response; reusing it for different input returns
`409`.

```text
POST /v1/runs                          create a run
POST /v1/runs/{run_id}/start           enqueue clarification
GET  /v1/runs/{run_id}                 inspect state, checkpoint, and budget
POST /v1/runs/{run_id}/clarifications  submit typed answers
PUT  /v1/runs/{run_id}/plan            save a replacement plan version
POST /v1/runs/{run_id}/plan/approve    approve exact version and SHA-256 hash
POST /v1/runs/{run_id}/cancel          request cooperative cancellation
GET  /v1/runs/{run_id}/events?after=N  poll replayable ordered events
GET  /v1/runs/{run_id}/report          retrieve Markdown after completion
```

Agent-level debug routes exist only when `create_app` receives an explicit gateway or
`expose_agent_debug_routes=True`. The normal API application does not construct research agents in
the request process.

## Testing

```bash
pytest
pytest -m live
ruff check src tests
```

The default Pytest configuration excludes `live` tests. The deterministic suite uses fake model
and research adapters and is safe to run without credentials. The live suite calls configured
models, Tavily, and public websites and therefore consumes external resources.

Test coverage includes:

- structured output validation and bounded repairs;
- depth budgets and planning DAG validation;
- evidence construction, merging, review, and citation resolution;
- page-cache single-flight behavior and cancellation;
- SSRF defenses and redirect handling;
- worker failure classification, redelivery ceilings, and checkpoint resume;
- run transitions, idempotency, event cursors, and stale approval;
- Cognito verification and tenant-scoped persistence;
- upload validation, scanning, parsing, and indexing;
- interactive and unattended CLI behavior.

## Failure behavior

| Failure code | Meaning | Worker behavior |
|---|---|---|
| `worker_validation_error` | Deterministic agent or checkpoint validation failed | Fail without redelivery |
| `model_output_limit` | Provider stopped at the configured output ceiling | Fail without repeating spend |
| `model_provider_rejected` | Credentials, billing, or request was rejected | Fail without redelivery |
| `research_service_configuration` | Approved plan requires an unavailable adapter | Fail immediately |
| `insufficient_evidence` | No reviewed evidence-backed claim remains | Do not generate a report |
| `worker_retry_ceiling` | Transient failures exhausted delivery attempts | Fail after the ceiling |
| `worker_conflict_ceiling` | Revision conflicts did not converge | Fail after the ceiling |

## Troubleshooting

- **Provider credential error:** ensure `MODEL_PROVIDER` matches a populated key. For Bedrock,
  verify that `aws sts get-caller-identity` works in the same environment.
- **Chromium missing:** run `playwright install chromium` inside the active virtual environment.
- **`model_output_limit`:** adjust the target's `max_tokens` and `timeout_seconds`; automatic
  redelivery is intentionally disabled for deterministic output exhaustion.
- **Tavily 401/403:** check the API key, quota, and outbound HTTPS access.
- **Public URL rejected:** the SSRF protection is intentionally not bypassable by configuration.
- **Run disappears after restart:** local defaults are process memory. Configure DynamoDB and SQS
  for persistence across API and worker restarts.
- **Report says it was assembled deterministically:** model prose failed a hard publication check;
  reviewed claims were used to preserve evidence integrity.

## Security notes

- Do not commit `.env`; it is ignored by Git.
- Development authentication injects a fixed identity and must not be exposed publicly.
- Upload scanning fails closed. Enabling uploads requires reachable ClamAV and OpenSearch services.
- Browser retrieval permits only public HTTP(S) targets on standard ports and revalidates
  redirects and resolved addresses.
- Application logs intentionally omit prompts, evidence text, and credentials.
