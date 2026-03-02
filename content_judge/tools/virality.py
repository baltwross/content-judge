"""
Virality scoring tool: 7-dimension rubric grounded in Berger & Milkman (2012).

Single code path for both video and text — Gemini scores the rubric directly
on the actual content.
"""

from __future__ import annotations

from content_judge.llm import call_gemini_structured
from content_judge.models import (
    ContentInput,
    ViralityDimension,
    ViralityLLMOutput,
    ViralityResult,
    VIRALITY_DIMENSION_WEIGHTS,
)
from content_judge.prompts import VIRALITY_SYSTEM_PROMPT


def run_virality(content: ContentInput) -> ViralityResult:
    """
    Score content virality using 7-dimension rubric.
    Gemini scores directly on actual content (video or text).
    """
    # Build prompt
    if content.has_video and content.video_source:
        prompt = (
            f"{VIRALITY_SYSTEM_PROMPT}\n\n"
            "VIDEO CONTENT ANALYSIS\n"
            "Analyze this video directly for virality potential. "
            "Assess the actual content — topic, emotional tone, pacing, "
            "production quality, hook strength, narrative arc, and "
            "shareability. Score each dimension based on what you observe."
        )
        llm_output: ViralityLLMOutput = call_gemini_structured(
            prompt=prompt,
            output_schema=ViralityLLMOutput,
            video_source=content.video_source,
        )
    else:
        prompt = (
            f"{VIRALITY_SYSTEM_PROMPT}\n\n"
            f"TEXT CONTENT TO ANALYZE:\n\n{content.text}"
        )
        llm_output = call_gemini_structured(
            prompt=prompt,
            output_schema=ViralityLLMOutput,
        )

    # Ensure correct weights are applied
    for dim in llm_output.dimensions:
        if dim.dimension_id in VIRALITY_DIMENSION_WEIGHTS:
            dim.weight = VIRALITY_DIMENSION_WEIGHTS[dim.dimension_id]

    # Convert ViralityLLMOutput → ViralityResult (adds computed fields)
    return ViralityResult(
        dimensions=llm_output.dimensions,
        emotional_quadrant=llm_output.emotional_quadrant,
        primary_emotions=llm_output.primary_emotions,
        key_strengths=llm_output.key_strengths,
        key_weaknesses=llm_output.key_weaknesses,
        explanation=llm_output.explanation,
    )
