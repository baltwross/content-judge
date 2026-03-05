"""
content_judge/cli.py

CLI entry point using Typer + Rich for content analysis.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text

from content_judge import __version__
from content_judge.models import (
    AIDetectionResult,
    AILabel,
    ContentInput,
    DistributionResult,
    JudgmentReport,
    SourceType,
    ToolError,
    ViralityResult,
)

app = typer.Typer(
    name="content-judge",
    help="Evaluate content for AI origin, virality potential, and audience fit.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"content-judge v{__version__}")
        raise typer.Exit()


@app.command()
def judge(
    input: str = typer.Argument(
        ..., help="Text, file path, URL, or video path to analyze."
    ),
    video: bool = typer.Option(False, "--video", help="Treat input as a video (local file or YouTube URL)."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    report: bool = typer.Option(False, "--report", help="Write full markdown report to auto-named .md file."),
    report_path: str = typer.Option(None, "--report-path", help="Write markdown report to specific file path."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show extended detail."),
    model: str = typer.Option(None, "--model", help="Override Gemini model."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color output."),
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Judge content for AI origin, virality potential, and audience distribution fit."""
    if no_color:
        console.no_color = True

    # Validate config
    try:
        from content_judge.config import get_settings
        settings = get_settings()
        effective_model = model or settings.default_model
    except Exception as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print("Set GEMINI_API_KEY in .env or environment. See .env.example.")
        raise typer.Exit(code=1)

    # Load content
    try:
        content = _load_content(input, video)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Run analysis with progress
    if json_output:
        # Suppress progress for JSON mode
        from content_judge.agent import CoordinatorAgent
        agent = CoordinatorAgent(model=effective_model)
        result = agent.run(content)
        typer.echo(result.to_json())
        return

    result = _run_with_progress(content, effective_model)

    # Markdown report mode
    if report or report_path:
        from datetime import datetime
        from content_judge.report import render_markdown
        md = render_markdown(result)
        out = report_path or f"report-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.md"
        Path(out).write_text(md, encoding="utf-8")
        console.print(f"Report written to [bold]{out}[/bold]")
        return

    # Render Rich output
    _render_report(result, verbose)


def _load_content(raw_input: str, is_video: bool) -> ContentInput:
    """Route input to the appropriate loader."""
    from content_judge.loaders import load_text, validate_video_url, ContentLoadError

    if is_video:
        validate_video_url(raw_input)
        return ContentInput(
            source_type=SourceType.VIDEO,
            video_source=raw_input,
        )

    text, source_type = load_text(raw_input)
    return ContentInput(source_type=source_type, text=text)


def _detect_is_video(raw_input: str) -> bool:
    """Auto-detect whether input is a video source."""
    from content_judge.loaders import is_youtube_url
    from content_judge.loaders.video import SUPPORTED_VIDEO_FORMATS

    if is_youtube_url(raw_input):
        return True

    ext = Path(raw_input).suffix.lower()
    if ext in SUPPORTED_VIDEO_FORMATS:
        return True

    return False


