# Key Decisions

**created:** 2/28/2026
**last updated:** 3/1/2026

## Challenge Context

The challenge is to build a small "judge agent" that can evaluate both text and video content and produce:
1. A prediction of whether the content is **AI-generated or human-generated**
1. A **virality score** (likelihood the content would perform well socially)
1. A short **distribution analysis** (which audiences or communities it might resonate with and why)
1. A concise explanation of why the agent produced each output

The spec is intentionally open-ended — they evaluate reasoning, assumptions, and design decisions, not polish or perfection. ~6 hour time constraint.

Reference: [Challenge-Build_a_Judge_Agent.md](../Challenge-Build_a_Judge_Agent.md)

---

## Model Strategy

**Status:** Decided
**Date:** 2/28/2026

### Decision: Single LLM Provider (Gemini) + Purpose-Built Detector (Hive)

**Decision:** The system uses Gemini as the sole LLM provider for all tasks. Hive Moderation API is used as a purpose-built AI video detector. There is no second LLM provider.

**Rationale:** One provider means one SDK, one API key, one error-handling path, and one structured-output format. Gemini handles all tasks (AI detection text analysis, coordinator review, synthesis, virality scoring, distribution analysis) without quality loss on any of them. For a 6-hour build, simplicity wins.

**Default model for MVP:** Gemini 2.5 Flash (fast, cost-effective, supports structured output, native video input).

**Eval dimensions (future):** Inter-model agreement on scores, pairwise ranking accuracy, reasoning quality. The eval harness concept remains valid for future iteration -- it just runs Gemini variants (Flash vs. Pro) rather than cross-provider comparisons.

---

## Video Processing

**Status:** Decided
**Date:** 2/28/2026
**Research reference:** [gemini-video-analysis-research.md](../research/gemini-video-analysis-research.md), [youtube-to-hive-bridge.md](../research/youtube-to-hive-bridge.md)

### Decision: Unified Video Pipeline with Gemini + Hive + yt-dlp

**Decision:** Use Gemini 2.5 Flash for ALL video analysis (YouTube URLs direct, local files via File API upload). Use Hive API for AI-generated content detection on all video. Use yt-dlp to resolve YouTube stream URLs for Hive.

**Rationale:** Gemini's native video input processes ~1fps visual frames, full audio, speech, on-screen text, and temporal continuity in a single API call -- far richer than static keyframes. The yt-dlp stream URL resolution allows Hive to analyze YouTube video without downloading it locally. This gives both Gemini's rich understanding AND Hive's 96-99% AI detection accuracy for every video input.

**Unified pipeline:**
1. **Gemini** for all video analysis (YouTube URL direct, local file via File API upload)
2. **Hive API** for AI video detection (YouTube via yt-dlp stream URL, local via file upload; clip-download fallback if stream URL fails)
3. **Gemini** for all LLM tasks: virality scoring, distribution analysis, AI detection text analysis, coordinator review, synthesis (all directly on actual content -- see Decisions VS-8, DA-1)

**Dependencies:** yt-dlp (stream URL resolution only, not video download). OpenCV is not needed.

---

## AI Detection

**Status:** Decided
**Date:** 2/28/2026
**Research reference:** [ai-vs-human-content-detection.md](../research/ai-vs-human-content-detection.md)

### Decision: Hive Moderation API as Primary Video Detector

**Decision:** Use Hive Moderation API for AI-generated video detection. Gemini for orchestration, text analysis, and explanation -- not as a video detection signal.

**Rationale:** Hive achieves 96-99% accuracy on AI-generated video, supports 100+ generators (Sora, Runway, Pika, Kling), and integrates in under 1 hour. VLMs achieve only 30-60% accuracy on the same task (arxiv:2506.10474). Layering a 30-60% signal on top of a 96-99% signal adds complexity without meaningful accuracy gain. Use the right tool for the job.

**C2PA** content credentials checked opportunistically as a supplementary provenance signal when metadata is present.

See detailed decisions AD-1 through AD-8 below for signal rubrics, confidence levels, and fallback behavior.

---

## Virality Scoring

**Status:** Decided
**Date:** 2/28/2026
**Research reference:** [virality-prediction-audience-analysis.md](../research/virality-prediction-audience-analysis.md)

### Decision: 7-Dimension Rubric Grounded in Empirical Research, Scored by Gemini

**Decision:** Score virality potential using a 7-dimension weighted rubric synthesized from Berger & Milkman (2012), STEPPS, and SUCCES frameworks. Framed as "virality potential" -- content feature assessment, not outcome prediction. **Scored by Gemini**, so the model can evaluate the actual content (including video audio, pacing, and visual signals) directly against the rubric.

**Dimensions:** Emotional Arousal (20%), Practical Value (15%), Narrative Quality (15%), Social Currency (15%), Novelty/Surprise (15%), Clarity/Accessibility (10%), Discussion Potential (10%).

