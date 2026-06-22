"""Live storage smoke test against the agents_dev schema.

Writes one synthetic (FetchedPost + Classification) row pair end-to-end:
start_run -> insert_classified_posts -> finish_run. Then re-runs the same
post through insert to verify UNIQUE(source_url) dedup. Cleans up both
rows on exit.

    python scripts/smoke_storage.py
    python scripts/smoke_storage.py --keep   # leave rows in place for inspection

Exit codes:
    0 success: both inserts behaved as expected, cleanup succeeded
    1 partial: writes worked but cleanup failed (rows still in DB)
    2 failure: any storage call raised, or dedup did not behave as expected

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env, with
SUPABASE_SCHEMA pointing at agents_dev (never agents_prod for this script).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make 'agents' and 'shared' importable when running this as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scout.config import ConfigError, load
from agents.scout.models import Classification, FetchedPost, Source
from agents.scout.storage.posts import insert_classified_posts
from shared import logging_setup
from shared.db.client import get_client
from shared.runs import finish_run, start_run

# A clearly-synthetic URL so cleanup queries can target this script's rows
# without any chance of catching production-ish data.
SMOKE_URL = "https://kl-scout-smoke.invalid/storage/2026-05-15/test-1"
SMOKE_AUTHOR = "kl-scout-smoke"


def _synthetic_post() -> FetchedPost:
    return FetchedPost(
        source=Source.REDDIT,
        source_url=SMOKE_URL,
        source_id="smoke-1",
        source_author=SMOKE_AUTHOR,
        posted_at=datetime.now(UTC),
        title="storage smoke synthetic post",
        body=(
            "This row was inserted by scripts/smoke_storage.py to verify the storage "
            "layer wires up end-to-end. Safe to delete."
        ),
        source_metadata={"subreddit": "kl-scout-smoke"},
    )


def _synthetic_classification() -> Classification:
    return Classification(
        ica_stage="unclear",
        confidence=0.0,
        signal_type=None,
        key_quote=None,
        reasoning="storage smoke; not a real classification",
    )


def _cleanup(*, run_id: str, log) -> bool:  # type: ignore[no-untyped-def]
    """Delete the smoke row and the run record. Returns True on success."""
    try:
        config = load(
            "config.yaml",
            require_reddit_creds=False,
            require_youtube_creds=False,
        )
    except ConfigError as exc:
        log.error("cleanup_config_failed", extra={"error": str(exc)})
        return False

    client = get_client(config.storage)
    try:
        # classified_posts has on_delete cascade from agent_runs, but we delete
        # explicitly so a future schema change doesn't silently strand the row.
        client.table("classified_posts").delete().eq("source_url", SMOKE_URL).execute()
        client.table("agent_runs").delete().eq("id", run_id).execute()
    except Exception as exc:
        log.error("cleanup_failed", extra={"error": str(exc), "run_id": run_id}, exc_info=True)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Live storage smoke against agents_dev.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Leave the smoke rows in the database for manual inspection.",
    )
    args = parser.parse_args()

    log = logging_setup.configure(level="INFO", agent="scout")

    # Guard: this script must never run against agents_prod.
    try:
        config = load(
            "config.yaml",
            require_reddit_creds=False,
            require_youtube_creds=False,
        )
    except ConfigError as exc:
        log.error("config_load_failed", extra={"error": str(exc)})
        return 2

    if config.storage.schema != "agents_dev":
        log.error(
            "wrong_schema",
            extra={
                "schema": config.storage.schema,
                "hint": "set SUPABASE_SCHEMA=agents_dev before running this script",
            },
        )
        return 2

    log.info(
        "smoke_started",
        extra={"schema": config.storage.schema, "url": config.storage.supabase_url},
    )

    # ---- Phase 1: start the run --------------------------------------------
    try:
        handle = start_run(config)
    except Exception as exc:
        log.error("start_run_failed", extra={"error": str(exc)}, exc_info=True)
        return 2
    log.info("run_id_assigned", extra={"run_id": handle.run_id})

    # ---- Phase 2: first insert (expect inserted=1, skipped=0) ---------------
    post = _synthetic_post()
    classification = _synthetic_classification()

    try:
        first = insert_classified_posts(handle, config, [(post, classification)])
    except Exception as exc:
        log.error("first_insert_failed", extra={"error": str(exc)}, exc_info=True)
        _cleanup(run_id=handle.run_id, log=log)
        return 2

    log.info(
        "first_insert_complete",
        extra={"inserted": first.inserted, "skipped": first.skipped},
    )
    if first.inserted != 1 or first.skipped != 0:
        log.error(
            "first_insert_unexpected_counts",
            extra={"expected": "1/0", "got": f"{first.inserted}/{first.skipped}"},
        )
        _cleanup(run_id=handle.run_id, log=log)
        return 2

    # ---- Phase 3: second insert of same URL (expect inserted=0, skipped=1) --
    try:
        second = insert_classified_posts(handle, config, [(post, classification)])
    except Exception as exc:
        log.error("second_insert_failed", extra={"error": str(exc)}, exc_info=True)
        _cleanup(run_id=handle.run_id, log=log)
        return 2

    log.info(
        "second_insert_complete",
        extra={"inserted": second.inserted, "skipped": second.skipped},
    )
    if second.inserted != 0 or second.skipped != 1:
        log.error(
            "dedup_did_not_behave",
            extra={"expected": "0/1", "got": f"{second.inserted}/{second.skipped}"},
        )
        _cleanup(run_id=handle.run_id, log=log)
        return 2

    # ---- Phase 4: finish the run -------------------------------------------
    try:
        smoke_counts = {
            "posts_fetched": 1,
            "posts_dedup_skipped": 1,
            "posts_classified": 1,
            "posts_queued": 0,
        }
        finish_run(
            handle,
            config,
            status="success",
            metrics=smoke_counts,
            legacy_counts=smoke_counts,
        )
    except Exception as exc:
        log.error("finish_run_failed", extra={"error": str(exc)}, exc_info=True)
        _cleanup(run_id=handle.run_id, log=log)
        return 2

    log.info("finish_run_complete", extra={"run_id": handle.run_id})

    # ---- Phase 5: cleanup (unless --keep) ----------------------------------
    if args.keep:
        log.info("kept_rows_for_inspection", extra={"run_id": handle.run_id, "url": SMOKE_URL})
        return 0

    if not _cleanup(run_id=handle.run_id, log=log):
        log.warning("cleanup_failed_but_writes_succeeded", extra={"run_id": handle.run_id})
        return 1

    log.info("smoke_complete_all_clean", extra={"run_id": handle.run_id})
    return 0


if __name__ == "__main__":
    sys.exit(main())
