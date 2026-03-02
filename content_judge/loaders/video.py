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
    """
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return info.get("url")
    except Exception:
        return None
