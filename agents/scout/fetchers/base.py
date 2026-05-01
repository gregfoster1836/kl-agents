"""Fetcher contract.

Every source-specific fetcher (reddit, youtube, future) implements this
protocol. The orchestrator iterates configured sources, calls fetch() on each,
and combines the results into one list[FetchedPost] for the classifier.

The protocol exists so adding source #3 means dropping a new file in
fetchers/ and registering it. No changes to the orchestrator. No changes
to the classifier. No changes to storage.
"""

from __future__ import annotations

from typing import Protocol

from agents.scout.models import FetchedPost, Source


class Fetcher(Protocol):
    """Common shape for all source fetchers.

    Implementations should:
    - Be safe to instantiate without making network calls
    - Skip removed/deleted/private content
    - Skip content older than max_age
    - Skip content with no usable title and no body
    - Log per-source failures and continue, never abort the whole run
    """

    name: Source

    def fetch(self) -> list[FetchedPost]:
        """Pull posts from this source. May raise on auth failure."""
        ...


class FetchError(Exception):
    """Base class for fetcher-level failures.

    Per-item problems (one bad post, one missing comment) should be logged
    and skipped, not raised. Raise this only when the whole source is
    unusable (auth failure, banned account, network outage).
    """
