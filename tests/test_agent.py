"""Tests for coordinator agent (mocked tools)."""

import pytest
from unittest.mock import patch, MagicMock

from content_judge.models import (
    AIDetectionResult,
    AILabel,
    AnalysisMetadata,
    AudienceSegment,
    ConfidenceLevel,
    ContentInput,
    DetectionSignal,
    DistributionResult,
    EmotionalQuadrant,
    FitStrength,
    JudgmentReport,
    Platform,
    ReviewDecision,
    SourceType,
    ToolError,
    ViralityDimension,
    ViralityResult,
    VIRALITY_DIMENSION_WEIGHTS,
)


def _make_content():
    return ContentInput(source_type=SourceType.STRING, text="Test content")


def _make_ai_result():
    return AIDetectionResult(
        verdict=AILabel.LIKELY_HUMAN,
        confidence=0.8,
        confidence_level=ConfidenceLevel.HIGH,
        signals=[DetectionSignal(signal_name="test", value="test", confidence=0.8, weight=1.0)],
        explanation="Likely human.",
    )


def _make_virality_result():
    dims = [
        ViralityDimension(dimension_id=k, name=k, score=5, weight=v, reasoning="test")
        for k, v in VIRALITY_DIMENSION_WEIGHTS.items()
    ]
    return ViralityResult(
        dimensions=dims,
        emotional_quadrant=EmotionalQuadrant.LOW_AROUSAL_POSITIVE,
        primary_emotions=["calm"],
        key_strengths=["clear"],
        key_weaknesses=["boring"],
        explanation="Average virality.",
    )


def _make_dist_result():
    seg = AudienceSegment(
        platform=Platform.TWITTER_X, community="Tech", estimated_fit=FitStrength.STRONG, reasoning="test"
    )
    return DistributionResult(
        primary_topics=["Technology"],
        audience_segments=[seg, AudienceSegment(
            platform=Platform.REDDIT, community="r/tech", estimated_fit=FitStrength.MODERATE, reasoning="test"
        )],
        strongest_fit=seg,
        weakest_reach=["Instagram"],
        content_format_notes="Short.",
        distribution_strategy="Twitter first.",
        explanation="Tech fit.",
    )


class TestCoordinatorAgent:
    @patch("content_judge.agent.run_distribution")
    @patch("content_judge.agent.run_virality")
    @patch("content_judge.agent.run_ai_detection")
    @patch("content_judge.agent.call_gemini_structured")
    def test_produces_report(self, mock_synth, mock_ai, mock_vir, mock_dist):
        mock_ai.return_value = _make_ai_result()
        mock_vir.return_value = _make_virality_result()
        mock_dist.return_value = _make_dist_result()
        # Review returns acceptable
        mock_synth.side_effect = [
            ReviewDecision(all_results_acceptable=True, review_notes="All good."),
            "Overall synthesis text.",
        ]

        from content_judge.agent import CoordinatorAgent
        agent = CoordinatorAgent(model="gemini-2.5-flash")
        report = agent.run(_make_content())

        assert isinstance(report, JudgmentReport)
        assert not report.has_errors()
        assert report.analysis_metadata.iterations == 1

    @patch("content_judge.agent.run_distribution")
    @patch("content_judge.agent.run_virality")
    @patch("content_judge.agent.run_ai_detection")
    @patch("content_judge.agent.call_gemini_structured")
    def test_handles_tool_failure(self, mock_synth, mock_ai, mock_vir, mock_dist):
        mock_ai.return_value = _make_ai_result()
        mock_vir.return_value = _make_virality_result()
        mock_dist.side_effect = Exception("API timeout")
        mock_synth.side_effect = [
            ReviewDecision(all_results_acceptable=True, review_notes="Partial."),
            "Partial synthesis.",
        ]

        from content_judge.agent import CoordinatorAgent
        agent = CoordinatorAgent(model="gemini-2.5-flash")
        report = agent.run(_make_content())

        assert isinstance(report, JudgmentReport)
        assert report.has_errors()
        assert "distribution" in report.error_summary()
