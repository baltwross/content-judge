"""Tests for the interactive wizard helpers."""

import pytest


def test_detect_video_youtube_url():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("https://www.youtube.com/watch?v=abc123def45") is True


def test_detect_video_youtu_be():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("https://youtu.be/abc123def45") is True


def test_detect_video_local_mp4():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("./clip.mp4") is True


def test_detect_video_local_mov():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("/path/to/video.mov") is True


def test_detect_text_url():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("https://example.com/article") is False


def test_detect_text_file():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("./article.txt") is False


def test_detect_text_literal():
    from content_judge.cli import _detect_is_video
    assert _detect_is_video("The quick brown fox jumps over the lazy dog") is False
