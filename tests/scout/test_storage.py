"""Tests for the storage layer.

These tests do not hit Supabase. They build a fake client whose table()
chain captures the payload and returns a canned response. The goal is to
verify:
- shared/db/client.py builds and caches a single Client per process
- agent_runs.start_run sends the right shape and reads run_id back
- agent_runs.finish_run rejects status='running' and sends counts
- classified_posts maps FetchedPost + Classification into row shape
- review_status is 'pending' above threshold and not 'unclear', else 'auto_rejected'
- empty input short-circuits without hitting the client
- dedup skip count is len(sent) - len(returned)

The fake client mirrors supabase-py's table().insert/update/upsert().execute()
chain just enough to capture the call and respond. Anything beyond that is
the library's problem, not ours.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from agents.scout.config import (
    ClassificationConfig,
    Config,
    LoggingConfig,
    RedditConfig,
    StorageConfig,
    YouTubeConfig,
)
from agents.scout.models import Classification, FetchedPost, Source
from agents.scout.storage import posts as posts_mod
from agents.scout.storage.posts import InsertResult, insert_classified_posts
from agents.scout.storage.runs import RunHandle, finish_run, start_run
from shared.db import client as client_mod

# ----- Helpers --------------------------------------------------------------


def _make_config(*, schema: str = "agents_dev", threshold: float = 0.6) -> Config:
    """Build a Config with just the fields the storage layer reads."""
    return Config(
        agent_name="scout",
        agent_version="0.1.0",
        reddit=RedditConfig(
            enabled=False,
            client_id="",
            client_secret="",
            user_agent="test",
            subreddits=(),
            posts_per_subreddit=0,
            sort="new",
            max_age_days=30,
        ),
        youtube=YouTubeConfig(
            enabled=False,
            api_key="",
            channels=(),
            default_videos_per_channel=0,
            default_comments_per_video=0,
            max_age_days=30,
        ),
        classification=ClassificationConfig(
            model="claude-sonnet-4-6",
            confidence_threshold=threshold,
            max_post_chars=8000,
            retry_on_rate_limit=True,
            max_retries=3,
        ),
        storage=StorageConfig(
            supabase_url="https://test.supabase.co",
            supabase_service_role_key="test-key",
            schema=schema,
        ),
        logging=LoggingConfig(level="INFO", format="json"),
    )


def _make_post(*, url: str = "https://reddit.com/r/restaurateur/comments/abc/x/") -> FetchedPost:
    return FetchedPost(
        source=Source.REDDIT,
        source_url=url,
        source_id="abc",
        source_author="an_operator",
        posted_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
        title="labor cost is killing me",
        body="tried everything, still cant find good people",
        source_metadata={"subreddit": "restaurateur"},
    )


def _make_classification(
    *,
    stage: str = "1",
    confidence: float = 0.8,
    signal: str | None = "work-harder-fixes-it",
) -> Classification:
    return Classification(
        ica_stage=stage,
        confidence=confidence,
        signal_type=signal,
        key_quote="tried everything",
        reasoning="symptom-aware operator describing labor pain",
    )


class FakeExecuteResponse:
    def __init__(self, data: list[dict[str, Any]] | None) -> None:
        self.data = data


class FakeBuilder:
    """Mirrors supabase-py's table builder for insert/update/upsert/eq/execute."""

    def __init__(self, response: FakeExecuteResponse) -> None:
        self._response = response
        # Captured for assertions:
        self.last_op: str | None = None
        self.last_payload: Any = None
        self.last_kwargs: dict[str, Any] = {}
        self.last_eq: tuple[str, Any] | None = None

    def insert(self, payload: Any, **kwargs: Any) -> FakeBuilder:
        self.last_op = "insert"
        self.last_payload = payload
        self.last_kwargs = kwargs
        return self

    def update(self, payload: Any, **kwargs: Any) -> FakeBuilder:
        self.last_op = "update"
        self.last_payload = payload
        self.last_kwargs = kwargs
        return self

    def upsert(self, payload: Any, **kwargs: Any) -> FakeBuilder:
        self.last_op = "upsert"
        self.last_payload = payload
        self.last_kwargs = kwargs
        return self

    def eq(self, column: str, value: Any) -> FakeBuilder:
        self.last_eq = (column, value)
        return self

    def execute(self) -> FakeExecuteResponse:
        return self._response


