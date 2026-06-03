"""Tests for the Scout orchestrator (agents/scout/main.py).

These tests do not hit Reddit, YouTube, Anthropic, or Supabase. They monkeypatch
the fetcher and storage modules and verify the orchestrator's logic:

- --source filter and per-source enabled flag combine correctly
- --dry-run path does not touch storage
- partial-failure semantics (one source fails, one succeeds) produce status=partial
- all-sources-failed produces status=failed and exit 2
- start_run failure exits 2 cleanly without leaving a half-written run
- finish_run failure logs but does not mask the run's true status
- _classify_run truth table
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from agents.scout import main as orchestrator
from agents.scout.config import (
    ClassificationConfig,
    Config,
    LoggingConfig,
    RedditConfig,
    StorageConfig,
    YouTubeConfig,
)
from agents.scout.fetchers import reddit as reddit_fetcher
from agents.scout.fetchers import youtube as youtube_fetcher
from agents.scout.models import Classification, FetchedPost, Source
from agents.scout.storage.posts import InsertResult
from agents.scout.storage.runs import RunHandle

# ----- Fixtures -------------------------------------------------------------


def _make_config(
    *,
    reddit_enabled: bool = True,
    youtube_enabled: bool = True,
) -> Config:
    return Config(
        agent_name="scout",
        agent_version="0.1.0",
        reddit=RedditConfig(
            enabled=reddit_enabled,
            client_id="test",
            client_secret="test",
            user_agent="test",
            subreddits=("restaurateur",),
            posts_per_subreddit=10,
            sort="new",
            max_age_days=30,
        ),
        youtube=YouTubeConfig(
            enabled=youtube_enabled,
            api_key="test",
            channels=(),
            default_videos_per_channel=1,
            default_comments_per_video=5,
            max_age_days=30,
        ),
        classification=ClassificationConfig(
            model="claude-sonnet-4-6",
            confidence_threshold=0.6,
            max_post_chars=8000,
            retry_on_rate_limit=True,
            max_retries=3,
        ),
        storage=StorageConfig(
            supabase_url="https://test.supabase.co",
            supabase_service_role_key="test-key",
            schema="agents_dev",
        ),
        logging=LoggingConfig(level="INFO", format="json"),
    )


def _make_post(*, source: Source = Source.REDDIT, url: str = "https://reddit.com/x") -> FetchedPost:
    return FetchedPost(
        source=source,
        source_url=url,
        source_id="abc",
        source_author="op",
        posted_at=datetime(2026, 5, 15, tzinfo=UTC),
        title="t",
        body="b",
        source_metadata={"subreddit": "restaurateur"} if source == Source.REDDIT else {},
    )


class _CapturedCalls:
    """Records calls to start_run, insert_classified_posts, finish_run."""

    def __init__(self) -> None:
        self.started = False
        self.inserted_items: list[Any] = []
        self.finished_with: dict[str, Any] | None = None


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> _CapturedCalls:
    """Replace the storage functions in main.py's namespace with fakes."""
    c = _CapturedCalls()

    def fake_start_run(_config: Config) -> RunHandle:
        c.started = True
        return RunHandle(run_id="test-run-1")

    def fake_insert(
        _handle: RunHandle,
        _config: Config,
        items: list[Any],
    ) -> InsertResult:
        c.inserted_items = list(items)
        return InsertResult(inserted=len(items), skipped=0)

    def fake_finish_run(
        _handle: RunHandle,
        _config: Config,
        **kwargs: Any,
    ) -> None:
        c.finished_with = kwargs

    def fake_classify_all(
        posts: list[FetchedPost],
        _cfg: Any,
        **_kw: Any,
    ) -> list[Any]:
        # Default: every post is a confident belief-match (queues).
        return [
            (
                post,
                Classification(
                    ica_stage="2",
                    confidence=0.9,
                    signal_type="marketing-problem",
                    key_quote="we just need more traffic",
                    reasoning="stub",
                ),
            )
            for post in posts
        ]

    monkeypatch.setattr(orchestrator, "start_run", fake_start_run)
    monkeypatch.setattr(orchestrator, "insert_classified_posts", fake_insert)
    monkeypatch.setattr(orchestrator, "finish_run", fake_finish_run)
    monkeypatch.setattr(orchestrator, "classify_all", fake_classify_all)
    return c


