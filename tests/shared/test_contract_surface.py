"""Enforce the kl-agent config-surface contract (requirement 2).

Every kl-agent's config must satisfy shared.runs.KLAgentConfig: agent_name,
agent_version, snapshot (a property/attribute, not a method), and storage. The
reference agent is Scout. This test pins that surface so a future agent (or a
refactor of Scout) cannot silently drop a member the run lifecycle reads.
"""

from __future__ import annotations

from agents.scout.config import Config
from shared.config import StorageConfig
from shared.runs import KLAgentConfig


def _scout_config() -> Config:
    """A minimal Scout Config built without touching the environment."""
    from agents.scout.config import (
        ClassificationConfig,
        LoggingConfig,
        RedditConfig,
        YouTubeConfig,
    )

    return Config(
        agent_name="scout",
        agent_version="0.1.0",
        reddit=RedditConfig(
            enabled=False,
            client_id="",
            client_secret="",
            user_agent="t",
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
            model="m",
            confidence_threshold=0.6,
            max_post_chars=8000,
            retry_on_rate_limit=True,
            max_retries=3,
        ),
        storage=StorageConfig(
            supabase_url="https://t.supabase.co",
            supabase_service_role_key="k",
            schema="agents_dev",
        ),
        logging=LoggingConfig(level="INFO", format="json"),
    )


def test_scout_config_satisfies_kl_agent_contract() -> None:
    cfg = _scout_config()
    # runtime_checkable Protocol: structural conformance at runtime.
    assert isinstance(cfg, KLAgentConfig)


def test_scout_config_exposes_each_contract_member() -> None:
    cfg = _scout_config()
    assert isinstance(cfg.agent_name, str)
    assert isinstance(cfg.agent_version, str)
    assert isinstance(cfg.storage, StorageConfig)
    # snapshot is a property/attribute (accessed, never called) returning a dict.
    assert isinstance(cfg.snapshot, dict)
    assert cfg.snapshot["agent"] == {"name": "scout", "version": "0.1.0"}


def test_snapshot_is_an_attribute_not_a_method() -> None:
    """The contract requires config.snapshot, not config.snapshot(). A method
    would make `isinstance(cfg, KLAgentConfig)` pass but break start_run, so pin
    that snapshot resolves to a value (dict), not a callable."""
    cfg = _scout_config()
    assert not callable(cfg.snapshot)


def test_kl_agent_config_protocol_member_set() -> None:
    """The Protocol declares exactly the contract surface the run lifecycle
    reads (start_run/finish_run): agent_name, snapshot, storage. agent_version
    is carried inside snapshot, not read directly, so it is not a Protocol
    member."""
    assert set(KLAgentConfig.__protocol_attrs__) == {"agent_name", "snapshot", "storage"}
