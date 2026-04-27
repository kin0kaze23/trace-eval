"""Report formatting: text and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from trace_eval.schema import FrictionFlag
from trace_eval.scoring import Scorecard

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ScoreRating(Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    NEEDS_WORK = "Needs Work"
    CRITICAL = "Critical"


# Plain-English score interpretation
SCORE_INTERPRETATION = {
    (80, 100): ("Good", "A clean session with minimal friction"),
    (60, 80): ("Fair", "Some issues but the agent completed the task"),
    (40, 60): ("Poor", "Significant friction — errors or wasted effort"),
    (0, 40): ("Critical", "Major problems — the agent struggled to complete the task"),
}


def score_interpretation(score: float) -> str:
    """Return a plain-English interpretation of a score with context."""
    for (low, high), (label, desc) in sorted(SCORE_INTERPRETATION.items(), key=lambda x: -x[0][0]):
        if low <= score < high:
            return f"{label} — {desc}"
    if score >= 100:
        return "Excellent — Near-perfect session"
    return "Unknown"


def compute_rating(score: float) -> ScoreRating:
    """Map a 0-100 score to a human-readable rating."""
    if score >= 90:
        return ScoreRating.EXCELLENT
    elif score >= 70:
        return ScoreRating.GOOD
    elif score >= 40:
        return ScoreRating.NEEDS_WORK
    else:
        return ScoreRating.CRITICAL


def format_text(card: Scorecard, adapter_report: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    preset_note = f"  Preset: {card.profile}" if card.profile != "default" else ""
    lines.append("=" * 60)
    lines.append(f"  TRACE-EVAL SESSION SCORE  Total: {card.total_score:.1f}/100  [{card.rating}]")
    if preset_note:
        lines.append(preset_note)
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

    lines.append("SCORE AREAS:")
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
        lines.append("  * = unscorable score area — weight redistributed to scorable areas")

    if sorted_flags:
        lines.append("")
        lines.append("ISSUES (sorted by severity):")
        for flag in sorted_flags:
            severity_tag = f"[{flag.severity.upper()}]"
            idx = f" @event {flag.event_index}" if flag.event_index is not None else ""
            lines.append(f"  {severity_tag} {flag.id}{idx}")
            lines.append(f"    -> {flag.suggestion}")

    if adapter_report:
        lines.append("")
        lines.append("CONNECTOR CAPABILITIES:")
        for key, val in adapter_report.items():
            lines.append(f"  {key}: {val}")

    lines.append("")
    return "\n".join(lines)


def format_json(
    card: Scorecard,
    adapter_report: dict[str, Any] | None = None,
    failed_thresholds: list[dict] | None = None,
    actions: list[Any] | None = None,
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
    for dim, _score in card.dimension_scores.items():
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

    # Build top_issues: top 3 friction flags sorted by severity
    sorted_flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
    top_issues = [{"id": f.id, "severity": f.severity, "summary": f.suggestion} for f in sorted_flags[:3]]

    # Build top_actions: AUTO-SAFE first, then by confidence, then action_type alphabetically
    if actions:
        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        sorted_actions = sorted(
            actions,
            key=lambda a: (
                not (a.safe_to_automate and not a.requires_approval),
                confidence_rank.get(a.confidence, 9),
                a.action_type,
            ),
        )
        top_actions = [
            {
                "action_type": a.action_type,
                "label": a.label,
                "description": a.description,
                "confidence": a.confidence,
                "safe_to_automate": a.safe_to_automate,
                "requires_approval": a.requires_approval,
            }
            for a in sorted_actions[:3]
        ]
    else:
        top_actions = []

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
        "rating": card.rating,
        "top_issues": top_issues,
        "top_actions": top_actions,
    }

    return json.dumps(output, indent=2)


def format_summary(card: Scorecard) -> str:
    """Concise, agent-friendly summary output.

    Designed for both human quick-scanning and agent programmatic parsing.
    Always under 10 lines of output.
    """
    lines: list[str] = []

    # Line 1: Score
    lines.append(f"Score: {card.total_score:.1f}/100  [{card.rating}]")

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
        dim for dim in card.scorable_dimensions if (score := card.dimension_scores.get(dim)) is not None and score < 50
    ]
    if weak_dims:
        dim_strs = [f"{dim}={card.dimension_scores[dim]:.0f}" for dim in weak_dims[:3]]
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


def format_session_default(result: dict) -> str:
    """Plain-English output for the default `trace-eval` command.

    Designed for both devs and non-devs.
    Problem-first format: what went wrong, evidence, what to fix.
    """
    if result.get("error"):
        lines = [result["error"]]
        if result.get("hint"):
            lines.append(result["hint"])
        return "\n".join(lines)

    card = result.get("scorecard")
    if card is None:
        return "ERROR: No scorecard available"

    interpretation = score_interpretation(card.total_score)
    actions = result.get("actions", [])

    # Build problem summary from extracted context
    error_count = 0
    error_tools = result.get("error_summary", {})
    if error_tools:
        error_count = sum(error_tools.values())

    token_info = result.get("token_info", {})
    tool_info = result.get("tool_info", {})
    retry_info = result.get("retry_info", {})

    lines: list[str] = []

    # Score line with visual indicator
    score_icon = _score_icon(card.total_score)
    lines.append(f"{score_icon} Session score: {card.total_score:.0f}/100 — {interpretation}")
    lines.append("")

    # Task context (if available)
    task_label = result.get("task_label")
    task_agent = result.get("trace_agent", "")
    session_duration = result.get("session_duration")
    if task_label or task_agent:
        parts = []
        if task_agent:
            agent_display = _agent_display_name(task_agent)
            parts.append(f"Agent: {agent_display}")
        if task_label:
            parts.append(f"Task: {task_label}")
        if session_duration:
            parts.append(f"Duration: {session_duration}")
        lines.append(" | ".join(parts))
        lines.append("")

    # Problem summary line
    problem_parts = []
    if error_count > 0:
        problem_parts.append(f"{error_count} command error{'s' if error_count != 1 else ''}")
    total_tokens = token_info.get("total_tokens", 0)
    if total_tokens >= 1_000_000:
        problem_parts.append(f"{total_tokens / 1_000_000:.0f}M tokens")
    elif total_tokens >= 1_000:
        problem_parts.append(f"{total_tokens / 1_000:.0f}K tokens")
    total_tools = tool_info.get("total", 0)
    if total_tools > 0:
        problem_parts.append(f"{total_tools} tool calls")
    total_retries = retry_info.get("total", 0)
    if total_retries > 0:
        problem_parts.append(f"{total_retries} retries")

    if problem_parts:
        lines.append(" | ".join(problem_parts))
        lines.append("")

    # Top actions in plain English (description-first, not label-first)
    if actions:
        lines.append("What to fix:")
        for i, action in enumerate(actions[:3], 1):
            tag = _action_tag(action)
            lines.append(f"  {i}. {tag} {action.description}")
        lines.append("")
        lines.append("More detail: trace-eval --details")
        lines.append("For agents:  trace-eval --json")
    else:
        lines.append("No issues detected. Session looks clean.")

    return "\n".join(lines)


def _score_icon(score: float) -> str:
    """Return a visual indicator for the score."""
    if score >= 80:
        return "✓"
    elif score >= 60:
        return "~"
    elif score >= 40:
        return "!"
    else:
        return "✗"


def _agent_display_name(agent_type: str) -> str:
    """Convert internal agent type to a display name."""
    names = {
        "claude-code": "Claude Code",
        "openclaw": "OpenClaw",
        "cursor": "Cursor",
        "canonical": "Agent",
    }
    return names.get(agent_type, agent_type.title())


def _action_tag(action) -> str:
    """Return a short tag for the action type."""
    if action.safe_to_automate and not action.requires_approval:
        return "[auto-fix]"
    return "[needs your OK]"
