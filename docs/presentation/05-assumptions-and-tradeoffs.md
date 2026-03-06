# Assumptions and Tradeoffs

What the system takes as given, where it falls short, what would improve it, and which decisions would change at scale.

**Status:** Final | **As of:** 2026-03-05

---

## 1. Explicit Assumptions

These are the premises the system is built on. Each one shapes how the system behaves, and each one could be wrong.

| Assumption | Implication | What Would Change It |
|-----------|------------|---------------------|
| **"AI-generated" means fully synthetic** -- the system asks "was this made by AI?", not "did AI assist?" | Human-AI collaborative content (AI draft with human edits, AI-assisted color grading) falls in a gray zone. The system returns probability scores and a 5-level verdict scale (`ai_generated` through `human`) rather than a binary label. | A clear industry definition of "AI-assisted" vs. "AI-generated" with detection benchmarks for the gradient. Currently no commercial detector reliably distinguishes partial AI involvement. |
| **Virality can be assessed, not predicted** -- content features explain ~50% of variance in sharing; network effects, timing, and randomness account for the rest | The system outputs "virality potential" scores labeled as content feature assessments, never engagement predictions. The explanation field explicitly frames this limitation. | Access to real engagement data, network topology, and temporal trend signals. Even then, the ceiling is ~0.71 Spearman correlation (arxiv:2512.21402). |
| **Short text (<200 characters) is unreliable for AI detection** -- insufficient signal density for reliable multi-trait scoring | When `is_short_text` is true (`text_length < 200` characters), `_aggregate_signals()` caps `confidence_level` at `MODERATE` regardless of signal strength. This is a single threshold, not a graduated scheme. See `ai_detection.py`, lines 219-220. | A detector specifically trained and validated for short-form content (titles, captions, tweets). Binoculars shows promise in the "few-token regime" but requires GPU infrastructure. |
| **Video AI detection is commercially solved** -- Hive achieves 96-99% accuracy across 100+ generators | Hive is the primary video detection signal (weight 0.9 when configured). The LLM's role is explanation and orchestration, not detection. VLMs achieve only 30-60% accuracy on the same task (arxiv:2506.10474). | A new generation of AI video generators that evades current frame-based detection. Hive's accuracy could degrade against novel architectures until their models update. |
| **English content only** -- all prompts, rubrics, and analysis are English-optimized | Non-English content will produce degraded results across all three tools. The virality rubric anchors, distribution platform descriptions, and AI detection signals are all calibrated for English text patterns. | Localized prompt sets per language, multilingual evaluation benchmarks, and language-specific detection signal calibration (e.g., AI hedging patterns differ across languages). |
| **Single LLM provider for a time-boxed build** -- one SDK, one API key, one error-handling path | If Gemini's structured output has a bug or its video analysis quality varies, every tool is affected simultaneously. There is no cross-provider validation or fallback. | An eval harness that benchmarks multiple providers on the same content, plus a provider-agnostic abstraction layer. |
| **Content is the input, not engagement data** -- the system works from the content itself, with no access to view counts, shares, comments, follower graphs, or algorithmic state | Virality and distribution analysis are based entirely on content features. Platform-specific performance predictions are impossible. The system cannot say "this will get X views" -- only "this exhibits features associated with sharing." | Integration with social media APIs for historical engagement data, audience analytics platforms, and real-time trend feeds. |

---

## 2. Known Limitations

Honest accounting of what the system cannot do, each tied to a specific technical or design constraint.