def _run_with_progress(content: ContentInput, model: str) -> JudgmentReport:
    """Run coordinator with Rich progress display."""
    from content_judge.agent import CoordinatorAgent

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20),
        TextColumn("{task.completed}/{task.total}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("Running analysis...", total=3)

        def on_tool_complete(tool_name: str) -> None:
            progress.advance(task)

        agent = CoordinatorAgent(model=model, on_tool_complete=on_tool_complete)
        report = agent.run(content)

    return report


def _render_report(report: JudgmentReport, verbose: bool) -> None:
    """Render the JudgmentReport as Rich panels."""
    console.print()

    # Header
    content_desc = report.content_type.value.upper()
    console.print(
        Panel(
            f"[bold]CONTENT JUDGE ANALYSIS[/bold]  |  Content type: {content_desc}",
            style="blue",
        )
    )

    # AI Detection
    _render_ai_detection(report.ai_detection, verbose)

    # Virality
    _render_virality(report.virality, verbose)

    # Distribution
    _render_distribution(report.distribution, verbose)

    # Overall Assessment
    console.print(
        Panel(
            report.overall_explanation,
            title="[bold]Overall Assessment[/bold]",
            border_style="bright_blue",
        )
    )

    # Errors
    if report.has_errors():
        console.print(
            Panel(
                f"[yellow]{report.error_summary()}[/yellow]",
                title="[bold yellow]Warnings[/bold yellow]",
                border_style="yellow",
            )
        )

    # Metadata (verbose only)
    if verbose:
        meta = report.analysis_metadata
        console.print(
            f"\n[dim]Model: {meta.model_used} | Iterations: {meta.iterations} | "
            f"Succeeded: {', '.join(meta.tools_succeeded)} | "
            f"Failed: {', '.join(meta.tools_failed) or 'none'}[/dim]"
        )

    console.print()


def _render_ai_detection(result: AIDetectionResult | ToolError, verbose: bool) -> None:
    """Render AI detection panel."""
    if isinstance(result, ToolError):
        console.print(
            Panel(f"[red]Error: {result.error}[/red]", title="[bold]AI Detection[/bold]")
        )
        return

    verdict_colors = {
        AILabel.AI_GENERATED: "red",
        AILabel.LIKELY_AI_GENERATED: "yellow",
        AILabel.UNCERTAIN: "dim",
        AILabel.LIKELY_HUMAN: "cyan",
        AILabel.HUMAN: "green",
    }
    color = verdict_colors.get(result.verdict, "white")
    verdict_display = result.verdict.value.replace("_", " ").title()

    conf_bar = _render_bar(result.confidence, 20)

    lines = [
        f"Verdict: [{color} bold]{verdict_display}[/{color} bold]",
        f"Confidence: {conf_bar} {result.confidence:.0%} ({result.confidence_level.value})",
    ]

    if result.detected_generator:
        lines.append(f"Detected generator: {result.detected_generator}")

    if result.c2pa.present:
        lines.append(f"C2PA metadata: present (issuer: {result.c2pa.issuer or 'unknown'})")

    lines.append(f"\n{result.explanation}")

    if verbose and result.signals:
        lines.append("\n[dim]Signals:[/dim]")
        for s in result.signals:
            lines.append(f"  {s.signal_name}: {s.value} (conf={s.confidence:.2f}, weight={s.weight:.2f})")

    console.print(
        Panel("\n".join(lines), title="[bold]AI Detection[/bold]", border_style=color)
    )


def _render_virality(result: ViralityResult | ToolError, verbose: bool) -> None:
    """Render virality panel."""
    if isinstance(result, ToolError):
        console.print(
            Panel(f"[red]Error: {result.error}[/red]", title="[bold]Virality Score[/bold]")
        )
        return

    level_colors = {
        "very_high": "bold red",
        "high": "bold yellow",
        "moderate": "bold cyan",
        "low": "dim",
    }
    color = level_colors.get(result.virality_level, "white")
    score_bar = _render_bar(result.overall_score / 10.0, 20)

    lines = [
        f"Score: [{color}]{result.overall_score}/10[/{color}] ({result.virality_level.replace('_', ' ').title()})",
        f"       {score_bar}",
        f"Emotional tone: {result.emotional_quadrant.value.replace('_', ' ').title()}",
        f"Primary emotions: {', '.join(result.primary_emotions)}",
        f"Strengths: {', '.join(result.key_strengths)}",
        f"Weaknesses: {', '.join(result.key_weaknesses)}",
        f"\n{result.explanation}",
    ]

    if verbose:
        lines.append("\n[dim]Dimension Scores:[/dim]")
        table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        table.add_column("Dimension", width=25)
        table.add_column("Score", width=8, justify="right")
        table.add_column("Weight", width=8, justify="right")
        table.add_column("Reasoning", ratio=1)
        for d in result.dimensions:
            table.add_row(
                d.name,
                f"{d.score}/10",
                f"{d.weight:.0%}",
                d.reasoning[:80] + ("..." if len(d.reasoning) > 80 else ""),
            )
        console.print(table)

    console.print(
        Panel("\n".join(lines), title="[bold]Virality Score[/bold]", border_style="yellow")
    )


def _render_distribution(result: DistributionResult | ToolError, verbose: bool) -> None:
    """Render distribution panel."""
    if isinstance(result, ToolError):
        console.print(
            Panel(f"[red]Error: {result.error}[/red]", title="[bold]Distribution Analysis[/bold]")
        )
        return

    lines = [
        f"Topics: {', '.join(result.primary_topics)}",
        "",
        "[bold]Best-fit audiences:[/bold]",
    ]

    segments_to_show = result.audience_segments if verbose else result.audience_segments[:3]
    for seg in segments_to_show:
        fit_icon = {"strong": "[green]+[/green]", "moderate": "[yellow]~[/yellow]", "weak": "[dim]-[/dim]"}.get(
            seg.estimated_fit.value, " "
        )
        lines.append(
            f"  {fit_icon} {seg.platform.value} — {seg.community} ({seg.estimated_fit.value})"
        )
        if verbose:
            lines.append(f"    [dim]{seg.reasoning}[/dim]")

    lines.append(f"\n[bold]Strategy:[/bold] {result.distribution_strategy}")
    lines.append(f"\n{result.explanation}")

    if result.weakest_reach:
        lines.append(f"\n[dim]Would not resonate with: {', '.join(result.weakest_reach)}[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]Distribution Analysis[/bold]",
            border_style="magenta",
        )
    )


def _render_bar(fraction: float, width: int = 20) -> str:
    """Render a text-based progress bar."""
    filled = int(fraction * width)
    empty = width - filled
    return f"[green]{'█' * filled}[/green][dim]{'░' * empty}[/dim]"


if __name__ == "__main__":
    app()
