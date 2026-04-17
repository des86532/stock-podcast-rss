from __future__ import annotations

import argparse
import logging
import sys

from .config import load_settings
from .gemini import build_dry_run_summary, summarize_episode
from .models import Video
from .state import load_processed_video_ids, mark_video_processed
from .telegram import send_telegram_message
from .transcript import TranscriptUnavailableError, fetch_transcript_text
from .youtube_feed import fetch_latest_videos

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    args = parse_args(argv)
    settings = load_settings()

    try:
        videos = _select_videos(args, settings)
        if not videos:
            logger.info("No new videos to process.")
            return 0

        for video in videos:
            processed = _process_video(video, args, settings)
            if processed and not args.dry_run:
                mark_video_processed(settings.state_file, video.video_id)

        return 0
    except Exception:
        logger.exception("Run failed.")
        return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track mentioned stock symbols from a YouTube podcast transcript."
    )
    parser.add_argument(
        "--video-id",
        help="Process one YouTube video ID directly instead of reading the RSS feed.",
    )
    parser.add_argument(
        "--title",
        default="Manual video",
        help="Title used with --video-id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch transcript and print output without calling Gemini or Telegram.",
    )
    parser.add_argument(
        "--ignore-state",
        action="store_true",
        help="Process matching videos even if they already exist in the state file.",
    )
    return parser.parse_args(argv)


def _select_videos(args: argparse.Namespace, settings: object) -> list[Video]:
    if args.video_id:
        return [
            Video(
                video_id=args.video_id,
                title=args.title,
                url=f"https://www.youtube.com/watch?v={args.video_id}",
                published="",
            )
        ]

    videos = fetch_latest_videos(settings.youtube_channel_id)
    processed_ids = set() if args.ignore_state else load_processed_video_ids(settings.state_file)
    new_videos = [video for video in videos if video.video_id not in processed_ids]
    return new_videos[: settings.max_videos_per_run]


def _process_video(video: Video, args: argparse.Namespace, settings: object) -> bool:
    logger.info("Processing video: %s (%s)", video.title, video.video_id)

    try:
        transcript_text = fetch_transcript_text(video.video_id)
    except TranscriptUnavailableError as exc:
        logger.warning("Transcript unavailable for %s: %s", video.video_id, exc)
        return False

    if args.dry_run:
        summary = build_dry_run_summary(video, transcript_text)
        print(summary)
        return False

    summary = summarize_episode(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        video=video,
        transcript_text=transcript_text,
    )
    send_telegram_message(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        text=summary,
    )
    logger.info("Video processed and sent: %s", video.video_id)
    return True


if __name__ == "__main__":
    sys.exit(main())
