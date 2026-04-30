"""Configuration loader.

Reads config.yaml plus environment variables and returns a typed Config object.
Fails loudly at startup if anything required is missing, so the agent never
runs in a half-broken state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class RedditConfig:
    client_id: str
    client_secret: str
    user_agent: str
    subreddits: tuple[str, ...]
    posts_per_subreddit: int
    sort: str
    max_age_days: int


@dataclass(frozen=True, slots=True)
class ClassificationConfig:
    model: str
    confidence_threshold: float
    max_post_chars: int
    retry_on_rate_limit: bool
    max_retries: int


@dataclass(frozen=True, slots=True)
class StorageConfig:
    supabase_url: str
    supabase_service_role_key: str
    schema: str
    source_name: str


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    format: str


@dataclass(frozen=True, slots=True)
class Config:
    agent_name: str
    agent_version: str
    reddit: RedditConfig
    classification: ClassificationConfig
    storage: StorageConfig
    logging: LoggingConfig

    @property
    def snapshot(self) -> dict[str, object]:
        """Serializable snapshot for agent_runs.config_snapshot. Secrets stripped."""
        return {
            "agent": {"name": self.agent_name, "version": self.agent_version},
            "reddit": {
                "subreddits": list(self.reddit.subreddits),
                "posts_per_subreddit": self.reddit.posts_per_subreddit,
                "sort": self.reddit.sort,
                "max_age_days": self.reddit.max_age_days,
                "user_agent": self.reddit.user_agent,
            },
            "classification": {
                "model": self.classification.model,
                "confidence_threshold": self.classification.confidence_threshold,
                "max_post_chars": self.classification.max_post_chars,
                "retry_on_rate_limit": self.classification.retry_on_rate_limit,
                "max_retries": self.classification.max_retries,
            },
            "storage": {
                "schema": self.storage.schema,
                "source_name": self.storage.source_name,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
            },
        }


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {key}")
    return value


def _optional_env(key: str, default: str) -> str:
    value = os.environ.get(key, "").strip()
    return value if value else default


def load(config_path: Path | str = "config.yaml") -> Config:
    """Load configuration from config.yaml and the environment.

    Order of operations:
    1. Load .env into os.environ if a .env file exists.
    2. Read config.yaml.
    3. Resolve env-backed fields and validate.
    """
    load_dotenv()

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    try:
        agent = raw["agent"]
        reddit_raw = raw["reddit"]
        classification_raw = raw["classification"]
        storage_raw = raw["storage"]
        logging_raw = raw["logging"]
    except KeyError as exc:
        raise ConfigError(f"config.yaml missing required section: {exc}") from exc

    reddit = RedditConfig(
        client_id=_require_env("REDDIT_CLIENT_ID"),
        client_secret=_require_env("REDDIT_CLIENT_SECRET"),
        user_agent=_require_env("REDDIT_USER_AGENT"),
        subreddits=tuple(reddit_raw["subreddits"]),
        posts_per_subreddit=int(reddit_raw["posts_per_subreddit"]),
        sort=str(reddit_raw["sort"]),
        max_age_days=int(reddit_raw["max_age_days"]),
    )

    classification = ClassificationConfig(
        model=str(classification_raw["model"]),
        confidence_threshold=float(classification_raw["confidence_threshold"]),
        max_post_chars=int(classification_raw["max_post_chars"]),
        retry_on_rate_limit=bool(classification_raw["retry_on_rate_limit"]),
        max_retries=int(classification_raw["max_retries"]),
    )

    storage = StorageConfig(
        supabase_url=_require_env("SUPABASE_URL"),
        supabase_service_role_key=_require_env("SUPABASE_SERVICE_ROLE_KEY"),
        schema=_optional_env("SUPABASE_SCHEMA", "agents_dev"),
        source_name=str(storage_raw["source_name"]),
    )

    logging_cfg = LoggingConfig(
        level=str(logging_raw["level"]),
        format=str(logging_raw["format"]),
    )

    return Config(
        agent_name=str(agent["name"]),
        agent_version=str(agent["version"]),
        reddit=reddit,
        classification=classification,
        storage=storage,
        logging=logging_cfg,
    )


def load_reddit_only(config_path: Path | str = "config.yaml") -> RedditConfig:
    """Load only the Reddit slice. Useful for the smoke script before Supabase
    credentials exist."""
    load_dotenv()

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    reddit_raw = raw["reddit"]
    return RedditConfig(
        client_id=_require_env("REDDIT_CLIENT_ID"),
        client_secret=_require_env("REDDIT_CLIENT_SECRET"),
        user_agent=_require_env("REDDIT_USER_AGENT"),
        subreddits=tuple(reddit_raw["subreddits"]),
        posts_per_subreddit=int(reddit_raw["posts_per_subreddit"]),
        sort=str(reddit_raw["sort"]),
        max_age_days=int(reddit_raw["max_age_days"]),
    )
