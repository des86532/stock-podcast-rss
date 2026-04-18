from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import Video


def save_video_metadata(output_dir: Path, video: Video) -> Path:
    video_dir = _video_output_dir(output_dir, video)
    video_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "video_id": video.video_id,
        "title": video.title,
        "url": video.url,
        "published": video.published,
        "processed_at": datetime.now(UTC).isoformat(),
    }
    path = video_dir / "metadata.json"
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def save_transcript(output_dir: Path, video: Video, transcript_text: str) -> Path:
    return _write_video_text(output_dir, video, "transcript.txt", transcript_text)


def save_dry_run_summary(output_dir: Path, video: Video, summary: str) -> Path:
    return _write_video_text(output_dir, video, "dry_run_summary.md", summary)


def save_summary(output_dir: Path, video: Video, summary: str) -> Path:
    return _write_video_text(output_dir, video, "summary.md", summary)


def _write_video_text(output_dir: Path, video: Video, filename: str, text: str) -> Path:
    video_dir = _video_output_dir(output_dir, video)
    video_dir.mkdir(parents=True, exist_ok=True)

    path = video_dir / filename
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _video_output_dir(output_dir: Path, video: Video) -> Path:
    date_prefix = _published_date(video.published) or datetime.now(UTC).date().isoformat()
    return output_dir / f"{date_prefix}_{video.video_id}"


def _published_date(published: str) -> str:
    if not published:
        return ""

    return published.split("T", 1)[0].strip()
