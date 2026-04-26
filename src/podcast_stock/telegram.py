from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

TELEGRAM_LIMIT = 4096
SAFE_CHUNK_SIZE = 3500

logger = logging.getLogger(__name__)


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

    chunks = list(split_message(text))
    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        if total_chunks > 1:
            chunk = f"({index}/{total_chunks})\n\n{chunk}"
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

    logger.warning(
        "Telegram Markdown send failed with status %s: %s",
        response.status_code,
        _telegram_error_description(response),
    )

    fallback_payload = {
        "chat_id": chat_id,
        "text": text[:TELEGRAM_LIMIT],
        "disable_web_page_preview": False,
    }
    fallback_response = requests.post(url, json=fallback_payload, timeout=30)
    if not fallback_response.ok:
        logger.error(
            "Telegram plain-text send failed with status %s: %s",
            fallback_response.status_code,
            _telegram_error_description(fallback_response),
        )
    fallback_response.raise_for_status()


def _telegram_error_description(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    description = payload.get("description")
    if description:
        return str(description)

    return str(payload)
