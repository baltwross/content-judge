# Presentation Documentation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Create a layered documentation set in `docs/presentation/` that walks an interviewer through the content-judge repo, emphasizing reasoning, assumptions, and decision-making.

**Architecture:** 6 markdown files in a layered structure (overview → architecture → data flow → design decisions → deep dives → assumptions). Built by a 5-agent team in 2 phases: 3 parallel research/draft agents, then 2 sequential review/polish agents.

**Output directory:** `docs/presentation/`

---

## Phase 1: Parallel Research & Draft (3 agents, run simultaneously)

### Task 1: Architecture Analyst — Draft `01-architecture.md` and `02-data-flow.md`

**Agent type:** `docs-manager`
**Files to create:**
- `docs/presentation/01-architecture.md`
- `docs/presentation/02-data-flow.md`

**Source files to read:**
- `content_judge/agent.py` — CoordinatorAgent, agentic loop, dispatch, review, synthesis
- `content_judge/models.py` — all Pydantic models, type unions, computed fields
- `content_judge/cli.py` — entry point, content loading, progress display, wizard mode
- `content_judge/llm.py` — Gemini wrappers, retry logic, structured output
- `content_judge/loaders/text.py` — text loading (string/file/URL)
- `content_judge/loaders/video.py` — video validation, YouTube URL parsing, stream resolution
- `content_judge/config.py` — settings, environment variables
- `content_judge/report.py` — markdown report rendering

**Instructions for 01-architecture.md:**

Write a system architecture document with these sections:

1. **System Overview** (3-4 sentences) — what Content Judge is, what it produces, the core architectural pattern (coordinator agent + parallel tools)

2. **Component Map** — Mermaid diagram showing all components and their relationships:
   - CLI layer (Typer + Rich)
   - Content loaders (text loader, video loader)
   - CoordinatorAgent (the agentic core)
   - 3 analysis tools (AI Detection, Virality, Distribution)
   - LLM layer (Gemini wrappers)
   - External services (Gemini API, Hive API, yt-dlp)
   - Report renderer
   - Use `graph TD` style with labeled edges showing what flows between components

3. **The Agentic Loop** — Mermaid sequence diagram showing:
   - CLI creates ContentInput → passes to CoordinatorAgent.run()
   - Video pre-processing (if video): call_gemini_video for description
   - Dispatch: parallel (text) or sequential (video) tool execution
   - Review: coordinator calls Gemini to review results → decision to accept or re-run
   - Re-dispatch: only failed/low-confidence tools re-run
   - Synthesis: coordinator calls Gemini for overall explanation
   - Return JudgmentReport
   - Show the max 3 iteration bound

4. **Key Architectural Properties:**
   - Single LLM provider (Gemini) — one SDK, one error path
   - Tool independence — each tool analyzes content independently, no cross-tool data flow
   - Graceful degradation — ToolError union types, partial reports
   - Parallel execution — ThreadPoolExecutor for text, sequential for video (token quota)

5. **Module Responsibility Table** — table with columns: Module | Responsibility | Key Classes/Functions

**Instructions for 02-data-flow.md:**

Write a data flow document with these sections:

1. **Input Processing** — Mermaid flowchart showing:
   - Raw CLI input → `_load_content()` routing logic
   - Text path: string detection → file detection → URL detection → `load_text()`
   - Video path: `--video` flag → `validate_video_url()` → YouTube vs local file
   - Wizard mode: no args → `_run_wizard()` → InquirerPy prompts → auto-detect video
   - All paths produce `ContentInput` model

2. **ContentInput Model** — show the fields and derived flags (has_text, has_video, text_length, is_short_text) with a note about model_post_init

3. **Tool Execution Flow** — Mermaid diagram showing:
   - Text path: ContentInput → ThreadPoolExecutor → 3 parallel Gemini calls → ToolResults
   - Video path: ContentInput → sequential execution (token quota) → ToolResults
   - Each tool's input (ContentInput) and output (specific Result model or ToolError)
   - Show the union types: `AIDetectionResult | ToolError`

4. **Video Pipeline Detail** — Mermaid sequence diagram showing:
   - YouTube URL → Gemini (direct URL) for virality/distribution
   - YouTube URL → yt-dlp stream resolution → Hive URL submission (fails with 400)
   - YouTube URL → yt-dlp 30s clip download (720p, 5-35s) → Hive file upload
   - Local file → Gemini File API upload → analysis
   - Local file → Hive direct file upload
   - Show fallback paths

