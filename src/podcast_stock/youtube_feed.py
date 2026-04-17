from __future__ import annotations

import feedparser

from .models import Video


def fetch_latest_videos(channel_id: str) -> list[Video]:
    if not channel_id:
        raise ValueError("YOUTUBE_CHANNEL_ID is required.")

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)

    if getattr(feed, "bozo", False):
        raise RuntimeError(f"Failed to parse YouTube RSS feed: {feed.bozo_exception}")

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


def _extract_video_id(entry: object) -> str:
    yt_video_id = getattr(entry, "yt_videoid", "")
    if yt_video_id:
        return str(yt_video_id)

    entry_id = getattr(entry, "id", "")
    if isinstance(entry_id, str) and "video:" in entry_id:
        return entry_id.rsplit("video:", 1)[-1]

    return ""
