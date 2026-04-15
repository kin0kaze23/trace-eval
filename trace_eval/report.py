"""Report formatting: text and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from trace_eval.scoring import Scorecard

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def format_text(card: Scorecard, adapter_report: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  TRACE-EVAL SCORECARD  Total: {card.total_score:.1f}/100")
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
        score_str = f"{score:.1f}" if score is not None else "N/A"
        marker = " *" if dim in card.unscorable_dimensions else ""
        lines.append(f"  {dim:20s} {score_str:>6s}  ({conf}){marker}")

    if card.unscorable_dimensions:
        lines.append("")
        lines.append("  * = unscorable (missing data)")

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
