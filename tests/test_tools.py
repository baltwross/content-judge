"""Tests for analysis tools (mocked LLM calls)."""

import pytest
from unittest.mock import patch, MagicMock

from content_judge.models import (
    AIDetectionResult,
    AILabel,
    AudienceSegment,
    ConfidenceLevel,
    ContentInput,
    DetectionSignal,
    DistributionResult,
    EmotionalQuadrant,
    FitStrength,
    Platform,
    SourceType,
    ViralityDimension,
    ViralityLLMOutput,
    ViralityResult,
    VIRALITY_DIMENSION_WEIGHTS,
)


def _make_text_content(text="Test content for analysis"):
    return ContentInput(source_type=SourceType.STRING, text=text)


def _make_virality_llm_output():
    dims = []
    for dim_id, weight in VIRALITY_DIMENSION_WEIGHTS.items():
        dims.append(ViralityDimension(
            dimension_id=dim_id,
            name=dim_id.replace("_", " ").title(),
            score=6,
            weight=weight,
            reasoning="Test reasoning.",
        ))
    return ViralityLLMOutput(
        dimensions=dims,
        emotional_quadrant=EmotionalQuadrant.HIGH_AROUSAL_POSITIVE,
        primary_emotions=["curiosity"],
        key_strengths=["novelty"],
        key_weaknesses=["niche"],
        explanation="Test virality explanation.",
    )


def _make_ai_detection_result():
    return AIDetectionResult(
        verdict=AILabel.LIKELY_HUMAN,
        confidence=0.75,
        confidence_level=ConfidenceLevel.HIGH,
        signals=[DetectionSignal(
            signal_name="llm_text_analysis",
            value="Low AI signals across text features",
            confidence=0.75,
            weight=1.0,
        )],
        explanation="Analysis suggests human-written content.",
    )


def _make_distribution_result():
    seg = AudienceSegment(
        platform=Platform.TWITTER_X,
        community="Tech Twitter",
        estimated_fit=FitStrength.STRONG,
        reasoning="Content matches tech community interests.",
    )
    return DistributionResult(
        primary_topics=["Technology"],
        audience_segments=[
            seg,
            AudienceSegment(
                platform=Platform.REDDIT,
                community="r/technology",
                estimated_fit=FitStrength.MODERATE,
                reasoning="Relevant to general tech audience.",
            ),
        ],
        strongest_fit=seg,
        weakest_reach=["Instagram lifestyle"],
        content_format_notes="Short text format.",
        distribution_strategy="Share on Twitter and Reddit.",
        explanation="Best fit for tech communities.",
    )


class TestViralityTool:
    @patch("content_judge.tools.virality.call_gemini_structured")
    def test_returns_valid_result(self, mock_gemini):
        mock_gemini.return_value = _make_virality_llm_output()

        from content_judge.tools.virality import run_virality
        result = run_virality(_make_text_content())

        assert isinstance(result, ViralityResult)
        assert len(result.dimensions) == 7
        assert 1.0 <= result.overall_score <= 10.0
        assert result.virality_level in ("low", "moderate", "high", "very_high")


class TestDistributionTool:
    @patch("content_judge.tools.distribution.call_gemini_structured")
    def test_returns_valid_result(self, mock_gemini):
        mock_gemini.return_value = _make_distribution_result()

        from content_judge.tools.distribution import run_distribution
        result = run_distribution(_make_text_content())

        assert isinstance(result, DistributionResult)
        assert len(result.primary_topics) >= 1
        assert len(result.audience_segments) >= 2


class TestAIDetectionTool:
    @patch("content_judge.tools.ai_detection.call_gemini_structured")
    def test_returns_valid_result(self, mock_gemini):
        mock_gemini.return_value = _make_ai_detection_result()

        from content_judge.tools.ai_detection import run_ai_detection
        result = run_ai_detection(_make_text_content())

        assert isinstance(result, AIDetectionResult)
        assert result.verdict in list(AILabel)