5. **Output Pipeline** — how JudgmentReport flows to:
   - `--json` → `report.to_json()` → stdout
   - Default → `_render_report()` → Rich panels
   - Always → `render_markdown()` → `.md` file
   - Show that all three are different renderings of the same JudgmentReport model

**Verification:** Read both files. Confirm all Mermaid diagrams use valid syntax. Confirm no component or data path is missing.

---

### Task 2: Decision Curator — Draft `03-design-decisions.md` and `05-assumptions-and-tradeoffs.md`

**Agent type:** `docs-manager`
**Files to create:**
- `docs/presentation/03-design-decisions.md`
- `docs/presentation/05-assumptions-and-tradeoffs.md`

**Source files to read:**
- `docs/decisions/key-decisions.md` — all detailed decisions (AD-1 through AD-8, VS-1 through VS-8, DA-1 through DA-10, SI-1 through SI-10)
- `docs/design-decisions.md` — additional design decisions
- `docs/archived/ai-vs-human-content-detection.md` — AI detection research
- `docs/archived/virality-prediction-audience-analysis.md` — virality research
- `docs/research/hive-video-detection.md` — Hive research
- `docs/research/youtube-to-hive-bridge.md` — YouTube-to-Hive bridge research
- `README.md` — assumptions section

**Instructions for 03-design-decisions.md:**

This is the most important document for the interview. Organize by THEME, not chronologically. Each decision should read as a narrative: context → options considered → decision → reasoning → what it means in practice.

Sections:

1. **Why a Single LLM Provider** — Gemini as sole LLM. Why not multi-provider? How this simplified the build. The tradeoff (vendor lock-in vs. complexity reduction). Note: Gemini chosen specifically for native video input (YouTube URLs direct, File API for local).

2. **The Coordinator Pattern** — Why an agentic loop instead of a simple pipeline? What makes it "genuinely agentic" (review + selective re-run). Why bounded to 3 iterations. What triggers re-runs (low confidence, contradictions) and what doesn't (low scores, niche results). The difference between this and a basic sequential pipeline.

3. **Right Tool for the Right Job: Hive for Video Detection** — Why not use the LLM for video AI detection? The 30-60% (VLM) vs 96-99% (Hive) accuracy gap. Why Hive is optional, not required. The graceful degradation when Hive isn't configured. The YouTube-to-Hive bridge (yt-dlp stream URL → 400 error → clip download fallback).

4. **Research-Grounded Virality Scoring** — Why a 7-dimension rubric instead of a single score? The research basis (Berger & Milkman 2012, STEPPS, SUCCES). Why "virality potential" not "virality prediction". Why computed overall_score (prevents LLM gaming). Why 5-anchor BARS. Why timing was removed as a dimension.

5. **Structured Output as Architecture** — How Gemini's constrained JSON decoding + Pydantic models create a compile-time-like guarantee. Why temperature=0 everywhere. Why the LLM schema excludes computed fields. How ToolError union types enable graceful degradation.

6. **Parallel vs Sequential Execution** — Why text runs parallel (small token footprint) and video runs sequential (100K+ tokens per call). The ThreadPoolExecutor choice over async/await.

**Style guide:** Each section should be 150-300 words. Lead with the decision, then explain why. Include "alternatives rejected" where relevant. Use direct, confident language — this is a presentation document, not hedged analysis. Include a brief Mermaid diagram where it clarifies the concept (e.g., the coordinator loop, the Hive fallback chain).

**Instructions for 05-assumptions-and-tradeoffs.md:**

Sections:

1. **Explicit Assumptions** — Pull from README assumptions section + key decisions. Format as a table: Assumption | Implication | What Would Change It. Cover: AI-generated means fully synthetic, virality assessed not predicted, short text unreliable, video detection commercially solved, English only, single LLM provider.

2. **Known Limitations** — What the system can't do and why. Be honest. Short text accuracy, non-English content, non-YouTube video platforms, no real-time trend data, no engagement history.

3. **What Would Improve With More Time** — Audio analysis, evaluation harness, web UI, caching, multi-language. For each: what it would add and why it wasn't included in the time-boxed build.

