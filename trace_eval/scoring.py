"""Weighted scoring engine for trace-eval."""

from __future__ import annotations

from dataclasses import dataclass

from trace_eval.schema import FrictionFlag, JudgeResult

# Lazy import to avoid circular dependency:
# from trace_eval.report import compute_rating


DEFAULT_PROFILE = {
    "reliability": 0.35,
    "efficiency": 0.20,
    "retrieval": 0.20,
    "tool_discipline": 0.15,
    "context": 0.10,
}

# Profiles for different agent types
PROFILES = {
    "default": DEFAULT_PROFILE,
    "coding_agent": {
        "reliability": 0.40,
        "efficiency": 0.25,
        "retrieval": 0.00,  # Not applicable for most coding workflows
        "tool_discipline": 0.25,
        "context": 0.10,
    },
    "rag_agent": {
        "reliability": 0.30,
        "efficiency": 0.15,
        "retrieval": 0.30,  # Higher weight for retrieval-heavy workflows
        "tool_discipline": 0.15,
        "context": 0.10,
    },
}

REQUIRED_JUDGES = {"reliability", "tool_discipline"}


@dataclass
class Scorecard:
    total_score: float
    dimension_scores: dict[str, float | None]
    dimension_confidence: dict[str, str]
    all_flags: list[FrictionFlag]
    scorable_dimensions: list[str]
    unscorable_dimensions: list[str]
    missing_required_judges: list[str]
    profile: str
    rating: str  # "Excellent", "Good", "Fair", "Poor", "Critical"


RATING_EXCELLENT = "Excellent"
RATING_GOOD = "Good"
RATING_FAIR = "Fair"
RATING_POOR = "Poor"
RATING_CRITICAL = "Critical"


def compute_rating(score: float) -> str:
    """Return the canonical rating label for a 0-100 score."""
    if score >= 90:
        return RATING_EXCELLENT
    elif score >= 80:
        return RATING_GOOD
    elif score >= 60:
        return RATING_FAIR
    elif score >= 40:
        return RATING_POOR
    else:
        return RATING_CRITICAL


def rating_explanation(score: float) -> str:
    """Return a plain-English explanation for a score."""
    rating = compute_rating(score)
    explanations = {
        RATING_EXCELLENT: "Near-perfect session with minimal friction",
        RATING_GOOD: "A clean session with minimal friction",
        RATING_FAIR: "Some issues but the agent completed the task",
        RATING_POOR: "Significant friction — errors or wasted effort",
        RATING_CRITICAL: "Major problems — the agent struggled to complete the task",
    }
    return explanations.get(rating, "Unknown")


def compute_scorecard(
    judges: dict[str, JudgeResult],
    profile: str | dict[str, float] | None = None,
) -> Scorecard:
    if profile is None:
        profile_name = "default"
        profile_weights = DEFAULT_PROFILE
    elif isinstance(profile, str):
        profile_name = profile
        profile_weights = PROFILES.get(profile, DEFAULT_PROFILE)
    else:
        profile_name = "custom"
        profile_weights = profile

    dimension_scores: dict[str, float | None] = {}
    dimension_confidence: dict[str, str] = {}
    all_flags: list[FrictionFlag] = []
    scorable: list[str] = []
    unscorable: list[str] = []

    for name, result in judges.items():
        dimension_scores[name] = result.score
        dimension_confidence[name] = result.confidence
        all_flags.extend(result.friction_flags)
        if result.scorable:
            scorable.append(name)
        else:
            unscorable.append(name)

    # Weighted total with proportional redistribution for unscorable judges
    total_weight = sum(profile_weights.get(n, 0) for n in scorable)
    total_score = 0.0
    for name in scorable:
        weight = profile_weights.get(name, 0) / total_weight if total_weight > 0 else 0
        total_score += weight * (dimension_scores[name] or 0)

    # Check missing required judges
    missing_required = [n for n in REQUIRED_JUDGES if n in unscorable]

    # Compute rating using canonical function
    rating = compute_rating(total_score)

    rounded_score = round(total_score, 2)

    return Scorecard(
        total_score=rounded_score,
        dimension_scores=dimension_scores,
        dimension_confidence=dimension_confidence,
        all_flags=all_flags,
        scorable_dimensions=scorable,
        unscorable_dimensions=unscorable,
        missing_required_judges=missing_required,
        profile=profile_name,
        rating=rating,
    )