### Short text accuracy degradation
AI detection accuracy degrades significantly on text under 200 characters (the `is_short_text` threshold in `ContentInput`). A 15-word tweet and a 3,000-word essay receive fundamentally different quality of analysis, but both go through the same pipeline. The confidence capping (short text caps `confidence_level` at `MODERATE`) mitigates overconfident verdicts but does not solve the underlying signal weakness. The 5-signal rubric (vocabulary uniformity, burstiness, hedging frequency, formulaic patterns, tonal uniformity) needs sufficient text volume to produce reliable scores. See [AI Detection Deep Dive -- Confidence Calibration](04-deep-dives.md#1c-confidence-calibration) for the full capping logic.

### Non-English content
Every prompt, rubric anchor, platform description, and signal calibration is written in English and assumes English-language content. The AI detection hedging patterns ("it's important to note," "furthermore") are English-specific tells. The distribution platform communities (BookTok, FinTwit, r/MachineLearning) are anglophone. Running non-English content through the system will produce results, but they will be poorly calibrated.

### Non-YouTube video platforms
The video pipeline supports YouTube URLs (via Gemini native input + yt-dlp bridge to Hive) and local files. Vimeo, Dailymotion, TikTok, Instagram Reels, and other platforms are not supported. The workaround is to download the video and pass the local file path, but this requires the user to handle the download themselves.

### No real-time trend data for virality timing
The "timing relevance" dimension was explicitly removed from the virality rubric because a zero-shot LLM cannot reliably assess what is currently trending. Content that is perfectly timed to a cultural moment (a meme format that is peaking this week, a news event from today) gets no credit for that timing. For trend-dependent content, the system flags this gap in `key_weaknesses`: "meme-format content: timing and in-group recognition cannot be assessed."

### No engagement history or network effects data
The system cannot account for the distribution advantage of a creator with 10 million followers versus one with 100. Network effects are the single largest factor in whether content actually goes viral, and the system has zero access to this data. The virality score reflects content quality for social spread, not the probability of actual spread.

### VLM-only video detection is 30-60% without Hive
When Hive is not configured (`SECRET_KEY` not set), video AI detection falls back to Gemini's text analysis on the video description alone -- the Hive signal is simply absent from the aggregation. Research shows VLMs achieve only 30-60% accuracy on AI video detection. Without Hive, the text-only confidence capping rule applies (capped at `HIGH`), but there is no explicit downgrade or fallback annotation in the current implementation. A confident AI detection verdict on video without Hive should be treated skeptically. See [Design Decisions -- Right Tool for the Right Job](03-design-decisions.md#3-right-tool-for-the-right-job----hive-for-video-detection) for the accuracy gap analysis.

### C2PA metadata stripped by most platforms
C2PA content credentials are a near-definitive signal when present (cryptographically signed assertion from the generating tool), but YouTube, TikTok, Instagram, Reddit, and most other platforms strip C2PA metadata during upload and transcoding. In practice, C2PA will almost never be present for content sourced from social platforms. It is most useful for local files directly from AI generation tools that embed C2PA (OpenAI/DALL-E, Adobe Firefly, some Sora outputs).

---

## 3. What Would Improve With More Time

Each item below would meaningfully improve the system. None was feasible within the 6-hour build constraint.

### Audio analysis
**What it adds:** Dedicated audio feature extraction -- speech cadence, music energy, sound design quality, audio-visual sync -- as separate signals feeding into both virality scoring and AI detection. The December 2025 virality rubric paper (arxiv:2512.21402) found audio energy dynamics to be among the top predictive features for video virality. For AI detection, synthetic speech patterns and audio-visual sync artifacts are independent signals from visual analysis.

**Why not in 6 hours:** Audio analysis requires either a dedicated speech/audio ML model (Whisper for transcription, librosa for feature extraction) or careful prompt engineering to extract structured audio signals from Gemini's multimodal assessment. Currently Gemini processes audio as part of its video analysis, but the system does not extract discrete audio features or weight them independently.

### Evaluation harness
**What it adds:** Systematic calibration against ground truth. Run a labeled dataset of AI-generated and human content through the system, measure detection precision/recall. Run content with known engagement metrics through the virality scorer, measure correlation. Tune dimension weights and score thresholds based on empirical performance rather than theoretical research.

**Why not in 6 hours:** Building the harness, curating a labeled dataset, running calibration, and tuning weights is a multi-day effort. The current dimension weights are based on Berger & Milkman's published findings (see [Design Decisions -- Research-Grounded Virality Scoring](03-design-decisions.md#4-research-grounded-virality-scoring)), which is a defensible starting point but not empirically validated for this specific system.

### Web UI
**What it adds:** An interactive dashboard for batch analysis -- upload multiple pieces of content, see score distributions, compare virality profiles side by side, visualize dimension breakdowns as radar charts. Would make the system demo-friendly for non-technical stakeholders.

**Why not in 6 hours:** A web frontend (even a minimal Streamlit/Gradio app) adds a dependency, requires UI design decisions, and distracts from the core analysis quality. The CLI with Rich panels serves the evaluation context well.

### Caching
**What it adds:** Cache Gemini File API uploads (video files are uploaded fresh on every run) and cache analysis results keyed by content hash. A re-run on the same content would return instantly instead of making 4-5 API calls. Would also help during development iteration.

**Why not in 6 hours:** Caching requires a storage backend (even just a local SQLite or file-based cache), cache invalidation logic (what if the model changes?), and content hashing that works across file paths and URLs.

### Multi-language support
**What it adds:** Localized prompt sets, language-specific AI detection signals (hedging patterns vary by language), multilingual distribution platform knowledge (Weibo, LINE, VK communities), and language-aware confidence calibration.

**Why not in 6 hours:** Each language needs its own validated signal set, prompt calibration, and platform community knowledge. This is a localization effort, not a feature toggle.

### Real-time trend integration for virality timing
**What it adds:** Integration with Google Trends, Twitter/X trending topics, or a social listening API to assess whether content aligns with currently trending topics. Would allow scoring the "timing relevance" dimension that was explicitly removed from the rubric.

**Why not in 6 hours:** Requires an additional API integration, rate-limited data source, and prompt logic to incorporate ephemeral trend data into a structured scoring framework. The trend data itself is volatile and requires careful interpretation.

---

## 4. Tradeoffs I'd Revisit at Scale

These decisions were correct for a 6-hour build. Several would change if the system needed to handle production traffic, support multiple teams, or provide contractual accuracy guarantees.

### Single LLM provider --> multi-provider with eval harness

**Current decision:** Gemini handles everything. One SDK, one code path, maximum simplicity. See [Design Decisions -- Why a Single LLM Provider](03-design-decisions.md#1-why-a-single-llm-provider).

**At scale:** A multi-provider architecture would run the same content through Gemini, Claude, and GPT, then use an evaluation harness to measure inter-model agreement. Where models agree, confidence is high. Where they diverge, the system flags uncertainty. This is the ensemble pattern that research shows produces the best results (EmoSense framework: 2.27% accuracy gains, surpassing GPT-4V by 10.7%). The eval harness would also detect model regression -- if a provider ships a bad update, the harness catches it before it reaches users. The cost is 3x API spend and a provider-agnostic abstraction layer.

### Sync ThreadPoolExecutor --> async for better concurrency

**Current decision:** `ThreadPoolExecutor(max_workers=3)` with the synchronous Gemini SDK. Simple to test, simple to debug. See [Design Decisions -- Parallel vs Sequential Execution](03-design-decisions.md#6-parallel-vs-sequential-execution).

**At scale:** An async architecture with `asyncio` and an async Gemini client would handle concurrent requests more efficiently -- particularly for a web server handling multiple users simultaneously. Thread pools have OS-level overhead per thread; async coroutines are lighter. The current sync architecture handles the CLI use case well but would not scale to a multi-user web service without a rewrite of the concurrency model. The upgrade path is clean: swap `call_gemini_structured` to an async version, replace `ThreadPoolExecutor` with `asyncio.gather`.

### Hive as optional --> Hive as required for video analysis claims

**Current decision:** Hive is optional (configured via `SECRET_KEY`). Without it, the Hive signal is absent from aggregation and text-only capping rules apply.

**At scale:** If the system were making consequential claims about video authenticity (content moderation, legal proceedings, journalistic verification), VLM-only video detection at 30-60% accuracy is not defensible. Hive (or an equivalent purpose-built detector) should be required for any video AI detection claim, with the system explicitly refusing to issue a video detection verdict without it. The current graceful degradation is appropriate for a demo tool but not for a production detection system.

### Temperature=0 --> ensemble with temperature diversity

**Current decision:** Temperature 0.0 everywhere for determinism and reproducibility. See [Design Decisions -- Structured Output as Architecture](03-design-decisions.md#5-structured-output-as-architecture).

**At scale:** Running the same prompt at temperatures 0.0, 0.3, and 0.7, then aggregating results, can improve robustness. Temperature diversity acts as a form of self-ensemble -- if the model produces the same score at all temperatures, confidence is high. If scores diverge, the content is genuinely ambiguous. The LLM-RUBRIC paper from ACL 2024 recommends temperature=0 for single-run evaluations, but production systems with latency budget could benefit from multi-temperature aggregation. The cost is 3x latency and token spend per tool.
