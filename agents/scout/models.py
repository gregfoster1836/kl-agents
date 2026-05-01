"""Data models shared across Scout's modules.

Kept deliberately simple. These dataclasses are the contract between layers:
the fetcher returns FetchedPost, the classifier returns Classification,
storage writes both. Each layer can be tested without the others.

Source-agnostic by design: source_metadata holds whatever shape the source
needs (subreddit name for Reddit, channel and video info for YouTube). New
sources slot in by writing a fetcher and populating source_metadata. No
schema migration required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Source(StrEnum):
    """Origin of a fetched post. Values match the SQL CHECK constraint on
    classified_posts.source. Adding a new source means adding a value here AND
    extending the CHECK constraint via a new migration."""

    REDDIT = "reddit"
    YOUTUBE = "youtube"


@dataclass(frozen=True, slots=True)
class FetchedPost:
    """A post pulled by a fetcher, before classification.

    Frozen because once we have the data, downstream code should not mutate it.
    Slots because we hold many of these in memory during a run.

    source_metadata is per-source context. Examples:
      Reddit:  {"subreddit": "restaurateur"}
      YouTube: {"channel_handle": "@RestaurantUnstoppable", "channel_id": "UC...",
                "video_id": "...", "video_title": "..."}
    """

    source: Source
    source_url: str
    source_id: str
    source_author: str | None
    posted_at: datetime
    title: str
    body: str
    source_metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Classification:
    """Classifier output. Not built this session, defined here so the fetcher
    and storage layers can compile against the type today."""

    ica_stage: str
    confidence: float
    signal_type: str | None
    key_quote: str | None
    reasoning: str
