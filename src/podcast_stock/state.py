from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_processed_video_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(item) for item in data}

    if isinstance(data, dict):
        videos = data.get("processed_videos", [])
        return {str(item) for item in videos}

    raise ValueError(f"Unsupported state file format: {path}")


def mark_video_processed(path: Path, video_id: str) -> None:
    processed = sorted(load_processed_video_ids(path) | {video_id})
    payload: list[str] | dict[str, Any] = processed
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