**Key insight from research:** The single strongest predictor of content sharing is emotional arousal, not sentiment. High-arousal emotions (awe, anger, anxiety) drive sharing regardless of positive/negative valence. Even the best ML systems with engagement data explain only ~50% of variance in sharing (~0.71 correlation).

**What this means:** The LLM isn't predicting virality from intuition. It's assessing content against empirically-validated features using anchor-based rubric prompts (1/10 and 10/10 explicitly defined for each dimension). The intelligence comes from the framework design, not the model freestyling. By using Gemini, video content is scored from the actual audio/visual source rather than a text proxy, preserving the strongest virality signals (audio energy, pacing, hook quality).

See detailed decisions VS-1 through VS-8 below for scoring mechanics, emotional quadrant classification, and Gemini-based scoring.

---

## Distribution Analysis

**Status:** Decided
**Date:** 2/28/2026
**Research reference:** [virality-prediction-audience-analysis.md](../research/virality-prediction-audience-analysis.md)

### Decision: Three-Layer Analysis (Topic → Platform-Audience → Resonance), Scored by Gemini

**Decision:** Distribution analysis follows a three-layer sequence, **scored by Gemini** so the model can evaluate the actual content (including video format, aspect ratio, editing style, and visual signals) directly against the framework:
1. **Topic classification** — 1-3 categories from an 18-category taxonomy adapted from IAB
2. **Platform-audience mapping** — 2-5 specific platform-community pairs with fit strength
3. **Resonance reasoning** — Per-segment explanation of WHY content fits, based on vocabulary match, value alignment, format fit, engagement hooks, topical relevance, and tone match

**Rationale:** Layer 1 anchors in subject matter. Layer 2 maps to distribution channels. Layer 3 produces the explanatory reasoning the challenge asks for. The three-layer sequence prevents the LLM from jumping to "post it on TikTok" without justifying the fit. By using Gemini, video content is scored from the actual audio/visual source rather than a text proxy, preserving the format signals (aspect ratio, editing style, duration, production quality) that drive platform fit.

See detailed decisions DA-1 through DA-10 below for taxonomy, platform enum, signal types, and tool independence.

---

---

## Distribution Analysis Decisions

**Last updated:** 3/1/2026
**Spec reference:** `/Users/rossbaltimore/content-judge/docs/specs/distribution-analysis-spec.md`

### Decision DA-1: Gemini Scores Distribution Directly on All Content

**Decision:** The distribution tool uses Gemini to score the three-layer framework directly on actual content (video or text). Single code path for both modalities via `call_gemini_structured()`.

**Rationale:** Platform fit for video is driven by format (aspect ratio, editing style, duration, production quality). These signals get lost in text translation. Gemini sees the video firsthand and assesses format fit from the actual source material. For text, the same code path works without branching.

**Impact:** For video: 5 Gemini calls total (video description, virality, distribution, AI detection text, synthesis). For text: 4 Gemini calls (virality, distribution, AI detection text, synthesis). The three-layer framework content stays unchanged.

---

### Decision DA-2: Topic Taxonomy — 18-Category Adapted IAB List

**Decision:** The distribution tool classifies content into 1-3 topics from a fixed 18-category taxonomy adapted from the IAB Content Taxonomy (not the full IAB taxonomy, not a free-form classification).

**Categories:** Technology | Business/Finance | Science/Education | Politics/Current Events | Entertainment/Pop Culture | Health/Wellness | Lifestyle/Personal Development | Sports | Arts/Creative | Food/Drink | Travel | Parenting/Family | Gaming | Fashion/Beauty | Environment/Sustainability | Humor/Comedy | Career/Professional Development | News/Journalism

**Rationale:** The full IAB taxonomy (1,500+ categories across 6 tiers) is far too granular for distribution analysis output. Free-form classification produces inconsistent category names across runs. A fixed 18-category list is broad enough to cover all major content types, specific enough to drive meaningful platform-audience mapping, and consistent across runs.

**Trade-off:** Some content genuinely sits between categories (e.g., a self-help post about financial psychology is both Lifestyle/Personal Development and Business/Finance). The 3-topic maximum and "dominant topic first" rule handle this.

**Alternatives rejected:**
- Full IAB taxonomy: Too granular, 1,500+ options degrade LLM classification reliability
- Free-form classification: Inconsistent across runs, cannot be used for structured mapping
- Platform-native categories (e.g., "BookTok," "FinTok"): Useful for community identification but not for first-pass topic classification

---

### Decision DA-3: Three-Layer Analysis Framework (Topic → Platform-Audience → Resonance)

**Decision:** The distribution analysis follows a mandatory three-layer sequence within a single LLM call: (1) topic classification, (2) platform-audience segment identification, (3) resonance reasoning per segment.

**Rationale:** Layer 1 anchors the analysis in subject matter before considering platforms. Layer 2 applies platform knowledge to map topic + content signals to specific communities. Layer 3 produces the explanatory reasoning that makes the analysis actionable rather than a list of platforms. Forcing this sequence via prompt structure prevents the LLM from jumping to conclusions and produces more systematic, defensible output.

