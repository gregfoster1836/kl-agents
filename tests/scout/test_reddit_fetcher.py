"""Tests for the Reddit fetcher.

These tests do not hit Reddit. They build fake Submission objects in memory
and feed them through the fetcher's filtering logic. The goal is to verify:
- removed and deleted posts are skipped
- old posts (older than max_age) are skipped
- empty title-and-body posts are skipped
- everything else maps cleanly into FetchedPost

This catches regressions in the filter logic without depending on Reddit's API
being available, which matters because Reddit credentials are gated behind a
manual review process.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from agents.scout.fetchers import reddit as reddit_fetcher
from agents.scout.models import FetchedPost

# ----- Fakes ----------------------------------------------------------------


@dataclass
class FakeAuthor:
    name: str


@dataclass
class FakeSubreddit:
    display_name: str


class FakeSubmission:
    """Minimal stand-in for praw.models.Submission."""

    def __init__(
        self,
        *,
        post_id: str = "abc",
        title: str = "labor cost is killing me",
        selftext: str = "tried everything, still cant find good people",
        permalink: str = "/r/restaurateur/comments/abc/labor_cost/",
        subreddit_name: str = "restaurateur",
        author_name: str | None = "an_operator",
        created_utc: float | None = None,
        removed_by_category: str | None = None,
    ) -> None:
        self.id = post_id
        self.title = title
        self.selftext = selftext
        self.permalink = permalink
        self.subreddit = FakeSubreddit(display_name=subreddit_name)
        self.author = FakeAuthor(name=author_name) if author_name else None
        if created_utc is None:
            created_utc = datetime.now(tz=UTC).timestamp()
        self.created_utc = created_utc
        self.removed_by_category = removed_by_category


def _client_returning(submissions: list[FakeSubmission]) -> MagicMock:
    """Build a fake PRAW client whose .subreddit(name).new(limit=...) returns
    the given submissions."""
    sub_obj = MagicMock()
    sub_obj.new.return_value = iter(submissions)
    sub_obj.hot.return_value = iter(submissions)
    sub_obj.top.return_value = iter(submissions)

    client = MagicMock()
    client.subreddit.return_value = sub_obj
    return client


# ----- Tests ----------------------------------------------------------------


def test_keeps_a_normal_recent_post() -> None:
    submission = FakeSubmission()
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client,
        "restaurateur",
        limit=10,
        sort="new",
        max_age=timedelta(days=30),
    )

    assert len(result) == 1
    post = result[0]
    assert isinstance(post, FetchedPost)
    assert post.source_subreddit == "restaurateur"
    assert post.source_id == "abc"
    assert post.source_author == "an_operator"
    assert post.title == "labor cost is killing me"
    assert post.body.startswith("tried everything")
    assert post.source_url == "https://www.reddit.com/r/restaurateur/comments/abc/labor_cost/"


def test_skips_removed_post() -> None:
    submission = FakeSubmission(
        post_id="rm1",
        selftext="[removed]",
    )
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_skips_deleted_post() -> None:
    submission = FakeSubmission(
        post_id="del1",
        selftext="[deleted]",
        author_name=None,
    )
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_skips_post_removed_by_moderator() -> None:
    submission = FakeSubmission(
        post_id="mod1",
        removed_by_category="moderator",
    )
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_skips_post_with_no_author() -> None:
    submission = FakeSubmission(post_id="noauth", author_name=None)
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_skips_old_post_outside_max_age() -> None:
    sixty_days_ago = (datetime.now(tz=UTC) - timedelta(days=60)).timestamp()
    submission = FakeSubmission(post_id="old", created_utc=sixty_days_ago)
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_skips_empty_post() -> None:
    submission = FakeSubmission(post_id="empty", title="", selftext="")
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert result == []


def test_keeps_title_only_post() -> None:
    submission = FakeSubmission(
        post_id="titleonly",
        title="busy but broke, what am I missing",
        selftext="",
    )
    client = _client_returning([submission])

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    assert len(result) == 1
    assert result[0].title == "busy but broke, what am I missing"
    assert result[0].body == ""


def test_mixed_batch_keeps_only_valid_posts() -> None:
    sixty_days_ago = (datetime.now(tz=UTC) - timedelta(days=60)).timestamp()

    submissions = [
        FakeSubmission(post_id="keep1"),
        FakeSubmission(post_id="rm1", selftext="[removed]"),
        FakeSubmission(post_id="old1", created_utc=sixty_days_ago),
        FakeSubmission(post_id="keep2", title="cant get good staff"),
        FakeSubmission(post_id="empty1", title="", selftext=""),
    ]
    client = _client_returning(submissions)

    result = reddit_fetcher.fetch_subreddit(
        client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
    )

    kept_ids = [p.source_id for p in result]
    assert kept_ids == ["keep1", "keep2"]


def test_unsupported_sort_raises() -> None:
    client = _client_returning([])

    with pytest.raises(reddit_fetcher.RedditFetchError, match="Unsupported sort"):
        reddit_fetcher.fetch_subreddit(
            client, "restaurateur", limit=10, sort="bogus", max_age=timedelta(days=30)
        )


def test_subreddit_open_failure_raises() -> None:
    client = MagicMock()
    client.subreddit.side_effect = RuntimeError("auth failed")

    with pytest.raises(reddit_fetcher.RedditFetchError, match="Failed to open subreddit"):
        reddit_fetcher.fetch_subreddit(
            client, "restaurateur", limit=10, sort="new", max_age=timedelta(days=30)
        )
