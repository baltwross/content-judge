# Interactive Wizard Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an interactive wizard that launches when `content-judge` is run with no arguments, walking the user through content input and model selection before running analysis and auto-saving a markdown report.

**Architecture:** Add InquirerPy dependency for interactive prompts. Modify the CLI entry point so a missing `input` argument triggers a wizard flow (`_run_wizard()`). The wizard collects input and model, then delegates to the existing `_run_with_progress()` and `render_markdown()` code paths. Always auto-save markdown reports regardless of mode.

**Tech Stack:** InquirerPy (interactive prompts), Typer (CLI framework), Rich (output rendering)

---

### Task 1: Add InquirerPy dependency

**Files:**
- Modify: `pyproject.toml:11` (dependencies list)

**Step 1: Add InquirerPy to dependencies**

In `pyproject.toml`, add `"InquirerPy>=0.3.4"` to the `dependencies` list:

```toml
dependencies = [
    "google-genai>=1.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "httpx>=0.27.0",
    "requests>=2.31.0",
    "yt-dlp>=2024.0.0",
    "python-dotenv>=1.0.0",
    "InquirerPy>=0.3.4",
]
```

**Step 2: Reinstall**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: InquirerPy installs successfully

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add InquirerPy dependency for interactive wizard"
```

---

### Task 2: Add AVAILABLE_MODELS to config

**Files:**
- Modify: `content_judge/config.py`
- Test: `tests/test_config_models.py` (create)

**Step 1: Write the failing test**

Create `tests/test_config_models.py`:

```python
"""Tests for config model list."""

from content_judge.config import AVAILABLE_MODELS


def test_available_models_is_list():
    assert isinstance(AVAILABLE_MODELS, list)
    assert len(AVAILABLE_MODELS) >= 2


def test_default_model_is_first():
    """The default model should be the first in the list."""
    from content_judge.config import Settings
    settings_default = Settings.__fields__["default_model"].default
    assert AVAILABLE_MODELS[0] == settings_default
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_config_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'AVAILABLE_MODELS'`

**Step 3: Write minimal implementation**

Add to `content_judge/config.py` after the imports, before the `Settings` class:

```python
AVAILABLE_MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_config_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add content_judge/config.py tests/test_config_models.py
git commit -m "feat: add AVAILABLE_MODELS list to config"
```

---

### Task 3: Add auto-detect helper for content type

**Files:**
- Modify: `content_judge/cli.py`
- Test: `tests/test_cli_wizard.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_cli_wizard.py`:

```python
"""Tests for the interactive wizard helpers."""

import pytest


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
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_cli_wizard.py -v`
Expected: FAIL with `ImportError: cannot import name '_detect_is_video'`

**Step 3: Write minimal implementation**

Add this function to `content_judge/cli.py` after the `_load_content` function:

```python
def _detect_is_video(raw_input: str) -> bool:
    """Auto-detect whether input is a video source."""
    from content_judge.loaders import is_youtube_url
    from content_judge.loaders.video import SUPPORTED_VIDEO_FORMATS
    from pathlib import Path

    if is_youtube_url(raw_input):
        return True

    ext = Path(raw_input).suffix.lower()
    if ext in SUPPORTED_VIDEO_FORMATS:
        return True

    return False
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_cli_wizard.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add content_judge/cli.py tests/test_cli_wizard.py
git commit -m "feat: add _detect_is_video helper for wizard auto-detection"
```

---

### Task 4: Implement the wizard flow

**Files:**
- Modify: `content_judge/cli.py` (add `_run_wizard`, modify `judge` command)

**Step 1: Add the `_run_wizard` function**

Add this function to `content_judge/cli.py` before the `judge` function:

```python
def _run_wizard() -> tuple[str, bool, str]:
    """
    Interactive wizard flow. Returns (input_value, is_video, model).
    """
    from InquirerPy import inquirer
    from content_judge.config import AVAILABLE_MODELS

    console.print(
        Panel(
            "[bold]Content Judge[/bold] — Interactive Analysis",
            style="blue",
        )
    )

    raw_input = inquirer.text(
        message="Enter content to analyze (URL, file path, or text):",
        validate=lambda val: len(val.strip()) > 0,
        invalid_message="Input cannot be empty.",
    ).execute()

    is_video = _detect_is_video(raw_input)
    if is_video:
        console.print(f"[dim]Detected as video input[/dim]")
    else:
        console.print(f"[dim]Detected as text input[/dim]")

    model = inquirer.select(
        message="Select model:",
        choices=AVAILABLE_MODELS,
        default=AVAILABLE_MODELS[0],
    ).execute()

    return raw_input.strip(), is_video, model
```

**Step 2: Modify the `judge` command to support wizard mode**

Change the `judge` function signature so `input` is optional:

```python
@app.command()
def judge(
    input: str = typer.Argument(
        None, help="Text, file path, URL, or video path to analyze."
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

    # Wizard mode when no input provided
    wizard_mode = input is None
    if wizard_mode:
        input, video, model_choice = _run_wizard()
        model = model_choice
        verbose = True  # verbose by default in wizard mode

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
        from content_judge.agent import CoordinatorAgent
        agent = CoordinatorAgent(model=effective_model)
        result = agent.run(content)
        typer.echo(result.to_json())
        return

    result = _run_with_progress(content, effective_model)

    # Render Rich output
    _render_report(result, verbose)

    # Always save markdown report
    from datetime import datetime
    from content_judge.report import render_markdown
    md = render_markdown(result)
    out = report_path or f"report-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.md"
    Path(out).write_text(md, encoding="utf-8")
    console.print(f"\n[bold green]Report saved to[/bold green] {out}")
```

**Step 3: Run existing tests to verify nothing is broken**

Run: `source .venv/bin/activate && pytest tests/ -v`
Expected: All existing tests PASS

**Step 4: Manually test wizard mode**

Run: `source .venv/bin/activate && content-judge`
Expected: Interactive prompts appear (content input, model selection)

**Step 5: Commit**

```bash
git add content_judge/cli.py
git commit -m "feat: add interactive wizard mode for content-judge"
```

---

### Task 5: Final integration test

**Step 1: Run full test suite**

Run: `source .venv/bin/activate && pytest tests/ -v`
Expected: All tests PASS

**Step 2: Test flag-based mode still works and saves report**

Run: `source .venv/bin/activate && content-judge "Test text for analysis" 2>&1 | head -5`
Expected: Rich output appears AND a `report-*.md` file is created in current directory

**Step 3: Clean up and final commit if needed**

```bash
git status
# If any uncommitted changes remain, commit them
```
