"""Smoke test for the YouTube fetcher.

Pulls comments from one channel and prints them as JSON, one per line.
No classification, no database writes.

    python scripts/smoke_youtube_fetch.py
    python scripts/smoke_youtube_fetch.py --handle "@RestaurantUnstoppable" --videos 1 --comments 5

Exit codes:
    0 success, comments printed
    1 partial (channel reached but no comments survived filters)
    2 failure (auth, network, missing config, handle does not resolve)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

# Make 'agents' and 'shared' importable when running this as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scout.config import ConfigError, YouTubeChannel, load_youtube_only
from agents.scout.fetchers import youtube as youtube_fetcher
from agents.scout.models import FetchedPost
from shared import logging_setup


def _post_to_jsonable(post: FetchedPost) -> dict[str, Any]:
    d = asdict(post)
    for key, value in d.items():
        if isinstance(value, datetime):
            d[key] = value.isoformat()
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the YouTube fetcher.")
    parser.add_argument(
        "--handle",
        default="@RestaurantUnstoppable",
        help="Channel handle to fetch from (default: @RestaurantUnstoppable)",
    )
    parser.add_argument(
        "--videos",
        type=int,
        default=1,
        help="How many recent videos to pull (default: 1)",
    )
    parser.add_argument(
        "--comments",
        type=int,
        default=5,
        help="How many top comments per video (default: 5)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml in cwd)",
    )
    args = parser.parse_args()

    log = logging_setup.configure(level="INFO", agent="scout")

    try:
        cfg = load_youtube_only(args.config)
    except ConfigError as exc:
        log.error("config_load_failed", extra={"error": str(exc)})
        return 2

    # Override the configured channel limits for this smoke run.
    handle = args.handle
    matching = next((c for c in cfg.channels if c.handle == handle), None)
    if matching is None:
        matching = YouTubeChannel(
            handle=handle,
            channel_id=None,
            note="cli smoke override",
            videos_per_run=None,
            comments_per_video=None,
        )
    matching = replace(
        matching,
        videos_per_run=args.videos,
        comments_per_video=args.comments,
    )

    client = youtube_fetcher.build_client(cfg)

    try:
        from datetime import timedelta

        posts = youtube_fetcher.fetch_channel(
            client,
            matching,
            default_videos_per_channel=cfg.default_videos_per_channel,
            default_comments_per_video=cfg.default_comments_per_video,
            max_age=timedelta(days=cfg.max_age_days),
        )
    except youtube_fetcher.YouTubeFetchError as exc:
        log.error("fetch_failed", extra={"error": str(exc)})
        return 2
    except Exception as exc:
        log.error("fetch_failed_unexpected", extra={"error": str(exc)}, exc_info=True)
        return 2

    if not posts:
        log.warning("no_comments_returned", extra={"handle": handle})
        return 1

    log.info("smoke_complete", extra={"comments_returned": len(posts)})

    for post in posts:
        print(json.dumps(_post_to_jsonable(post), default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