**Trade-off:** Three-layer reasoning within one prompt is more complex than a simple "what platforms would like this?" instruction. The complexity is necessary for output quality.

---

### Decision DA-4: Platform Enum with Nine Values

**Decision:** The `Platform` enum includes nine values: Twitter/X, LinkedIn, TikTok, Reddit, Instagram, YouTube, Newsletter/Email, Podcast, Blog/SEO.

**Rationale:** These nine platforms cover the distribution landscape for the content types the judge will encounter. Including Newsletter, Podcast, and Blog/SEO extends the analysis beyond social media to owned-media distribution channels, which is more complete and actionable. Facebook is excluded because its organic reach for content distribution has declined dramatically and it is not a primary platform for the content types the judge will analyze. Threads/Mastodon/Bluesky are excluded as emerging platforms without established community taxonomies.

**Trade-off:** The platform list will age. Facebook exclusion may be wrong for specific content types (parenting, community groups). This can be updated in a later iteration.

---

### Decision DA-5: ResonanceSignal Typed Enum for Signal Categories

**Decision:** `ResonanceSignal.signal_type` is a typed enum with six values (`vocabulary_match`, `value_alignment`, `format_fit`, `engagement_hook`, `topical_relevance`, `tone_match`) rather than a free-form string.

**Rationale:** A typed enum forces structured reasoning. The LLM must categorize each resonance signal into one of six defined types, preventing generic or circular reasoning ("this content fits this platform because this platform likes this content"). The six types cover the analytically distinct mechanisms of content-audience fit.

**Trade-off:** The enum may not capture all possible signal types. The `topical_relevance` and `tone_match` types were added to the research doc's original four (vocabulary, value, format, engagement) to handle common cases those four miss.

---

### Decision DA-6: Temperature=0 for Distribution Tool

**Decision:** The distribution tool LLM call uses `temperature=0` (or the lowest available deterministic setting).

**Rationale:** Distribution analysis should be deterministic for the same content input. Variability in platform recommendations for identical content would make the system unreliable and untestable. Temperature=0 enables the inter-run consistency test in the testing strategy.

**Trade-off:** Temperature=0 may produce slightly less diverse reasoning in the `reasoning` fields. The structured prompting and anchor-based guidance compensate for this.

---

### Decision DA-7: strongest_fit Field Duplicates audience_segments[0]

**Decision:** The `DistributionResult.strongest_fit` field is populated with the same `AudienceSegment` object as `audience_segments[0]`. This is explicit duplication.

**Rationale:** The coordinator agent needs to extract the top distribution recommendation without indexing into a list. The `strongest_fit` field makes this extraction trivial and self-documenting. The prompt instructs the LLM to keep these identical; the Pydantic model's field description reinforces this.

**Trade-off:** Minor duplication in the JSON output. Acceptable for the ergonomic gain.

---

### Decision DA-8: weakest_reach Field is Required

**Decision:** `DistributionResult.weakest_reach` is a required field with minimum length 1. The distribution tool must always identify at least one platform or audience type that would NOT resonate with the content.

**Rationale:** A distribution analysis that recommends every platform for every piece of content is not analysis — it is noise. Requiring identification of weak fits forces discrimination and produces more useful output. It also prevents the LLM from defaulting to a safe "this works everywhere" answer.

**Trade-off:** Some content genuinely could perform across many platforms. In these cases, `weakest_reach` should identify the platform where the fit is least strong, not claim the content fails everywhere.

---

### Decision DA-9: 2-5 Audience Segments Constraint

**Decision:** `audience_segments` has a minimum of 2 and maximum of 5 segments.

**Rationale:** Fewer than 2 segments is too narrow — almost all content has at least two viable platform communities. More than 5 segments is too broad and dilutes the analysis. The 2-5 range forces prioritization while ensuring the analysis covers cross-platform opportunities.

**Trade-off:** Niche content may genuinely have only one strong fit. In these cases, the tool should include one strong-fit and one moderate-fit segment rather than forcing five platforms.

---

### Decision DA-10: Distribution Analysis Does Not Receive AI Detection Results

**Decision:** The distribution tool analyzes content independently and does not receive the AI detection result as input. It does not adjust its distribution recommendations based on whether content is AI-generated or human-generated.

**Rationale:** Maintaining tool independence preserves the clean coordinator pattern. Each tool analyzes content from its own specialized lens. The coordinator is responsible for synthesizing cross-tool insights, including any impact of AI-generated status on distribution viability (e.g., "this AI-generated content targets academic Twitter, a community increasingly sensitized to AI content").

**Trade-off:** The distribution tool cannot flag platform-specific AI-content risks (e.g., some Reddit communities explicitly ban AI-generated content). These risks should be noted in the coordinator synthesis layer, not the distribution tool.

