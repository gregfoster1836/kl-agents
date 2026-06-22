"""classified_posts writer.

Bulk-inserts (FetchedPost + Classification) pairs against a run.

Dedup is enforced at the database via UNIQUE(source_url). A re-run that
sees the same URL twice does not crash; it skips. The diff between rows
sent and rows returned tells us how many were skipped, which the
orchestrator feeds into agent_runs.posts_dedup_skipped.

review_status is derived here, not in the classifier, because the
threshold lives in config. The queue gate is belief-match + confidence:
a post reaches the human review queue only when it expresses one of the
canonical false beliefs (signal_type is not null) AND the classifier is
confident enough.
  confidence >= threshold AND signal_type is not None -> 'pending'
  otherwise                                            -> 'auto_rejected'
ica_stage is stored as metadata but does not drive the queue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.scout.config import Config
from agents.scout.models import Classification, FetchedPost
from shared.db.client import get_client
from shared.runs import RunHandle


@dataclass(frozen=True, slots=True)
class InsertResult:
    """Outcome of a bulk insert.

    inserted is the number of rows that actually landed in classified_posts.
    skipped is the number of rows the database rejected as duplicates
    (same source_url already present from a prior run).
    """

    inserted: int
    skipped: int


def _row(
    run_id: str,
    post: FetchedPost,
    classification: Classification,
    *,
    confidence_threshold: float,
) -> dict[str, Any]:
    """Build one classified_posts row from a fetched post + classification."""
    queues = (
        classification.confidence >= confidence_threshold and classification.signal_type is not None
    )
    review_status = "pending" if queues else "auto_rejected"

    return {
        "run_id": run_id,
        "source": post.source.value,
        "source_metadata": dict(post.source_metadata),
        "source_url": post.source_url,
        "source_id": post.source_id,
        "source_author": post.source_author,
        "posted_at": post.posted_at.isoformat(),
        "title": post.title,
        "body": post.body,
        "ica_stage": classification.ica_stage,
        "confidence": classification.confidence,
        "signal_type": classification.signal_type,
        "key_quote": classification.key_quote,
        "reasoning": classification.reasoning,
        "review_status": review_status,
    }


def insert_classified_posts(
    handle: RunHandle,
    config: Config,
    items: list[tuple[FetchedPost, Classification]],
) -> InsertResult:
    """Insert all classified posts for a run, skipping duplicates by source_url.

    Returns counts so the caller can record them on agent_runs. Empty input
    is a valid case (nothing matched filtering); returns 0/0 without hitting
    the database.
    """
    if not items:
        return InsertResult(inserted=0, skipped=0)

    rows = [
        _row(
            handle.run_id,
            post,
            classification,
            confidence_threshold=config.classification.confidence_threshold,
        )
        for post, classification in items
    ]

    client = get_client(config.storage)
    response = (
        client.table("classified_posts")
        .upsert(rows, on_conflict="source_url", ignore_duplicates=True)
        .execute()
    )

    returned = response.data or []
    inserted = len(returned)
    skipped = len(rows) - inserted
    if skipped < 0:
        # Should not happen: upsert cannot return more rows than were sent.
        raise RuntimeError(f"classified_posts upsert returned {inserted} rows for {len(rows)} sent")
    return InsertResult(inserted=inserted, skipped=skipped)
