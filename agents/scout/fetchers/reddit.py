"""Reddit fetcher.

Pulls the newest posts from one or more subreddits using PRAW in read-only mode.
Returns FetchedPost objects. Knows nothing about classification or storage.

Read-only mode means:
- No Reddit account password in .env
- App-only OAuth using client_id + client_secret
- Cannot read private subs or do anything write-y, which is exactly what we want

Posts older than max_age_days are skipped. Removed and deleted posts are skipped
because their bodies are gone and titles alone are insufficient signal for an
ICA stage call.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import praw
from praw.models import Submission
from praw.reddit import Reddit

from agents.scout.config import RedditConfig
from agents.scout.models import FetchedPost

log = logging.getLogger("scout")


class RedditFetchError(Exception):
    """Raised when a subreddit cannot be read at all (auth failure, banned, etc).
    Per-post problems are logged and skipped, not raised."""


def build_client(cfg: RedditConfig) -> Reddit:
    """Build a read-only PRAW client from config. No network call yet, that
    happens on the first request."""
    client = praw.Reddit(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        user_agent=cfg.user_agent,
    )
    client.read_only = True
    return client


def _is_removed(submission: Submission) -> bool:
    """A post is considered removed/deleted if its body is gone or the author
    is gone. Reddit signals this in a few ways; we check all of them."""
    if getattr(submission, "removed_by_category", None):
        return True
    selftext = (getattr(submission, "selftext", "") or "").strip()
    if selftext in ("[removed]", "[deleted]"):
        return True
    author = getattr(submission, "author", None)
    if author is None:
        return True
    return False


def _to_fetched_post(submission: Submission, source_name: str) -> FetchedPost:
    posted_at = datetime.fromtimestamp(submission.created_utc, tz=UTC)
    author_name = submission.author.name if submission.author else None
    return FetchedPost(
        source=source_name,
        source_subreddit=str(submission.subreddit.display_name),
        source_url=f"https://www.reddit.com{submission.permalink}",
        source_id=str(submission.id),
        source_author=author_name,
        posted_at=posted_at,
        title=str(submission.title or ""),
        body=str(submission.selftext or ""),
        is_removed=False,
    )


def fetch_subreddit(
    client: Reddit,
    subreddit_name: str,
    *,
    limit: int,
    sort: str,
    max_age: timedelta,
    source_name: str = "reddit",
) -> list[FetchedPost]:
    """Fetch the newest N posts from one subreddit.

    Filters applied in order:
    1. Skip removed and deleted posts.
    2. Skip posts older than max_age.
    3. Skip posts with no title and no body (rare but possible).

    Returns the survivors as FetchedPost. Logs counters for each filter.
    """
    log.info(
        "subreddit_fetch_started",
        extra={"subreddit": subreddit_name, "limit": limit, "sort": sort},
    )

    cutoff = datetime.now(tz=UTC) - max_age

    try:
        subreddit = client.subreddit(subreddit_name)
        if sort == "new":
            stream = subreddit.new(limit=limit)
        elif sort == "hot":
            stream = subreddit.hot(limit=limit)
        elif sort == "top":
            stream = subreddit.top(limit=limit)
        else:
            raise RedditFetchError(f"Unsupported sort: {sort}")
    except Exception as exc:
        log.error(
            "subreddit_fetch_failed",
            extra={"subreddit": subreddit_name, "error": str(exc)},
            exc_info=True,
        )
        raise RedditFetchError(f"Failed to open subreddit {subreddit_name}: {exc}") from exc

    fetched: list[FetchedPost] = []
    skipped_removed = 0
    skipped_old = 0
    skipped_empty = 0

    try:
        for submission in stream:
            if _is_removed(submission):
                skipped_removed += 1
                continue

            posted_at = datetime.fromtimestamp(submission.created_utc, tz=UTC)
            if posted_at < cutoff:
                skipped_old += 1
                continue

            title = str(submission.title or "").strip()
            body = str(submission.selftext or "").strip()
            if not title and not body:
                skipped_empty += 1
                continue

            fetched.append(_to_fetched_post(submission, source_name))
    except Exception as exc:
        log.error(
            "subreddit_stream_failed",
            extra={
                "subreddit": subreddit_name,
                "fetched_so_far": len(fetched),
                "error": str(exc),
            },
            exc_info=True,
        )
        raise RedditFetchError(f"Stream failed mid-fetch on {subreddit_name}: {exc}") from exc

    log.info(
        "subreddit_fetch_completed",
        extra={
            "subreddit": subreddit_name,
            "kept": len(fetched),
            "skipped_removed": skipped_removed,
            "skipped_old": skipped_old,
            "skipped_empty": skipped_empty,
        },
    )

    return fetched


def fetch_all(
    cfg: RedditConfig,
    *,
    source_name: str = "reddit",
    subreddit_override: str | None = None,
    limit_override: int | None = None,
) -> list[FetchedPost]:
    """Fetch posts across all configured subreddits. CLI overrides win.

    A failure on one subreddit does not abort the others. The caller decides
    how to summarize partial-failure runs.
    """
    client = build_client(cfg)
    subreddits = (subreddit_override,) if subreddit_override else cfg.subreddits
    limit = limit_override if limit_override is not None else cfg.posts_per_subreddit
    max_age = timedelta(days=cfg.max_age_days)

    all_posts: list[FetchedPost] = []
    failures: list[str] = []

    for sub in subreddits:
        try:
            posts = fetch_subreddit(
                client,
                sub,
                limit=limit,
                sort=cfg.sort,
                max_age=max_age,
                source_name=source_name,
            )
            all_posts.extend(posts)
        except RedditFetchError:
            failures.append(sub)

    if failures:
        log.warning(
            "fetch_partial_failure",
            extra={"failed_subreddits": failures, "ok_subreddits": [s for s in subreddits if s not in failures]},
        )

    return all_posts
