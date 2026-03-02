"""
Distribution analysis tool: 3-layer framework for content-audience matching.

Single code path for both video and text — Gemini scores the distribution
framework directly on the actual content.
"""

from __future__ import annotations

from content_judge.llm import call_gemini_structured
from content_judge.models import ContentInput, DistributionResult
from content_judge.prompts import DISTRIBUTION_SYSTEM_PROMPT


def run_distribution(content: ContentInput) -> DistributionResult:
    """
    Analyze content distribution potential using 3-layer framework.
    Gemini scores directly on actual content (video or text).
    """
    if content.has_video and content.video_source:
        prompt = (
            f"{DISTRIBUTION_SYSTEM_PROMPT}\n\n"
            "VIDEO CONTENT ANALYSIS\n"
            "Analyze this video directly for distribution potential. "
            "Assess the actual format (aspect ratio, vertical vs horizontal), "
            "editing style (jump cuts, smooth transitions, single take), "
            "production quality, duration, pacing, audio, on-screen text, "
            "and content topic/tone. Use these direct observations to drive "
            "your platform-audience mapping and resonance reasoning."
        )
        return call_gemini_structured(
            prompt=prompt,
            output_schema=DistributionResult,
            video_source=content.video_source,
        )
    else:
        prompt = (
            f"{DISTRIBUTION_SYSTEM_PROMPT}\n\n"
            f"TEXT CONTENT TO ANALYZE:\n\n{content.text}"
        )
        return call_gemini_structured(
            prompt=prompt,
            output_schema=DistributionResult,
        )
