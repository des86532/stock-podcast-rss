from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import yt_dlp
from faster_whisper import WhisperModel
from tqdm import tqdm

logger = logging.getLogger(__name__)


class WhisperTranscriptError(RuntimeError):
    pass


def transcribe_youtube_video(
    video_id: str,
    *,
    model_name: str,
    language: str,
) -> str:
    with tempfile.TemporaryDirectory(prefix="podcast-stock-") as temp_dir:
        audio_path = _download_audio(video_id, Path(temp_dir))
        logger.info("Transcribing audio with faster-whisper model: %s", model_name)

        try:
            model = WhisperModel(model_name, device="auto", compute_type="auto")
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
            )
            text_parts = _collect_segments_with_progress(segments, info.duration)
        except Exception as exc:
            raise WhisperTranscriptError(f"Whisper transcription failed: {exc}") from exc

    text = " ".join(text_parts)
    if not text:
        raise WhisperTranscriptError("Whisper transcription is empty.")

    return text


def _download_audio(video_id: str, output_dir: Path) -> Path:
    output_template = str(output_dir / "%(id)s.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"
    options = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "progress_hooks": [_create_download_progress_hook()],
    }

    logger.info("Downloading audio for Whisper fallback: %s", video_id)
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            prepared_filename = downloader.prepare_filename(info)
    except Exception as exc:
        raise WhisperTranscriptError(f"Failed to download YouTube audio: {exc}") from exc

    audio_path = Path(prepared_filename)
    if not audio_path.exists():
        downloaded_id = str(info.get("id") or video_id)
        candidates = sorted(output_dir.glob(f"{downloaded_id}.*"))
        if candidates:
            audio_path = candidates[0]

    if not audio_path.exists():
        raise WhisperTranscriptError("Downloaded audio file was not found.")

    return audio_path


def _create_download_progress_hook() -> object:
    progress_bar: tqdm | None = None

    def hook(status: dict[str, object]) -> None:
        nonlocal progress_bar

        state = status.get("status")
        if state == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = int(status.get("downloaded_bytes") or 0)

            if progress_bar is None:
                progress_bar = tqdm(
                    total=int(total) if total else None,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Downloading audio",
                )
            elif total and progress_bar.total != int(total):
                progress_bar.total = int(total)

            delta = downloaded - progress_bar.n
            if delta > 0:
                progress_bar.update(delta)

        if state == "finished" and progress_bar is not None:
            if progress_bar.total and progress_bar.n < progress_bar.total:
                progress_bar.update(progress_bar.total - progress_bar.n)
            progress_bar.close()
            progress_bar = None

    return hook


def _collect_segments_with_progress(segments: object, duration: float) -> list[str]:
    text_parts: list[str] = []
    total = int(duration) if duration and duration > 0 else None

    with tqdm(total=total, unit="sec", desc="Transcribing audio") as progress_bar:
        last_end = 0.0
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_parts.append(text)

            segment_end = float(getattr(segment, "end", last_end) or last_end)
            if segment_end > last_end:
                progress_bar.update(int(segment_end) - int(last_end))
                last_end = segment_end

        if progress_bar.total and progress_bar.n < progress_bar.total:
            progress_bar.update(progress_bar.total - progress_bar.n)

    return text_parts
