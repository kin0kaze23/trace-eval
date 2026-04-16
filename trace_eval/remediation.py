"""Rule-based guided remediation: diagnose → recommend → assess automation safety."""

from __future__ import annotations

from dataclasses import dataclass

from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag

ACTION_TYPES = {
    "reduce_retries": {
        "label": "Reduce tool call retries",
        "description": "Add branch guards or pre-conditions before tool calls to avoid repeated failures.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": True,
    },
    "reduce_prompt_size": {
        "label": "Reduce prompt scope",
        "description": "Break tasks into smaller steps to reduce token usage and context pressure.",
        "confidence": "medium",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "fix_errors": {
        "label": "Fix command errors",
        "description": "Review and fix failed commands. Common causes: missing dependencies, wrong paths, permission issues.",
        "confidence": "high",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "switch_profile": {
        "label": "Use appropriate scoring profile",
        "description": "Switch to 'coding_agent' profile if retrieval is not applicable to your workflow.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": False,
    },
    "reduce_tool_calls": {
        "label": "Reduce tool call volume",
        "description": "Batch operations where possible. Combine multiple file reads/writes into single calls.",
        "confidence": "medium",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "improve_retrieval": {
        "label": "Improve retrieval strategy",
        "description": "Use canonical retrieval entrypoint instead of fallback search.",
        "confidence": "high",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "add_ci_gate": {
        "label": "Add CI quality gate",
        "description": "Add trace-eval CI gate to prevent low-quality agent runs from being merged.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": True,
    },
}


@dataclass
class RemediationAction:
    action_type: str
    label: str
    description: str
    confidence: str  # "high", "medium", "low"
    safe_to_automate: bool
    requires_approval: bool
    triggered_by: str


def analyze(card: Scorecard) -> list[RemediationAction]:
    """Analyze a scorecard and return recommended remediation actions.

    Rules are deterministic: specific flag patterns and dimension scores
    map to specific recommended actions.
    """
    actions: list[RemediationAction] = []
    flag_ids = {f.id for f in card.all_flags}
    dim_scores = card.dimension_scores

    # Rule 1: reliability errors → fix_errors
    if "reliability_errors" in flag_ids:
        actions.append(_make_action("fix_errors", "reliability_errors"))

    # Rule 2: low reliability score → fix_errors (broader catch)
    rel_score = dim_scores.get("reliability")
    if rel_score is not None and rel_score < 50:
        if not any(a.action_type == "fix_errors" for a in actions):
            actions.append(_make_action("fix_errors", "low_reliability_score"))

    # Rule 3: high token usage → reduce_prompt_size
    if "efficiency_high_tokens" in flag_ids:
        actions.append(_make_action("reduce_prompt_size", "efficiency_high_tokens"))

    # Rule 4: high tool calls → reduce_tool_calls
    if "efficiency_high_tool_calls" in flag_ids:
        actions.append(_make_action("reduce_tool_calls", "efficiency_high_tool_calls"))

    # Rule 5: tool retries/redundant → reduce_retries
    if "tool_retries" in flag_ids or "tool_redundant" in flag_ids:
        actions.append(_make_action("reduce_retries", "tool_discipline_issue"))

    # Rule 6: retrieval issues → improve_retrieval
    retrieval_flags = {"retrieval_no_entrypoint", "retrieval_deprecated_file", "retrieval_fallback_search"}
    if flag_ids & retrieval_flags:
        actions.append(_make_action("improve_retrieval", "retrieval_issue"))

    # Rule 7: retrieval N/A for coding agent on default profile → suggest switch
    if "retrieval" in card.unscorable_dimensions and card.profile == "default":
        actions.append(_make_action("switch_profile", "retrieval_not_applicable"))

    # Rule 8: low overall score → suggest CI gate
    if card.total_score < 80:
        actions.append(_make_action("add_ci_gate", "low_overall_score"))

    # Sort by confidence (high first), then by action type
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (confidence_order.get(a.confidence, 9), a.action_type))

    return actions[:5]  # Top 5 actions


def _make_action(action_type: str, triggered_by: str) -> RemediationAction:
    template = ACTION_TYPES[action_type]
    return RemediationAction(
        action_type=action_type,
        label=template["label"],
        description=template["description"],
        confidence=template["confidence"],
        safe_to_automate=template["safe_to_automate"],
        requires_approval=template["requires_approval"],
        triggered_by=triggered_by,
    )


def format_remediation(actions: list[RemediationAction], card: Scorecard) -> str:
    """Format remediation actions for display."""
    if not actions:
        return "No recommended actions. Score looks good."

    lines = [
        "=" * 60,
        f"  REMEDIATION RECOMMENDATIONS  Score: {card.total_score:.1f}/100 [{card.rating}]",
        "=" * 60,
        "",
    ]

    for i, action in enumerate(actions, 1):
        approval_note = ""
        if action.safe_to_automate and not action.requires_approval:
            approval_note = " [AUTO-SAFE]"
        elif action.requires_approval:
            approval_note = " [REQUIRES APPROVAL]"
        lines.append(f"  {i}. {action.label}{approval_note}")
        lines.append(f"     {action.description}")
        lines.append(f"     Confidence: {action.confidence}")
        lines.append("")

    lines.append("To auto-apply safe fixes: trace-eval remediate trace.jsonl --apply-safe")
    lines.append("To generate full report: trace-eval remediate trace.jsonl --report")
    return "\n".join(lines)
