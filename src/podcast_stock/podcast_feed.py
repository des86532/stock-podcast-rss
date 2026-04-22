from __future__ import annotations

import hashlib
import time

import feedparser
import requests

from .models import Video

REQUEST_TIMEOUT_SECONDS = 20
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
PODCAST_FEED_HEADERS = {
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "User-Agent": "podcast-stock-rss/0.1",
}


class PodcastFeedError(RuntimeError):
    pass


def fetch_latest_podcast_episodes(feed_url: str, *, max_results: int) -> list[Video]:
    if not feed_url:
        raise ValueError("PODCAST_RSS_URL is required.")

    feed_content = _fetch_feed_content(feed_url)
    feed = feedparser.parse(feed_content)

    if getattr(feed, "bozo", False):
        raise PodcastFeedError(
            "Failed to parse podcast RSS feed: "
            f"{feed.bozo_exception}; response preview: {_preview_response(feed_content)}"
        )

    episodes: list[Video] = []
    for entry in feed.entries:
        audio_url = _extract_audio_url(entry)
        if not audio_url:
            continue

        episode_id = _extract_episode_id(entry, audio_url)
        episodes.append(
            Video(
                video_id=episode_id,
                title=getattr(entry, "title", "").strip() or episode_id,
                url=getattr(entry, "link", "").strip() or audio_url,
                published=getattr(entry, "published", "").strip()
                or getattr(entry, "updated", "").strip(),
                audio_url=audio_url,
            )
        )

        if len(episodes) >= max(1, max_results):
            break

    return episodes


def _fetch_feed_content(feed_url: str) -> bytes:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                feed_url,
                headers=PODCAST_FEED_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            content = response.content.strip()
            if not content:
                raise PodcastFeedError("Podcast RSS feed response was empty.")
            if not content.startswith(b"<"):
                raise PodcastFeedError(
                    "Podcast RSS feed response was not XML-like; "
                    f"status={response.status_code}; "
                    f"content-type={response.headers.get('content-type', '')}; "
                    f"preview={_preview_response(content)}"
                )

            return content
        except (requests.RequestException, PodcastFeedError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    raise PodcastFeedError(
        f"Failed to fetch podcast RSS feed after {MAX_ATTEMPTS} attempts: {last_error}"
    )


def _extract_audio_url(entry: object) -> str:
    for enclosure in getattr(entry, "enclosures", []) or []:
        href = getattr(enclosure, "href", "") or enclosure.get("href", "")
        media_type = getattr(enclosure, "type", "") or enclosure.get("type", "")
        if href and (not media_type or str(media_type).startswith("audio/")):
            return str(href).strip()

    return ""


def _extract_episode_id(entry: object, audio_url: str) -> str:
    raw_id = (
        getattr(entry, "id", "")
        or getattr(entry, "guid", "")
        or getattr(entry, "link", "")
        or audio_url
    )
    raw_id = str(raw_id).strip()
    if raw_id and "/" not in raw_id and "\\" not in raw_id:
        return raw_id

    return hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]


def _preview_response(content: bytes, limit: int = 300) -> str:
    text = content[:limit].decode("utf-8", errors="replace")
    return " ".join(text.split())
