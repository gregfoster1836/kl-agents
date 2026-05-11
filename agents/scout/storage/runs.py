"""agent_runs writer.

Each Scout invocation writes one row here at start (status='running') and
updates the same row at finish (status='success'|'partial'|'failed' plus
counts and optional error_summary).

The flow is intentionally two-step rather than one row at the end:
- We want a record of partial work even if the process is killed mid-run
- The run_id is the foreign key for classified_posts, so we need it early
- Operators investigating a failure want to see what was attempted, not
  just an absence of rows
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from agents.scout.config import Config
from shared.db.client import get_client

RunStatus = Literal["running", "success", "partial", "failed"]


@dataclass(frozen=True, slots=True)
class RunHandle:
    """Pointer to an in-progress run. Pass this to finish_run."""

    run_id: str


def start_run(config: Config) -> RunHandle:
    """Insert a fresh agent_runs row in 'running' state and return its id.

    Captures the config snapshot at run start so a later config edit cannot
    rewrite history. Raises if the insert fails: a run with no row in the
    table is worse than crashing early.
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
    config: Config,
    *,
    status: RunStatus,
    posts_fetched: int,
    posts_dedup_skipped: int,
    posts_classified: int,
    posts_queued: int,
    error_summary: str | None = None,
) -> None:
    """Update the run row with final status, counts, and optional error.

    Sets finished_at to now() server-side. Callers should pass status
    'failed' when no useful work happened, 'partial' when some sources
    failed but others succeeded, and 'success' when every source ran
    cleanly.
    """
    if status == "running":
        raise ValueError("finish_run cannot set status back to 'running'")

    client = get_client(config.storage)
    payload: dict[str, Any] = {
        "status": status,
        "finished_at": datetime.now(UTC).isoformat(),
        "posts_fetched": posts_fetched,
        "posts_dedup_skipped": posts_dedup_skipped,
        "posts_classified": posts_classified,
        "posts_queued": posts_queued,
    }
    if error_summary is not None:
        payload["error_summary"] = error_summary

    response = client.table("agent_runs").update(payload).eq("id", handle.run_id).execute()
    if not response.data:
        raise RuntimeError(f"agent_runs update for {handle.run_id} returned no rows")
