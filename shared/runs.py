"""Shared agent run lifecycle.

Every kl-agent records one row in agent_runs per invocation: insert at start
(status='running'), update at finish (terminal status + metrics + optional
error). This module owns that lifecycle so each agent does not reimplement it.

Contract surface an agent's config must provide (see KLAgentConfig):
    agent_name: str          identifies the agent in agent_runs.agent_name
    snapshot:  dict          secrets-stripped config, stored as config_snapshot
    storage:   StorageConfig connection to the shared backend

Status / exit-code model:
    running -> in progress (never a terminal state)
    success -> exit 0   clean completion
    partial -> exit 1   useful work done but >=1 non-fatal unit failed
                        (OPTIONAL: agents that cannot partially fail omit it)
    failed  -> exit 2   no useful work

Metrics: each agent writes its own work-specific numbers as flat JSONB scalars
(MetricValue). The four legacy posts_* columns are deprecated (migration 0008);
callers that still write them do so via the explicit legacy_counts argument
during the transition, not as first-class kwargs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from shared.config import StorageConfig
from shared.db.client import get_client

RunStatus = Literal["running", "success", "partial", "failed"]
TerminalStatus = Literal["success", "partial", "failed"]

# A metric value is a flat JSON scalar. Nested dicts/lists are intentionally
# disallowed: every current agent's metrics are scalar counts, and keeping the
# shape flat means JSONB cannot reject a payload late and opaquely on write.
MetricValue = str | int | float | bool | None

_EXIT_CODES: dict[TerminalStatus, int] = {"success": 0, "partial": 1, "failed": 2}


@runtime_checkable
class KLAgentConfig(Protocol):
    """The config surface shared/runs requires of any kl-agent.

    snapshot is a property/attribute (accessed as config.snapshot, never
    called), returning a secrets-stripped dict for agent_runs.config_snapshot.
    """

    @property
    def agent_name(self) -> str: ...

    @property
    def snapshot(self) -> dict[str, object]: ...

    @property
    def storage(self) -> StorageConfig: ...


@dataclass(frozen=True, slots=True)
class RunHandle:
    """Pointer to an in-progress run. Pass this to finish_run."""

    run_id: str


def status_to_exit_code(status: TerminalStatus) -> int:
    """Map a terminal run status to a process exit code (success=0/partial=1/failed=2)."""
    return _EXIT_CODES[status]


def _validate_metrics(metrics: dict[str, MetricValue]) -> None:
    """Reject a metrics payload that JSONB would accept late or store misleadingly.

    Keys must be strings; values must be flat scalars (str/int/float/bool/None).
    Raises ValueError before any DB write so a bad payload fails loudly at the
    call site, not opaquely inside PostgREST.
    """
    if not isinstance(metrics, dict):
        raise ValueError(f"metrics must be a dict, got {type(metrics).__name__}")
    for key, value in metrics.items():
        if not isinstance(key, str):
            raise ValueError(f"metrics key must be str, got {type(key).__name__}: {key!r}")
        # bool is a subclass of int; both are valid scalars, so no special-case
        # needed here (unlike config int-coercion which rejects bool).
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError(
                f"metrics[{key!r}] must be a flat scalar "
                f"(str/int/float/bool/None), got {type(value).__name__}: {value!r}"
            )


def start_run(config: KLAgentConfig) -> RunHandle:
    """Insert a fresh agent_runs row in 'running' state and return its id.

    Captures the config snapshot at run start so a later config edit cannot
    rewrite history. Raises if the insert fails: a run with no row is worse
    than crashing early.
    """
    client = get_client(config.storage)
    payload: dict[str, Any] = {
        "agent_name": config.agent_name,
        "status": "running",
        "config_snapshot": config.snapshot,
    }
    response = client.table("agent_runs").insert(payload).execute()

    data = response.data
    if not data:
        raise RuntimeError("agent_runs insert returned no rows")
    row = data[0]
    if not isinstance(row, dict):
        raise RuntimeError(f"agent_runs insert returned non-dict row: {row!r}")
    run_id = row.get("id")
    if not isinstance(run_id, str):
        raise RuntimeError(f"agent_runs insert returned no id: {row!r}")
    return RunHandle(run_id=run_id)


def finish_run(
    handle: RunHandle,
    config: KLAgentConfig,
    *,
    status: RunStatus,
    metrics: dict[str, MetricValue],
    error_summary: str | None = None,
    legacy_counts: dict[str, int] | None = None,
) -> None:
    """Update the run row with terminal status, metrics, and optional error.

    Sets finished_at server-side. status must be terminal; 'running' is
    rejected at runtime (the param accepts RunStatus so the guard is reachable
    even when a caller bypasses the type with a bad value). metrics is the
    agent's own work-specific JSONB payload.

    legacy_counts is a transition-only escape hatch: agents may also mirror
    values into the deprecated posts_* columns while consumers (Echo,
    dashboards) still read them. It is dropped once those columns are removed.
    """
    if status == "running":
        raise ValueError("finish_run cannot set status back to 'running'")
    _validate_metrics(metrics)

    client = get_client(config.storage)
    payload: dict[str, Any] = {
        "status": status,
        "finished_at": datetime.now(UTC).isoformat(),
        "metrics": metrics,
    }
    if legacy_counts:
        payload.update(legacy_counts)
    if error_summary is not None:
        payload["error_summary"] = error_summary

    response = client.table("agent_runs").update(payload).eq("id", handle.run_id).execute()
    if not response.data:
        raise RuntimeError(f"agent_runs update for {handle.run_id} returned no rows")


def finish_safely(
    handle: RunHandle,
    config: KLAgentConfig,
    *,
    status: TerminalStatus,
    metrics: dict[str, MetricValue],
    error_summary: str | None = None,
    legacy_counts: dict[str, int] | None = None,
    log: Any,
) -> None:
    """Call finish_run, swallowing bookkeeping failures so they cannot mask the
    real error that prompted the finish.

    A failure to write the final agent_runs row is logged, not raised: the run's
    actual outcome (its exit code) is already decided by the caller.
    """
    try:
        finish_run(
            handle,
            config,
            status=status,
            metrics=metrics,
            error_summary=error_summary,
            legacy_counts=legacy_counts,
        )
    except Exception as exc:
        log.error(
            "finish_run_failed",
            extra={"run_id": handle.run_id, "error": str(exc)},
            exc_info=True,
        )
