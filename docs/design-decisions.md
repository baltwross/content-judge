# Design Decisions

How and why the system works the way it does.

---

## Architecture: Agentic Coordinator + Parallel Tools

The system uses a coordinator agent that dispatches three analysis tools in parallel via `ThreadPoolExecutor`, reviews results, and can re-run tools if confidence is too low (max 3 iterations). This is more than a static pipeline — the coordinator makes runtime decisions about whether results need refinement.

**Why parallel, not sequential:** Each tool makes independent Gemini API calls. Running them concurrently means total time equals the slowest tool, not the sum. For a system making 4-5 API calls per analysis, this matters.

**Why graceful degradation:** If any tool fails (API timeout, rate limit), the report is still produced with available results and explicit error notes. Partial results are more useful than a crash.

---

## Model Strategy: Gemini Only + Hive for Video Detection

**Decision:** Gemini 2.5 Flash is the sole LLM for all tasks. Hive Moderation API handles video AI detection.

**Why not two LLM providers:** An earlier design used both Gemini and Claude. This meant two SDKs, two API keys, two retry strategies, two structured output formats. For a 6-hour build, one provider is simpler. Gemini handles text analysis, video analysis, structured output, and synthesis equally well.

**Why Hive for video AI detection:** VLMs achieve 30-60% accuracy detecting AI-generated video. Hive achieves 96-99% across 100+ generators (Sora, Runway, Pika, Kling, Flux, etc.). Using the right tool for the job -- no point layering a weak LLM signal on top of a near-perfect purpose-built detector. For YouTube, yt-dlp downloads a 30-second clip at 720p (starting at 5s to skip title cards) and uploads it to Hive.

**Why Gemini specifically:** Native video input (YouTube URLs directly, local files via File API). Structured JSON output via `response_schema`. This means virality and distribution tools can analyze the actual video content — not a text description of it.

---

## AI Detection: Multi-Signal Ensemble

**Approach:** Combine multiple detection signals rather than relying on any single method.

- **Text content:** Gemini scores 5 rubric signals (vocabulary uniformity, burstiness, hedging frequency, formulaic patterns, tonal uniformity). Each signal 0.0-1.0, higher = more AI-like.
- **Video content:** Hive API is the primary signal (96-99% accuracy). Gemini provides supplementary text analysis of a video description.
- **C2PA metadata:** Checked opportunistically when present — content provenance standards are reliable when available but rarely present.

**Signal aggregation:** Hive analyzes video at ~1 frame per second and returns per-frame scores. The parser aggregates across ALL frames using max ai_score (per Hive's documented guidance: "if any frame scores >= 0.9, flag as AI-generated"). When Hive's aggregated confidence > 0.9, trust Hive. Otherwise, weighted average across all available signals. The parser also identifies the specific AI generator from 70+ recognized classes (e.g., flux, sora, midjourney). 5-level verdict scale (ai_generated -> likely_ai -> uncertain -> likely_human -> human) rather than binary, because honest uncertainty is more useful than forced confidence.

**Confidence capping:** Short text (< 200 chars) caps at "moderate" regardless of signals — there simply isn't enough content to be confident. Single-source analysis caps at "high." Only multi-source corroboration allows "very high."

---

## Virality Scoring: Research-Grounded 7-Dimension Rubric

**The problem with naive virality scoring:** Asking an LLM to "rate virality 1-10" produces arbitrary numbers. The score needs grounding in empirical research to be defensible.

**The framework:** 7 dimensions synthesized from Berger & Milkman (2012), the STEPPS framework, and the SUCCES framework:

| Dimension | Weight | Grounding |
|-----------|--------|-----------|
| Emotional Arousal | 20% | Berger & Milkman 2012 — strongest empirical predictor |
| Practical Value | 15% | STEPPS "Practical Value" |
| Narrative Quality | 15% | STEPPS + SUCCES "Stories" |
| Social Currency | 15% | STEPPS "Social Currency" |
| Novelty/Surprise | 15% | SUCCES "Unexpected" |
| Clarity/Accessibility | 10% | SUCCES "Simple" + "Concrete" |
| Discussion Potential | 10% | Social contagion research |

**Key insight:** The strongest predictor of sharing is emotional arousal, not sentiment. Anger and awe both drive sharing. Sadness suppresses it. This is why Emotional Arousal gets the highest weight.

**Why BARS anchors:** Each dimension has explicit 1/3/5/7/10 anchor descriptions ("1 = emotionally flat, dry, purely factual" ... "10 = provokes awe, outrage, or visceral excitement"). Without anchors, LLMs cluster all scores around 5-7. With anchors, they discriminate.

**Framing:** The system assesses "virality potential" — content features empirically associated with sharing — not a prediction of actual engagement. Even the best ML systems with real engagement data explain only ~50% of variance in sharing. We're honest about this.

---

## Distribution Analysis: Three-Layer Framework

**The problem with naive distribution analysis:** "Post it on Twitter" is not analysis. The system needs to explain *why* specific communities would care, grounded in content signals.

**Three layers, mandatory sequence:**

1. **Topic classification** — 1-3 categories from a fixed 18-category taxonomy (adapted from IAB). Fixed list prevents inconsistent free-form categories across runs.
2. **Platform-audience mapping** — 2-5 specific platform-community pairs (e.g., "r/MachineLearning" not "Reddit tech users"). 9 platforms: Twitter/X, LinkedIn, TikTok, Reddit, Instagram, YouTube, Newsletter/Email, Podcast, Blog/SEO.
3. **Resonance reasoning** — Per-segment explanation of content-audience fit, structured around vocabulary match, value alignment, format fit, and engagement hooks.

**Why three layers:** Forcing topic → platform → reasoning in sequence prevents the LLM from jumping to platform recommendations without justifying the fit. Each layer constrains the next.

**Why `weakest_reach` is required:** A distribution analysis that recommends every platform for every content is noise. The tool must always identify where the content would NOT land well, which forces genuine discrimination.

**Why Gemini scores video directly:** Video distribution fit is primarily driven by format (vertical vs. horizontal, raw vs. polished, 15 seconds vs. 10 minutes). A text summary saying "cooking video" can't distinguish a TikTok from a YouTube tutorial. Gemini sees the actual aspect ratio, editing style, and production quality.

---

## What I'd Do Differently With More Time

- **Evaluation harness** — Run calibration sets through the system and measure score discrimination. Currently relies on manual spot-checks.
- **Audio feature extraction** — Dedicated audio analysis (speech cadence, music energy, sound design quality) as separate signals rather than relying on Gemini's multimodal assessment.
- **Web UI** — Interactive dashboard for batch analysis. The CLI works but isn't demo-friendly.
- **Caching** — Cache Gemini File API uploads and analysis results to avoid redundant API calls on re-runs.
- **Cross-model evaluation** — Run the same content through Gemini Flash vs. Pro and measure inter-model agreement to assess scoring reliability.
