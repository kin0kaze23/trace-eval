"""Rule-based guided remediation: diagnose → recommend → assess automation safety."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from trace_eval.schema import Event, FrictionFlag
from trace_eval.scoring import Scorecard

# v1 static mapping: missing-tool patterns → agent-ready capability IDs.
# Not imported from agent-ready — trace-eval references by string only.
_CAPABILITY_HINTS = {
    # pattern (case-insensitive regex) → agent-ready capability ID
    r"command not found:\s*vercel": "vercel_cli",
    r"vercel:\s*command not found": "vercel_cli",
    r"command not found:\s*gh\b": "github_cli",
    r"gh:\s*command not found": "github_cli",
    r"command not found:\s*node\b": "nodejs",
    r"node:\s*command not found": "nodejs",
    r"command not found:\s*python3?": "python",
    r"python3?:\s*command not found": "python",
    r"ModuleNotFoundError": "python",
    r"Cannot find module\s+['\"]": "nodejs",
}

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
        "label": "Use appropriate scoring preset",
        "description": "Switch to 'coding_agent' preset if retrieval is not applicable to your workflow.",
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
        "description": "Add trace-eval CI gate to prevent low-quality agent sessions from being merged.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": True,
    },
    "install_capability": {
        "label": "Install missing tool",
        "description": "A required tool is not installed in the environment.",
        "confidence": "high",
        "safe_to_automate": False,
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
    context: dict[str, str] = field(default_factory=dict)


def analyze(card: Scorecard) -> list[RemediationAction]:
    """Analyze a scorecard and return recommended remediation actions.

    Rules are deterministic: specific flag patterns and dimension scores
    map to specific recommended actions.

    This is the legacy entry point — for enriched actions with trace context,
    use analyze_with_context(card, events).
    """
    return _analyze_rules(card, events=None)


def analyze_with_context(card: Scorecard, events: list[Event]) -> list[RemediationAction]:
    """Analyze a scorecard with full trace context for specific remediation.

    Enriches action labels and descriptions with actual failure data:
    - Which tools failed and how often
    - What error patterns appeared
    - Specific event indices and counts
    """
    return _analyze_rules(card, events=events)


def _analyze_rules(card: Scorecard, events: list[Event] | None) -> list[RemediationAction]:
    """Core rule engine. If events are provided, enriches actions with context."""
    actions: list[RemediationAction] = []
    flag_ids = {f.id for f in card.all_flags}
    dim_scores = card.dimension_scores

    # Extract contextual failure data if events are available
    error_tools: dict[str, int] = {}
    error_patterns: list[str] = []
    tool_retry_tools: dict[str, int] = {}
    total_errors = 0
    if events:
        error_tools, error_patterns, tool_retry_tools, total_errors = _extract_failure_context(events, card.all_flags)

    # Rule 1: reliability errors → fix_errors
    if "reliability_errors" in flag_ids:
        if error_tools and total_errors > 0:
            # Enriched: reference specific tools and counts
            top_tools = sorted(error_tools.items(), key=lambda x: -x[1])[:3]
            tool_strs = [f"{name} ({count}x)" for name, count in top_tools]
            actions.append(
                _make_action_enriched(
                    "fix_errors",
                    "reliability_errors",
                    label=f"Fix {total_errors} command error(s)",
                    description=(
                        f"Most frequent failures: {', '.join(tool_strs)}. "
                        f"Common patterns: {', '.join(error_patterns[:3])}. "
                        f"Review error events and add pre-conditions or guards."
                    ),
                )
            )
        else:
            actions.append(_make_action("fix_errors", "reliability_errors"))

    # Rule 2: low reliability score → fix_errors (broader catch)
    rel_score = dim_scores.get("reliability")
    if rel_score is not None and rel_score < 50:
        if not any(a.action_type == "fix_errors" for a in actions):
            if error_tools and total_errors > 0:
                top_tools = sorted(error_tools.items(), key=lambda x: -x[1])[:3]
                tool_strs = [f"{name} ({count}x)" for name, count in top_tools]
                actions.append(
                    _make_action_enriched(
                        "fix_errors",
                        "low_reliability_score",
                        label=f"Fix reliability ({rel_score:.0f}/100) — {total_errors} error(s)",
                        description=(
                            f"Failing tools: {', '.join(tool_strs)}. "
                            f"Patterns: {', '.join(error_patterns[:3])}. "
                            f"Add error handling or pre-conditions before these calls."
                        ),
                    )
                )
            else:
                actions.append(_make_action("fix_errors", "low_reliability_score"))

    # Rule 3: high token usage → reduce_prompt_size
    if "efficiency_high_tokens" in flag_ids:
        token_info = _extract_token_context(events) if events else None
        if token_info:
            actions.append(
                _make_action_enriched(
                    "reduce_prompt_size",
                    "efficiency_high_tokens",
                    label=f"Reduce token usage ({token_info['total_tokens']:,} tokens)",
                    description=(
                        f"Agent used {token_info['total_tokens']:,} tokens across "
                        f"{token_info['llm_calls']} LLM calls. "
                        f"Break tasks into smaller steps or use focused prompts."
                    ),
                )
            )
        else:
            actions.append(_make_action("reduce_prompt_size", "efficiency_high_tokens"))

    # Rule 4: high tool calls → reduce_tool_calls
    if "efficiency_high_tool_calls" in flag_ids:
        tool_info = _extract_tool_context(events) if events else None
        if tool_info:
            top_tools = sorted(tool_info.items(), key=lambda x: -x[1])[:3]
            tool_strs = [f"{name} ({count}x)" for name, count in top_tools]
            actions.append(
                _make_action_enriched(
                    "reduce_tool_calls",
                    "efficiency_high_tool_calls",
                    label=f"Reduce tool call volume ({tool_info['total']} calls)",
                    description=(
                        f"Most used tools: {', '.join(tool_strs)}. "
                        f"Batch operations where possible — combine reads, use wildcards."
                    ),
                )
            )
        else:
            actions.append(_make_action("reduce_tool_calls", "efficiency_high_tool_calls"))

    # Rule 5: tool retries/redundant → reduce_retries
    if "tool_retries" in flag_ids or "tool_redundant" in flag_ids:
        retry_label = "Reduce tool call retries"
        retry_desc = "Add branch guards or pre-conditions before tool calls to avoid repeated failures."
        if tool_retry_tools:
            top_retry = sorted(tool_retry_tools.items(), key=lambda x: -x[1])[:3]
            retry_strs = [f"{name} ({count}x)" for name, count in top_retry]
            retry_label = f"Reduce tool retries ({', '.join(retry_strs)})"
            retry_desc = (
                f"These tools retried after failure: {', '.join(retry_strs)}. "
                f"Pre-check conditions (file exists, permissions, branch) before calling."
            )
        actions.append(
            _make_action_enriched(
                "reduce_retries",
                "tool_discipline_issue",
                label=retry_label,
                description=retry_desc,
            )
        )

    # Rule 6: retrieval issues → improve_retrieval
    retrieval_flags = {
        "retrieval_no_entrypoint",
        "retrieval_deprecated_file",
        "retrieval_fallback_search",
    }
    if flag_ids & retrieval_flags:
        actions.append(_make_action("improve_retrieval", "retrieval_issue"))

    # Rule 7: retrieval N/A for coding agent on default profile → suggest switch
    if "retrieval" in card.unscorable_dimensions and card.profile == "default":
        actions.append(_make_action("switch_profile", "retrieval_not_applicable"))

    # Rule 8: low overall score → suggest CI gate
    if card.total_score < 80:
        actions.append(_make_action("add_ci_gate", "low_overall_score"))

    # Rule 9: missing-tool patterns detected → install_capability
    # One action per distinct capability_id; deduped across multiple patterns.
    missing_caps = _detect_missing_capabilities(events, error_patterns, card.all_flags)
    for cap_id, trigger in missing_caps.items():
        suggested_cmd = f"agent-ready fix --capability {cap_id}"
        actions.append(
            RemediationAction(
                action_type="install_capability",
                label=f"Install missing tool: {cap_id}",
                description=f"Detected '{trigger}' in trace. Run: {suggested_cmd}",
                confidence=ACTION_TYPES["install_capability"]["confidence"],
                safe_to_automate=ACTION_TYPES["install_capability"]["safe_to_automate"],
                requires_approval=ACTION_TYPES["install_capability"]["requires_approval"],
                triggered_by=trigger,
                context={"capability_id": cap_id, "suggested_command": suggested_cmd},
            )
        )

    # Sort by confidence (high first), then by action type
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (confidence_order.get(a.confidence, 9), a.action_type))

    return actions[:5]  # Top 5 actions


def _extract_failure_context(
    events: list[Event], flags: list[FrictionFlag]
) -> tuple[dict[str, int], list[str], dict[str, int], int]:
    """Extract tool failure context from events.

    Returns:
        - error_tools: {tool_name: count} of tools that produced errors
        - error_patterns: list of error pattern descriptions
        - tool_retry_tools: {tool_name: count} of tools that retried
        - total_errors: total error count
    """
    error_tools: dict[str, int] = {}
    tool_retry_tools: dict[str, int] = {}
    total_errors = 0

    error_event_indices = set()
    for f in flags:
        if f.event_index is not None:
            error_event_indices.add(f.event_index)

    # Count errors by tool name
    error_events = [e for e in events if e.status is not None and e.status.value == "error"]
    total_errors = len(error_events)

    for e in error_events:
        tool = e.tool_name or "unknown"
        error_tools[tool] = error_tools.get(tool, 0) + 1

    # Detect retry patterns (same tool error then success)
    tool_calls = [e for e in events if e.event_type is not None and e.event_type.value == "tool_call"]
    for i in range(1, len(tool_calls)):
        prev = tool_calls[i - 1]
        curr = tool_calls[i]
        if (
            curr.tool_name == prev.tool_name
            and prev.status is not None
            and prev.status.value == "error"
            and curr.status is not None
            and curr.status.value == "success"
        ):
            tool_name = curr.tool_name or "unknown"
            tool_retry_tools[tool_name] = tool_retry_tools.get(tool_name, 0) + 1

    # Detect error patterns from event metadata
    patterns: list[str] = []
    error_types = set()
    for e in error_events:
        if e.error_type:
            error_types.add(e.error_type)

    if error_types:
        patterns.extend(list(error_types)[:3])

    # Infer patterns from tool names
    if "Bash" in error_tools or "bash" in error_tools:
        patterns.append("command execution")
    if "Write" in error_tools or "write" in error_tools:
        patterns.append("file write")
    if "Read" in error_tools or "read" in error_tools:
        patterns.append("file read")
    if "Glob" in error_tools or "glob" in error_tools:
        patterns.append("file search")
    if "Edit" in error_tools or "edit" in error_tools:
        patterns.append("file edit")

    # Deduplicate patterns
    seen = set()
    unique_patterns = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique_patterns.append(p)

    return error_tools, unique_patterns, tool_retry_tools, total_errors


def _extract_token_context(events: list[Event]) -> dict | None:
    """Extract token usage context from events."""
    total_tokens = sum((e.tokens_in or 0) + (e.tokens_out or 0) for e in events)
    if total_tokens == 0:
        return None

    llm_calls = sum(1 for e in events if e.event_type is not None and e.event_type.value == "llm_call")

    return {
        "total_tokens": total_tokens,
        "llm_calls": llm_calls,
    }


def _extract_tool_context(events: list[Event]) -> dict | None:
    """Extract tool call context from events."""
    tool_counts: dict[str, int] = {}
    total = 0
    for e in events:
        if e.event_type is not None and e.event_type.value == "tool_call":
            name = e.tool_name or "unknown"
            tool_counts[name] = tool_counts.get(name, 0) + 1
            total += 1

    if total == 0:
        return None

    tool_counts["total"] = total
    return tool_counts


def _detect_missing_capabilities(
    events: list[Event] | None,
    error_patterns: list[str],
    flags: list[FrictionFlag],
) -> dict[str, str]:
    """Scan trace for missing-tool patterns and return {capability_id: first_triggering_pattern}.

    Sources scanned (in order):
    1. error_patterns extracted from event error_type fields
    2. raw event error_type fields (unlimited, unlike error_patterns[:3])
    3. friction flag suggestions

    Each capability_id appears at most once — multiple patterns mapping to
    the same capability are deduped, keeping the first trigger.
    """
    seen: dict[str, str] = {}  # capability_id → triggering pattern

    def _scan(text: str) -> None:
        if seen is None:
            return
        for pattern, cap_id in _CAPABILITY_HINTS.items():
            if cap_id in seen:
                continue
            if re.search(pattern, text, re.IGNORECASE):
                seen[cap_id] = text

    # Source 1: error patterns from _extract_failure_context
    for p in error_patterns:
        _scan(p)

    # Source 2: raw event error_type fields (not capped at 3)
    if events:
        for e in events:
            if e.error_type:
                _scan(e.error_type)

    # Source 3: friction flag suggestions
    for f in flags:
        _scan(f.suggestion)

    return seen


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


def _make_action_enriched(
    action_type: str,
    triggered_by: str,
    label: str,
    description: str,
) -> RemediationAction:
    template = ACTION_TYPES[action_type]
    return RemediationAction(
        action_type=action_type,
        label=label,
        description=description,
        confidence=template["confidence"],
        safe_to_automate=template["safe_to_automate"],
        requires_approval=template["requires_approval"],
        triggered_by=triggered_by,
    )


def format_remediation(actions: list[RemediationAction], card: Scorecard) -> str:
    """Format remediation actions for display with top-3 prioritization."""
    if not actions:
        return "No recommended actions. Score looks good."

    lines = [
        "=" * 60,
        f"  REMEDIATION RECOMMENDATIONS  Score: {card.total_score:.1f}/100 [{card.rating}]",
        "=" * 60,
        "",
    ]

    # Top 3 actions prominently
    top_3 = actions[:3]
    lines.append("  TOP 3 ACTIONS:")
    for i, action in enumerate(top_3, 1):
        approval_tag = (
            "[AUTO-SAFE]" if (action.safe_to_automate and not action.requires_approval) else "[REQUIRES APPROVAL]"
        )
        lines.append(f"  {i}. {approval_tag} {action.label}")
        lines.append(f"     {action.description}")
        lines.append(f"     Confidence: {action.confidence}")
        lines.append("")

    # Remaining actions beyond top 3
    remaining = actions[3:]
    if remaining:
        lines.append("  Additional actions:")
        for i, action in enumerate(remaining, 4):
            approval_tag = (
                "[AUTO-SAFE]" if (action.safe_to_automate and not action.requires_approval) else "[REQUIRES APPROVAL]"
            )
            lines.append(f"  {i}. {approval_tag} {action.label}")
            lines.append(f"     {action.description}")
            lines.append("")

    lines.append("To auto-apply safe fixes: trace-eval remediate trace.jsonl --apply-safe")
    lines.append("To generate full report: trace-eval remediate trace.jsonl --report")
    return "\n".join(lines)


def format_next_steps(actions: list[RemediationAction], card: Scorecard) -> str:
    """Compact top-3 next-actions for inline display after scorecard."""
    if not actions:
        return "\nNo recommended actions. Score looks good."

    lines = [
        "",
        "Next steps:",
    ]
    for i, action in enumerate(actions[:3], 1):
        approval_tag = (
            "[AUTO-SAFE]" if (action.safe_to_automate and not action.requires_approval) else "[REQUIRES APPROVAL]"
        )
        lines.append(f"  {i}. {approval_tag} {action.label}")
    return "\n".join(lines)
