"""Weighted scoring engine for trace-eval."""

from __future__ import annotations

from dataclasses import dataclass, field

from trace_eval.schema import FrictionFlag, JudgeResult


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

    return Scorecard(
        total_score=round(total_score, 2),
        dimension_scores=dimension_scores,
        dimension_confidence=dimension_confidence,
        all_flags=all_flags,
        scorable_dimensions=scorable,
        unscorable_dimensions=unscorable,
        missing_required_judges=missing_required,
        profile=profile_name,
    )
