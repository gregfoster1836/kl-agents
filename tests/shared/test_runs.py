"""Tests for the shared run lifecycle (shared/runs.py).

These do not hit Supabase. A minimal fake client captures the payload sent to
agent_runs and returns a canned response. Focus:
- status_to_exit_code maps the three terminal states
- start_run inserts a running row carrying the config snapshot
- finish_run writes metrics (JSONB) + terminal status, rejects 'running'
- finish_run validates the metrics payload BEFORE any DB write (the new
  MetricValue guard) and mirrors legacy_counts when asked
- finish_safely swallows a bookkeeping failure rather than masking the run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from shared.config import StorageConfig
from shared.db import client as client_mod
from shared.runs import RunHandle, finish_run, finish_safely, start_run, status_to_exit_code

# ----- Minimal config double (satisfies the KLAgentConfig surface) ----------


def _fake_storage() -> StorageConfig:
    return StorageConfig(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test-key",
        schema="agents_dev",
    )


@dataclass(frozen=True)
class _FakeConfig:
    agent_name: str = "validation"
    storage: StorageConfig = field(default_factory=_fake_storage)

    @property
    def snapshot(self) -> dict[str, object]:
        return {"agent": {"name": self.agent_name, "version": "0.1.0"}}


# ----- Minimal fake Supabase client -----------------------------------------


class _FakeResponse:
    def __init__(self, data: list[dict[str, Any]] | None) -> None:
        self.data = data


class _FakeBuilder:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_op: str | None = None
        self.last_payload: Any = None
        self.last_eq: tuple[str, Any] | None = None

    def insert(self, payload: Any, **_kw: Any) -> _FakeBuilder:
        self.last_op = "insert"
        self.last_payload = payload
        return self

    def update(self, payload: Any, **_kw: Any) -> _FakeBuilder:
        self.last_op = "update"
        self.last_payload = payload
        return self

    def eq(self, column: str, value: Any) -> _FakeBuilder:
        self.last_eq = (column, value)
        return self

    def execute(self) -> _FakeResponse:
        return self._response


class _FakeClient:
    def __init__(self) -> None:
        self.builders: dict[str, _FakeBuilder] = {}

    def set_response(self, table: str, data: list[dict[str, Any]] | None) -> _FakeBuilder:
        b = _FakeBuilder(_FakeResponse(data))
        self.builders[table] = b
        return b

    def table(self, name: str) -> _FakeBuilder:
        if name not in self.builders:
            self.builders[name] = _FakeBuilder(_FakeResponse([]))
        return self.builders[name]


@pytest.fixture(autouse=True)
def _reset_client() -> None:
    client_mod.reset_client()
    yield
    client_mod.reset_client()


def _install_fake(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    fake = _FakeClient()
    monkeypatch.setattr(client_mod, "create_client", lambda *a, **k: fake)
    return fake


# ----- status_to_exit_code --------------------------------------------------


def test_status_to_exit_code_maps_three_terminal_states() -> None:
    assert status_to_exit_code("success") == 0
    assert status_to_exit_code("partial") == 1
    assert status_to_exit_code("failed") == 2


# ----- start_run ------------------------------------------------------------


def test_start_run_inserts_running_row_with_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])

    handle = start_run(_FakeConfig())

    assert handle.run_id == "run-1"
    payload = fake.builders["agent_runs"].last_payload
    assert payload["agent_name"] == "validation"
    assert payload["status"] == "running"
    assert payload["config_snapshot"]["agent"]["name"] == "validation"


def test_start_run_raises_when_insert_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [])
    with pytest.raises(RuntimeError, match="no rows"):
        start_run(_FakeConfig())


# ----- finish_run: metrics + status -----------------------------------------


def test_finish_run_writes_metrics_and_terminal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])

    finish_run(
        RunHandle(run_id="run-1"),
        _FakeConfig(),
        status="success",
        metrics={"themes_ranked": 7, "top_theme": "labor"},
    )

    payload = fake.builders["agent_runs"].last_payload
    assert payload["status"] == "success"
    assert payload["metrics"] == {"themes_ranked": 7, "top_theme": "labor"}
    assert "finished_at" in payload
    assert "error_summary" not in payload


def test_finish_run_refuses_running_status() -> None:
    with pytest.raises(ValueError, match="cannot set status back to 'running'"):
        finish_run(
            RunHandle(run_id="run-1"),
            _FakeConfig(),
            status="running",  # type: ignore[arg-type]
            metrics={},
        )


def test_finish_run_includes_error_summary_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])
    finish_run(
        RunHandle(run_id="run-1"),
        _FakeConfig(),
        status="failed",
        metrics={},
        error_summary="corpus preflight failed",
    )
    assert fake.builders["agent_runs"].last_payload["error_summary"] == "corpus preflight failed"


def test_finish_run_raises_when_update_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [])
    with pytest.raises(RuntimeError, match="returned no rows"):
        finish_run(RunHandle(run_id="run-1"), _FakeConfig(), status="success", metrics={})


# ----- finish_run: metrics validation (the new MetricValue guard) -----------


def test_finish_run_rejects_nested_dict_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch)
    with pytest.raises(ValueError, match="flat scalar"):
        finish_run(
            RunHandle(run_id="run-1"),
            _FakeConfig(),
            status="success",
            metrics={"counts": {"a": 1}},  # nested dict not allowed
        )


def test_finish_run_rejects_list_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch)
    with pytest.raises(ValueError, match="flat scalar"):
        finish_run(
            RunHandle(run_id="run-1"),
            _FakeConfig(),
            status="success",
            metrics={"themes": ["labor", "rent"]},  # list not allowed
        )


def test_finish_run_accepts_all_scalar_types(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])
    finish_run(
        RunHandle(run_id="run-1"),
        _FakeConfig(),
        status="success",
        metrics={"n": 5, "rate": 0.5, "label": "x", "flagged": True, "missing": None},
    )
    assert fake.builders["agent_runs"].last_payload["metrics"]["flagged"] is True


def test_finish_run_validates_before_db_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bad metrics payload must raise before any client call (fail at the
    call site, not opaquely inside PostgREST)."""
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])
    with pytest.raises(ValueError, match="flat scalar"):
        finish_run(
            RunHandle(run_id="run-1"),
            _FakeConfig(),
            status="success",
            metrics={"bad": {"nested": 1}},
        )
    # update was never called: the only op (if any) is never 'update'
    assert fake.builders.get("agent_runs") is None or fake.builders["agent_runs"].last_op is None


# ----- finish_run: legacy_counts transition mirror --------------------------


def test_finish_run_mirrors_legacy_counts_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [{"id": "run-1"}])
    finish_run(
        RunHandle(run_id="run-1"),
        _FakeConfig(),
        status="success",
        metrics={"posts_fetched": 10, "posts_queued": 3},
        legacy_counts={"posts_fetched": 10, "posts_queued": 3},
    )
    payload = fake.builders["agent_runs"].last_payload
    assert payload["metrics"]["posts_fetched"] == 10
    assert payload["posts_fetched"] == 10  # mirrored to the deprecated column
    assert payload["posts_queued"] == 3


# ----- finish_safely --------------------------------------------------------


class _RecordingLog:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, event: str, **_kw: Any) -> None:
        self.errors.append(event)


def test_finish_safely_swallows_bookkeeping_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake(monkeypatch)
    fake.set_response("agent_runs", [])  # update returns nothing -> finish_run raises
    log = _RecordingLog()

    # Must NOT raise: a finish failure cannot mask the real run outcome.
    finish_safely(
        RunHandle(run_id="run-1"),
        _FakeConfig(),
        status="failed",
        metrics={},
        log=log,
    )
    assert "finish_run_failed" in log.errors
