"""Smoke test for the Reddit fetcher.

Pulls a handful of posts from one subreddit and prints them as JSON, one per line.
No classification, no database writes. Run this as the first verification once
Reddit API credentials land in .env.

    python scripts/smoke_reddit_fetch.py
    python scripts/smoke_reddit_fetch.py --subreddit restaurateur --limit 5

Exit codes:
    0 success, posts printed
    1 partial (subreddit fetched but no posts survived filters)
    2 failure (auth, network, missing config)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Make 'agents' and 'shared' importable when running this as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scout.config import ConfigError, load_reddit_only
from agents.scout.fetchers import reddit as reddit_fetcher
from agents.scout.models import FetchedPost
from shared import logging_setup


def _post_to_jsonable(post: FetchedPost) -> dict[str, Any]:
    d = asdict(post)
    for key, value in d.items():
        if isinstance(value, datetime):
            d[key] = value.isoformat()
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Reddit fetcher.")
    parser.add_argument(
        "--subreddit",
        default="restaurateur",
        help="Subreddit to fetch from (default: restaurateur)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of posts to fetch (default: 5)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml in cwd)",
    )
    args = parser.parse_args()

    log = logging_setup.configure(level="INFO", agent="scout")

    try:
        cfg = load_reddit_only(args.config)
    except ConfigError as exc:
        log.error("config_load_failed", extra={"error": str(exc)})
        return 2

    try:
        posts = reddit_fetcher.fetch_all(
            cfg,
            subreddit_override=args.subreddit,
            limit_override=args.limit,
        )
    except Exception as exc:
        log.error("fetch_failed", extra={"error": str(exc)}, exc_info=True)
        return 2

    if not posts:
        log.warning("no_posts_returned", extra={"subreddit": args.subreddit})
        return 1

    log.info("smoke_complete", extra={"posts_returned": len(posts)})

    for post in posts:
        print(json.dumps(_post_to_jsonable(post), default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