---

## System Integration & UX Decisions

**Decision owner:** System Cohesion & UX Specialist
**Date:** 2/28/2026
**Spec reference:** `/Users/rossbaltimore/content-judge/docs/specs/system-integration-spec.md`

---

### Decision SI-1: Structured Output via Gemini JSON Mode

**Decision:** Use Gemini's structured output (`response_mime_type="application/json"` + `response_schema`) for all analysis tool calls. The `response_schema` parameter accepts Pydantic model JSON schemas directly.

**Rationale:** Constrained decoding guarantees schema compliance at the generation level -- no post-hoc JSON parsing errors, no missing fields, no type mismatches.

---

### Decision SI-2: Parallel Tool Execution via `ThreadPoolExecutor`

**Decision:** All three analysis tools run concurrently using `concurrent.futures.ThreadPoolExecutor(max_workers=3)`. The coordinator does not wait for one tool before dispatching the next.

**Rationale:** The three tools are fully independent — AI detection does not feed data into virality, and virality does not feed into distribution. Sequential execution wastes time equal to the sum of the two slower calls (~15-20 seconds). Parallel execution is bounded by the single slowest call (~6-8 seconds). This is a 2-3x latency improvement for no implementation complexity cost.

**Why not async:** The Google GenAI SDK's synchronous client combined with `ThreadPoolExecutor` achieves the same parallelism as `asyncio` without requiring async/await throughout the codebase. Sync code is simpler to test, simpler to debug, and easy to upgrade to async later.

---

### Decision SI-3: `JudgmentReport` as the Single Source of Truth for All Output

**Decision:** The `JudgmentReport` Pydantic model is the complete output contract. All output formats (Rich terminal panels, JSON, verbose) are renderings of this single validated model.

**Rationale:** Separating the data model from its rendering means: `--json` mode requires no special handling (just `report.to_json()`); Rich rendering code is isolated in `cli.py` and never touches business logic; tests validate the data model independently of display logic; the coordinator never needs to know about terminal formatting.

**Trade-off:** The model must represent partial results (one tool fails, others succeed) without being invalid. This is handled via `AIDetectionResult | ToolError` union types. Any rendering layer must check for `ToolError` and display an appropriate fallback.

---

### Decision SI-4: `content-judge <input>` Flat Command Structure (No Subcommands)

**Decision:** The CLI has one command (`content-judge`) with one required argument (the content) and option flags. No subcommand structure (`content-judge analyze`, `content-judge detect`, etc.).

**Rationale:** For a demo/evaluation tool with one job, subcommands add syntax overhead without benefit. `content-judge "some text"` is immediately intuitive. The `--video` flag explicitly routes video content rather than auto-detecting file type, because auto-detection would require attempting to open files as video before knowing they are valid, adding complexity and confusing error messages.

**Flags:** `--video`, `--json`, `--verbose` / `-v`, `--model`, `--no-color`, `--version`.

---

### Decision SI-5: Coordinator Loop Bounded to 3 Iterations; Re-Runs Are the Exception

**Decision:** The coordinator agent's agentic loop has a hard maximum of 3 iterations. In the typical case, iteration 1 runs all tools and the coordinator synthesizes. Re-runs (iterations 2-3) are triggered only when the review step identifies genuinely problematic results.

**Rationale:** Unbounded loops create unpredictable token costs and latency. Three iterations is sufficient to handle the realistic failure modes (one tool returns a low-confidence result, a transient API error, an internal contradiction). In practice, the vast majority of runs complete in one iteration. The coordinator demonstrates genuine agentic reasoning without becoming an expensive loop.

**Re-run criteria:** Low AI detection confidence below 0.4 on non-trivially-short content; an internal contradiction between AI detection verdict and virality score that suggests misanalysis; a transient tool error worth retrying. Low scores, niche results, or disagreements between tools do NOT trigger re-runs — those are valid findings.

---

### Decision SI-6: Transient Progress Spinners + Static Final Panel Output

**Decision:** During analysis, use Rich `Progress` with `transient=True` so the spinner disappears after completion and the final output is clean static panels. Do not mix in-progress text with final result text.

**Rationale:** Transient progress gives feedback during the 6-8 second wait without polluting the final output. The evaluator sees a clean panel layout, not a mix of animated spinner artifacts and results. This is the standard pattern used by production CLI tools (pip, poetry, gh).

**Panel layout:** One panel per section (AI Detection, Virality, Distribution, Overall Assessment) with a consistent `bright_blue` border style. Color-coding by result intensity: green for confident positive findings, yellow for uncertain/moderate, red for flagged/failed.

---

### Decision SI-7: `c2pa-python` Is an Optional Dependency (Not in `pyproject.toml`)

**Decision:** `c2pa-python` is not listed in `pyproject.toml` dependencies. The AI detection tool imports it inside a `try/except ImportError` block and silently skips the C2PA check if the library is not installed.

