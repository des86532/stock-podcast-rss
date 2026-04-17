from __future__ import annotations

import time
from typing import Iterable

import requests

TELEGRAM_LIMIT = 4096
SAFE_CHUNK_SIZE = 3800


def send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
) -> None:
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required unless --dry-run is used.")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is required unless --dry-run is used.")

    for chunk in split_message(text):
        _send_chunk(bot_token=bot_token, chat_id=chat_id, text=chunk)
        time.sleep(0.5)


def split_message(text: str) -> Iterable[str]:
    remaining = text.strip()
    while len(remaining) > SAFE_CHUNK_SIZE:
        split_at = remaining.rfind("\n", 0, SAFE_CHUNK_SIZE)
        if split_at < 1:
            split_at = SAFE_CHUNK_SIZE

        yield remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()

    if remaining:
        yield remaining


def _send_chunk(*, bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:TELEGRAM_LIMIT],
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, json=payload, timeout=30)
    if response.ok:
        return

    fallback_payload = {
        "chat_id": chat_id,
        "text": text[:TELEGRAM_LIMIT],
        "disable_web_page_preview": False,
    }
    fallback_response = requests.post(url, json=fallback_payload, timeout=30)
    fallback_response.raise_for_status()