4. **Tradeoffs I'd Revisit** — 2-3 decisions that were right for a 6-hour build but might change at scale. E.g., single LLM provider, sync over async, Hive as optional.

**Verification:** Read both files. Confirm decisions reference specific code or research. Confirm no decision from key-decisions.md is contradicted.

---

### Task 3: Tool Deep-Diver — Draft `04-deep-dives.md` ✅ COMPLETED

**Agent type:** `docs-manager`
**Files to create:**
- `docs/presentation/04-deep-dives.md`

**Source files to read:**
- `content_judge/tools/ai_detection.py` — full detection pipeline
- `content_judge/tools/virality.py` — virality scoring
- `content_judge/tools/distribution.py` — distribution analysis
- `content_judge/tools/hive_client.py` — Hive API client
- `content_judge/prompts.py` — all system prompts
- `content_judge/models.py` — all data models
- `content_judge/llm.py` — LLM wrappers

**Instructions for 04-deep-dives.md:**

Organized as three self-contained sections, each covering one analysis tool. For each tool, cover:

**Section 1: AI Detection Deep Dive**
- **Signal Architecture** — the 5 text signals and 5 video signals with descriptions. Why these specific signals (research basis: EMNLP 2025, Chiang & Lee 2023). Why signal independence matters (mixed evidence is informative).
- **Multi-Source Aggregation** — Mermaid flowchart showing the signal priority chain: C2PA check → Hive API (if video + configured) → Gemini text analysis → weighted aggregation → verdict mapping. Show the confidence thresholds (>0.7 = ai_generated, 0.55-0.7 = likely_ai, etc.)
- **Confidence Calibration** — the capping rules: short text caps at MODERATE, text-only caps at HIGH, multiple sources allow VERY_HIGH. Why this exists (false positive harm > false negative harm).
- **Hive Integration Detail** — The V3 endpoint, per-frame analysis (1 FPS), max-aggregation strategy, 70+ generator recognition. The YouTube bridge: stream URL attempt → 400 → clip download (30s, 720p, 5-35s offset) → upload.
- **Honest Framing** — Decision AD-4: "analysis suggests" not "verified". Why hedged language is both more ethical and more accurate.

**Section 2: Virality Scoring Deep Dive**
- **The 7-Dimension Rubric** — Table showing all 7 dimensions with weights, research grounding, and what the 1 and 10 anchors look like. Note the counter-bias instructions in each dimension prompt.
- **Prompt Engineering** — How the VIRALITY_SYSTEM_PROMPT is structured: framing caveat → dimension definitions → BARS anchors → emotional quadrant → output schema. Why 5-anchor BARS over 3-anchor (25%+ reduction in score clustering).
- **Computed vs LLM-Supplied Fields** — The ViralityLLMOutput → ViralityResult transformation. Why overall_score is @computed_field (prevents LLM gaming the aggregate). How weights are re-applied after LLM output (dim.weight = VIRALITY_DIMENSION_WEIGHTS[dim.dimension_id]).
- **Single Code Path** — How `run_virality()` handles both text and video with the same function, branching only on prompt construction and whether to pass video_source.

**Section 3: Distribution Analysis Deep Dive**
- **Three-Layer Framework** — Topic classification (18-category IAB adaptation) → Platform-audience mapping (9 platforms) → Resonance reasoning. Why forcing this sequence prevents "post it on TikTok" without justification.
- **Platform Knowledge** — The 9 platforms and their community taxonomies embedded in the prompt. Why Facebook was excluded. Why Newsletter/Podcast/Blog were included (owned media matters).
- **Tool Independence** — Decision DA-10: distribution does not receive AI detection results. The coordinator handles cross-tool synthesis. Why this preserves clean architecture.
- **Output Model** — DistributionResult fields: primary_topics, audience_segments (2-5), strongest_fit (duplicates segments[0] for ergonomics), weakest_reach (required — forces discrimination), distribution_strategy, explanation.

**Verification:** Read the file. Confirm all signal names match the actual code. Confirm all thresholds match the actual code. Confirm Mermaid diagrams are valid.

---

## Phase 2: Sequential Review & Polish

### Task 4: Consistency Reviewer — Review and edit all 5 documents