def _stub_fetchers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reddit_posts: list[FetchedPost] | None = None,
    youtube_posts: list[FetchedPost] | None = None,
    reddit_raises: Exception | None = None,
    youtube_raises: Exception | None = None,
) -> None:
    """Replace fetcher.fetch_all with stubs that return canned posts or raise."""

    def reddit_stub(_cfg: RedditConfig, **_kw: Any) -> list[FetchedPost]:
        if reddit_raises is not None:
            raise reddit_raises
        return reddit_posts or []

    def youtube_stub(_cfg: YouTubeConfig, **_kw: Any) -> list[FetchedPost]:
        if youtube_raises is not None:
            raise youtube_raises
        return youtube_posts or []

    monkeypatch.setattr(reddit_fetcher, "fetch_all", reddit_stub)
    monkeypatch.setattr(youtube_fetcher, "fetch_all", youtube_stub)


# ----- _classify_run truth table --------------------------------------------


def test_classify_no_sources_attempted_is_failed() -> None:
    assert (
        orchestrator._classify_run(attempted_sources=0, failed_sources=0, posts_count=0) == "failed"
    )


def test_classify_all_clean_is_success() -> None:
    assert (
        orchestrator._classify_run(attempted_sources=2, failed_sources=0, posts_count=5)
        == "success"
    )


def test_classify_some_failed_but_posts_landed_is_partial() -> None:
    assert (
        orchestrator._classify_run(attempted_sources=2, failed_sources=1, posts_count=3)
        == "partial"
    )


def test_classify_all_failed_is_failed() -> None:
    assert (
        orchestrator._classify_run(attempted_sources=2, failed_sources=2, posts_count=0) == "failed"
    )


def test_classify_some_failed_no_posts_is_failed() -> None:
    # Reddit fails AND YouTube succeeds-but-returns-nothing: nothing to review,
    # at least one failure: this is a failed run, not partial.
    assert (
        orchestrator._classify_run(attempted_sources=2, failed_sources=1, posts_count=0) == "failed"
    )


# ----- _select_sources logic ------------------------------------------------


def test_select_sources_all_filter_respects_enabled_flags() -> None:
    config = _make_config(reddit_enabled=True, youtube_enabled=False)
    reddit_active, youtube_active = orchestrator._select_sources(config, source_filter="all")
    assert reddit_active is True
    assert youtube_active is False


def test_select_sources_reddit_filter_excludes_youtube() -> None:
    config = _make_config(reddit_enabled=True, youtube_enabled=True)
    reddit_active, youtube_active = orchestrator._select_sources(config, source_filter="reddit")
    assert reddit_active is True
    assert youtube_active is False


def test_select_sources_filter_cannot_override_disabled_flag() -> None:
    """--source reddit + enabled=False in config: source still skipped."""
    config = _make_config(reddit_enabled=False, youtube_enabled=True)
    reddit_active, _ = orchestrator._select_sources(config, source_filter="reddit")
    assert reddit_active is False


# ----- Dry-run path does not touch storage ----------------------------------


