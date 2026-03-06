"""Tests for the interactive wizard helpers."""

import pytest
from unittest.mock import MagicMock

from content_judge.models import (
    AIDetectionResult,
    AILabel,
    AnalysisMetadata,
    AudienceSegment,
    ConfidenceLevel,
    DetectionSignal,
    DistributionResult,
    EmotionalQuadrant,
    FitStrength,
    JudgmentReport,
    Platform,
    SourceType,
    ViralityDimension,
    ViralityResult,
    VIRALITY_DIMENSION_WEIGHTS,
)


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


def _make_report() -> JudgmentReport:
    ai = AIDetectionResult(
        verdict=AILabel.LIKELY_HUMAN,
        confidence=0.8,
        confidence_level=ConfidenceLevel.HIGH,
        signals=[DetectionSignal(signal_name="test", value="test", confidence=0.8, weight=1.0)],
        explanation="Likely human content.",
    )
    virality = ViralityResult(
        dimensions=[
            ViralityDimension(dimension_id=did, name=did, score=5, weight=weight, reasoning="test")
            for did, weight in VIRALITY_DIMENSION_WEIGHTS.items()
        ],
        emotional_quadrant=EmotionalQuadrant.HIGH_AROUSAL_POSITIVE,
        primary_emotions=["awe"],
        key_strengths=["good"],
        key_weaknesses=["bad"],
        explanation="test",
    )
    strongest_fit = AudienceSegment(
        platform=Platform.TWITTER_X,
        community="Tech Twitter",
        estimated_fit=FitStrength.STRONG,
        reasoning="test",
    )
    distribution = DistributionResult(
        primary_topics=["Technology"],
        audience_segments=[
            strongest_fit,
            AudienceSegment(
                platform=Platform.REDDIT,
                community="r/technology",
                estimated_fit=FitStrength.MODERATE,
                reasoning="test",
            ),
        ],
        strongest_fit=strongest_fit,
        weakest_reach=["Instagram lifestyle"],
        content_format_notes="Short text format.",
        distribution_strategy="Post on Twitter first.",
        explanation="test",
    )
    return JudgmentReport(
        content_type=SourceType.STRING,
        ai_detection=ai,
        virality=virality,
        distribution=distribution,
        overall_explanation="Test synthesis.",
        analysis_metadata=AnalysisMetadata(
            model_used="gemini-2.5-flash",
            iterations=1,
            tools_succeeded=["ai_detection", "virality", "distribution"],
            tools_failed=[],
        ),
    )


def test_judge_json_output_still_writes_markdown_report(monkeypatch, tmp_path):
    from content_judge.cli import judge

    report_path = tmp_path / "report.md"
    emitted = []

    monkeypatch.setattr(
        "content_judge.config.get_settings",
        lambda: type("Settings", (), {"default_model": "gemini-2.5-flash"})(),
    )
    monkeypatch.setattr("content_judge.cli._load_content", lambda raw_input, is_video: MagicMock())

    fake_agent = MagicMock()
    fake_agent.run.return_value = _make_report()
    monkeypatch.setattr("content_judge.agent.CoordinatorAgent", lambda model: fake_agent)
    monkeypatch.setattr("typer.echo", emitted.append)

    judge("hello world", json_output=True, report_path=str(report_path))

    assert emitted == [fake_agent.run.return_value.to_json()]
    assert report_path.exists()
    assert "# Content Judge Report" in report_path.read_text(encoding="utf-8")
