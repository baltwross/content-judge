"""
AI Detection tool: determines whether content is AI-generated or human-generated.

Combines multiple signals:
- Gemini text analysis (rubric-based signal scoring)
- Hive API (96-99% accuracy on video, if configured)
- C2PA metadata (optional)
"""

from __future__ import annotations

import logging

from content_judge.config import get_settings
from content_judge.llm import call_gemini_structured, LLMError
from content_judge.models import (
    AIDetectionResult,
    AILabel,
    C2PASignal,
    ConfidenceLevel,
    ContentInput,
    DetectionSignal,
    TextSignalScores,
    VideoSignalScores,
)
from content_judge.prompts import AI_DETECTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class _TextAnalysisLLMOutput(AIDetectionResult):
    """Schema for Gemini structured output — matches AIDetectionResult."""

    pass


def run_ai_detection(content: ContentInput) -> AIDetectionResult:
    """Run AI detection analysis on content. Returns AIDetectionResult."""
    signals: list[DetectionSignal] = []
    text_scores: TextSignalScores | None = None
    video_scores: VideoSignalScores | None = None
    hive_result: dict | None = None
    c2pa = C2PASignal()

    # C2PA check (optional)
    c2pa = _check_c2pa(content)
    if c2pa.present:
        signals.append(DetectionSignal(
            signal_name="c2pa_metadata",
            value=f"C2PA present, generator: {c2pa.generator or 'unknown'}",
            confidence=0.95,
            weight=0.9,
        ))

    # Hive API for video (if configured)
    if content.has_video:
        hive_result = _run_hive(content)
        if hive_result:
            score = hive_result["ai_score"]
            signals.append(DetectionSignal(
                signal_name="hive_api",
                value=f"AI score: {score:.3f}, generator: {hive_result.get('generator', 'unknown')}",
                confidence=score if score > 0.5 else 1.0 - score,
                weight=0.9,
            ))

    # Gemini text analysis
    if content.has_text:
        text_result = _run_gemini_text_analysis(content)
        if text_result:
            text_scores = text_result.text_scores
            signals.extend(text_result.signals)

            # If we already have better signals, use gemini as supporting
            if not signals:
                return text_result

    # Aggregate signals into final result
    return _aggregate_signals(
        signals=signals,
        text_scores=text_scores,
        video_scores=video_scores,
        hive_result=hive_result,
        c2pa=c2pa,
        content=content,
    )


def _run_hive(content: ContentInput) -> dict | None:
    """Run Hive API detection on video content."""
    settings = get_settings()
    if not settings.hive_api_token:
        return None

    from content_judge.tools.hive_client import hive_detect_youtube, hive_detect_from_file
    from content_judge.loaders.video import is_youtube_url

    try:
        if content.video_source and is_youtube_url(content.video_source):
            return hive_detect_youtube(content.video_source, settings.hive_api_token)
        elif content.video_source:
            return hive_detect_from_file(content.video_source, settings.hive_api_token)
    except Exception as e:
        logger.warning(f"Hive detection failed: {e}")

    return None


def _run_gemini_text_analysis(content: ContentInput) -> AIDetectionResult | None:
    """Run Gemini structured text analysis."""
    try:
        prompt = f"{AI_DETECTION_SYSTEM_PROMPT}\n\nCONTENT TO ANALYZE:\n\n{content.text}"
        return call_gemini_structured(
            prompt=prompt,
            output_schema=AIDetectionResult,
        )
    except LLMError as e:
        logger.warning(f"Gemini text analysis failed: {e}")
        return None


def _check_c2pa(content: ContentInput) -> C2PASignal:
    """Check for C2PA content provenance metadata."""
    try:
        from c2pa import Reader
        if content.video_source and not content.video_source.startswith("http"):
            reader = Reader.from_file(content.video_source)
            if reader.manifest_store:
                manifest = reader.manifest_store.active_manifest
                return C2PASignal(
                    present=True,
                    issuer=getattr(manifest, "claim_generator", None),
                    generator=getattr(manifest, "claim_generator", None),
                )
    except ImportError:
        pass
    except Exception:
        pass
    return C2PASignal()


