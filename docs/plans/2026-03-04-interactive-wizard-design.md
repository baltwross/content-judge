# Interactive Wizard Mode Design

**Date:** 2026-03-04
**Status:** Approved

## Problem

Running an analysis requires remembering flags and argument order. A step-by-step interactive flow would make the tool more approachable.

## Design

### Entry Point

- `content-judge` with no arguments → launches interactive wizard
- `content-judge --video "url"` (with arguments) → works as today, but always saves a markdown report

The Typer `input` argument becomes `Optional[str] = None`. When `None`, wizard mode activates.

### Wizard Steps

1. **Content input** — InquirerPy `text` prompt asking for a URL, file path, or raw text. Auto-detects video vs text from the input (YouTube URLs and video file extensions trigger video mode).
2. **Model selection** — InquirerPy `list` prompt with arrow-key navigation. Default: `gemini-3.1-pro-preview`. Options: `gemini-2.5-pro`, `gemini-2.5-flash`.
3. **Run analysis** — Existing Rich progress spinner. Display verbose Rich output.
4. **Auto-save report** — Always write markdown report to `report-YYYY-MM-DD-HHMMSS.md`. Print path.

### Auto-detection Logic

| Input pattern | Mode |
|---------------|------|
| YouTube URL (`youtube.com`, `youtu.be`) | video |
| File with video extension (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.wmv`) | video |
| File with `.txt` extension or existing file | text (file) |
| HTTP(S) URL (non-YouTube) | text (URL) |
| Everything else | text (literal) |

### Always-generate Reports

Both wizard mode and flag-based mode now always save a markdown report. The `--report` flag becomes a no-op (kept for backwards compat). `--report-path` still overrides the output path.

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Add `InquirerPy` to dependencies |
| `content_judge/cli.py` | Make `input` optional, add `_run_wizard()`, always generate report |
| `content_judge/config.py` | Add `AVAILABLE_MODELS` list |

No changes to agent, tools, report renderer, or models.
