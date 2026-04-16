"""Report formatting: text and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def format_text(card: Scorecard, adapter_report: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    profile_note = f"  Profile: {card.profile}" if card.profile != "default" else ""
    lines.append("=" * 60)
    lines.append(f"  TRACE-EVAL SCORECARD  Total: {card.total_score:.1f}/100")
    if profile_note:
        lines.append(profile_note)
    lines.append("=" * 60)
    lines.append("")

    # Sort flags by severity for display
    sorted_flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    # Root causes: top critical/high severity flags
    root_causes = [f for f in sorted_flags if f.severity in ("critical", "high")]
    if root_causes:
        lines.append("LIKELY ROOT CAUSES:")
        for flag in root_causes[:3]:  # Show top 3
            lines.append(f"  - {flag.suggestion}")
        lines.append("")

    lines.append("DIMENSION SCORES:")
    for dim, score in card.dimension_scores.items():
        conf = card.dimension_confidence.get(dim, "")
        if dim in card.unscorable_dimensions:
            score_str = "N/A"
            marker = " *"
            # Add a note for retrieval that's not applicable
            if dim == "retrieval" and card.dimension_confidence.get(dim) == "low":
                marker = " * (not applicable to this workflow)"
        else:
            score_str = f"{score:.1f}"
            marker = ""
        lines.append(f"  {dim:20s} {score_str:>6s}  ({conf}){marker}")

    if card.unscorable_dimensions:
        lines.append("")
        lines.append("  * = unscorable dimension — weight redistributed to scorable dimensions")

    if sorted_flags:
        lines.append("")
        lines.append("FRICTION FLAGS (sorted by severity):")
        for flag in sorted_flags:
            severity_tag = f"[{flag.severity.upper()}]"
            idx = f" @event {flag.event_index}" if flag.event_index is not None else ""
            lines.append(f"  {severity_tag} {flag.id}{idx}")
            lines.append(f"    -> {flag.suggestion}")

    if adapter_report:
        lines.append("")
        lines.append("ADAPTER CAPABILITY REPORT:")
        for key, val in adapter_report.items():
            lines.append(f"  {key}: {val}")

    lines.append("")
    return "\n".join(lines)


def format_json(
    card: Scorecard,
    adapter_report: dict[str, Any] | None = None,
    failed_thresholds: list[dict] | None = None,
) -> str:
    # Build likely_causes and suggestions from flags
    likely_causes: list[str] = []
    suggestions: list[str] = []
    for flag in card.all_flags:
        if flag.severity in ("critical", "high"):
            likely_causes.append(flag.suggestion)
        suggestions.append(flag.suggestion)

    # Build judge_coverage
    judge_coverage: dict[str, dict] = {}
    for dim, score in card.dimension_scores.items():
        if dim in card.unscorable_dimensions:
            judge_coverage[dim] = {
                "scorable": False,
                "confidence": card.dimension_confidence.get(dim, "low"),
                "reason": "missing required data",
            }
        else:
            judge_coverage[dim] = {
                "scorable": True,
                "confidence": card.dimension_confidence.get(dim, "high"),
            }

    output: dict[str, Any] = {
        "total_score": card.total_score,
        "dimension_scores": card.dimension_scores,
        "dimension_confidence": card.dimension_confidence,
        "friction_flags": [asdict(f) for f in card.all_flags],
        "likely_causes": likely_causes,
        "suggestions": suggestions,
        "scorable_dimensions": card.scorable_dimensions,
        "unscorable_dimensions": card.unscorable_dimensions,
        "judge_coverage": judge_coverage,
        "adapter_capability_report": adapter_report or {},
        "failed_thresholds": failed_thresholds or [],
    }

    return json.dumps(output, indent=2)


def format_summary(card: Scorecard) -> str:
    """Concise, agent-friendly summary output.

    Designed for both human quick-scanning and agent programmatic parsing.
    Always under 10 lines of output.
    """
    lines: list[str] = []

    # Line 1: Score
    lines.append(f"Score: {card.total_score:.1f}/100")

    # Line 2: Top 3 flags by severity
    sorted_flags = sorted(
        card.all_flags,
        key=lambda f: SEVERITY_ORDER.get(f.severity, 99),
    )
    top_flags = sorted_flags[:3]
    if top_flags:
        flag_parts = [f.id for f in top_flags]
        lines.append(f"Flags: {', '.join(flag_parts)}")

    # Line 3: Key weak dimensions (scorable ones that scored < 50)
    weak_dims = [
        dim for dim in card.scorable_dimensions
        if (score := card.dimension_scores.get(dim)) is not None and score < 50
    ]
    if weak_dims:
        dim_strs = [
            f"{dim}={card.dimension_scores[dim]:.0f}"
            for dim in weak_dims[:3]
        ]
        lines.append(f"Weak: {', '.join(dim_strs)}")

    # Line 4: Diagnosis
    diagnosis = _build_diagnosis(card, top_flags, weak_dims)
    lines.append(f"Diagnosis: {diagnosis}")

    return "\n".join(lines)


def _build_diagnosis(
    card: Scorecard,
    top_flags: list[FrictionFlag],
    weak_dims: list[str],
) -> str:
    """Build a 1-2 sentence diagnosis from scorecard signals."""
    parts: list[str] = []

    if card.total_score < 40:
        parts.append("Agent run with significant friction")
    elif card.total_score < 70:
        parts.append("Agent completed with notable issues")
    elif card.total_score < 90:
        parts.append("Agent run mostly healthy with minor issues")

    if "reliability" in weak_dims:
        rel_score = card.dimension_scores.get("reliability", 0) or 0
        error_flags = [f for f in card.all_flags if "error" in f.id]
        if error_flags:
            parts.append(f"fix errors ({rel_score:.0f}/100 reliability)")
        else:
            parts.append(f"low reliability ({rel_score:.0f}/100)")

    if "efficiency" in weak_dims:
        parts.append("reduce token/tool usage")

    if "retrieval" in card.unscorable_dimensions:
        parts.append("no retrieval strategy detected")

    if not parts:
        return "Run looks good"

    return ". ".join(parts) + "."