class FakeClient:
    """Mirrors supabase Client.table() routing to a per-table FakeBuilder."""

    def __init__(self) -> None:
        self.builders: dict[str, FakeBuilder] = {}

    def set_response(self, table_name: str, data: list[dict[str, Any]] | None) -> FakeBuilder:
        builder = FakeBuilder(FakeExecuteResponse(data))
        self.builders[table_name] = builder
        return builder

    def table(self, name: str) -> FakeBuilder:
        if name not in self.builders:
            # Default to empty success so tests that forget to set a response
            # fail loudly on the assertion, not on a KeyError.
            self.builders[name] = FakeBuilder(FakeExecuteResponse([]))
        return self.builders[name]


@pytest.fixture(autouse=True)
def _reset_client_singleton() -> None:
    """Storage tests must not share the cached Client across cases."""
    client_mod.reset_client()
    yield
    client_mod.reset_client()


# ----- shared/db/client.py --------------------------------------------------


def test_get_client_constructs_once_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_config(schema="agents_dev")
    call_count = {"n": 0}

    def fake_create_client(url: str, key: str, options: Any) -> FakeClient:
        call_count["n"] += 1
        assert url == config.storage.supabase_url
        assert key == config.storage.supabase_service_role_key
        assert options.schema == "agents_dev"
        return FakeClient()

    monkeypatch.setattr(client_mod, "create_client", fake_create_client)

    first = client_mod.get_client(config.storage)
    second = client_mod.get_client(config.storage)
    assert first is second
    assert call_count["n"] == 1


def test_get_client_refuses_schema_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "create_client", lambda *a, **k: FakeClient())
    client_mod.get_client(_make_config(schema="agents_dev").storage)
    with pytest.raises(RuntimeError, match="already bound to schema"):
        client_mod.get_client(_make_config(schema="agents_prod").storage)


# ----- agents/scout/storage/runs.py -----------------------------------------


def _install_fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    fake = FakeClient()
    monkeypatch.setattr(client_mod, "create_client", lambda *a, **k: fake)
    return fake


def test_start_run_inserts_running_row_with_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [{"id": "11111111-1111-1111-1111-111111111111"}])

    config = _make_config()
    handle = start_run(config)

    assert handle.run_id == "11111111-1111-1111-1111-111111111111"
    builder = fake.builders["agent_runs"]
    assert builder.last_op == "insert"
    payload = builder.last_payload
    assert payload["agent_name"] == "scout"
    assert payload["status"] == "running"
    # Snapshot is the secrets-stripped Config.snapshot.
    assert payload["config_snapshot"]["agent"] == {"name": "scout", "version": "0.1.0"}
    assert "supabase_service_role_key" not in str(payload["config_snapshot"])


def test_start_run_raises_when_insert_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [])
    with pytest.raises(RuntimeError, match="no rows"):
        start_run(_make_config())


def test_start_run_raises_when_row_has_no_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [{"agent_name": "scout"}])
    with pytest.raises(RuntimeError, match="no id"):
        start_run(_make_config())


def test_finish_run_updates_row_and_sets_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [{"id": "abc"}])
    config = _make_config()
    handle = RunHandle(run_id="abc")

    finish_run(
        handle,
        config,
        status="success",
        posts_fetched=10,
        posts_dedup_skipped=2,
        posts_classified=8,
        posts_queued=5,
    )

    builder = fake.builders["agent_runs"]
    assert builder.last_op == "update"
    assert builder.last_eq == ("id", "abc")
    payload = builder.last_payload
    assert payload["status"] == "success"
    assert payload["posts_fetched"] == 10
    assert payload["posts_dedup_skipped"] == 2
    assert payload["posts_classified"] == 8
    assert payload["posts_queued"] == 5
    assert "finished_at" in payload  # ISO timestamp set client-side
    assert "error_summary" not in payload  # omitted when None


def test_finish_run_includes_error_summary_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [{"id": "abc"}])
    finish_run(
        RunHandle(run_id="abc"),
        _make_config(),
        status="partial",
        posts_fetched=5,
        posts_dedup_skipped=0,
        posts_classified=3,
        posts_queued=1,
        error_summary="reddit auth failed; youtube succeeded",
    )
    payload = fake.builders["agent_runs"].last_payload
    assert payload["error_summary"] == "reddit auth failed; youtube succeeded"


