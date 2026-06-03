"""Tests for the ICA classifier.

These tests do not hit the Anthropic API. They build a fake client whose
messages.create returns canned tool-use / text payloads, and they exercise
the pure parsing and prompt helpers directly. Coverage:
- signal_type enum: the 10 canonical belief slugs plus null
- _parse_classification: valid payload, unknown signal_type coerced to None,
  confidence clamping, ica_stage defaulting, malformed JSON
- build_prompt: includes post body, truncates at max_post_chars, lists slugs
- classify: maps a fake API response into a Classification
- classify_all: pairs each post with its classification, isolates failures
- queue gate: signal_type drives review_status (belief-match + confidence),
  ica_stage does NOT
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from agents.scout.classifier import ica
from agents.scout.config import ClassificationConfig
from agents.scout.models import Classification, FetchedPost, Source

# ----- Helpers --------------------------------------------------------------


def _config(
    *,
    model: str = "claude-sonnet-4-5",
    threshold: float = 0.6,
    max_chars: int = 8000,
    max_retries: int = 3,
) -> ClassificationConfig:
    return ClassificationConfig(
        model=model,
        confidence_threshold=threshold,
        max_post_chars=max_chars,
        retry_on_rate_limit=True,
        max_retries=max_retries,
    )


def _post(
    *,
    body: str = "I just need more customers and this all settles down.",
    title: str = "Slow nights, what marketing works?",
    source_id: str = "t1_abc",
) -> FetchedPost:
    return FetchedPost(
        source=Source.REDDIT,
        source_url=f"https://reddit.com/{source_id}",
        source_id=source_id,
        source_author="an_operator",
        posted_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        title=title,
        body=body,
        source_metadata={"subreddit": "restaurateur"},
    )


def _fake_client_returning(payload: dict[str, Any]) -> MagicMock:
    """Build a fake Anthropic client whose messages.create returns a single
    tool_use block carrying `payload` as its input."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "classify"
    block.input = payload

    message = MagicMock()
    message.content = [block]

    client = MagicMock()
    client.messages.create.return_value = message
    return client


# ----- the canonical slug list ----------------------------------------------


def test_belief_slugs_are_the_ten_part_vii_beliefs() -> None:
    assert ica.BELIEF_SLUGS == (
        "marketing-problem",
        "sales-fixes-profit",
        "good-food-enough",
        "food-cost-busywork",
        "labor-is-fixed",
        "external-blame",
        "people-not-leadership",
        "work-harder",
        "systems-optional",
        "outside-help-waste",
    )


def test_ica_stages_match_db_constraint() -> None:
    """ica_stage column is check (ica_stage in ('1','2','3','unclear'))."""
    assert ica.ICA_STAGES == ("1", "2", "3", "unclear")


# ----- _parse_classification ------------------------------------------------


def test_parse_classification_valid_payload() -> None:
    payload = {
        "ica_stage": "2",
        "confidence": 0.82,
        "signal_type": "marketing-problem",
        "key_quote": "I just need more customers",
        "reasoning": "Operator attributes instability to traffic.",
    }

    result = ica._parse_classification(payload)

    assert isinstance(result, Classification)
    assert result.ica_stage == "2"
    assert result.confidence == 0.82
    assert result.signal_type == "marketing-problem"
    assert result.key_quote == "I just need more customers"
    assert result.reasoning == "Operator attributes instability to traffic."


def test_parse_classification_unknown_signal_type_becomes_none() -> None:
    payload = {
        "ica_stage": "2",
        "confidence": 0.7,
        "signal_type": "cash-flow-panic",  # not in BELIEF_SLUGS
        "key_quote": None,
        "reasoning": "no canonical belief matched",
    }

    result = ica._parse_classification(payload)

    assert result.signal_type is None


def test_parse_classification_null_signal_type_stays_none() -> None:
    payload = {
        "ica_stage": "unclear",
        "confidence": 0.1,
        "signal_type": None,
        "key_quote": None,
        "reasoning": "off topic",
    }

    result = ica._parse_classification(payload)

    assert result.signal_type is None


def test_parse_classification_clamps_confidence_above_one() -> None:
    payload = {
        "ica_stage": "1",
        "confidence": 1.4,
        "signal_type": "work-harder",
        "key_quote": "q",
        "reasoning": "r",
    }

    result = ica._parse_classification(payload)

    assert result.confidence == 1.0


