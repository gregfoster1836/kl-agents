"""ICA classifier.

Turns a FetchedPost into a Classification by asking Claude which of the ten
canonical K&L false beliefs the post expresses, how confident that read is,
and which awareness stage the operator is at.

The ten beliefs come from 01_Core_Systems/Messaging/Part VII - False Belief
Map.md (the K&L vault). Each maps to one signal_type slug. A post that does
not clearly express one of the ten gets signal_type=None: it lands in the
corpus but never reaches the human review queue. The queue gate itself lives
in storage/posts.py (belief-match + confidence); this module only produces
the classification.

Design mirrors the fetchers: small pure helpers (build_prompt,
_parse_classification) tested directly, plus thin orchestration (classify,
classify_all) that takes an injected Anthropic client so tests never touch
the network.
"""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam

from agents.scout.config import ClassificationConfig
from agents.scout.models import Classification, FetchedPost

# The ten canonical false beliefs, in Part VII order. signal_type is exactly
# one of these or None. This tuple is the source of truth: the prompt lists
# them, _parse_classification validates against them, storage queues on them.
BELIEF_SLUGS: tuple[str, ...] = (
    "marketing-problem",  # FB1: "It's a marketing problem."
    "sales-fixes-profit",  # FB2: "If sales go up, profit will follow."
    "good-food-enough",  # FB3: "If the food is good, the business should work."
    "food-cost-busywork",  # FB4: "Food cost controls are back-office busywork."
    "labor-is-fixed",  # FB5: "Labor is just too expensive now, nothing I can do."
    "external-blame",  # FB6: "It's the location, economy, competition, or staff."
    "people-not-leadership",  # FB7: "My people are the problem, not my leadership."
    "work-harder",  # FB8: "Working harder and staying involved will fix it."
    "systems-optional",  # FB9: "Technology and systems are nice to have, not essential."
    "outside-help-waste",  # FB10: "Outside help is a waste; no one knows my business."
)

# Awareness stage. Constrained by the classified_posts.ica_stage CHECK in
# migration 0002 to exactly these values. Anything else coerces to 'unclear'.
ICA_STAGES: tuple[str, ...] = ("1", "2", "3", "unclear")

# Short gloss of each belief, fed to the model so it classifies against the
# real K&L framing rather than guessing from the slug name.
_BELIEF_GLOSS: dict[str, str] = {
    "marketing-problem": "Blames empty seats / low traffic; thinks more customers fixes everything.",
    "sales-fixes-profit": "Thinks more volume or revenue automatically means more profit.",
    "good-food-enough": "Believes great food alone should make the business work.",
    "food-cost-busywork": "Treats inventory, recipe costing, food-cost control as optional busywork.",
    "labor-is-fixed": "Treats high labor cost as an unfixable external given (wages, market).",
    "external-blame": "Blames location, economy, competition, or staff for instability.",
    "people-not-leadership": "Blames employees/managers rather than systems or own leadership.",
    "work-harder": "Believes more owner hours / tighter personal grip will stabilize it.",
    "systems-optional": "Thinks systems, dashboards, and visibility are non-essential overhead.",
    "outside-help-waste": "Believes outside help is wasteful; no one understands the business better.",
}

_TOOL_NAME = "classify"

_SYSTEM_PROMPT = (
    "You are Scout, a research classifier for Knife & Ledger, a restaurant "
    "operations advisory. You read public posts and comments from restaurant "
    "operators and identify which, if any, of ten canonical operator false "
    "beliefs the post expresses. You never invent a belief that is not clearly "
    "present. When the post does not clearly express one of the ten, you return "
    "signal_type null. You always call the classify tool."
)


class ClassificationError(Exception):
    """Raised when the model response cannot be turned into a Classification."""


def _belief_menu() -> str:
    """Render the ten beliefs as a slug: gloss menu for the prompt."""
    return "\n".join(f"- {slug}: {_BELIEF_GLOSS[slug]}" for slug in BELIEF_SLUGS)


def build_prompt(post: FetchedPost, *, max_post_chars: int) -> str:
    """Build the user-message text for one post. Pure and deterministic.

    Body is truncated to max_post_chars so a long thread cannot blow the
    token budget. Title is included whole (always short).
    """
    body = post.body[:max_post_chars]
    return (
        "Classify this restaurant-operator post against the ten K&L false "
        "beliefs.\n\n"
        "The ten beliefs (signal_type must be exactly one of these slugs, or "
        "null if none clearly applies):\n"
        f"{_belief_menu()}\n\n"
        "Awareness stage (ica_stage):\n"
        "- '1': unaware the instability is structural (symptom talk only)\n"
        "- '2': problem-aware, sensing something deeper but misattributing it\n"
        "- '3': solution-aware, looking for structural help\n"
        "- 'unclear': cannot tell\n\n"
        f"POST TITLE: {post.title}\n"
        f"POST BODY:\n{body}\n\n"
        "Call the classify tool. signal_type null unless a belief is clearly "
        "expressed. confidence is your certainty (0 to 1) that the chosen "
        "signal_type is correct. key_quote is the shortest verbatim span that "
        "shows the belief, or null. reasoning is one sentence."
    )