def test_finish_run_refuses_running_status() -> None:
    with pytest.raises(ValueError, match="cannot set status back to 'running'"):
        finish_run(
            RunHandle(run_id="abc"),
            _make_config(),
            status="running",  # type: ignore[arg-type]
            posts_fetched=0,
            posts_dedup_skipped=0,
            posts_classified=0,
            posts_queued=0,
        )


def test_finish_run_raises_when_update_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("agent_runs", [])
    with pytest.raises(RuntimeError, match="returned no rows"):
        finish_run(
            RunHandle(run_id="abc"),
            _make_config(),
            status="success",
            posts_fetched=0,
            posts_dedup_skipped=0,
            posts_classified=0,
            posts_queued=0,
        )


# ----- agents/scout/storage/posts.py ----------------------------------------


def test_insert_classified_posts_empty_does_not_call_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If get_client is even invoked here, the test fails.
    def explode(*a: Any, **k: Any) -> Any:
        raise AssertionError("get_client must not be called when items is empty")

    monkeypatch.setattr(posts_mod, "get_client", explode)
    result = insert_classified_posts(RunHandle(run_id="r1"), _make_config(), [])
    assert result == InsertResult(inserted=0, skipped=0)


def test_insert_classified_posts_maps_row_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("classified_posts", [{"id": "p1"}])

    post = _make_post()
    classification = _make_classification()
    result = insert_classified_posts(
        RunHandle(run_id="run-1"),
        _make_config(threshold=0.6),
        [(post, classification)],
    )

    assert result == InsertResult(inserted=1, skipped=0)
    builder = fake.builders["classified_posts"]
    assert builder.last_op == "upsert"
    assert builder.last_kwargs["on_conflict"] == "source_url"
    assert builder.last_kwargs["ignore_duplicates"] is True

    rows = builder.last_payload
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run-1"
    assert row["source"] == "reddit"
    assert row["source_metadata"] == {"subreddit": "restaurateur"}
    assert row["source_url"] == post.source_url
    assert row["ica_stage"] == "1"
    assert row["confidence"] == 0.8
    assert row["signal_type"] == "work-harder-fixes-it"
    assert row["posted_at"] == "2026-05-11T10:00:00+00:00"
    assert row["review_status"] == "pending"


def test_review_status_pending_above_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("classified_posts", [{"id": "p1"}])
    insert_classified_posts(
        RunHandle(run_id="r"),
        _make_config(threshold=0.6),
        [(_make_post(), _make_classification(stage="2", confidence=0.6))],
    )
    assert fake.builders["classified_posts"].last_payload[0]["review_status"] == "pending"


def test_review_status_auto_rejected_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("classified_posts", [{"id": "p1"}])
    insert_classified_posts(
        RunHandle(run_id="r"),
        _make_config(threshold=0.6),
        [(_make_post(), _make_classification(confidence=0.59))],
    )
    assert fake.builders["classified_posts"].last_payload[0]["review_status"] == "auto_rejected"


def test_review_status_auto_rejected_when_stage_unclear(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("classified_posts", [{"id": "p1"}])
    insert_classified_posts(
        RunHandle(run_id="r"),
        _make_config(threshold=0.6),
        # Confident, but stage is unclear: still gets auto_rejected.
        [(_make_post(), _make_classification(stage="unclear", confidence=0.99))],
    )
    assert fake.builders["classified_posts"].last_payload[0]["review_status"] == "auto_rejected"


def test_dedup_skip_counted_from_response_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    # Sent 3, DB returned 1 (other two collided on source_url).
    fake.set_response("classified_posts", [{"id": "p1"}])

    items = [
        (_make_post(url=f"https://reddit.com/r/x/comments/{i}/"), _make_classification())
        for i in range(3)
    ]
    result = insert_classified_posts(RunHandle(run_id="r"), _make_config(), items)
    assert result == InsertResult(inserted=1, skipped=2)


def test_dedup_handles_none_response_as_zero_inserted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_client(monkeypatch)
    fake.set_response("classified_posts", None)
    result = insert_classified_posts(
        RunHandle(run_id="r"),
        _make_config(),
        [(_make_post(), _make_classification())],
    )
    assert result == InsertResult(inserted=0, skipped=1)