**Agent type:** `superpowers:code-reviewer`
**Files to read and edit:**
- `docs/presentation/01-architecture.md`
- `docs/presentation/02-data-flow.md`
- `docs/presentation/03-design-decisions.md`
- `docs/presentation/04-deep-dives.md`
- `docs/presentation/05-assumptions-and-tradeoffs.md`

**Also read for fact-checking:**
- `content_judge/agent.py`
- `content_judge/models.py`
- `content_judge/tools/ai_detection.py`
- `content_judge/prompts.py`

**Review checklist:**
1. **Cross-reference accuracy** — Do architecture diagrams match actual code? Do data flow descriptions match actual model fields? Do decision descriptions match actual implementation?
2. **Terminology consistency** — Same terms used across all docs (e.g., "CoordinatorAgent" not sometimes "Coordinator" and sometimes "Agent"). Same formatting for model names, function names, file paths.
3. **No contradictions** — If 01 says "parallel execution" and 04 says "sequential for video", both must explain the distinction. No doc should contradict another.
4. **No redundancy** — If a concept is explained in detail in 04, docs 01-03 should reference it, not re-explain it. Cross-link with relative markdown links.
5. **Layered navigation** — 01 should be readable without 04. 04 should be readable without 01. But each should reference the other where relevant. Add "See [Architecture](01-architecture.md)" style links.
6. **Mermaid validation** — All diagrams use valid Mermaid syntax (graph TD, sequenceDiagram, flowchart LR, etc.). No broken arrows or undefined nodes.
7. **Interview readiness** — Each doc should have clear sections the interviewer can ask "tell me more about X" and the candidate can drill into. Decisions should be stated confidently with reasoning, not hedged.

**Output:** Edit each file in place with fixes. Add cross-reference links between documents.

---

### Task 5: Overview Writer — Create `00-overview.md`

**Agent type:** `docs-manager`
**Files to create:**
- `docs/presentation/00-overview.md`

**Files to read:**
- All 5 reviewed documents from Task 4
- `README.md`

**Instructions:**

Write the overview as a 2-minute read that serves as the entry point to the documentation set. Sections:

1. **What is Content Judge?** (3-4 sentences) — An AI-powered content analysis agent. Evaluates text and video across three dimensions. Built as a genuinely agentic system (not a simple pipeline). Produces structured, explainable reports.

2. **What does it produce?** — Brief description of the three analyses (AI detection, virality potential, distribution fit) with one sentence each on what makes each interesting (e.g., "virality scoring uses a research-grounded 7-dimension rubric, not LLM intuition").

3. **How does it work?** — 4-5 sentence summary of the architecture: CLI input → content loader → coordinator agent → parallel tool dispatch → review loop → synthesis → report. Link to [Architecture](01-architecture.md) for details.

4. **Key Design Principles** — Bullet list of 4-5 principles with one-line descriptions:
   - Single LLM provider (simplicity over flexibility)
   - Right tool for the right job (Hive for video detection, Gemini for everything else)
   - Research-grounded scoring (Berger & Milkman, STEPPS, SUCCES)
   - Graceful degradation (partial results > total failure)
   - Structured output as architecture (Pydantic + Gemini JSON mode)

5. **Documentation Guide** — Table linking to each doc with a one-sentence description:
   | Document | What it covers |
   | [Architecture](01-architecture.md) | System components, agentic loop, module responsibilities |
   | [Data Flow](02-data-flow.md) | How content moves through the system, text vs video paths |
   | [Design Decisions](03-design-decisions.md) | Key decisions with reasoning and alternatives rejected |
   | [Deep Dives](04-deep-dives.md) | Detailed analysis of each tool: signals, prompts, scoring |
   | [Assumptions & Tradeoffs](05-assumptions-and-tradeoffs.md) | What was assumed, what would change, what to revisit |

6. **Quick Start** — 3-line code block showing basic usage (`pip install`, `content-judge "text"`, `content-judge --video URL`)

**Verification:** Read the file. Confirm all links point to real files. Confirm the overview accurately reflects the content of the detailed docs.

---

## Task 6: Final commit

**Step 1:** Verify all 6 files exist in `docs/presentation/`
```bash
ls -la docs/presentation/
```

**Step 2:** Commit
```bash
git add docs/presentation/
git commit -m "docs: add presentation walkthrough documentation for technical interview"
```
