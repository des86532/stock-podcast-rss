from __future__ import annotations

import time

import feedparser
import requests

from .models import Video

REQUEST_TIMEOUT_SECONDS = 20
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
YOUTUBE_FEED_HEADERS = {
    "Accept": "application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "User-Agent": (
        "Mozilla/5.0 (compatible; podcast-stock-rss/0.1; "
        "+https://github.com/actions)"
    ),
}
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeFeedError(RuntimeError):
    pass


class YouTubeApiError(RuntimeError):
    pass


def fetch_latest_videos_from_api(
    *,
    channel_id: str,
    api_key: str,
    max_results: int,
) -> list[Video]:
    if not channel_id:
        raise ValueError("YOUTUBE_CHANNEL_ID is required.")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is required.")

    uploads_playlist_id = _fetch_uploads_playlist_id(channel_id=channel_id, api_key=api_key)
    return _fetch_playlist_videos(
        playlist_id=uploads_playlist_id,
        api_key=api_key,
        max_results=max_results,
    )


def fetch_latest_videos(channel_id: str) -> list[Video]:
    if not channel_id:
        raise ValueError("YOUTUBE_CHANNEL_ID is required.")

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed_content = _fetch_feed_content(feed_url)
    feed = feedparser.parse(feed_content)

    if getattr(feed, "bozo", False):
        preview = _preview_response(feed_content)
        raise YouTubeFeedError(
            "Failed to parse YouTube RSS feed: "
            f"{feed.bozo_exception}; response preview: {preview}"
        )

    videos: list[Video] = []
    for entry in feed.entries:
        video_id = _extract_video_id(entry)
        if not video_id:
            continue

        videos.append(
            Video(
                video_id=video_id,
                title=getattr(entry, "title", "").strip() or video_id,
                url=getattr(entry, "link", "").strip()
                or f"https://www.youtube.com/watch?v={video_id}",
                published=getattr(entry, "published", "").strip(),
            )
        )

    return videos


def _fetch_uploads_playlist_id(*, channel_id: str, api_key: str) -> str:
    data = _get_youtube_api_json(
        "channels",
        params={
            "part": "contentDetails",
            "id": channel_id,
            "key": api_key,
        },
    )

    items = data.get("items") or []
    if not items:
        raise YouTubeApiError(f"YouTube channel was not found: {channel_id}")

    uploads_playlist_id = (
        items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )
    if not uploads_playlist_id:
        raise YouTubeApiError(f"YouTube channel has no uploads playlist: {channel_id}")

    return str(uploads_playlist_id)


def _fetch_playlist_videos(
    *,
    playlist_id: str,
    api_key: str,
    max_results: int,
) -> list[Video]:
    data = _get_youtube_api_json(
        "playlistItems",
        params={
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": str(max(1, min(max_results, 50))),
            "key": api_key,
        },
    )

    videos: list[Video] = []
    for item in data.get("items") or []:
        snippet = item.get("snippet") or {}
        content_details = item.get("contentDetails") or {}
        resource_id = snippet.get("resourceId") or {}
        video_id = content_details.get("videoId") or resource_id.get("videoId") or ""
        if not video_id:
            continue

        videos.append(
            Video(
                video_id=str(video_id),
                title=str(snippet.get("title") or video_id).strip(),
                url=f"https://www.youtube.com/watch?v={video_id}",
                published=str(content_details.get("videoPublishedAt") or snippet.get("publishedAt") or "").strip(),
            )
        )

    return videos


def _get_youtube_api_json(endpoint: str, *, params: dict[str, str]) -> dict[str, object]:
    url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise YouTubeApiError(f"YouTube Data API request failed: {exc}") from exc

    if not response.ok:
        message = _youtube_api_error_message(response)
        raise YouTubeApiError(
            f"YouTube Data API request failed: status={response.status_code}; {message}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise YouTubeApiError(
            "YouTube Data API returned invalid JSON: "
            f"{_preview_response(response.content)}"
        ) from exc

    if not isinstance(data, dict):
        raise YouTubeApiError("YouTube Data API returned an unexpected JSON payload.")

    return data


def _youtube_api_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"response preview={_preview_response(response.content)}"

    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return f"response preview={_preview_response(response.content)}"

    reason = ""
    errors = error.get("errors") or []
    if errors and isinstance(errors[0], dict):
        reason = str(errors[0].get("reason") or "")

    message = str(error.get("message") or "unknown error")
    return f"reason={reason or 'unknown'}; message={message}"


def _fetch_feed_content(feed_url: str) -> bytes:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                feed_url,
                headers=YOUTUBE_FEED_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            content = response.content.strip()
            if not content:
                raise YouTubeFeedError("YouTube RSS feed response was empty.")

            content_type = response.headers.get("content-type", "")
            if not content.startswith(b"<"):
                raise YouTubeFeedError(
                    "YouTube RSS feed response was not XML-like; "
                    f"status={response.status_code}; content-type={content_type}; "
                    f"preview={_preview_response(content)}"
                )

            return content
        except (requests.RequestException, YouTubeFeedError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    raise YouTubeFeedError(f"Failed to fetch YouTube RSS feed after {MAX_ATTEMPTS} attempts: {last_error}")


def _preview_response(content: bytes, limit: int = 300) -> str:
    text = content[:limit].decode("utf-8", errors="replace")
    return " ".join(text.split())


def _extract_video_id(entry: object) -> str:
    yt_video_id = getattr(entry, "yt_videoid", "")
    if yt_video_id:
        return str(yt_video_id)

    entry_id = getattr(entry, "id", "")
    if isinstance(entry_id, str) and "video:" in entry_id:
        return entry_id.rsplit("video:", 1)[-1]

    return ""
