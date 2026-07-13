"""Tool Discipline judge: Retries, redundancy, timeouts, fallbacks.

Uses tool call/result correlation via tool_call_id for accurate
retry and timeout detection. Does not infer status from tool_call events.
"""

from __future__ import annotations

from trace_eval.schema import Event, EventType, FrictionFlag, JudgeResult
from trace_eval.tool_correlation import (
    compute_correlation_metrics,
    correlation_confidence,
    pair_tool_attempts,
)


def judge_tool_discipline(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation="No events to evaluate",
            raw_metrics={},
            scorable=False,
        )

    # Check if there are any tool-related events
    has_tool_activity = any(e.event_type in (EventType.tool_call, EventType.tool_result) for e in events)
    if not has_tool_activity:
        return JudgeResult(
            score=100.0,
            confidence="high",
            friction_flags=[],
            explanation="No tool activity — perfect discipline by default",
            raw_metrics={"tool_attempts": 0, "paired_attempts": 0},
            scorable=True,
        )

    # Pair tool calls with results using correlation IDs
    attempts = pair_tool_attempts(events)
    metrics = compute_correlation_metrics(attempts)
    confidence = correlation_confidence(metrics)

    # Count fallback events (unchanged from original)
    fallback_events = sum(1 for e in events if e.event_type == EventType.search_fallback)

    # Scoring
    score = 100.0
    score -= min(30, 10 * metrics["tool_retries"])
    score -= min(30, 8 * metrics["redundant_calls"])
    score -= min(30, 15 * metrics["tool_timeouts"])
    score -= min(15, 5 * fallback_events)
    score = max(0.0, score)

    # Friction flags
    flags: list[FrictionFlag] = []
    if metrics["tool_retries"] > 0:
        flags.append(
            FrictionFlag(
                id="tool_retries",
                severity="medium",
                dimension="tool_discipline",
                event_index=None,
                suggestion=f"{metrics['tool_retries']} tool retry(ies) detected",
            )
        )
    if metrics["redundant_calls"] > 0:
        flags.append(
            FrictionFlag(
                id="tool_redundant",
                severity="low",
                dimension="tool_discipline",
                event_index=None,
                suggestion=f"{metrics['redundant_calls']} redundant tool call(s)",
            )
        )
    if metrics["tool_timeouts"] > 0:
        flags.append(
            FrictionFlag(
                id="tool_timeout",
                severity="high",
                dimension="tool_discipline",
                event_index=None,
                suggestion=f"{metrics['tool_timeouts']} tool call(s) timed out",
            )
        )
    if metrics["unmatched_calls"] > 0:
        flags.append(
            FrictionFlag(
                id="tool_unmatched_calls",
                severity="low",
                dimension="tool_discipline",
                event_index=None,
                suggestion=f"{metrics['unmatched_calls']} tool call(s) without results",
            )
        )

    explanation = (
        f"Retries: {metrics['tool_retries']}. "
        f"Redundant: {metrics['redundant_calls']}. "
        f"Timeouts: {metrics['tool_timeouts']}. "
        f"Fallbacks: {fallback_events}. "
        f"Paired: {metrics['paired_attempts']}/{metrics['tool_attempts']} "
        f"({metrics['correlation_coverage_pct']}% coverage). "
        f"Unmatched calls: {metrics['unmatched_calls']}. "
        f"Orphan results: {metrics['orphan_results']}."
    )

    return JudgeResult(
        score=score,
        confidence=confidence,
        friction_flags=flags,
        explanation=explanation,
        raw_metrics={
            **metrics,
            "fallback_events": fallback_events,
        },
        scorable=True,
    )
