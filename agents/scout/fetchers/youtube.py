"""YouTube fetcher.

Pulls top-level comments from the newest videos of configured channels via the
YouTube Data API v3. Returns FetchedPost objects, one per comment. Knows nothing
about classification or storage.

Design notes:
- An API key alone is enough for reading public comments. No OAuth flow.
- Channel handles (@RestaurantUnstoppable) must be resolved to channel IDs
  (UC...) before we can list videos. The fetcher caches the resolved IDs in
  memory for the duration of a run. Future: write resolved IDs back to
  config.yaml so we skip resolution on subsequent runs.
- Top-level comments only in v1. Replies skipped because each comment thread
  call costs the same quota whether or not we ask for replies, but replies
  add noise without adding much operator-voice signal.
- Removed/deleted comments raise an exception from the API rather than
  appearing as flagged rows; we catch and skip.
- Comments older than max_age_days are skipped, mirroring Reddit behavior.

Quota cost (free tier 10,000 units/day):
- Resolving one channel handle: 100 units (channels.list call)
- Listing recent videos for a channel: 100 units (search.list)
- Listing comments for one video: 1 unit per page (commentThreads.list)
- Total per channel per run: ~201 units. 11 channels = ~2,200 units.
  Well under daily limit, with room for retries.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from agents.scout.config import YouTubeChannel, YouTubeConfig
from agents.scout.fetchers.base import FetchError
from agents.scout.models import FetchedPost, Source

log = logging.getLogger("scout")


class YouTubeFetchError(FetchError):
    """Raised when a channel cannot be read at all (auth, quota exceeded,
    handle does not resolve). Per-comment problems are logged and skipped."""


def build_client(cfg: YouTubeConfig) -> Resource:
    """Build a YouTube Data API v3 client. No network call yet."""
    return build("youtube", "v3", developerKey=cfg.api_key, cache_discovery=False)


def resolve_channel_id(client: Resource, handle: str) -> str:
    """Resolve a channel handle (e.g. @RestaurantUnstoppable) to a channel ID
    (UC...). The API supports forHandle directly; strip the leading @ if present
    since the API accepts both.

    Costs 1 quota unit (channels.list with id only)."""
    handle_clean = handle.lstrip("@")
    try:
        response = client.channels().list(part="id", forHandle=handle_clean).execute()
    except HttpError as exc:
        raise YouTubeFetchError(f"Failed to resolve handle {handle}: {exc}") from exc

    items = response.get("items", [])
    if not items:
        raise YouTubeFetchError(f"Handle {handle} did not resolve to any channel")

    channel_id = str(items[0]["id"])
    return channel_id


def list_recent_video_ids(
    client: Resource,
    channel_id: str,
    *,
    limit: int,
    max_age: timedelta,
) -> list[tuple[str, str, datetime]]:
    """List the newest video IDs for a channel via search.list.

    Returns tuples of (video_id, title, published_at), filtered to videos
    published within max_age. Costs 100 quota units."""
    cutoff = datetime.now(tz=UTC) - max_age
    published_after = cutoff.isoformat().replace("+00:00", "Z")

    try:
        response = (
            client.search()
            .list(
                part="snippet",
                channelId=channel_id,
                order="date",
                type="video",
                maxResults=limit,
                publishedAfter=published_after,
            )
            .execute()
        )
    except HttpError as exc:
        raise YouTubeFetchError(f"Failed to list videos for {channel_id}: {exc}") from exc

    out: list[tuple[str, str, datetime]] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        video_id_raw = item.get("id", {}).get("videoId")
        if not video_id_raw:
            continue
        title = str(snippet.get("title", ""))
        published_str = str(snippet.get("publishedAt", ""))
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append((str(video_id_raw), title, published_at))

    return out


def list_top_level_comments(
    client: Resource,
    video_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """List top-level comments for one video.

    Costs 1 quota unit per page. We pull at most one page (limit cap is
    typically 100 from the API). Returns the raw snippet dicts so the caller
    can convert to FetchedPost."""
    try:
        response = (
            client.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                maxResults=min(limit, 100),
                order="relevance",
                textFormat="plainText",
            )
            .execute()
        )
    except HttpError as exc:
        # Comments can be disabled on a video. Log and return empty.
        log.warning(
            "comments_unavailable",
            extra={"video_id": video_id, "error": str(exc)},
        )
        return []

    return list(response.get("items", []))


def _comment_to_fetched_post(
    item: dict[str, Any],
    *,
    channel_handle: str,
    channel_id: str,
    video_id: str,
    video_title: str,
) -> FetchedPost | None:
    """Convert a YouTube commentThread item into a FetchedPost. Returns None
    if the comment is unusable (missing fields, unparseable timestamp)."""
    snippet = item.get("snippet", {})
    top_level = snippet.get("topLevelComment", {}).get("snippet", {})

    body = str(top_level.get("textOriginal") or top_level.get("textDisplay") or "").strip()
    if not body:
        return None

    comment_id = str(item.get("id", "")).strip()
    if not comment_id:
        return None

    published_str = str(top_level.get("publishedAt", ""))
    try:
        posted_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    author = top_level.get("authorDisplayName")
    author_str = str(author).strip() if author else None

    return FetchedPost(
        source=Source.YOUTUBE,
        source_url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
        source_id=comment_id,
        source_author=author_str,
        posted_at=posted_at,
        title=video_title,  # The comment's parent video title doubles as the post title for context
        body=body,
        source_metadata={
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "video_id": video_id,
            "video_title": video_title,
        },
    )


def fetch_channel(
    client: Resource,
    channel: YouTubeChannel,
    *,
    default_videos_per_channel: int,
    default_comments_per_video: int,
    max_age: timedelta,
) -> list[FetchedPost]:
    """Fetch top-level comments from a channel's recent videos.

    Per-channel overrides win over defaults. Failures on a single video do
    not abort the channel; failures resolving the channel itself do."""
    videos_limit = (
        channel.videos_per_run if channel.videos_per_run is not None else default_videos_per_channel
    )
    comments_limit = (
        channel.comments_per_video
        if channel.comments_per_video is not None
        else default_comments_per_video
    )

    log.info(
        "channel_fetch_started",
        extra={
            "channel_handle": channel.handle,
            "videos_limit": videos_limit,
            "comments_limit": comments_limit,
        },
    )

    channel_id = channel.channel_id or resolve_channel_id(client, channel.handle)

    videos = list_recent_video_ids(
        client,
        channel_id,
        limit=videos_limit,
        max_age=max_age,
    )

    if not videos:
        log.info(
            "channel_no_recent_videos",
            extra={"channel_handle": channel.handle, "channel_id": channel_id},
        )
        return []

    cutoff = datetime.now(tz=UTC) - max_age
    fetched: list[FetchedPost] = []
    skipped_old = 0
    skipped_unparseable = 0

    for video_id, video_title, _ in videos:
        items = list_top_level_comments(client, video_id, limit=comments_limit)
        for item in items:
            post = _comment_to_fetched_post(
                item,
                channel_handle=channel.handle,
                channel_id=channel_id,
                video_id=video_id,
                video_title=video_title,
            )
            if post is None:
                skipped_unparseable += 1
                continue
            if post.posted_at < cutoff:
                skipped_old += 1
                continue
            fetched.append(post)

    log.info(
        "channel_fetch_completed",
        extra={
            "channel_handle": channel.handle,
            "channel_id": channel_id,
            "videos_pulled": len(videos),
            "comments_kept": len(fetched),
            "skipped_old": skipped_old,
            "skipped_unparseable": skipped_unparseable,
        },
    )

    return fetched


def fetch_all(
    cfg: YouTubeConfig,
    *,
    handle_override: str | None = None,
) -> list[FetchedPost]:
    """Fetch comments across all configured channels. CLI override wins.

    A failure on one channel does not abort the others."""
    if not cfg.enabled:
        log.info("youtube_disabled_in_config")
        return []

    client = build_client(cfg)
    if handle_override:
        channels = tuple(c for c in cfg.channels if c.handle == handle_override)
        if not channels:
            # Treat an unknown override as a one-off channel with default settings.
            channels = (
                YouTubeChannel(
                    handle=handle_override,
                    channel_id=None,
                    note="cli override",
                    videos_per_run=None,
                    comments_per_video=None,
                ),
            )
    else:
        channels = cfg.channels

    max_age = timedelta(days=cfg.max_age_days)
    all_posts: list[FetchedPost] = []
    failures: list[str] = []

    for ch in channels:
        try:
            posts = fetch_channel(
                client,
                ch,
                default_videos_per_channel=cfg.default_videos_per_channel,
                default_comments_per_video=cfg.default_comments_per_video,
                max_age=max_age,
            )
            all_posts.extend(posts)
        except YouTubeFetchError as exc:
            log.error(
                "channel_fetch_failed",
                extra={"channel_handle": ch.handle, "error": str(exc)},
            )
            failures.append(ch.handle)

    if failures:
        log.warning(
            "youtube_partial_failure",
            extra={
                "failed_channels": failures,
                "ok_channels": [c.handle for c in channels if c.handle not in failures],
            },
        )

    return all_posts
