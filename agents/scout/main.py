"""Scout orchestrator.

Wires the multi-source pipeline together: load config, fetch from enabled
sources, write to the review queue. Until the classifier exists, every post
is written with a placeholder 'unclear' classification (review_status falls
to auto_rejected), so the storage layer can be exercised end-to-end without
classifier coupling.

CLI:
    python -m agents.scout.main                          # all enabled sources
    python -m agents.scout.main --source reddit          # one source only
    python -m agents.scout.main --source youtube --limit 1
    python -m agents.scout.main --dry-run                # fetch, print, no DB

Exit codes:
    0 success: at least one source ran clean
    1 partial: every source attempted hit at least one failure but some posts landed
    2 fatal: nothing usable (config error, every source dead, storage unavailable)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Make 'agents' and 'shared' importable when running this as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scout import logging_setup
from agents.scout.config import (
    Config,
    ConfigError,
    RedditConfig,
    YouTubeConfig,
    load,
)
from agents.scout.fetchers import reddit as reddit_fetcher
from agents.scout.fetchers import youtube as youtube_fetcher
from agents.scout.models import Classification, FetchedPost
from agents.scout.storage.posts import InsertResult, insert_classified_posts
from agents.scout.storage.runs import RunHandle, finish_run, start_run

SourceFilter = Literal["reddit", "youtube", "all"]

# Until the classifier exists, every post gets this stand-in. ica_stage='unclear'
# means review_status will be 'auto_rejected', which is fine: rows land in the
# DB for the corpus, but they do not pollute the human review queue.
_UNCLASSIFIED = Classification(
    ica_stage="unclear",
    confidence=0.0,
    signal_type=None,
    key_quote=None,
    reasoning="classifier not yet built; placeholder pending agents/scout/classifier/ica.py",
)


def _post_to_jsonable(post: FetchedPost) -> dict[str, Any]:
    """Convert FetchedPost to a JSON-printable dict for --dry-run output."""
    d = asdict(post)
    for key, value in d.items():
        if isinstance(value, datetime):
            d[key] = value.isoformat()
    return d


def _fetch_reddit(
    cfg: RedditConfig,
    *,
    limit_override: int | None,
    log: Any,
) -> tuple[list[FetchedPost], bool]:
    """Run the Reddit fetcher. Returns (posts, hit_failure).

    hit_failure is True if the fetcher raised at all. The caller decides
    how to combine partial failures across sources into a run status.
    """
    try:
        posts = reddit_fetcher.fetch_all(cfg, limit_override=limit_override)
        return posts, False
    except reddit_fetcher.RedditFetchError as exc:
        log.error("reddit_fetch_failed", extra={"error": str(exc)})
        return [], True
    except Exception as exc:
        log.error("reddit_fetch_unexpected", extra={"error": str(exc)}, exc_info=True)
        return [], True


def _fetch_youtube(
    cfg: YouTubeConfig,
    *,
    log: Any,
) -> tuple[list[FetchedPost], bool]:
    """Run the YouTube fetcher. Returns (posts, hit_failure)."""
    try:
        posts = youtube_fetcher.fetch_all(cfg)
        return posts, False
    except youtube_fetcher.YouTubeFetchError as exc:
        log.error("youtube_fetch_failed", extra={"error": str(exc)})
        return [], True
    except Exception as exc:
        log.error("youtube_fetch_unexpected", extra={"error": str(exc)}, exc_info=True)
        return [], True


def _select_sources(config: Config, *, source_filter: SourceFilter) -> tuple[bool, bool]:
    """Resolve which sources actually run for this invocation.

    Returns (reddit_active, youtube_active). A source is active iff:
    - it is enabled in config AND
    - the CLI --source flag does not exclude it
    """
    reddit_active = config.reddit.enabled and source_filter in ("reddit", "all")
    youtube_active = config.youtube.enabled and source_filter in ("youtube", "all")
    return reddit_active, youtube_active


def _classify_run(
    *,
    attempted_sources: int,
    failed_sources: int,
    posts_count: int,
) -> Literal["success", "partial", "failed"]:
    """Translate per-source outcomes into the run-level status.

    - failed:  every attempted source failed, OR nothing was attempted
    - partial: some sources failed AND some posts landed
    - success: nothing failed
    """
    if attempted_sources == 0:
        return "failed"
    if failed_sources == 0:
        return "success"
    if posts_count == 0:
        return "failed"
    return "partial"


def _status_to_exit_code(status: Literal["success", "partial", "failed"]) -> int:
    return {"success": 0, "partial": 1, "failed": 2}[status]


def _run_dry(
    config: Config,
    *,
    source_filter: SourceFilter,
    limit_override: int | None,
    log: Any,
) -> int:
    """Dry run: fetch, print, no storage writes."""
    reddit_active, youtube_active = _select_sources(config, source_filter=source_filter)
    log.info(
        "dry_run_started",
        extra={
            "reddit_active": reddit_active,
            "youtube_active": youtube_active,
            "limit_override": limit_override,
        },
    )

    attempted = 0
    failed = 0
    all_posts: list[FetchedPost] = []

    if reddit_active:
        attempted += 1
        posts, hit_failure = _fetch_reddit(config.reddit, limit_override=limit_override, log=log)
        all_posts.extend(posts)
        if hit_failure:
            failed += 1

    if youtube_active:
        attempted += 1
        posts, hit_failure = _fetch_youtube(config.youtube, log=log)
        all_posts.extend(posts)
        if hit_failure:
            failed += 1

    for post in all_posts:
        print(json.dumps(_post_to_jsonable(post), default=str))

    status = _classify_run(
        attempted_sources=attempted,
        failed_sources=failed,
        posts_count=len(all_posts),
    )
    log.info(
        "dry_run_complete",
        extra={
            "status": status,
            "posts_fetched": len(all_posts),
            "sources_attempted": attempted,
            "sources_failed": failed,
        },
    )
    return _status_to_exit_code(status)


def _run_live(
    config: Config,
    *,
    source_filter: SourceFilter,
    limit_override: int | None,
    log: Any,
) -> int:
    """Live run: fetch, classify with placeholder, write to storage."""
    reddit_active, youtube_active = _select_sources(config, source_filter=source_filter)
    log.info(
        "run_started",
        extra={
            "reddit_active": reddit_active,
            "youtube_active": youtube_active,
            "limit_override": limit_override,
        },
    )

    try:
        handle = start_run(config)
    except Exception as exc:
        log.error("start_run_failed", extra={"error": str(exc)}, exc_info=True)
        return 2

    log.info("run_id_assigned", extra={"run_id": handle.run_id})

    attempted = 0
    failed = 0
    all_posts: list[FetchedPost] = []

    if reddit_active:
        attempted += 1
        posts, hit_failure = _fetch_reddit(config.reddit, limit_override=limit_override, log=log)
        all_posts.extend(posts)
        if hit_failure:
            failed += 1

    if youtube_active:
        attempted += 1
        posts, hit_failure = _fetch_youtube(config.youtube, log=log)
        all_posts.extend(posts)
        if hit_failure:
            failed += 1

    items = [(post, _UNCLASSIFIED) for post in all_posts]
    try:
        insert_result = insert_classified_posts(handle, config, items)
    except Exception as exc:
        log.error("insert_failed", extra={"error": str(exc)}, exc_info=True)
        _finish_safely(
            handle,
            config,
            status="failed",
            posts_fetched=len(all_posts),
            insert_result=InsertResult(inserted=0, skipped=0),
            error_summary=f"insert failed: {exc}",
            log=log,
        )
        return 2

    status = _classify_run(
        attempted_sources=attempted,
        failed_sources=failed,
        posts_count=insert_result.inserted,
    )

    error_summary: str | None = None
    if failed > 0:
        error_summary = f"{failed} of {attempted} sources hit failures"

    _finish_safely(
        handle,
        config,
        status=status,
        posts_fetched=len(all_posts),
        insert_result=insert_result,
        error_summary=error_summary,
        log=log,
    )

    log.info(
        "run_complete",
        extra={
            "run_id": handle.run_id,
            "status": status,
            "posts_fetched": len(all_posts),
            "posts_inserted": insert_result.inserted,
            "posts_dedup_skipped": insert_result.skipped,
            "sources_attempted": attempted,
            "sources_failed": failed,
        },
    )
    return _status_to_exit_code(status)


def _finish_safely(
    handle: RunHandle,
    config: Config,
    *,
    status: Literal["success", "partial", "failed"],
    posts_fetched: int,
    insert_result: InsertResult,
    error_summary: str | None,
    log: Any,
) -> None:
    """Wrap finish_run so a bookkeeping failure cannot mask the real error.

    Until the classifier exists, posts_classified equals posts_inserted and
    posts_queued is always zero (every row is auto_rejected).
    """
    try:
        finish_run(
            handle,
            config,
            status=status,
            posts_fetched=posts_fetched,
            posts_dedup_skipped=insert_result.skipped,
            posts_classified=insert_result.inserted,
            posts_queued=0,
            error_summary=error_summary,
        )
    except Exception as exc:
        log.error(
            "finish_run_failed",
            extra={"run_id": handle.run_id, "error": str(exc)},
            exc_info=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scout orchestrator.")
    parser.add_argument(
        "--source",
        choices=("reddit", "youtube", "all"),
        default="all",
        help="Which source(s) to fetch from. Overrides per-source enabled flags only as a filter.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print posts as JSON. No storage writes, no run record.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Per-source post limit override. Currently honored by the Reddit fetcher only.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml in cwd).",
    )
    args = parser.parse_args(argv)

    log = logging_setup.configure(level="INFO")

    source_filter: SourceFilter = args.source

    # Only enforce credentials for sources this invocation will actually run.
    # Without this, a missing Reddit cred would block a `--source youtube` run
    # while Reddit API approval is pending.
    try:
        config = load(
            args.config,
            require_reddit_creds=source_filter in ("reddit", "all"),
            require_youtube_creds=source_filter in ("youtube", "all"),
        )
    except ConfigError as exc:
        log.error("config_load_failed", extra={"error": str(exc)})
        return 2

    if args.dry_run:
        return _run_dry(
            config,
            source_filter=source_filter,
            limit_override=args.limit,
            log=log,
        )
    return _run_live(
        config,
        source_filter=source_filter,
        limit_override=args.limit,
        log=log,
    )


if __name__ == "__main__":
    sys.exit(main())
