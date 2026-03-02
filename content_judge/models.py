"""
content_judge/models.py

All Pydantic v2 data models for the content judge system.
These are the interface contracts between components.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


# ─────────────────────────────────────────────────────────────────────
# Content Loading Models
# ─────────────────────────────────────────────────────────────────────


class SourceType(str, Enum):
    STRING = "string"
    FILE = "file"
    URL = "url"
    VIDEO = "video"


class ContentInput(BaseModel):
    """Normalized content object passed from loaders to the coordinator."""

    source_type: SourceType
    text: str | None = None
    video_source: str | None = None

    # Derived flags — set by model_post_init
    has_text: bool = False
    has_video: bool = False
    text_length: int = 0
    is_short_text: bool = False

    def model_post_init(self, __context) -> None:
        self.has_text = bool(self.text and self.text.strip())
        self.has_video = self.video_source is not None
        self.text_length = len(self.text) if self.text else 0
        self.is_short_text = self.text_length < 200


# ─────────────────────────────────────────────────────────────────────
# AI Detection Models
# ─────────────────────────────────────────────────────────────────────


class AILabel(str, Enum):
    AI_GENERATED = "ai_generated"
    LIKELY_AI_GENERATED = "likely_ai_generated"
    UNCERTAIN = "uncertain"
    LIKELY_HUMAN = "likely_human"
    HUMAN = "human"


class ConfidenceLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class TextSignalScores(BaseModel):
    """5 text signals scored 0.0-1.0 (higher = more AI-like)."""

    vocabulary_uniformity: float = Field(ge=0.0, le=1.0)
    burstiness: float = Field(ge=0.0, le=1.0)
    hedging_frequency: float = Field(ge=0.0, le=1.0)
    formulaic_patterns: float = Field(ge=0.0, le=1.0)
    tonal_uniformity: float = Field(ge=0.0, le=1.0)


class VideoSignalScores(BaseModel):
    """5 video signals scored 0.0-1.0 (higher = more AI-like) + Hive results."""

    temporal_consistency: float = Field(ge=0.0, le=1.0)
    physics_plausibility: float = Field(ge=0.0, le=1.0)
    texture_artifacts: float = Field(ge=0.0, le=1.0)
    lighting_consistency: float = Field(ge=0.0, le=1.0)
    composition_naturalness: float = Field(ge=0.0, le=1.0)
    hive_ai_score: float | None = Field(default=None, ge=0.0, le=1.0)
    hive_generator: str | None = None


class C2PASignal(BaseModel):
    """C2PA content provenance metadata signal."""

    present: bool = False
    issuer: str | None = None
    generator: str | None = None


class DetectionSignal(BaseModel):
    """A single evidence signal for the AI detection decision."""

    signal_name: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)


class AIDetectionResult(BaseModel):
    """Output of the AI detection tool."""

    verdict: AILabel
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    signals: list[DetectionSignal]
    text_scores: TextSignalScores | None = None
    video_scores: VideoSignalScores | None = None
    detected_generator: str | None = None
    c2pa: C2PASignal = Field(default_factory=C2PASignal)
    explanation: str


# ─────────────────────────────────────────────────────────────────────
# Virality Models
# ─────────────────────────────────────────────────────────────────────


class EmotionalQuadrant(str, Enum):
    HIGH_AROUSAL_POSITIVE = "high_arousal_positive"
    HIGH_AROUSAL_NEGATIVE = "high_arousal_negative"
    LOW_AROUSAL_POSITIVE = "low_arousal_positive"
    LOW_AROUSAL_NEGATIVE = "low_arousal_negative"


class ViralityDimension(BaseModel):
    """A single dimension in the 7-dimension virality rubric."""

    dimension_id: str
    name: str
    score: int = Field(ge=1, le=10)
    weight: float = Field(ge=0.0, le=1.0)
    reasoning: str


# Dimension weights from Berger & Milkman research
VIRALITY_DIMENSION_WEIGHTS: dict[str, float] = {
    "emotional_arousal": 0.20,
    "practical_value": 0.15,
    "narrative_quality": 0.15,
    "social_currency": 0.15,
    "novelty_surprise": 0.15,
    "clarity_accessibility": 0.10,
    "discussion_potential": 0.10,
}


class ViralityLLMOutput(BaseModel):
    """Schema sent to Gemini for virality scoring (excludes computed fields)."""

    dimensions: list[ViralityDimension] = Field(min_length=7, max_length=7)
    emotional_quadrant: EmotionalQuadrant
    primary_emotions: list[str] = Field(min_length=1, max_length=5)
    key_strengths: list[str] = Field(min_length=1, max_length=3)
    key_weaknesses: list[str] = Field(min_length=1, max_length=3)
    explanation: str


class ViralityResult(BaseModel):
    """Full virality result with computed overall_score and virality_level."""

    dimensions: list[ViralityDimension] = Field(min_length=7, max_length=7)
    emotional_quadrant: EmotionalQuadrant
    primary_emotions: list[str] = Field(min_length=1, max_length=5)
    key_strengths: list[str] = Field(min_length=1, max_length=3)
    key_weaknesses: list[str] = Field(min_length=1, max_length=3)
    explanation: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_score(self) -> float:
        """Weighted aggregate score across all dimensions."""
        total = sum(d.score * d.weight for d in self.dimensions)
        return round(total, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def virality_level(self) -> str:
        """Categorical level derived from overall_score."""
        score = self.overall_score
        if score >= 7.5:
            return "very_high"
        elif score >= 5.5:
            return "high"
        elif score >= 3.5:
            return "moderate"
        else:
            return "low"


# ─────────────────────────────────────────────────────────────────────
# Distribution Models
# ─────────────────────────────────────────────────────────────────────


class Platform(str, Enum):
    TWITTER_X = "Twitter/X"
    LINKEDIN = "LinkedIn"
    TIKTOK = "TikTok"
    REDDIT = "Reddit"
    INSTAGRAM = "Instagram"
    YOUTUBE = "YouTube"
    NEWSLETTER = "Newsletter/Email"
    PODCAST = "Podcast"
    BLOG = "Blog/SEO"


class FitStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class AudienceSegment(BaseModel):
    """A specific platform-community audience that would resonate with this content."""

    platform: Platform
    community: str
    estimated_fit: FitStrength
    reasoning: str


class DistributionResult(BaseModel):
    """Output of the distribution analysis tool."""

    primary_topics: list[str] = Field(min_length=1, max_length=3)
    audience_segments: list[AudienceSegment] = Field(min_length=2, max_length=5)
    strongest_fit: AudienceSegment
    weakest_reach: list[str] = Field(min_length=1, max_length=3)
    content_format_notes: str
    distribution_strategy: str
    explanation: str


# ─────────────────────────────────────────────────────────────────────
# Coordinator / Agent Models
# ─────────────────────────────────────────────────────────────────────


class ToolError(BaseModel):
    """Returned by a tool when it fails. Enables graceful degradation."""

    tool: str
    error: str
    is_retryable: bool = False


class ToolResults(BaseModel):
    """Container for all three tool results (or errors)."""

    ai_detection: AIDetectionResult | ToolError
    virality: ViralityResult | ToolError
    distribution: DistributionResult | ToolError


class ReviewDecision(BaseModel):
    """The coordinator's decision after reviewing intermediate tool results."""

    all_results_acceptable: bool
    re_run_tools: list[str] = Field(default_factory=list)
    re_run_hints: dict[str, str] = Field(default_factory=dict)
    review_notes: str


class AnalysisMetadata(BaseModel):
    """Technical metadata about the analysis run."""

    model_used: str
    iterations: int
    tools_succeeded: list[str]
    tools_failed: list[str]


# ─────────────────────────────────────────────────────────────────────
# Final Output Model
# ─────────────────────────────────────────────────────────────────────


class JudgmentReport(BaseModel):
    """The final output of the content judge agent."""

    content_type: SourceType
    ai_detection: AIDetectionResult | ToolError
    virality: ViralityResult | ToolError
    distribution: DistributionResult | ToolError
    overall_explanation: str
    analysis_metadata: AnalysisMetadata

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> JudgmentReport:
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)

    def has_errors(self) -> bool:
        return any(
            isinstance(r, ToolError)
            for r in [self.ai_detection, self.virality, self.distribution]
        )

    def error_summary(self) -> str:
        errors = []
        for field_name in ["ai_detection", "virality", "distribution"]:
            result = getattr(self, field_name)
            if isinstance(result, ToolError):
                errors.append(f"{field_name}: {result.error}")
        return "; ".join(errors) if errors else ""