def _aggregate_signals(
    signals: list[DetectionSignal],
    text_scores: TextSignalScores | None,
    video_scores: VideoSignalScores | None,
    hive_result: dict | None,
    c2pa: C2PASignal,
    content: ContentInput,
) -> AIDetectionResult:
    """Aggregate all signals into a final AIDetectionResult."""
    # If Hive has high confidence, trust it
    if hive_result and hive_result["ai_score"] > 0.9:
        verdict = AILabel.AI_GENERATED
        confidence = hive_result["ai_score"]
        explanation = (
            f"Hive AI detection identifies this video as AI-generated with "
            f"{hive_result['ai_score']:.1%} confidence."
        )
        if hive_result.get("generator"):
            explanation += f" Detected generator: {hive_result['generator']}."
        return AIDetectionResult(
            verdict=verdict,
            confidence=confidence,
            confidence_level=_confidence_to_level(confidence),
            signals=signals,
            text_scores=text_scores,
            video_scores=video_scores,
            detected_generator=hive_result.get("generator"),
            c2pa=c2pa,
            explanation=explanation,
        )

    if hive_result and hive_result["ai_score"] < 0.1:
        verdict = AILabel.HUMAN
        confidence = 1.0 - hive_result["ai_score"]
        return AIDetectionResult(
            verdict=verdict,
            confidence=confidence,
            confidence_level=_confidence_to_level(confidence),
            signals=signals,
            text_scores=text_scores,
            video_scores=video_scores,
            detected_generator=None,
            c2pa=c2pa,
            explanation=f"Hive AI detection identifies this video as human-created with {confidence:.1%} confidence.",
        )

    # Weighted average of all signal confidences
    if not signals:
        return AIDetectionResult(
            verdict=AILabel.UNCERTAIN,
            confidence=0.5,
            confidence_level=ConfidenceLevel.LOW,
            signals=[],
            text_scores=text_scores,
            video_scores=video_scores,
            detected_generator=None,
            c2pa=c2pa,
            explanation="No detection signals available.",
        )

    weighted_sum = sum(s.confidence * s.weight for s in signals)
    total_weight = sum(s.weight for s in signals)
    avg_confidence = weighted_sum / total_weight if total_weight > 0 else 0.5

    # Map to verdict
    if avg_confidence > 0.7:
        verdict = AILabel.AI_GENERATED
    elif avg_confidence > 0.55:
        verdict = AILabel.LIKELY_AI_GENERATED
    elif avg_confidence > 0.45:
        verdict = AILabel.UNCERTAIN
    elif avg_confidence > 0.3:
        verdict = AILabel.LIKELY_HUMAN
    else:
        verdict = AILabel.HUMAN

    # Apply confidence capping
    if content.is_short_text:
        conf_level = ConfidenceLevel.MODERATE
    elif not content.has_video:
        conf_level = min(_confidence_to_level(avg_confidence), ConfidenceLevel.HIGH, key=_level_order)
    else:
        conf_level = _confidence_to_level(avg_confidence)

    explanation_parts = []
    for s in signals:
        explanation_parts.append(f"{s.signal_name}: {s.value}")

    return AIDetectionResult(
        verdict=verdict,
        confidence=avg_confidence,
        confidence_level=conf_level,
        signals=signals,
        text_scores=text_scores,
        video_scores=video_scores,
        detected_generator=hive_result.get("generator") if hive_result else None,
        c2pa=c2pa,
        explanation=f"Analysis based on {len(signals)} signal(s). " + "; ".join(explanation_parts),
    )


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    if confidence >= 0.9:
        return ConfidenceLevel.VERY_HIGH
    elif confidence >= 0.75:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.55:
        return ConfidenceLevel.MODERATE
    elif confidence >= 0.35:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW


def _level_order(level: ConfidenceLevel) -> int:
    return {
        ConfidenceLevel.VERY_LOW: 0,
        ConfidenceLevel.LOW: 1,
        ConfidenceLevel.MODERATE: 2,
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.VERY_HIGH: 4,
    }[level]
