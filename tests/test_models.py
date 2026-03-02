"""Tests for Pydantic data models."""

import json
import pytest

from content_judge.models import (
    AIDetectionResult,
    AILabel,
    AudienceSegment,
    AnalysisMetadata,
    C2PASignal,
    ConfidenceLevel,
    ContentInput,
    DetectionSignal,
    DistributionResult,
    EmotionalQuadrant,
    FitStrength,
    JudgmentReport,
    Platform,
    SourceType,
    ToolError,
    ToolResults,
    ViralityDimension,
    ViralityResult,
    VIRALITY_DIMENSION_WEIGHTS,
)


class TestContentInput:
    def test_text_input_flags(self):
        c = ContentInput(source_type=SourceType.STRING, text="Hello world")
        assert c.has_text is True
        assert c.has_video is False
        assert c.text_length == 11
        assert c.is_short_text is True

    def test_video_input_flags(self):
        c = ContentInput(
            source_type=SourceType.VIDEO,
            video_source="https://www.youtube.com/watch?v=abc",
        )
        assert c.has_text is False
        assert c.has_video is True

    def test_long_text_not_short(self):
        c = ContentInput(source_type=SourceType.STRING, text="x" * 300)
        assert c.is_short_text is False

    def test_empty_text_has_text_false(self):
        c = ContentInput(source_type=SourceType.STRING, text="")
        assert c.has_text is False


class TestViralityResult:
    def _make_dimensions(self, score=5):
        dims = []
        for dim_id, weight in VIRALITY_DIMENSION_WEIGHTS.items():
            dims.append(ViralityDimension(
                dimension_id=dim_id,
                name=dim_id.replace("_", " ").title(),
                score=score,
                weight=weight,
                reasoning="test",
            ))
        return dims

    def test_computed_overall_score(self):
        result = ViralityResult(
            dimensions=self._make_dimensions(score=5),
            emotional_quadrant=EmotionalQuadrant.LOW_AROUSAL_POSITIVE,
            primary_emotions=["contentment"],
            key_strengths=["test"],
            key_weaknesses=["test"],
            explanation="test",
        )
        assert result.overall_score == 5.0

    def test_virality_level_low(self):
        result = ViralityResult(
            dimensions=self._make_dimensions(score=2),
            emotional_quadrant=EmotionalQuadrant.LOW_AROUSAL_NEGATIVE,
            primary_emotions=["boredom"],
            key_strengths=["none"],
            key_weaknesses=["everything"],
            explanation="test",
        )
        assert result.virality_level == "low"

    def test_virality_level_very_high(self):
        result = ViralityResult(
            dimensions=self._make_dimensions(score=9),
            emotional_quadrant=EmotionalQuadrant.HIGH_AROUSAL_POSITIVE,
            primary_emotions=["awe"],
            key_strengths=["amazing"],
            key_weaknesses=["none"],
            explanation="test",
        )
        assert result.virality_level == "very_high"


class TestJudgmentReport:
    def _make_report(self, with_error=False):
        ai = AIDetectionResult(
            verdict=AILabel.LIKELY_HUMAN,
            confidence=0.8,
            confidence_level=ConfidenceLevel.HIGH,
            signals=[DetectionSignal(signal_name="test", value="test", confidence=0.8, weight=1.0)],
            explanation="Likely human content.",
        )
        virality = ViralityResult(
            dimensions=[
                ViralityDimension(
                    dimension_id=did, name=did, score=5, weight=w, reasoning="test"
                )
                for did, w in VIRALITY_DIMENSION_WEIGHTS.items()
            ],
            emotional_quadrant=EmotionalQuadrant.HIGH_AROUSAL_POSITIVE,
            primary_emotions=["awe"],
            key_strengths=["good"],
            key_weaknesses=["bad"],
            explanation="test",
        )
        dist = DistributionResult(
            primary_topics=["Technology"],
            audience_segments=[
                AudienceSegment(
                    platform=Platform.TWITTER_X,
                    community="Tech Twitter",
                    estimated_fit=FitStrength.STRONG,
                    reasoning="test",
                ),
                AudienceSegment(
                    platform=Platform.REDDIT,
                    community="r/technology",
                    estimated_fit=FitStrength.MODERATE,
                    reasoning="test",
                ),
            ],
            strongest_fit=AudienceSegment(
                platform=Platform.TWITTER_X,
                community="Tech Twitter",
                estimated_fit=FitStrength.STRONG,
                reasoning="test",
            ),
            weakest_reach=["Instagram lifestyle"],
            content_format_notes="Short text format.",
            distribution_strategy="Post on Twitter first.",
            explanation="test",
        )

        if with_error:
            dist = ToolError(tool="distribution", error="API timeout")

        return JudgmentReport(
            content_type=SourceType.STRING,
            ai_detection=ai,
            virality=virality,
            distribution=dist,
            overall_explanation="Test synthesis.",
            analysis_metadata=AnalysisMetadata(
                model_used="gemini-2.5-flash",
                iterations=1,
                tools_succeeded=["ai_detection", "virality"] + (["distribution"] if not with_error else []),
                tools_failed=["distribution"] if with_error else [],
            ),
        )

    def test_json_round_trip(self):
        report = self._make_report()
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["content_type"] == "string"
        assert parsed["ai_detection"]["verdict"] == "likely_human"

        restored = JudgmentReport.from_json(json_str)
        assert restored.content_type == SourceType.STRING

    def test_has_errors_false(self):
        report = self._make_report()
        assert report.has_errors() is False

    def test_has_errors_true(self):
        report = self._make_report(with_error=True)
        assert report.has_errors() is True
        assert "distribution" in report.error_summary()
