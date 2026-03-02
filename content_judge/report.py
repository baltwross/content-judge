"""
content_judge/report.py

Renders a JudgmentReport as a full markdown document.
"""

from __future__ import annotations

from datetime import datetime

from content_judge import __version__
from content_judge.models import (
    AIDetectionResult,
    DistributionResult,
    JudgmentReport,
    ToolError,
    ViralityResult,
)


def render_markdown(report: JudgmentReport) -> str:
    """Convert a JudgmentReport into a formatted markdown string."""
    sections = [
        _header(report),
        _ai_detection(report.ai_detection),
        _virality(report.virality),
        _distribution(report.distribution),
        _overall(report),
        _footer(),
    ]
    return "\n".join(sections)


def _header(report: JudgmentReport) -> str:
    meta = report.analysis_metadata
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content_type = report.content_type.value.upper()

    return (
        f"# Content Judge Report\n\n"
        f"**Date:** {now}  \n"
        f"**Content type:** {content_type}  \n"
        f"**Model:** {meta.model_used}  \n"
        f"**Iterations:** {meta.iterations}\n\n"
        f"---\n"
    )


def _ai_detection(result: AIDetectionResult | ToolError) -> str:
    lines = ["\n## AI Detection\n"]

    if isinstance(result, ToolError):
        lines.append(f"> **Error:** {result.error}\n")
        return "\n".join(lines)

    verdict = result.verdict.value.replace("_", " ").title()
    lines.append(f"**Verdict:** {verdict}  ")
    lines.append(f"**Confidence:** {result.confidence:.0%} ({result.confidence_level.value})  ")

    if result.detected_generator:
        lines.append(f"**Detected generator:** {result.detected_generator}  ")

    if result.c2pa.present:
        lines.append(f"**C2PA metadata:** present (issuer: {result.c2pa.issuer or 'unknown'})  ")

    lines.append(f"\n{result.explanation}\n")

    if result.signals:
        lines.append("### Signals\n")
        lines.append("| Signal | Value | Confidence | Weight |")
        lines.append("|--------|-------|------------|--------|")
        for s in result.signals:
            lines.append(f"| {s.signal_name} | {s.value} | {s.confidence:.2f} | {s.weight:.2f} |")
        lines.append("")

    if result.text_scores:
        ts = result.text_scores
        lines.append("### Text Signal Scores\n")
        lines.append("| Signal | Score |")
        lines.append("|--------|-------|")
        lines.append(f"| Vocabulary uniformity | {ts.vocabulary_uniformity:.2f} |")
        lines.append(f"| Burstiness | {ts.burstiness:.2f} |")
        lines.append(f"| Hedging frequency | {ts.hedging_frequency:.2f} |")
        lines.append(f"| Formulaic patterns | {ts.formulaic_patterns:.2f} |")
        lines.append(f"| Tonal uniformity | {ts.tonal_uniformity:.2f} |")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _virality(result: ViralityResult | ToolError) -> str:
    lines = ["\n## Virality Score\n"]

    if isinstance(result, ToolError):
        lines.append(f"> **Error:** {result.error}\n")
        return "\n".join(lines)

    level = result.virality_level.replace("_", " ").title()
    quadrant = result.emotional_quadrant.value.replace("_", " ").title()

    lines.append(f"**Score:** {result.overall_score}/10 ({level})  ")
    lines.append(f"**Emotional tone:** {quadrant}  ")
    lines.append(f"**Primary emotions:** {', '.join(result.primary_emotions)}  ")
    lines.append(f"\n**Strengths:** {', '.join(result.key_strengths)}  ")
    lines.append(f"**Weaknesses:** {', '.join(result.key_weaknesses)}  ")
    lines.append(f"\n{result.explanation}\n")

    lines.append("### Dimension Scores\n")
    lines.append("| Dimension | Score | Weight | Reasoning |")
    lines.append("|-----------|-------|--------|-----------|")
    for d in result.dimensions:
        lines.append(f"| {d.name} | {d.score}/10 | {d.weight:.0%} | {d.reasoning} |")
    lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _distribution(result: DistributionResult | ToolError) -> str:
    lines = ["\n## Distribution Analysis\n"]

    if isinstance(result, ToolError):
        lines.append(f"> **Error:** {result.error}\n")
        return "\n".join(lines)

    lines.append(f"**Topics:** {', '.join(result.primary_topics)}\n")

    lines.append("### Audience Segments\n")
    lines.append("| Platform | Community | Fit | Reasoning |")
    lines.append("|----------|-----------|-----|-----------|")
    for seg in result.audience_segments:
        lines.append(
            f"| {seg.platform.value} | {seg.community} | {seg.estimated_fit.value} | {seg.reasoning} |"
        )
    lines.append("")

    lines.append(f"**Strategy:** {result.distribution_strategy}\n")

    if result.weakest_reach:
        lines.append(f"**Would not resonate with:** {', '.join(result.weakest_reach)}\n")

    lines.append(f"{result.explanation}\n")

    lines.append("---\n")
    return "\n".join(lines)


def _overall(report: JudgmentReport) -> str:
    lines = ["\n## Overall Assessment\n"]
    lines.append(f"{report.overall_explanation}\n")

    if report.has_errors():
        lines.append(f"\n> **Warnings:** {report.error_summary()}\n")

    return "\n".join(lines)


def _footer() -> str:
    return f"\n---\n\n*Generated by content-judge v{__version__}*\n"
