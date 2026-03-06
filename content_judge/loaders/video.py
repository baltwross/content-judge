"""Video content loader: YouTube URL parsing, validation, stream URL resolution."""

import re
from pathlib import Path


SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}


def parse_youtube_url(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_youtube_url(url: str) -> bool:
    """Check if URL matches YouTube patterns."""
    return parse_youtube_url(url) is not None


def validate_video_url(url: str) -> None:
    """
    Validate that a video URL is a supported source.
    Only YouTube URLs and local video files are supported.
    Raises ContentLoadError for non-YouTube video URLs.
    """
    from content_judge.loaders import ContentLoadError

    if url.startswith(("http://", "https://")) and not is_youtube_url(url):
        raise ContentLoadError(
            "Only YouTube URLs and local video files are supported. "
            "For other platforms, download the video and pass the local file path."
        )

    # Local file validation
    if not url.startswith(("http://", "https://")):
        path = Path(url)
        if not path.exists():
            raise ContentLoadError(f"Video file not found: {url}")
        if path.suffix.lower() not in SUPPORTED_VIDEO_FORMATS:
            raise ContentLoadError(
                f"Unsupported video format: {path.suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_VIDEO_FORMATS))}"
            )


def resolve_youtube_stream_url(youtube_url: str) -> str | None:
    """
    Use yt-dlp to resolve YouTube's temporary direct stream URL.
    No video is downloaded — just URL resolution (~1-2 seconds).
    Returns the direct stream URL or None on failure.

    Tries 'bestvideo[ext=mp4][height<=720]' first for highest resolution
    (video-only is fine since Hive only analyzes visual frames). Falls back
    to 'best[ext=mp4][height<=720]' (combined) if video-only isn't available.
    Combined MP4 formats often max at 360p, while video-only reaches 720p+.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        import yt_dlp

        # Prefer video-only for higher resolution; fall back to combined
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[ext=mp4][height<=720]/best[ext=mp4][height<=720]",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            url = info.get("url")

            if not url:
                # Fallback: check requested_formats for DASH streams
                for fmt in info.get("requested_formats", []):
                    if fmt.get("vcodec", "none") != "none":
                        url = fmt.get("url")
                        break

            if url:
                logger.debug("Resolved stream URL (height=%s, format=%s)",
                             info.get("height"), info.get("format"))
            else:
                logger.debug("No stream URL found in info keys: %s", list(info.keys()))

            return url
    except Exception as e:
        logging.getLogger(__name__).debug("Stream URL resolution failed: %s", e)
        return None
