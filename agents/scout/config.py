"""Configuration loader.

Reads config.yaml plus environment variables and returns a typed Config object.
Fails loudly at startup if anything required is missing, so the agent never
runs in a half-broken state.

Multi-source structure:
- Each source has its own block under sources: in config.yaml
- Each source has an enabled flag so individual sources can be disabled
  without removing config
- The CLI can override which sources run via --source on the command line
- A source whose required env vars are missing logs an error and that source
  is skipped (other sources still run)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class RedditConfig:
    enabled: bool
    client_id: str
    client_secret: str
    user_agent: str
    subreddits: tuple[str, ...]
    posts_per_subreddit: int
    sort: str
    max_age_days: int


@dataclass(frozen=True, slots=True)
class YouTubeChannel:
    handle: str
    channel_id: str | None
    note: str
    videos_per_run: int | None  # None = use default
    comments_per_video: int | None


@dataclass(frozen=True, slots=True)
class YouTubeConfig:
    enabled: bool
    api_key: str
    channels: tuple[YouTubeChannel, ...]
    default_videos_per_channel: int
    default_comments_per_video: int
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


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    format: str


@dataclass(frozen=True, slots=True)
class Config:
    agent_name: str
    agent_version: str
    reddit: RedditConfig
    youtube: YouTubeConfig
    classification: ClassificationConfig
    storage: StorageConfig
    logging: LoggingConfig

    @property
    def snapshot(self) -> dict[str, object]:
        """Serializable snapshot for agent_runs.config_snapshot. Secrets stripped."""
        return {
            "agent": {"name": self.agent_name, "version": self.agent_version},
            "sources": {
                "reddit": {
                    "enabled": self.reddit.enabled,
                    "subreddits": list(self.reddit.subreddits),
                    "posts_per_subreddit": self.reddit.posts_per_subreddit,
                    "sort": self.reddit.sort,
                    "max_age_days": self.reddit.max_age_days,
                    "user_agent": self.reddit.user_agent,
                },
                "youtube": {
                    "enabled": self.youtube.enabled,
                    "channels": [
                        {
                            "handle": ch.handle,
                            "channel_id": ch.channel_id,
                            "note": ch.note,
                            "videos_per_run": ch.videos_per_run,
                            "comments_per_video": ch.comments_per_video,
                        }
                        for ch in self.youtube.channels
                    ],
                    "default_videos_per_channel": self.youtube.default_videos_per_channel,
                    "default_comments_per_video": self.youtube.default_comments_per_video,
                    "max_age_days": self.youtube.max_age_days,
                },
            },
            "classification": {
                "model": self.classification.model,
                "confidence_threshold": self.classification.confidence_threshold,
                "max_post_chars": self.classification.max_post_chars,
                "retry_on_rate_limit": self.classification.retry_on_rate_limit,
                "max_retries": self.classification.max_retries,
            },
            "storage": {"schema": self.storage.schema},
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


def _optional_env(key: str, default: str = "") -> str:
    value = os.environ.get(key, "").strip()
    return value if value else default


def _as_int(value: object, default: int) -> int:
    """Coerce a YAML-loaded object into an int, falling back to default if absent."""
    if value is None:
        return default
    if isinstance(value, bool):
        # bool is a subclass of int in Python; explicitly reject so a stray
        # 'true' in config does not silently become 1.
        raise ConfigError(f"Expected integer, got bool: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ConfigError(f"Expected integer, got string {value!r}") from exc
    raise ConfigError(f"Expected integer, got {type(value).__name__}: {value!r}")


def _as_float(value: object, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ConfigError(f"Expected number, got bool: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise ConfigError(f"Expected number, got string {value!r}") from exc
    raise ConfigError(f"Expected number, got {type(value).__name__}: {value!r}")


def _read_yaml(config_path: Path | str) -> dict[str, object]:
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        result = yaml.safe_load(fh)
    if not isinstance(result, dict):
        raise ConfigError(f"Config file is not a YAML mapping: {path}")
    return result


def _build_reddit(raw: dict[str, object], *, require_creds: bool) -> RedditConfig:
    enabled = bool(raw.get("enabled", True))
    if require_creds and enabled:
        client_id = _require_env("REDDIT_CLIENT_ID")
        client_secret = _require_env("REDDIT_CLIENT_SECRET")
        user_agent = _require_env("REDDIT_USER_AGENT")
    else:
        client_id = _optional_env("REDDIT_CLIENT_ID")
        client_secret = _optional_env("REDDIT_CLIENT_SECRET")
        user_agent = _optional_env("REDDIT_USER_AGENT", "kl-scout/0.1")

    subreddits_raw = raw.get("subreddits", [])
    if not isinstance(subreddits_raw, list):
        raise ConfigError("reddit.subreddits must be a list")

    return RedditConfig(
        enabled=enabled,
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        subreddits=tuple(str(s) for s in subreddits_raw),
        posts_per_subreddit=_as_int(raw.get("posts_per_subreddit"), 50),
        sort=str(raw.get("sort", "new")),
        max_age_days=_as_int(raw.get("max_age_days"), 30),
    )


def _build_youtube(raw: dict[str, object], *, require_creds: bool) -> YouTubeConfig:
    enabled = bool(raw.get("enabled", True))
    if require_creds and enabled:
        api_key = _require_env("YOUTUBE_API_KEY")
    else:
        api_key = _optional_env("YOUTUBE_API_KEY")

    channels_raw = raw.get("channels", [])
    if not isinstance(channels_raw, list):
        raise ConfigError("youtube.channels must be a list")

    channels: list[YouTubeChannel] = []
    for entry in channels_raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"youtube.channels entry must be a mapping: {entry!r}")
        channel_id_raw = entry.get("channel_id")
        videos_override = entry.get("videos_per_run")
        comments_override = entry.get("comments_per_video")
        channels.append(
            YouTubeChannel(
                handle=str(entry["handle"]),
                channel_id=(str(channel_id_raw) if channel_id_raw else None),
                note=str(entry.get("note", "")),
                videos_per_run=(
                    _as_int(videos_override, 0) if videos_override is not None else None
                ),
                comments_per_video=(
                    _as_int(comments_override, 0) if comments_override is not None else None
                ),
            )
        )

    return YouTubeConfig(
        enabled=enabled,
        api_key=api_key,
        channels=tuple(channels),
        default_videos_per_channel=_as_int(raw.get("default_videos_per_channel"), 3),
        default_comments_per_video=_as_int(raw.get("default_comments_per_video"), 50),
        max_age_days=_as_int(raw.get("max_age_days"), 30),
    )


def load(
    config_path: Path | str = "config.yaml",
    *,
    require_reddit_creds: bool = True,
    require_youtube_creds: bool = True,
) -> Config:
    """Load full configuration. Required for the orchestrator that writes to
    Supabase.

    By default, each enabled source must have its credentials present. The
    require_*_creds flags exist so the orchestrator can ask for only the
    sources it will actually invoke (e.g. --source youtube while Reddit
    credentials are still pending API approval).
    """
    raw = _read_yaml(config_path)

    try:
        agent = raw["agent"]
        sources_raw = raw["sources"]
        classification_raw = raw["classification"]
        logging_raw = raw["logging"]
    except KeyError as exc:
        raise ConfigError(f"config.yaml missing required section: {exc}") from exc

    if not isinstance(sources_raw, dict):
        raise ConfigError("config.yaml: 'sources' must be a mapping")
    if not isinstance(agent, dict):
        raise ConfigError("config.yaml: 'agent' must be a mapping")
    if not isinstance(classification_raw, dict):
        raise ConfigError("config.yaml: 'classification' must be a mapping")
    if not isinstance(logging_raw, dict):
        raise ConfigError("config.yaml: 'logging' must be a mapping")

    reddit_raw = sources_raw.get("reddit", {})
    youtube_raw = sources_raw.get("youtube", {})
    if not isinstance(reddit_raw, dict):
        raise ConfigError("sources.reddit must be a mapping")
    if not isinstance(youtube_raw, dict):
        raise ConfigError("sources.youtube must be a mapping")

    reddit = _build_reddit(reddit_raw, require_creds=require_reddit_creds)
    youtube = _build_youtube(youtube_raw, require_creds=require_youtube_creds)

    classification = ClassificationConfig(
        model=str(classification_raw["model"]),
        confidence_threshold=_as_float(classification_raw["confidence_threshold"], 0.6),
        max_post_chars=_as_int(classification_raw["max_post_chars"], 8000),
        retry_on_rate_limit=bool(classification_raw["retry_on_rate_limit"]),
        max_retries=_as_int(classification_raw["max_retries"], 3),
    )

    storage = StorageConfig(
        supabase_url=_require_env("SUPABASE_URL"),
        supabase_service_role_key=_require_env("SUPABASE_SERVICE_ROLE_KEY"),
        schema=_optional_env("SUPABASE_SCHEMA", "agents_dev"),
    )

    logging_cfg = LoggingConfig(
        level=str(logging_raw["level"]),
        format=str(logging_raw["format"]),
    )

    return Config(
        agent_name=str(agent["name"]),
        agent_version=str(agent["version"]),
        reddit=reddit,
        youtube=youtube,
        classification=classification,
        storage=storage,
        logging=logging_cfg,
    )


def load_reddit_only(config_path: Path | str = "config.yaml") -> RedditConfig:
    """Load only the Reddit slice. Used by the smoke script before Supabase
    creds exist or before YouTube is wired up."""
    raw = _read_yaml(config_path)
    sources_raw = raw.get("sources", {})
    if not isinstance(sources_raw, dict):
        raise ConfigError("config.yaml: 'sources' must be a mapping")
    reddit_raw = sources_raw.get("reddit", {})
    if not isinstance(reddit_raw, dict):
        raise ConfigError("sources.reddit must be a mapping")
    return _build_reddit(reddit_raw, require_creds=True)


def load_youtube_only(config_path: Path | str = "config.yaml") -> YouTubeConfig:
    """Load only the YouTube slice. Used by smoke scripts before full wiring."""
    raw = _read_yaml(config_path)
    sources_raw = raw.get("sources", {})
    if not isinstance(sources_raw, dict):
        raise ConfigError("config.yaml: 'sources' must be a mapping")
    youtube_raw = sources_raw.get("youtube", {})
    if not isinstance(youtube_raw, dict):
        raise ConfigError("sources.youtube must be a mapping")
    return _build_youtube(youtube_raw, require_creds=True)
