# Content Judge Agent

An AI-powered content analysis agent that evaluates text and video content across three dimensions: AI detection, virality potential, and audience distribution fit. Built as an agentic system using Gemini as the sole LLM provider with an optional Hive API integration for high-accuracy AI video detection.

## Quick Start

If you're trying this from the public GitHub repo, the easiest path is the interactive wizard:

1. Run `content-judge`
2. Paste a YouTube URL, type text, or drag and drop a local file into the prompt
3. Select one of the 3 Gemini models
4. Press `Enter`
5. Wait for analysis to finish
6. Open the generated `report-*.md` file

If you run the command from the repo root, the markdown report is written to the repo root.

## How to Run

### Prerequisites

- Python 3.11+
- A [Gemini API key](https://aistudio.google.com/apikey) (required)
- A [Hive API key](https://thehive.ai/) (optional — enables 96-99% accurate AI video detection)

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd content-judge

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the CLI
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (required)
```

Optional:

- Add `HIVE_API_KEY` to `.env` to enable high-accuracy AI video detection
- Install dev dependencies with `pip install -e ".[dev]"` if you want to run tests

### Usage

```bash
# Recommended: interactive wizard mode
content-judge

# In the wizard, you can:
# - paste a YouTube URL
# - drag and drop a local video file
# - paste text directly
```

### Wizard Behavior

- You do not need `--video` in wizard mode for YouTube URLs or common local video files; the CLI auto-detects them
- The model picker currently offers 3 choices:
  - `gemini-3.1-pro-preview` (default)
  - `gemini-2.5-pro`
  - `gemini-2.5-flash`
- Every run writes a markdown report named `report-YYYY-MM-DD-HHMMSS.md`
- `--report-path` lets you override where that markdown report is written

Example wizard flow:

```text
$ content-judge
Enter content to analyze (URL, file path, or text): https://www.youtube.com/watch?v=...
Detected as video input
Select model: gemini-3.1-pro-preview
...
Report saved to report-2026-03-05-184328.md
```

### Direct CLI Examples

```bash
# Analyze a text string directly
content-judge "The discovery of a hidden Roman city beneath Naples shocked archaeologists today"

# Analyze a text file
content-judge ./article.txt

# Analyze a URL
content-judge https://example.com/article

# Analyze a YouTube video
content-judge --video "https://www.youtube.com/watch?v=..."

# Analyze a local video file
content-judge --video ./clip.mp4

# Get JSON output for scripting
content-judge --json "Some text" | python -m json.tool

# Verbose analysis with all dimension scores
content-judge --verbose "Some text"

# Use a different Gemini model
content-judge --model gemini-2.5-pro "Some text"

# Enable debug logging (shows Hive frame scores, yt-dlp details, etc.)
content-judge --debug --video "https://www.youtube.com/watch?v=..."

# Save the markdown report to a specific path
content-judge --report-path ./reports/latest.md "Some text"
```

### Running Tests

```bash
pytest tests/ -v
```

## Architecture

```
                      ┌─────────────────────┐
                      │   CLI (Typer+Rich)   │
                      │  content-judge <in>  │
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │   Content Loader     │
                      │  text: str/file/URL  │
                      │  video: file or YT   │
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │  Coordinator Agent   │
                      │  (agentic loop, ≤3)  │
                      └──────────┬──────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
┌──────────▼──────────┐ ┌───────▼────────┐ ┌─────────▼─────────┐
│   AI Detection      │ │   Virality     │ │   Distribution    │
│                     │ │   Scoring      │ │   Analysis        │
│ • Gemini (text)     │ │ • 7-dimension  │ │ • 3-layer:        │
│ • Hive API (video)  │ │   rubric via   │ │   topic→platform  │
│ • C2PA (optional)   │ │   Gemini       │ │   →resonance      │
└──────────┬──────────┘ └───────┬────────┘ └─────────┬─────────┘
           └─────────────────────┼─────────────────────┘
                                 │
                      ┌──────────▼──────────┐
                      │  Synthesis → Report  │
                      └─────────────────────┘
```

The coordinator is genuinely agentic — it dispatches all three tools in parallel, reviews results, and can re-run tools if confidence is too low or results are contradictory (bounded to 3 iterations max).

### Key Design Decisions

- **Gemini as sole LLM provider.** All analysis tasks (virality, distribution, AI detection text analysis, synthesis) use Gemini with structured JSON output. This eliminates multi-SDK complexity and ensures the video analysis pipeline is unified.
- **Hive for video AI detection.** Hive Moderation API achieves 96-99% accuracy on AI-generated video detection across 100+ generators. When configured, it's the primary video detection signal. For YouTube, yt-dlp downloads a 30-second clip at 720p and uploads it to Hive. The response parser aggregates across all frames (max ai_score) and identifies the specific AI generator from 70+ recognized classes.
- **Research-grounded virality rubric.** The 7-dimension scoring rubric is grounded in Berger & Milkman (2012) empirical findings, the STEPPS framework, and the SUCCES framework. Each dimension has explicit BARS anchors (1/3/5/7/10) to reduce score clustering.
- **3-layer distribution framework.** Topic classification (18 categories from IAB taxonomy) → platform-audience mapping (9 platforms) → resonance reasoning. Produces actionable distribution strategy, not generic audience labels.
- **Parallel tool execution.** All three analysis tools run concurrently via `ThreadPoolExecutor`, so total time is bounded by the slowest tool, not the sum.
- **Graceful degradation.** If any tool fails, the report is still produced with available results and explicit error notes.

### Supported Video Inputs

- **YouTube URLs** — Gemini analyzes the video directly via URL; Hive detects via yt-dlp 30s clip download (720p, 5-35s offset) + upload
- **Local video files** (.mp4, .mov, .avi, .mkv, .webm, .wmv) — Gemini via File API upload; Hive via direct upload
- Other video platforms (Vimeo, Dailymotion, etc.) are **not supported** — download the video and pass the local file path instead

## Assumptions

- **"AI-generated" means fully synthetic.** The system asks "was this made by AI?", not "did AI assist?" Human-AI collaborative content (e.g., AI draft with human edits) is a known gray zone — the system returns probability scores rather than binary labels to handle it.
- **Virality can be assessed, not predicted.** Even the best ML systems with real engagement data explain only ~50% of variance in sharing. The system scores content features empirically correlated with sharing (Berger & Milkman 2012, STEPPS, SUCCES) and labels output "virality potential," not "virality prediction."
- **Short text is unreliable for AI detection.** All commercial detectors lose 10-15% accuracy below 200 words. The system caps confidence for short text accordingly (e.g., under 50 words caps at LOW).
- **Video AI detection is commercially solved.** VLMs achieve 30-60% accuracy on AI video detection; Hive achieves 96-99%. The system uses the purpose-built tool for detection and the LLM for explanation, not the reverse.
- **English content only.** All prompts, rubrics, and analysis are English-optimized. Non-English content will produce degraded results.
- **Single LLM provider for a time-boxed build.** One SDK, one API key, one error-handling path. Gemini was chosen specifically for native video input (YouTube URLs direct, local files via File API) and structured JSON output.

## What Would Improve With More Time

- **Audio analysis** — Dedicated audio feature extraction (speech cadence, music energy, audio quality) as separate signals
- **Evaluation harness** — Systematic calibration against ground truth engagement data to tune dimension weights and score thresholds
- **Web UI** — Interactive dashboard for batch analysis with visualization of score distributions
- **Caching** — Cache Gemini File API uploads and analysis results to avoid redundant API calls
- **Multi-language support** — Current prompts and analysis are English-optimized
