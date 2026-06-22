# The kl-agent contract

What makes a module a kl-agent. This is a LIGHT contract: a small, documented,
enforced surface, NOT a base class or framework. An agent is "a kl-agent" when
it satisfies the five requirements below and respects the one hard invariant.
The proof it works: a second agent (Validation) builds on `shared/` with zero
copy-paste of Scout internals.

Established Bucket 3 (2026-06-22). Reference implementation: Scout
(`agents/scout/`). The shared spine lives in `shared/`.

## The one hard invariant

**`shared/` never imports from `agents/`.** The platform spine must not depend
on any single agent built on top of it. This is the seam Bucket 3 existed to
cut (`shared/db/client.py` used to import `agents.scout.config`). It is enforced
by an AST test, not convention: see `tests/shared/test_import_invariant.py`. A
violating import fails the test, not a code review.

## The five requirements

A kl-agent module MUST:

### 1. Run lifecycle via `shared/runs.py`

Record one `agent_runs` row per invocation through the shared lifecycle, never
a reimplementation:

- `start_run(config) -> RunHandle` at the start (inserts a `status='running'`
  row carrying the config snapshot; the `run_id` is the FK for the agent's
  output rows).
- `finish_run(handle, config, *, status, metrics, error_summary=None,
  legacy_counts=None)` at the end, OR `finish_safely(...)` to swallow a
  bookkeeping failure so it cannot mask the real run outcome.

### 2. Config surface (`shared/runs.KLAgentConfig`)

The agent's config object MUST expose exactly what the run lifecycle reads.
These three are the `KLAgentConfig` Protocol members:

| Member | Type | Notes |
|---|---|---|
| `agent_name` | `str` | written to `agent_runs.agent_name` |
| `snapshot` | `dict[str, object]` | **a property/attribute, accessed as `config.snapshot` (never called).** Secrets stripped. Stored as `agent_runs.config_snapshot`. |
| `storage` | `StorageConfig` | from `shared/config.py`; connects to the shared backend |

`agent_version` is also expected on a config, but it is carried INSIDE the
snapshot (`snapshot["agent"]["version"]`), not read directly by the lifecycle,
so it is not a Protocol member.

`KLAgentConfig` is a `runtime_checkable` Protocol. An agent config that misses a
member fails the contract check (`tests/shared/test_contract_surface.py`).
Scout's `agents/scout/config.Config` is the reference: note `snapshot` is a
`@property`.

### 3. Structured logging via `shared/logging_setup.py`

`configure(level, *, agent="<name>")` once at startup. `agent` is REQUIRED: it
is stamped onto every JSON log line by the formatter, so any logger obtained via
`logging.getLogger(...)` is correctly attributed without each call site
repeating the name. There is no default agent; a missing one is a wiring bug,
not a silent mislabel.

### 4. Status to exit code (`shared/runs.status_to_exit_code`)

Map the terminal run status to a process exit code: `success=0`, `partial=1`,
`failed=2`. **`partial` is OPTIONAL.** It means "useful work completed but at
least one non-fatal unit failed." An agent that cannot partially fail (e.g. a
non-listener with no per-source work, like Validation) simply never emits it and
uses `success`/`failed` only.

### 5. Writes to the shared backend; reads what it needs

The agent persists to the shared Supabase backend through `shared/db/client.py`
(`get_client(storage)`), writing its own tables and reading whatever upstream
tables it consumes. Work-specific run numbers go in `agent_runs.metrics` (flat
JSONB scalars, validated by `finish_run`), NOT in per-agent columns. The four
`posts_*` count columns are deprecated (migration 0008); they are listener-
shaped and a non-listener leaves them null rather than writing fake zeros.

## What is NOT in the contract

- No base class, no inheritance, no plugin system, no agent registry.
- No required directory layout beyond "an importable module under `agents/`."
- Agent-specific logic (Scout's keeper-gate, classifier, fetchers; a future
  agent's own pipeline) stays in that agent. The contract is only the spine.

## Where each piece lives

| Concern | Module |
|---|---|
| Run lifecycle | `shared/runs.py` |
| Config surface type | `shared/runs.KLAgentConfig`, `shared/config.StorageConfig` |
| Structured logging | `shared/logging_setup.py` |
| Backend client | `shared/db/client.py` |
| Schema | `shared/db/migrations/` |
| Invariant enforcement | `tests/shared/test_import_invariant.py` |
