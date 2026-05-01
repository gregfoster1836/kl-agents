"""Tests for the YouTube fetcher.

These tests do not hit YouTube. They build fake API response dicts and feed
them through the fetcher's helpers. Coverage:
- Channel handle resolution success and not-found cases
- Recent video listing with timestamp parsing and age filtering
- Comment-to-FetchedPost conversion: source enum, metadata payload, URL shape
- Empty body, missing id, unparseable timestamp all produce None
- Disabled-comments video returns empty without aborting the channel
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from agents.scout.config import YouTubeChannel
from agents.scout.fetchers import youtube as yt
from agents.scout.models import FetchedPost, Source

# ----- Helpers --------------------------------------------------------------


def _http_error(status: int = 404, message: str = "not found") -> HttpError:
    """Build a plausible-enough HttpError for tests."""
    resp = MagicMock()
    resp.status = status
    resp.reason = message
    return HttpError(resp, b'{"error": "test"}')


def _fake_client_with(
    *,
    channels_response: dict[str, Any] | None = None,
    channels_error: HttpError | None = None,
    search_response: dict[str, Any] | None = None,
    search_error: HttpError | None = None,
    comments_response: dict[str, Any] | None = None,
    comments_error: HttpError | None = None,
) -> MagicMock:
    """Build a fake YouTube Data API client whose chained calls return the
    provided fixtures."""
    client = MagicMock()

    channels_exec = MagicMock()
    if channels_error is not None:
        channels_exec.execute.side_effect = channels_error
    else:
        channels_exec.execute.return_value = channels_response or {"items": []}
    client.channels.return_value.list.return_value = channels_exec

    search_exec = MagicMock()
    if search_error is not None:
        search_exec.execute.side_effect = search_error
    else:
        search_exec.execute.return_value = search_response or {"items": []}
    client.search.return_value.list.return_value = search_exec

    comments_exec = MagicMock()
    if comments_error is not None:
        comments_exec.execute.side_effect = comments_error
    else:
        comments_exec.execute.return_value = comments_response or {"items": []}
    client.commentThreads.return_value.list.return_value = comments_exec

    return client


def _comment_item(
    *,
    comment_id: str = "Ugw_test",
    body: str = "labor cost is killing me, anyone else?",
    author: str = "an_operator",
    minutes_ago: float = 60,
) -> dict[str, Any]:
    posted = datetime.now(tz=UTC) - timedelta(minutes=minutes_ago)
    return {
        "id": comment_id,
        "snippet": {
            "topLevelComment": {
                "snippet": {
                    "textOriginal": body,
                    "authorDisplayName": author,
                    "publishedAt": posted.isoformat().replace("+00:00", "Z"),
                }
            }
        },
    }


# ----- resolve_channel_id ---------------------------------------------------


def test_resolve_channel_id_strips_leading_at_and_returns_id() -> None:
    client = _fake_client_with(channels_response={"items": [{"id": "UCabc123"}]})

    result = yt.resolve_channel_id(client, "@RestaurantUnstoppable")

    assert result == "UCabc123"
    # Confirm we passed the bare handle (no @) to the API
    list_call = client.channels.return_value.list
    list_call.assert_called_once()
    kwargs = list_call.call_args.kwargs
    assert kwargs["forHandle"] == "RestaurantUnstoppable"


def test_resolve_channel_id_raises_when_no_items() -> None:
    client = _fake_client_with(channels_response={"items": []})

    with pytest.raises(yt.YouTubeFetchError, match="did not resolve"):
        yt.resolve_channel_id(client, "@nonexistent")


def test_resolve_channel_id_raises_on_api_error() -> None:
    client = _fake_client_with(channels_error=_http_error(403, "forbidden"))

    with pytest.raises(yt.YouTubeFetchError, match="Failed to resolve"):
        yt.resolve_channel_id(client, "@something")


# ----- list_recent_video_ids ------------------------------------------------


def test_list_recent_video_ids_parses_response() -> None:
    now = datetime.now(tz=UTC)
    response = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "How to fix labor cost",
                    "publishedAt": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                },
            },
            {
                "id": {"videoId": "vid2"},
                "snippet": {
                    "title": "Owner shock absorber",
                    "publishedAt": (now - timedelta(days=10)).isoformat().replace("+00:00", "Z"),
                },
            },
        ]
    }
    client = _fake_client_with(search_response=response)

    result = yt.list_recent_video_ids(client, "UCabc", limit=5, max_age=timedelta(days=30))

    assert len(result) == 2
    assert [r[0] for r in result] == ["vid1", "vid2"]
    assert result[0][1] == "How to fix labor cost"


def test_list_recent_video_ids_skips_items_without_video_id() -> None:
    response = {
        "items": [
            {"id": {"channelId": "UCxxx"}, "snippet": {"title": "channel result"}},
            {
                "id": {"videoId": "vid_real"},
                "snippet": {
                    "title": "real video",
                    "publishedAt": "2026-04-15T12:00:00Z",
                },
            },
        ]
    }
    client = _fake_client_with(search_response=response)

    result = yt.list_recent_video_ids(client, "UCabc", limit=5, max_age=timedelta(days=365))

    assert [r[0] for r in result] == ["vid_real"]


def test_list_recent_video_ids_raises_on_api_error() -> None:
    client = _fake_client_with(search_error=_http_error(403, "quota exceeded"))

    with pytest.raises(yt.YouTubeFetchError, match="Failed to list videos"):
        yt.list_recent_video_ids(client, "UCabc", limit=5, max_age=timedelta(days=30))


# ----- _comment_to_fetched_post ---------------------------------------------


def test_comment_to_fetched_post_populates_all_fields() -> None:
    item = _comment_item(comment_id="Ugw_x", body="hello operators", author="me")

    post = yt._comment_to_fetched_post(
        item,
        channel_handle="@RestaurantUnstoppable",
        channel_id="UCxyz",
        video_id="vid42",
        video_title="Why labor is broken",
    )

    assert post is not None
    assert isinstance(post, FetchedPost)
    assert post.source == Source.YOUTUBE
    assert post.source_id == "Ugw_x"
    assert post.source_author == "me"
    assert post.title == "Why labor is broken"
    assert post.body == "hello operators"
    assert post.source_url == "https://www.youtube.com/watch?v=vid42&lc=Ugw_x"
    assert post.source_metadata == {
        "channel_handle": "@RestaurantUnstoppable",
        "channel_id": "UCxyz",
        "video_id": "vid42",
        "video_title": "Why labor is broken",
    }


def test_comment_to_fetched_post_returns_none_for_empty_body() -> None:
    item = _comment_item(body="")

    post = yt._comment_to_fetched_post(
        item,
        channel_handle="@x",
        channel_id="UCx",
        video_id="v",
        video_title="t",
    )

    assert post is None


def test_comment_to_fetched_post_returns_none_for_missing_id() -> None:
    item = _comment_item()
    item["id"] = ""

    post = yt._comment_to_fetched_post(
        item,
        channel_handle="@x",
        channel_id="UCx",
        video_id="v",
        video_title="t",
    )

    assert post is None


def test_comment_to_fetched_post_returns_none_for_unparseable_timestamp() -> None:
    item = _comment_item()
    item["snippet"]["topLevelComment"]["snippet"]["publishedAt"] = "not-a-date"

    post = yt._comment_to_fetched_post(
        item,
        channel_handle="@x",
        channel_id="UCx",
        video_id="v",
        video_title="t",
    )

    assert post is None


# ----- list_top_level_comments ----------------------------------------------


def test_list_top_level_comments_returns_items() -> None:
    response = {"items": [_comment_item(comment_id="a"), _comment_item(comment_id="b")]}
    client = _fake_client_with(comments_response=response)

    result = yt.list_top_level_comments(client, "vid42", limit=10)

    assert len(result) == 2
    assert {item["id"] for item in result} == {"a", "b"}


def test_list_top_level_comments_returns_empty_when_disabled() -> None:
    """Videos with comments disabled raise an HttpError. We log and return []
    rather than raising, so one bad video does not abort the channel."""
    client = _fake_client_with(comments_error=_http_error(403, "commentsDisabled"))

    result = yt.list_top_level_comments(client, "vid42", limit=10)

    assert result == []


# ----- fetch_channel (integration of helpers) -------------------------------


def test_fetch_channel_uses_configured_channel_id_when_present() -> None:
    """When channel.channel_id is already set, we skip the resolve call."""
    now = datetime.now(tz=UTC)
    search_response = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "vid title",
                    "publishedAt": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                },
            }
        ]
    }
    comments_response = {"items": [_comment_item(comment_id="c1")]}
    client = _fake_client_with(
        search_response=search_response,
        comments_response=comments_response,
    )
    channel = YouTubeChannel(
        handle="@x",
        channel_id="UCprecached",
        note="",
        videos_per_run=None,
        comments_per_video=None,
    )

    posts = yt.fetch_channel(
        client,
        channel,
        default_videos_per_channel=3,
        default_comments_per_video=10,
        max_age=timedelta(days=30),
    )

    assert len(posts) == 1
    assert posts[0].source_metadata["channel_id"] == "UCprecached"
    # channels.list (the resolver) should never have been called
    client.channels.return_value.list.assert_not_called()


def test_fetch_channel_resolves_handle_when_channel_id_missing() -> None:
    now = datetime.now(tz=UTC)
    client = _fake_client_with(
        channels_response={"items": [{"id": "UCresolved"}]},
        search_response={
            "items": [
                {
                    "id": {"videoId": "v"},
                    "snippet": {
                        "title": "t",
                        "publishedAt": (now - timedelta(hours=1))
                        .isoformat()
                        .replace("+00:00", "Z"),
                    },
                }
            ]
        },
        comments_response={"items": [_comment_item()]},
    )
    channel = YouTubeChannel(
        handle="@somechannel",
        channel_id=None,
        note="",
        videos_per_run=None,
        comments_per_video=None,
    )

    posts = yt.fetch_channel(
        client,
        channel,
        default_videos_per_channel=3,
        default_comments_per_video=10,
        max_age=timedelta(days=30),
    )

    assert len(posts) == 1
    assert posts[0].source_metadata["channel_id"] == "UCresolved"
    client.channels.return_value.list.assert_called_once()


def test_fetch_channel_returns_empty_when_no_recent_videos() -> None:
    client = _fake_client_with(
        channels_response={"items": [{"id": "UCx"}]},
        search_response={"items": []},
    )
    channel = YouTubeChannel(
        handle="@x",
        channel_id="UCx",
        note="",
        videos_per_run=None,
        comments_per_video=None,
    )

    posts = yt.fetch_channel(
        client,
        channel,
        default_videos_per_channel=3,
        default_comments_per_video=10,
        max_age=timedelta(days=30),
    )

    assert posts == []
    client.commentThreads.return_value.list.assert_not_called()


def test_fetch_channel_skips_comments_older_than_max_age() -> None:
    now = datetime.now(tz=UTC)
    client = _fake_client_with(
        search_response={
            "items": [
                {
                    "id": {"videoId": "v"},
                    "snippet": {
                        "title": "t",
                        "publishedAt": (now - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
                    },
                }
            ]
        },
        comments_response={
            "items": [
                _comment_item(comment_id="recent", minutes_ago=60),
                _comment_item(comment_id="old", minutes_ago=60 * 24 * 90),
            ]
        },
    )
    channel = YouTubeChannel(
        handle="@x",
        channel_id="UCx",
        note="",
        videos_per_run=None,
        comments_per_video=None,
    )

    posts = yt.fetch_channel(
        client,
        channel,
        default_videos_per_channel=3,
        default_comments_per_video=10,
        max_age=timedelta(days=30),
    )

    assert [p.source_id for p in posts] == ["recent"]
