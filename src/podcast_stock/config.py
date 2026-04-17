from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    youtube_channel_id: str
    gemini_model: str = "gemini-2.5-flash"
    state_file: Path = Path("processed_videos.json")
    max_videos_per_run: int = 1


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        youtube_channel_id=os.getenv("YOUTUBE_CHANNEL_ID", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        state_file=Path(os.getenv("STATE_FILE", "processed_videos.json")),
        max_videos_per_run=_parse_positive_int(os.getenv("MAX_VIDEOS_PER_RUN"), 1),
    )


def _parse_positive_int(raw_value: str | None, default: int) -> int:
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return value if value > 0 else default