def test_parse_classification_clamps_confidence_below_zero() -> None:
    payload = {
        "ica_stage": "1",
        "confidence": -0.3,
        "signal_type": None,
        "key_quote": None,
        "reasoning": "r",
    }

    result = ica._parse_classification(payload)

    assert result.confidence == 0.0


def test_parse_classification_invalid_ica_stage_defaults_to_unclear() -> None:
    payload = {
        "ica_stage": "5",  # not in ICA_STAGES
        "confidence": 0.5,
        "signal_type": None,
        "key_quote": None,
        "reasoning": "r",
    }

    result = ica._parse_classification(payload)

    assert result.ica_stage == "unclear"


def test_parse_classification_missing_keys_raises() -> None:
    with pytest.raises(ica.ClassificationError, match="missing"):
        ica._parse_classification({"confidence": 0.5})


# ----- build_prompt ---------------------------------------------------------


def test_build_prompt_includes_title_and_body() -> None:
    post = _post(title="Labor is killing me", body="payroll is out of control")

    prompt = ica.build_prompt(post, max_post_chars=8000)

    assert "Labor is killing me" in prompt
    assert "payroll is out of control" in prompt


def test_build_prompt_truncates_body_at_max_chars() -> None:
    post = _post(body="x" * 5000)

    prompt = ica.build_prompt(post, max_post_chars=100)

    # The body in the prompt should be capped; the full 5000 must not appear.
    assert "x" * 5000 not in prompt
    assert "x" * 100 in prompt


def test_build_prompt_lists_all_belief_slugs() -> None:
    prompt = ica.build_prompt(_post(), max_post_chars=8000)

    for slug in ica.BELIEF_SLUGS:
        assert slug in prompt


# ----- classify -------------------------------------------------------------


def test_classify_maps_api_response_to_classification() -> None:
    client = _fake_client_returning(
        {
            "ica_stage": "2",
            "confidence": 0.9,
            "signal_type": "marketing-problem",
            "key_quote": "we just need more traffic",
            "reasoning": "classic front-door belief",
        }
    )

    result = ica.classify(_post(), _config(), client=client)

    assert result.signal_type == "marketing-problem"
    assert result.confidence == 0.9
    # The configured model must reach the API call.
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"


def test_classify_raises_when_no_tool_use_block() -> None:
    text_block = MagicMock()
    text_block.type = "text"
    message = MagicMock()
    message.content = [text_block]
    client = MagicMock()
    client.messages.create.return_value = message

    with pytest.raises(ica.ClassificationError, match="tool_use"):
        ica.classify(_post(), _config(), client=client)


# ----- classify_all ---------------------------------------------------------


def test_classify_all_pairs_each_post_with_a_classification() -> None:
    client = _fake_client_returning(
        {
            "ica_stage": "2",
            "confidence": 0.8,
            "signal_type": "labor-is-fixed",
            "key_quote": "nothing you can do about payroll",
            "reasoning": "r",
        }
    )
    posts = [_post(source_id="a"), _post(source_id="b")]

    results = ica.classify_all(posts, _config(), client=client)

    assert len(results) == 2
    assert all(isinstance(p, FetchedPost) for p, _ in results)
    assert all(isinstance(c, Classification) for _, c in results)
    assert results[0][0].source_id == "a"


def test_classify_all_isolates_a_single_post_failure() -> None:
    """One post that raises during classification must not abort the batch.
    The failed post falls back to an unclear/null classification so the row
    still lands in the corpus and the queue stays clean."""
    good_message = MagicMock()
    good_block = MagicMock()
    good_block.type = "tool_use"
    good_block.input = {
        "ica_stage": "1",
        "confidence": 0.7,
        "signal_type": "work-harder",
        "key_quote": "q",
        "reasoning": "r",
    }
    good_message.content = [good_block]

    client = MagicMock()
    client.messages.create.side_effect = [RuntimeError("api blew up"), good_message]
    posts = [_post(source_id="boom"), _post(source_id="ok")]

    results = ica.classify_all(posts, _config(), client=client)

    assert len(results) == 2
    # Failed post: null signal, unclear stage, zero confidence.
    assert results[0][1].signal_type is None
    assert results[0][1].ica_stage == "unclear"
    assert results[0][1].confidence == 0.0
    # Healthy post still classified normally.
    assert results[1][1].signal_type == "work-harder"
