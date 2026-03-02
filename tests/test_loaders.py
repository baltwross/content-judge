"""Tests for content loaders."""

import pytest

from content_judge.loaders import (
    ContentLoadError,
    load_text,
    is_youtube_url,
    parse_youtube_url,
    validate_video_url,
)
from content_judge.models import SourceType


class TestLoadText:
    def test_raw_string(self):
        text, source = load_text("hello world")
        assert text == "hello world"
        assert source == SourceType.STRING

    def test_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("file content", encoding="utf-8")
        text, source = load_text(str(f))
        assert text == "file content"
        assert source == SourceType.FILE

    def test_empty_string_raises(self):
        with pytest.raises(ContentLoadError, match="empty"):
            load_text("   ")

    def test_file_too_large(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * (101 * 1024), encoding="utf-8")
        with pytest.raises(ContentLoadError, match="too large"):
            load_text(str(f))


class TestYouTubeUrlParsing:
    def test_standard_url(self):
        assert parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert parse_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert parse_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_non_youtube(self):
        assert parse_youtube_url("https://vimeo.com/123456") is None

    def test_is_youtube_url(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=abc12345678") is True
        assert is_youtube_url("https://vimeo.com/123") is False


class TestValidateVideoUrl:
    def test_vimeo_rejected(self):
        with pytest.raises(ContentLoadError, match="Only YouTube URLs"):
            validate_video_url("https://vimeo.com/123456")

    def test_dailymotion_rejected(self):
        with pytest.raises(ContentLoadError, match="Only YouTube URLs"):
            validate_video_url("https://www.dailymotion.com/video/x123")

    def test_youtube_accepted(self):
        # Should not raise
        validate_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_nonexistent_file_rejected(self):
        with pytest.raises(ContentLoadError, match="not found"):
            validate_video_url("/nonexistent/video.mp4")