**Rationale:** `c2pa-python` has native C++ library bindings that can fail on some platforms (particularly on machines without the required system libraries). Since C2PA metadata is only present in a minority of content and is treated as a bonus confirmation signal (presence confirms AI generation; absence proves nothing), making it optional avoids install friction for a marginal improvement.

**Impact:** `pip install -e .` always works cleanly. Users who want C2PA checking can install it separately: `pip install c2pa-python`.

---

### Decision SI-8: `LLMError` Propagates to Coordinator, Not Caught in Tools

**Decision:** The three tool functions (`run_ai_detection`, `run_virality`, `run_distribution`) do not catch `LLMError`. They let it propagate to the coordinator's `_dispatch_tools()` method, which wraps it in a `ToolError` and stores it in `ToolResults`.

**Rationale:** Centralizing error handling at the coordinator level gives the coordinator complete visibility into what failed and why. It can then decide: retry? degrade gracefully? fail entirely? If tools silently caught their own errors, the coordinator would receive apparently-successful empty results rather than explicit failure signals, making it impossible to implement intelligent recovery.

**Pattern:** Tool raises `LLMError` → coordinator `_dispatch_tools()` catches it → stores `ToolError(tool=name, error=msg, is_retryable=bool)` in `ToolResults` → coordinator synthesizes partial report or requests a retry on next iteration.

---

### Decision SI-9: Temperature Always 0 for All LLM Analysis Calls

**Decision:** All LLM calls within analysis tools and the coordinator use `temperature=0.0`. No exceptions.

**Rationale:** Content analysis must be deterministic and reproducible. Running the same content through the system twice should produce the same scores. This is essential for testing (mock-based tests would fail if temperature introduced variance) and for user trust (scores that change on each run undermine confidence in the system). The LLM-RUBRIC framework (ACL 2024) and LLM-as-judge best practices both recommend temperature=0 for rubric-based scoring. Analytical depth comes from rich prompts and explicit rubrics, not sampling diversity.

---

### Decision SI-10: Distribution Tool Receives Actual Content via Gemini

**Decision:** The distribution tool uses `call_gemini_structured()` to score the framework directly on actual content (video or text). Single code path, no branching.

**Rationale:** Same as DA-1 -- format-critical video signals get lost in text translation. Gemini sees the content firsthand.

---

## Virality Scoring — Key Decisions

**Last updated:** 3/1/2026
**Spec reference:** `/Users/rossbaltimore/content-judge/docs/specs/virality-scoring-spec.md`

---

### Decision VS-1: "Virality Potential" Framing, Not Outcome Prediction

**Decision:** The system outputs a "virality potential" score, explicitly framed as a content feature assessment, not an outcome prediction.

**Rationale:** No system can predict whether specific content will go viral. Network effects, timing, distribution, and randomness account for the majority of virality outcomes. The best ML systems using engagement history and network data achieve only ~0.71 Spearman correlation with actual sharing (arxiv 2512.21402, December 2025). An LLM operating from content alone cannot exceed this. What the LLM CAN reliably assess is whether content exhibits structural, emotional, and narrative features that empirically correlate with higher sharing rates.

**Impact:** The score is labeled "Virality Potential" throughout the system. The `explanation` field in `ViralityResult` is required to explicitly state this is potential, not a prediction. The CLI output panel includes a caveat note.

---

### Decision VS-2: 7-Dimension Rubric Over Single Holistic Score

**Decision:** Use a 7-dimension weighted rubric (Emotional Arousal 20%, Practical Value 15%, Narrative Quality 15%, Social Currency 15%, Novelty/Surprise 15%, Clarity/Accessibility 10%, Discussion Potential 10%) rather than asking the LLM for a single overall virality score.

**Rationale:** Multi-dimensional rubric evaluation with LLMs outperforms single holistic judgments in reliability and consistency (LLM-RUBRIC, Microsoft Research, ACL 2024). A single-score prompt produces arbitrary numbers. A rubric-based approach produces scores grounded in specific, auditable observations per dimension. The multi-dimensional output is more useful to the end user — it identifies exactly which features are strong or weak.

**Trade-off:** Higher prompt complexity and token cost per call (~30% more tokens than single-score approach). The improvement in output quality and explainability is worth the cost.

---

### Decision VS-3: Overall Score Is Computed, Not LLM-Supplied

**Decision:** The `overall_score` field in `ViralityResult` is a `@computed_field` calculated from dimension scores and fixed weights. The LLM does not supply an `overall_score` field in its output.

**Rationale:** When LLMs supply both dimension scores and an overall score, the overall score frequently diverges from the weighted average of dimension scores — a known inconsistency in LLM multi-score evaluation. Computing the overall score deterministically post-generation guarantees mathematical consistency and prevents the LLM from gaming the aggregate (inflating it for content it "wants" to succeed).