def test_dry_run_does_not_call_storage(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    _stub_fetchers(monkeypatch, reddit_posts=[_make_post()])
    log = orchestrator.logging_setup.configure(level="WARNING")

    exit_code = orchestrator._run_dry(
        _make_config(youtube_enabled=False),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 0
    assert captured.started is False
    assert captured.finished_with is None
    assert captured.inserted_items == []


# ----- Live run: happy path -------------------------------------------------


def test_live_run_success_writes_all_posts(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    reddit_post = _make_post(url="https://r/x/1")
    youtube_post = _make_post(source=Source.YOUTUBE, url="https://y/1")
    _stub_fetchers(monkeypatch, reddit_posts=[reddit_post], youtube_posts=[youtube_post])
    log = orchestrator.logging_setup.configure(level="WARNING")

    exit_code = orchestrator._run_live(
        _make_config(),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 0
    assert captured.started is True
    assert len(captured.inserted_items) == 2
    assert captured.finished_with is not None
    assert captured.finished_with["status"] == "success"
    assert captured.finished_with["posts_fetched"] == 2
    assert captured.finished_with["posts_classified"] == 2
    assert captured.finished_with["posts_queued"] == 2  # both confident belief-matches
    assert captured.finished_with["error_summary"] is None


def test_live_run_posts_queued_counts_only_belief_matches(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    """posts_queued reflects the belief-match + confidence gate, not raw count.
    Two posts fetched, but only the confident belief-match queues."""
    post_a = _make_post(url="https://r/x/1")
    post_b = _make_post(url="https://r/x/2")
    _stub_fetchers(monkeypatch, reddit_posts=[post_a, post_b], youtube_posts=[])

    def mixed_classify(posts: list[FetchedPost], _cfg: Any, **_kw: Any) -> list[Any]:
        return [
            (
                posts[0],
                Classification(
                    ica_stage="2",
                    confidence=0.9,
                    signal_type="marketing-problem",
                    key_quote="more traffic",
                    reasoning="match",
                ),
            ),
            (
                posts[1],
                Classification(
                    ica_stage="unclear",
                    confidence=0.95,
                    signal_type=None,  # no belief: must not queue despite high confidence
                    key_quote=None,
                    reasoning="off topic",
                ),
            ),
        ]

    monkeypatch.setattr(orchestrator, "classify_all", mixed_classify)
    log = orchestrator.logging_setup.configure(level="WARNING")

    exit_code = orchestrator._run_live(
        _make_config(youtube_enabled=False),
        source_filter="reddit",
        limit_override=None,
        log=log,
    )

    assert exit_code == 0
    assert captured.finished_with is not None
    assert captured.finished_with["posts_classified"] == 2
    assert captured.finished_with["posts_queued"] == 1  # only the belief-match


# ----- Live run: partial failure --------------------------------------------


def test_live_run_partial_when_one_source_fails_and_other_lands(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    _stub_fetchers(
        monkeypatch,
        reddit_raises=reddit_fetcher.RedditFetchError("auth"),
        youtube_posts=[_make_post(source=Source.YOUTUBE, url="https://y/1")],
    )
    log = orchestrator.logging_setup.configure(level="CRITICAL")

    exit_code = orchestrator._run_live(
        _make_config(),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 1
    assert captured.finished_with is not None
    assert captured.finished_with["status"] == "partial"
    assert captured.finished_with["error_summary"] is not None
    assert "1 of 2 sources" in captured.finished_with["error_summary"]


# ----- Live run: total failure ----------------------------------------------


def test_live_run_failed_when_both_sources_fail(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    _stub_fetchers(
        monkeypatch,
        reddit_raises=reddit_fetcher.RedditFetchError("auth"),
        youtube_raises=youtube_fetcher.YouTubeFetchError("quota"),
    )
    log = orchestrator.logging_setup.configure(level="CRITICAL")

    exit_code = orchestrator._run_live(
        _make_config(),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 2
    assert captured.finished_with is not None
    assert captured.finished_with["status"] == "failed"


# ----- Live run: unexpected error during fetch is also a per-source failure --


def test_live_run_treats_unexpected_fetch_error_as_source_failure(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    # Not a RedditFetchError, not a YouTubeFetchError: a generic Exception.
    # The orchestrator should treat this as a source failure, not crash.
    _stub_fetchers(
        monkeypatch,
        reddit_raises=RuntimeError("network blip"),
        youtube_posts=[_make_post(source=Source.YOUTUBE, url="https://y/1")],
    )
    log = orchestrator.logging_setup.configure(level="CRITICAL")

    exit_code = orchestrator._run_live(
        _make_config(),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 1  # partial: one failed, one succeeded


# ----- Live run: start_run failure exits 2 ----------------------------------


def test_live_run_exits_2_when_start_run_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If we cannot get a run_id, we cannot do anything else."""

    def raising_start_run(_config: Config) -> RunHandle:
        raise RuntimeError("supabase unreachable")

    monkeypatch.setattr(orchestrator, "start_run", raising_start_run)
    _stub_fetchers(monkeypatch, reddit_posts=[_make_post()])
    log = orchestrator.logging_setup.configure(level="CRITICAL")

    exit_code = orchestrator._run_live(
        _make_config(),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    assert exit_code == 2


# ----- Live run: finish_run failure does not mask the real run status -------


def test_live_run_finish_failure_does_not_change_exit_code(
    monkeypatch: pytest.MonkeyPatch, captured: _CapturedCalls
) -> None:
    """If finish_run raises, we still return the exit code for the real outcome."""

    def raising_finish(
        _handle: RunHandle,
        _config: Config,
        **_kw: Any,
    ) -> None:
        raise RuntimeError("update failed")

    _stub_fetchers(monkeypatch, reddit_posts=[_make_post()])
    monkeypatch.setattr(orchestrator, "finish_run", raising_finish)
    log = orchestrator.logging_setup.configure(level="CRITICAL")

    exit_code = orchestrator._run_live(
        _make_config(youtube_enabled=False),
        source_filter="all",
        limit_override=None,
        log=log,
    )

    # Run actually succeeded (one source landed). finish_run blowing up should
    # not change that.
    assert exit_code == 0