def _tool_schema() -> ToolParam:
    """The classify tool input schema. Forces structured output."""
    return {
        "name": _TOOL_NAME,
        "description": "Record the classification of one operator post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ica_stage": {"type": "string", "enum": list(ICA_STAGES)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "signal_type": {
                    "type": ["string", "null"],
                    "enum": [*BELIEF_SLUGS, None],
                },
                "key_quote": {"type": ["string", "null"]},
                "reasoning": {"type": "string"},
            },
            "required": [
                "ica_stage",
                "confidence",
                "signal_type",
                "key_quote",
                "reasoning",
            ],
        },
    }


def _parse_classification(payload: dict[str, Any]) -> Classification:
    """Turn the tool-use input dict into a validated Classification.

    Defensive on every field the model controls:
    - signal_type not in BELIEF_SLUGS (or null) coerces to None
    - confidence clamps to [0, 1]
    - ica_stage not in ICA_STAGES defaults to 'unclear'
    Missing required keys raise ClassificationError (the tool schema should
    prevent this, but a belt-and-suspenders check keeps storage safe).
    """
    required = ("ica_stage", "confidence", "signal_type", "key_quote", "reasoning")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ClassificationError(f"classification payload missing keys: {missing}")

    raw_signal = payload["signal_type"]
    signal_type = raw_signal if raw_signal in BELIEF_SLUGS else None

    raw_stage = payload["ica_stage"]
    ica_stage = raw_stage if raw_stage in ICA_STAGES else "unclear"

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise ClassificationError(f"confidence not a number: {payload['confidence']!r}") from exc
    confidence = max(0.0, min(1.0, confidence))

    key_quote = payload["key_quote"]
    if key_quote is not None:
        key_quote = str(key_quote)

    return Classification(
        ica_stage=ica_stage,
        confidence=confidence,
        signal_type=signal_type,
        key_quote=key_quote,
        reasoning=str(payload["reasoning"]),
    )


def _extract_tool_input(message: Any) -> dict[str, Any]:
    """Pull the classify tool_use input out of a messages.create response."""
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise ClassificationError("model response contained no tool_use block")


def _unclassified() -> Classification:
    """Fallback when a single post fails to classify. Null signal keeps it out
    of the review queue; the row still lands in the corpus."""
    return Classification(
        ica_stage="unclear",
        confidence=0.0,
        signal_type=None,
        key_quote=None,
        reasoning="classification failed; recorded as unclassified",
    )


def _get_client(client: Anthropic | None) -> Anthropic:
    """Return the injected client, or build one from ANTHROPIC_API_KEY."""
    if client is not None:
        return client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClassificationError("ANTHROPIC_API_KEY not set and no client injected")
    return Anthropic(api_key=api_key)


def _invoke(api: Anthropic, post: FetchedPost, config: ClassificationConfig) -> Classification:
    """Single typed call site for the Anthropic API. Forces the classify tool
    and parses the result. Raises ClassificationError on an unusable response."""
    tools: list[ToolParam] = [_tool_schema()]
    tool_choice: ToolChoiceToolParam = {"type": "tool", "name": _TOOL_NAME}
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": build_prompt(post, max_post_chars=config.max_post_chars),
        }
    ]
    message = api.messages.create(
        model=config.model,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        tools=tools,
        tool_choice=tool_choice,
        messages=messages,
    )
    return _parse_classification(_extract_tool_input(message))


def classify(
    post: FetchedPost,
    config: ClassificationConfig,
    *,
    client: Anthropic | None = None,
) -> Classification:
    """Classify one post. Raises ClassificationError on an unusable response."""
    return _invoke(_get_client(client), post, config)


def classify_all(
    posts: list[FetchedPost],
    config: ClassificationConfig,
    *,
    client: Anthropic | None = None,
) -> list[tuple[FetchedPost, Classification]]:
    """Classify every post, pairing each with its Classification.

    A single post that fails (API error, unparseable response) falls back to
    an unclassified result rather than aborting the batch. One bad post must
    not cost a whole run's worth of fetched data.
    """
    if not posts:
        return []
    api = _get_client(client)
    results: list[tuple[FetchedPost, Classification]] = []
    for post in posts:
        try:
            classification = _invoke(api, post, config)
        except Exception:
            classification = _unclassified()
        results.append((post, classification))
    return results
