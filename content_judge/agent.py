"""
content_judge/agent.py

Coordinator agent: orchestrates analysis tools, reviews results, synthesizes report.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from content_judge.config import get_settings
from content_judge.llm import call_gemini_video, call_gemini_structured, LLMError
from content_judge.models import (
    AIDetectionResult,
    AnalysisMetadata,
    ContentInput,
    DistributionResult,
    JudgmentReport,
    ReviewDecision,
    ToolError,
    ToolResults,
    ViralityResult,
)
from content_judge.prompts import (
    AI_DETECTION_VIDEO_SUMMARY_PROMPT,
    COORDINATOR_REVIEW_PROMPT,
    COORDINATOR_SYNTHESIS_PROMPT,
)
from content_judge.tools.ai_detection import run_ai_detection
from content_judge.tools.virality import run_virality
from content_judge.tools.distribution import run_distribution

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


class CoordinatorAgent:
    """
    Agentic coordinator that dispatches analysis tools, reviews results,
    and synthesizes a final JudgmentReport.
    """

    def __init__(
        self,
        model: str | None = None,
        on_tool_complete: Callable[[str], None] | None = None,
    ):
        settings = get_settings()
        self.model = model or settings.default_model
        self.on_tool_complete = on_tool_complete

    def run(self, content: ContentInput) -> JudgmentReport:
        """Main entry point: analyze content and produce a JudgmentReport."""
        iteration = 0

        # Video pre-processing: get rich description for AI detection text analysis
        if content.has_video and content.video_source:
            self._preprocess_video(content)

        # First dispatch
        iteration += 1
        results = self._dispatch_tools(content)

        # Review loop (max 3 iterations)
        while iteration < MAX_ITERATIONS:
            review = self._review_results(content, results)
            if review.all_results_acceptable:
                break

            iteration += 1
            logger.info(f"Re-running tools (iteration {iteration}): {review.re_run_tools}")
            results = self._re_dispatch(content, results, review)

        # Synthesize final report
        explanation = self._synthesize(content, results)

        tools_succeeded = []
        tools_failed = []
        for name in ["ai_detection", "virality", "distribution"]:
            result = getattr(results, name)
            if isinstance(result, ToolError):
                tools_failed.append(name)
            else:
                tools_succeeded.append(name)

        return JudgmentReport(
            content_type=content.source_type,
            ai_detection=results.ai_detection,
            virality=results.virality,
            distribution=results.distribution,
            overall_explanation=explanation,
            analysis_metadata=AnalysisMetadata(
                model_used=self.model,
                iterations=iteration,
                tools_succeeded=tools_succeeded,
                tools_failed=tools_failed,
            ),
        )

    def _preprocess_video(self, content: ContentInput) -> None:
        """
        For video: call Gemini for a rich description used by AI detection text analysis.
        Stores in content.text. Does NOT modify content.video_source.
        """
        try:
            description = call_gemini_video(
                prompt=AI_DETECTION_VIDEO_SUMMARY_PROMPT,
                video_source=content.video_source,
                model=self.model,
            )
            content.text = description
            content.has_text = True
            content.text_length = len(description)
            content.is_short_text = content.text_length < 200
        except LLMError as e:
            logger.warning(f"Video pre-processing failed: {e}")

    def _dispatch_tools(self, content: ContentInput) -> ToolResults:
        """
        Run all three analysis tools.
        Sequential for video (avoids blowing through token-per-minute quota
        by sending the same video to Gemini 3x simultaneously).
        Parallel for text (small token footprint).
        """
        results: dict[str, AIDetectionResult | ViralityResult | DistributionResult | ToolError] = {}

        tool_fns = [
            ("ai_detection", run_ai_detection),
            ("virality", run_virality),
            ("distribution", run_distribution),
        ]

        if content.has_video:
            # Sequential — each video call uses ~100K+ tokens
            for tool_name, fn in tool_fns:
                try:
                    results[tool_name] = fn(content)
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    results[tool_name] = ToolError(
                        tool=tool_name,
                        error=str(e),
                        is_retryable="timeout" in str(e).lower() or "rate" in str(e).lower(),
                    )
                if self.on_tool_complete:
                    self.on_tool_complete(tool_name)
        else:
            # Parallel — text is small
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(fn, content): name
                    for name, fn in tool_fns
                }
                for future in as_completed(futures):
                    tool_name = futures[future]
                    try:
                        results[tool_name] = future.result()
                    except Exception as e:
                        logger.error(f"Tool {tool_name} failed: {e}")
                        results[tool_name] = ToolError(
                            tool=tool_name,
                            error=str(e),
                            is_retryable="timeout" in str(e).lower() or "rate" in str(e).lower(),
                        )
                    if self.on_tool_complete:
                        self.on_tool_complete(tool_name)

        return ToolResults(
            ai_detection=results.get("ai_detection", ToolError(tool="ai_detection", error="Not executed")),
            virality=results.get("virality", ToolError(tool="virality", error="Not executed")),
            distribution=results.get("distribution", ToolError(tool="distribution", error="Not executed")),
        )

    def _review_results(self, content: ContentInput, results: ToolResults) -> ReviewDecision:
        """Review results and decide whether to re-run any tools."""
        try:
            summary = self._build_review_prompt(content, results)
            return call_gemini_structured(
                prompt=summary,
                output_schema=ReviewDecision,
                system_prompt=COORDINATOR_REVIEW_PROMPT,
                model=self.model,
            )
        except LLMError:
            # If review fails, accept results as-is
            return ReviewDecision(
                all_results_acceptable=True,
                review_notes="Review call failed; accepting results as-is.",
            )

    def _re_dispatch(
        self,
        content: ContentInput,
        previous: ToolResults,
        review: ReviewDecision,
    ) -> ToolResults:
        """Re-run only the tools that need refinement."""
        results = {
            "ai_detection": previous.ai_detection,
            "virality": previous.virality,
            "distribution": previous.distribution,
        }

        tool_fns = {
            "ai_detection": run_ai_detection,
            "virality": run_virality,
            "distribution": run_distribution,
        }

        for tool_name in review.re_run_tools:
            if tool_name in tool_fns:
                try:
                    results[tool_name] = tool_fns[tool_name](content)
                except Exception as e:
                    results[tool_name] = ToolError(tool=tool_name, error=str(e))
                if self.on_tool_complete:
                    self.on_tool_complete(tool_name)

        return ToolResults(**results)

    def _build_review_prompt(self, content: ContentInput, results: ToolResults) -> str:
        """Build the prompt for the coordinator review call."""
        parts = [f"CONTENT: type={content.source_type.value}, text_length={content.text_length}"]

        if isinstance(results.ai_detection, AIDetectionResult):
            ai = results.ai_detection
            parts.append(f"AI Detection: verdict={ai.verdict.value}, confidence={ai.confidence:.2f}")
        else:
            parts.append(f"AI Detection: ERROR - {results.ai_detection.error}")

        if isinstance(results.virality, ViralityResult):
            v = results.virality
            parts.append(f"Virality: overall_score={v.overall_score}, level={v.virality_level}")
        else:
            parts.append(f"Virality: ERROR - {results.virality.error}")

        if isinstance(results.distribution, DistributionResult):
            d = results.distribution
            parts.append(
                f"Distribution: topics={d.primary_topics}, segments={len(d.audience_segments)}"
            )
        else:
            parts.append(f"Distribution: ERROR - {results.distribution.error}")

        return "\n".join(parts)

    def _synthesize(self, content: ContentInput, results: ToolResults) -> str:
        """Build synthesis prompt with full reasoning fields and get explanation."""
        prompt_parts = [
            f"CONTENT TYPE: {content.source_type.value}",
            "",
        ]

        # AI Detection reasoning
        if isinstance(results.ai_detection, AIDetectionResult):
            ai = results.ai_detection
            prompt_parts.append(
                f"AI DETECTION:\n"
                f"Verdict: {ai.verdict.value} (confidence: {ai.confidence:.2f})\n"
                f"Explanation: {ai.explanation}"
            )
        else:
            prompt_parts.append(f"AI DETECTION: Failed - {results.ai_detection.error}")

        # Virality reasoning (top dimensions)
        if isinstance(results.virality, ViralityResult):
            v = results.virality
            top_dims = sorted(v.dimensions, key=lambda d: d.score, reverse=True)[:3]
            dim_reasoning = "; ".join(
                f"{d.name} ({d.score}/10): {d.reasoning}" for d in top_dims
            )
            prompt_parts.append(
                f"\nVIRALITY:\n"
                f"Overall: {v.overall_score}/10 ({v.virality_level})\n"
                f"Top dimensions: {dim_reasoning}\n"
                f"Explanation: {v.explanation}"
            )
        else:
            prompt_parts.append(f"\nVIRALITY: Failed - {results.virality.error}")

        # Distribution reasoning
        if isinstance(results.distribution, DistributionResult):
            d = results.distribution
            prompt_parts.append(
                f"\nDISTRIBUTION:\n"
                f"Topics: {', '.join(d.primary_topics)}\n"
                f"Strongest fit: {d.strongest_fit.platform.value} — {d.strongest_fit.community} "
                f"({d.strongest_fit.estimated_fit.value}): {d.strongest_fit.reasoning}\n"
                f"Explanation: {d.explanation}"
            )
        else:
            prompt_parts.append(f"\nDISTRIBUTION: Failed - {results.distribution.error}")

        synthesis_input = "\n".join(prompt_parts)

        try:
            result = call_gemini_structured(
                prompt=f"{COORDINATOR_SYNTHESIS_PROMPT}\n\n{synthesis_input}",
                output_schema=None,
                model=self.model,
            )
            return result
        except LLMError:
            # Fallback: construct a basic synthesis
            return self._fallback_synthesis(results)

    def _fallback_synthesis(self, results: ToolResults) -> str:
        """Generate a basic synthesis when the LLM call fails."""
        parts = []
        if isinstance(results.ai_detection, AIDetectionResult):
            parts.append(
                f"AI detection analysis returned a verdict of {results.ai_detection.verdict.value} "
                f"with {results.ai_detection.confidence:.0%} confidence."
            )
        if isinstance(results.virality, ViralityResult):
            parts.append(
                f"Virality potential scored {results.virality.overall_score}/10 "
                f"({results.virality.virality_level})."
            )
        if isinstance(results.distribution, DistributionResult):
            parts.append(
                f"Best distribution fit: {results.distribution.strongest_fit.platform.value} "
                f"({results.distribution.strongest_fit.community})."
            )
        return " ".join(parts) if parts else "Analysis completed with partial results."