**Impact:** Pydantic `@computed_field` handles the weighted average. Pydantic validators confirm dimension weights match the fixed `DIMENSION_WEIGHTS` dict. The JSON schema sent to the LLM excludes `overall_score` and `virality_level` (both computed fields). Running `ViralityResult.model_json_schema()` excludes computed fields automatically in Pydantic v2.

---

### Decision VS-4: 5-Anchor Rubric Per Dimension (1, 3, 5, 7, 10)

**Decision:** Each scoring dimension provides behavioral anchor descriptions at five score points: 1, 3, 5, 7, and 10.

**Rationale:** The research doc recommended 3-anchor rubrics (1, 5, 10). However, score clustering occurs primarily in the intermediate zones — the LLM defaults to 5 when content is "better than bad but not great" and to 7 when content is "better than average but not excellent." Without behavioral descriptions at 3 and 7, there are no reference points for these critical calibration zones. Five-anchor Behaviorally Anchored Rating Scales (BARS) are standard in industrial psychology and have been shown to reduce rater clustering by 25%+ versus generic numeric scales.

**Impact:** Longer dimension descriptions in the system prompt. Score distribution quality improvement justifies the additional tokens.

---

### Decision VS-5: Emotional Quadrant Is Metadata, Not a Scoring Dimension

**Decision:** Valence-arousal quadrant classification (`emotional_quadrant: EmotionalQuadrant`) is a separate output field in `ViralityResult`, not an eighth scoring dimension contributing to the weighted average.

**Rationale:** The valence-arousal model is already captured through Dimension 1 (Emotional Arousal). Adding it as a scored dimension would double-count emotional content and inflate the score for high-arousal pieces. Its value is interpretive — it explains the type of arousal (awe vs. outrage vs. sadness) and informs the distribution tool's platform-fit reasoning. The coordinator synthesis can use the quadrant to add nuance (e.g., "high virality potential but anger-dominant tone may limit LinkedIn distribution") without it affecting the numeric score.

**Impact:** `ViralityResult` has two distinct emotional fields: `emotional_arousal` dimension (quantitative, 20% weight) and `emotional_quadrant` enum (categorical, metadata only). The distribution tool and coordinator synthesis use `emotional_quadrant` for platform-specific recommendations.

---

### Decision VS-6: "Timing Relevance" Dimension Removed

**Decision:** The planning doc specified "timing relevance" as one of its 6 virality dimensions. This spec removes it entirely and does not replace it with a timing-equivalent dimension.

**Rationale:** Timing relevance requires real-time knowledge of what is culturally trending — information a zero-shot LLM cannot reliably assess without live data access. Scoring this dimension would produce arbitrary, unstable results across different LLM versions and time periods. The dimension is replaced by Narrative Quality and Social Currency (both content-intrinsic and grounded in STEPPS and SUCCES frameworks), which the planning doc's 6 dimensions did not include.

**Supersedes:** Planning doc assumption #2 ("6-dimension framework including timing relevance").

**Impact:** 7 dimensions instead of 6. The coordinator synthesis should note this gap if content appears to be highly trend-dependent: "Note: Timing relevance — whether this content participates in a current trend — was not scored. For trend-dependent content, actual virality may differ significantly from this potential score."

---

### Decision VS-7: Meme and Trend-Dependent Content — Flag in Output, Not a Special Code Path

**Decision:** When content is identified as meme-format or trend-dependent, the tool scores it on available intrinsic features and adds a flag to `key_weaknesses`. No special branching code in `virality.py`.

**Rationale:** A special code path for memes adds maintenance burden and may incorrectly suppress scores for meme content with strong intrinsic features. The `key_weaknesses` flag ("meme-format content: timing and in-group recognition cannot be assessed") captures the limitation without suppressing the valid intrinsic evaluation. The distribution tool is better positioned to handle whether specific meme formats are currently trending.

**Impact:** System prompt includes meme-detection instruction with prescribed flag language. `virality.py` has no conditional branches for content type beyond `text` vs. `video`.

---

### Decision VS-8: Gemini Scores Virality Rubric Directly on All Content

**Decision:** The virality tool uses Gemini to score the 7-dimension rubric directly on actual content (video or text). Single code path via `call_gemini_structured()`.

**Rationale:** The strongest video virality predictors (audio energy, pacing, hook quality per arxiv 2512.21402) get lost in text translation. Gemini scores the rubric from the actual audio/visual source. For text, the same code path works without branching. The rubric content (dimensions, weights, anchors) stays unchanged.

**Impact:** `GEMINI_API_KEY` is required. Same API call counts as DA-1.

---

## AI Detection Component Decisions

**Last updated:** 2/28/2026
**Author:** AI vs Human Detection Specialist
**Spec reference:** `/Users/rossbaltimore/content-judge/docs/specs/ai-detection-spec.md`

---

### Decision AD-1: Rubric-Driven LLM Analyst as Primary Detection Strategy

**Status:** Decided

