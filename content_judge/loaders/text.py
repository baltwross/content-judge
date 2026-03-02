"""Text content loader: string, file, or URL → text."""

import re
from pathlib import Path

import httpx

from content_judge.models import SourceType


def load_text(raw_input: str) -> tuple[str, SourceType]:
    """
    Resolve text from a string, file path, or URL.
    Returns (text_content, source_type).
    Raises ContentLoadError on failure.
    """
    from content_judge.loaders import ContentLoadError

    # File path check
    path = Path(raw_input)
    if path.exists() and path.is_file():
        if path.stat().st_size > 100 * 1024:
            raise ContentLoadError(
                f"File too large: {path.stat().st_size} bytes (max 100KB)"
            )
        try:
            return path.read_text(encoding="utf-8"), SourceType.FILE
        except UnicodeDecodeError:
            raise ContentLoadError(f"File is not valid UTF-8 text: {path}")

    # URL check
    if raw_input.startswith(("http://", "https://")):
        try:
            response = httpx.get(raw_input, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
            text = re.sub(r"<[^>]+>", " ", response.text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:50_000], SourceType.URL
        except httpx.HTTPError as e:
            raise ContentLoadError(f"Failed to fetch URL: {e}")

    # Raw string
    if not raw_input.strip():
        raise ContentLoadError("Input text is empty")
    return raw_input, SourceType.STRING
