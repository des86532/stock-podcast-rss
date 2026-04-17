from __future__ import annotations

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptAvailable,
    NoTranscriptFound,
)

PREFERRED_LANGUAGES = ("zh-Hant", "zh-TW", "zh-Hans", "zh-CN", "zh")


class TranscriptUnavailableError(RuntimeError):
    pass


def fetch_transcript_text(video_id: str) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptUnavailableError(str(exc)) from exc

    transcript = _find_best_transcript(transcript_list)
    if transcript is None:
        raise TranscriptUnavailableError("No Chinese transcript is available yet.")

    try:
        rows = transcript.fetch()
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptUnavailableError(str(exc)) from exc

    text_parts = [row.get("text", "").replace("\n", " ").strip() for row in rows]
    text = " ".join(part for part in text_parts if part)
    if not text:
        raise TranscriptUnavailableError("Transcript is empty.")

    return text


def _find_best_transcript(transcript_list: object) -> object | None:
    for language in PREFERRED_LANGUAGES:
        try:
            return transcript_list.find_transcript([language])
        except (NoTranscriptFound, NoTranscriptAvailable):
            pass

    for transcript in transcript_list:
        language_code = getattr(transcript, "language_code", "")
        if str(language_code).lower().startswith("zh"):
            return transcript

    return None