**Context:** We need to detect whether text and video content is AI-generated. Options ranged from pure API-based detection (GPTZero, Hive, Originality.ai) to open-source models (Binoculars, GenConViT, Skyra) to LLM-as-judge approaches.

**Decision:** Use Gemini as a structured multi-signal analyst driven by an explicit rubric, with Hive Moderation API as an optional high-weight signal for video AI detection (all video sources via the unified pipeline).

**Rationale:**
- All commercial text detection APIs (GPTZero, Originality.ai, Sapling) are calibrated for 250+ word documents. Our primary text format — titles (5-20 words), captions (20-100 words) — falls below their reliable operating range. Accuracy degrades 10-15% below 200 words (Scribbr 2024 evaluation).
- Open-source models (Binoculars: two 7B LLMs on GPU; Skyra: Qwen2.5-VL; GenConViT) require GPU infrastructure and significant setup time incompatible with a 6-hour build.
- Research (EMNLP 2025 survey, Chiang and Lee 2023) shows LLMs examining individual signals via chain-of-thought reasoning before a verdict outperform single-verdict LLM prompts. Multi-trait specialization improves zero-shot accuracy.
- The system's explanation requirement (why did the agent produce this output) is naturally satisfied by the chain-of-thought reasoning without additional work.
- Hive API achieves 96-99% accuracy on AI-generated video per an independent 2024 benchmark and supports 100+ generators including Sora, Runway, Pika, and Kling. Integration requires under 1 hour.

**Alternatives rejected:**
- GPTZero-only: Insufficient for short text; does not handle video; black-box scores with no explanation
- Hive-only: Handles video well, limited text detection; no explanation generation
- Pure LLM single-verdict: Research shows single-verdict prompts are less reliable than rubric + chain-of-thought
- Open-source models (Skyra, GenConViT, Binoculars): GPU dependency and setup time are incompatible with 6-hour constraint
- Statistical methods alone (perplexity/burstiness): Pangram's own research shows these fail as standalone signals because LLMs are trained to minimize perplexity on common writing styles, creating false positives on formal human writing

---

### Decision AD-2: Five-Signal Rubrics for Text and Video Modalities

**Status:** Decided

**Context:** The detection prompt must be specific enough to produce reliable assessments. Asking "is this AI-generated?" as a single question produces worse calibrated results than asking about specific observable signals.

**Decision:** Decompose detection into 5 independent signals per modality. Each is scored 0.0-1.0 by the LLM before an overall judgment is formed. The LLM observes and describes each signal before assigning a score.

**Text signals (0.0 = strongly human, 1.0 = strongly AI):**
1. Vocabulary uniformity — AI uses restricted, middle-frequency vocabulary
2. Sentence length variance — AI has low burstiness; uniform sentence lengths
3. Hedging and transition pattern density — AI overuses "it is important to note," "furthermore," "in conclusion"
4. Structural formulaicity — AI follows predictable templates and parallel structures
5. Tonal uniformity — AI maintains a flat, professionally consistent tone throughout

