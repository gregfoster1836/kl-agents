"""Data models shared across Scout's modules.

Kept deliberately simple. These dataclasses are the contract between layers:
the fetcher returns FetchedPost, the classifier returns Classification,
storage writes both. Each layer can be tested without the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FetchedPost:
    """A Reddit post pulled by the fetcher, before classification.

    Frozen because once we have the data, downstream code should not mutate it.
    Slots because we hold many of these in memory during a run.
    """

    source: str
    source_subreddit: str
    source_url: str
    source_id: str
    source_author: str | None
    posted_at: datetime
    title: str
    body: str
    is_removed: bool


@dataclass(frozen=True, slots=True)
class Classification:
    """Classifier output. Not built this session, defined here so the fetcher
    and storage layers can compile against the type today."""

    ica_stage: str
    confidence: float
    signal_type: str | None
    key_quote: str | None
    reasoning: str
