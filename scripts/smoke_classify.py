"""Standalone smoke test for the ICA classifier.

Hits the live Anthropic API with one or more hand-written operator posts and
prints the resulting Classification as JSON. Use this to eyeball that the
classifier picks the right false belief on obvious cases before trusting it in
a real run.

Requires ANTHROPIC_API_KEY in the environment (or .env loaded by your shell).

    python scripts/smoke_classify.py
    python scripts/smoke_classify.py --body "labor is just brutal, nothing I can do"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scout.classifier.ica import classify
from agents.scout.config import load
from agents.scout.models import FetchedPost, Source

# A few obvious cases, one per cluster, so a quick run shows the spread.
_SAMPLES: list[tuple[str, str]] = [
    ("Slow nights, need help", "We just need more customers in the door and the rest works out."),
    (
        "Payroll is brutal",
        "Labor is just too expensive now. There is nothing you can do about wages.",
    ),
    (
        "Great food, still struggling",
        "People love our food. So the business should be working better.",
    ),
    ("Team problem", "No one takes ownership. I cannot find good people who care."),
    ("Off topic", "Anyone know a good POS paper supplier near Tampa?"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the ICA classifier.")
    parser.add_argument("--title", default=None, help="Single-post title.")
    parser.add_argument("--body", default=None, help="Single-post body. Overrides the samples.")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args(argv)

    config = load(args.config, require_reddit_creds=False, require_youtube_creds=False)

    if args.body:
        samples = [(args.title or "smoke", args.body)]
    else:
        samples = _SAMPLES

    for title, body in samples:
        post = FetchedPost(
            source=Source.REDDIT,
            source_url=f"https://example.com/{abs(hash(body))}",
            source_id="smoke",
            source_author="smoke_operator",
            posted_at=datetime.now(tz=UTC),
            title=title,
            body=body,
            source_metadata={"subreddit": "smoke"},
        )
        result = classify(post, config.classification)
        print(json.dumps({"title": title, "classification": asdict(result)}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
