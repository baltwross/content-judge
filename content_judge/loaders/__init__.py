"""Content loaders for text and video input."""

from content_judge.loaders.text import load_text
from content_judge.loaders.video import (
    is_youtube_url,
    parse_youtube_url,
    resolve_youtube_stream_url,
    validate_video_url,
)


class ContentLoadError(Exception):
    """Raised when content loading fails."""

    pass


__all__ = [
    "ContentLoadError",
    "load_text",
    "is_youtube_url",
    "parse_youtube_url",
    "resolve_youtube_stream_url",
    "validate_video_url",
]