**Video signals (analyzed via Gemini's full video analysis):**
1. Temporal consistency — AI video has cross-frame continuity errors (objects appear/disappear)
2. Physics plausibility — AI video has physics violations (fluid dynamics, cloth, motion arcs)
3. Texture artifact score — AI video has "rendered" surface qualities (over-smooth skin, boundary blur)
4. Lighting and shadow consistency — AI video has inconsistent or unmotivated light sources
5. Composition naturalness — AI video has overly cinematic, un-cameralike framing

**Rationale:** Signal independence means that mixed evidence (some signals high, some low) is informative and can be surfaced in the explanation. The 5-signal structure produces specific, falsifiable findings ("signals T3 and T5 are elevated") rather than a vague holistic impression.

**Alternatives rejected:**
- Single holistic score: Less reliable, harder to explain, harder to calibrate against known examples
- 10+ signals: Diminishing returns; the LLM handles 5+5 signals reliably in a single call
- Statistical signals only (perplexity, token probability distributions): These require access to model internals or corpus-level analysis and fail on short text

---

### Decision AD-3: Qualitative Confidence Levels as Primary Output; Numeric Probability as Secondary

**Status:** Decided

**Context:** What form should the confidence output take?

**Decision:** Output both: a qualitative `ConfidenceLevel` enum (VERY_HIGH / HIGH / MODERATE / LOW / VERY_LOW) and a numeric `ai_probability` float (0.0-1.0). Label assignment is gated by BOTH — high probability with LOW confidence cannot produce the `ai_generated` or `human` labels.

**Rationale:** Numeric probabilities imply calibration we cannot guarantee without a labeled evaluation set. "73% confident" implies we are correct 73% of the time on similar inputs — but we have no calibration data to validate this. Qualitative levels communicate signal strength without implying false precision. The numeric value remains useful for downstream ranking and sorting by the coordinator.

**Alternatives rejected:**
- Numeric probability only: Implies calibration we cannot guarantee
- Qualitative only: Loses useful ordering information for downstream synthesis and sorting

---

### Decision AD-4: Honest Detection Framing — "Analysis Suggests," Not "Verified"

**Status:** Decided

**Context:** LLMs are not reliable standalone detectors for synthetic media. Academic research (arxiv:2506.10474) confirms VLMs achieve only 30-77% accuracy on video detection. How should the system frame its outputs given this constraint?

**Decision:** All outputs use hedged language by convention enforced in the system prompt. The `explanation` field must use phrases like "analysis suggests," "signals indicate," "assessment points toward." The strong labels (`ai_generated`, `human`) are still used when evidence warrants -- they communicate a strong verdict -- but the accompanying explanation remains hedged.

**Rationale:** False positives (incorrectly labeling human content as AI-generated) harm creators. Honest uncertainty framing reduces this harm and reflects the actual limits of the technique. The system's value is in evidence synthesis and explanation, not binary certification. Hedged language is both more ethical and more accurate given the known limitations of LLMs on synthetic media detection.

---

### Decision AD-5: C2PA as Strong Opportunistic Signal, Not Required

**Status:** Decided

**Context:** C2PA (Coalition for Content Provenance and Authenticity) content credentials can definitively identify some AI-generated content. Should C2PA checking be required?

**Decision:** Check C2PA opportunistically using `c2pa-python`. If present and declaring AI generation, treat as near-definitive: override `ai_probability` to ≥ 0.90, force label to `ai_generated`, confidence to `very_high`. If absent, continue with content analysis — absence proves nothing.

**Rationale:** Most social platforms (TikTok, Instagram, YouTube, Reddit) strip C2PA metadata during upload/transcoding. Absence is the norm, not a signal. When present, C2PA is the strongest possible signal — a cryptographically signed assertion from the generating tool itself. The `c2pa-python` library (MIT-licensed) integrates in approximately 30 minutes.

**Note:** Aligns with Decision SI-7 (c2pa-python as optional dependency). The AI detection tool imports it inside a `try/except ImportError` block.

---

### Decision AD-6: Hive API is Optional, Not Required; Degrades Gracefully

**Status:** Decided

**Context:** Hive Moderation API offers 96-99% accuracy on AI-generated video (independent 2024 benchmark, 0% false positive rate). Should it be a required dependency?

**Decision:** Hive API is optional, configured via `HIVE_API_KEY` environment variable. When present, it is the primary video signal (weight 0.50 in signal aggregation). When absent, the system falls back to LLM-only video analysis with `video_confidence` downgraded one level and an `analysis_note` recording the fallback.

**Rationale:** Making Hive optional means the system works without additional API keys while allowing operators who want higher video detection accuracy to configure it. The free V3 tier (100 requests/day) is sufficient for demo use. VLMs alone achieve only 30-77% accuracy on video deepfake detection (arxiv:2506.10474), so Hive's contribution is significant when available.

**Implementation:** Hive receives video via the unified pipeline (YouTube: yt-dlp stream URL; fallback: 5-10s clip download; local: file upload). The Hive result is passed to the Gemini analysis prompt for agreement/disagreement explanation.

---

### Decision AD-7: Single LLM Call Per Content Item

**Status:** Decided

**Context:** Should the detection pipeline use one LLM call (all signals in one prompt) or multiple calls (one per signal or modality)?

**Decision:** Single LLM call per content item. All modalities and all 5+5 signals are analyzed in one structured prompt that returns a fully populated `AIDetectionResult` via structured output.

**Rationale:** Multiple calls increase latency and cost linearly. The rubric handles 10 signal assessments reliably in a single call. The coordinator architecture expects each tool to be a single call. The chain-of-thought signal reasoning produces a single coherent narrative that becomes the explanation.

**Trade-off:** A single long prompt may compress reasoning compared to separate calls. For MVP this is the correct choice given the 6-hour constraint.

---

### Decision AD-8: Text-Only Analysis Caps at MODERATE Confidence; Labels Capped at `likely_*`

**Status:** Decided

**Context:** When only text is provided (no video), what is the maximum confidence we should express?

**Decision:** Text-only analysis caps at MODERATE confidence regardless of signal strength, unless C2PA or another external signal is present. The `ai_generated` and `human` labels cannot be assigned from text signals alone. The maximum labels for text-only input are `likely_ai_generated` and `likely_human`.

**Confidence ceiling by word count (text-only):**
- Under 50 words: LOW (maximum)
- 50-150 words: MODERATE (maximum)
- 150+ words with 3+ clearly elevated signals: HIGH (maximum; VERY_HIGH requires Hive or C2PA)

**Rationale:** Short-form text is unreliable for AI detection. All commercial detectors lose 10-15% accuracy below 200 words. A confident `ai_generated` verdict on a 10-word title is overconfident and could harm creators who happen to write formal, structured prose. MODERATE confidence with `likely_ai_generated` is still actionable without the risk of a definitive false positive.
