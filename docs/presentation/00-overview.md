# Content Judge — Overview

Content Judge is an AI-powered content analysis agent that evaluates text and video across three dimensions: AI detection, virality potential, and audience distribution fit. It is built as a genuinely agentic system — the `CoordinatorAgent` dispatches three independent analysis tools, reviews their results via Gemini, selectively re-runs tools that need refinement (bounded to 3 iterations), and synthesizes a final report. Every analysis produces structured, explainable output: scored dimensions with reasoning, not opaque verdicts.

## What It Produces

**AI Detection** — Multi-source signal aggregation, not a single-verdict prompt. Combines Gemini text analysis (5 independent linguistic signals), Hive API for video (96-99% accuracy across 100+ generators), and C2PA content credentials. Signals are weighted and aggregated into a 5-level verdict from `human` to `ai_generated` with calibrated confidence.

**Virality Potential** — A 7-dimension weighted rubric grounded in Berger & Milkman (2012), STEPPS, and SUCCES frameworks. Each dimension has 5-anchor BARS (Behaviorally Anchored Rating Scales) to reduce LLM score clustering. The overall score is computed deterministically from dimension weights — the LLM scores individual dimensions, the code enforces the math.

**Distribution Analysis** — A 3-layer framework: topic classification (18-category IAB-adapted taxonomy) to platform-audience mapping (9 platforms, community-specific) to resonance reasoning (vocabulary match, value alignment, format fit, engagement hook). Forces justified recommendations by requiring the LLM to explain *why* content fits each community.

## How It Works

The CLI accepts text (string, file, URL) or video (YouTube URL, local file) and constructs a `ContentInput`. The `CoordinatorAgent` dispatches all three analysis tools — in parallel for text via `ThreadPoolExecutor`, sequentially for video to stay within Gemini's token-per-minute quota. After dispatch, a Gemini-powered review step evaluates result quality and can selectively re-run flagged tools (low confidence, internal contradictions, transient errors). Once all results pass review, a synthesis step produces a 3-5 sentence explanation reconciling findings across tools. The final `JudgmentReport` renders to Rich terminal panels, JSON (for piping), and a saved markdown report.

See [Architecture](01-architecture.md) for the full component map, agentic loop sequence diagram, and module responsibility table.

## Key Design Principles

- **Single LLM provider** — Gemini for everything: one SDK, one error path, chosen for native video input and structured JSON output via constrained decoding
- **Right tool for the right job** — Hive (96-99% accuracy) for video AI detection, Gemini for analysis and scoring; VLMs at 30-60% accuracy are not acceptable for detection claims
- **Research-grounded scoring** — Berger & Milkman, STEPPS, SUCCES frameworks with 5-anchor BARS rubrics and per-dimension counter-bias instructions
- **Graceful degradation** — `ToolError` union types mean partial results always beat total failure; Hive is optional, C2PA is optional, every tool can fail independently
- **Structured output as architecture** — Pydantic models + Gemini JSON mode (`response_mime_type="application/json"` + `response_schema`) = schema-level guarantees with zero parsing errors

See [Design Decisions](03-design-decisions.md) for the full reasoning behind each principle, alternatives rejected, and code references.

## Documentation Guide

| Document | What It Covers |
|----------|---------------|
| [Architecture](01-architecture.md) | System components, agentic loop sequence diagram, module responsibilities |
| [Data Flow](02-data-flow.md) | How content moves through the system — text vs video paths, input/output pipelines |
| [Design Decisions](03-design-decisions.md) | Key decisions with reasoning, alternatives rejected, and implementation references |
| [Deep Dives](04-deep-dives.md) | Signal architectures, prompt engineering, scoring mechanics for each analysis tool |
| [Assumptions & Tradeoffs](05-assumptions-and-tradeoffs.md) | What was assumed, known limitations, what would change with more time |

## Quick Start

```bash
pip install -e ".[dev]"
content-judge "Some text to analyze"
content-judge --video "https://www.youtube.com/watch?v=..."
content-judge  # interactive wizard mode
```
