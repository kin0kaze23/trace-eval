"""Efficiency judge: Token usage, cost, latency, tool density."""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult

# Fixed component weights — these do NOT change when telemetry is missing.
# Missing components contribute zero weighted points, which is conservative:
# removing a low-scoring component cannot increase the score because its
# weight is retained but its contribution drops to zero.
TOKEN_WEIGHT = 0.4
COST_WEIGHT = 0.3
TOOL_DENSITY_WEIGHT = 0.3


def judge_efficiency(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation="No events to evaluate",
            raw_metrics={},
            scorable=False,
        )

    # Track which telemetry sources are actually observed (not missing).
    # A session with zero tool calls has OBSERVED zero tool calls,
    # not missing tool-call telemetry.
    has_token_data = any(e.tokens_in is not None or e.tokens_out is not None for e in events)
    has_cost_data = any(e.cost_estimate is not None for e in events)
    # Tool-call telemetry is "observed" if the trace contains any events
    # at all (the absence of tool_call events means zero observed calls).
    has_tool_calls = len(events) > 0
    has_latency = any(e.latency_ms is not None for e in events)

    # Compute observed values
    total_tokens = sum(
        (e.tokens_in or 0) + (e.tokens_out or 0) for e in events if e.tokens_in is not None or e.tokens_out is not None
    )
    cost_estimate = sum(e.cost_estimate or 0 for e in events if e.cost_estimate is not None)
    tool_call_count = sum(1 for e in events if e.event_type is not None and e.event_type.value == "tool_call")
    total_latency_ms = sum(e.latency_ms or 0 for e in events if e.latency_ms is not None)

    # Compute sub-scores using FIXED weights.
    # Missing components contribute 0 * weight = 0 to the total.
    # This ensures removing a low-scoring component cannot increase the score.
    score = 0.0

    if has_token_data:
        token_sub = max(0, 100 - total_tokens / 500)
        score += TOKEN_WEIGHT * token_sub

    if has_cost_data:
        cost_sub = max(0, 100 - cost_estimate * 100)
        score += COST_WEIGHT * cost_sub

    if has_tool_calls:
        tool_density_sub = max(0, 100 - tool_call_count * 2)
        score += TOOL_DENSITY_WEIGHT * tool_density_sub

    # If no efficiency metrics are available at all, the judge is not scorable
    if not has_token_data and not has_cost_data and not has_tool_calls:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation="No efficiency telemetry available (tokens, cost, tool calls all missing)",
            raw_metrics={
                "has_token_data": False,
                "has_cost_data": False,
                "has_tool_calls": False,
                "has_latency": False,
            },
            scorable=False,
        )

    # Latency penalty (only if latency data exists)
    if has_latency and total_latency_ms > 0:
        score -= min(20, total_latency_ms / 60000)

    score = max(0.0, min(100.0, score))

    # Confidence: high if all metrics present, medium if partial
    all_metrics = [has_token_data, has_cost_data, has_tool_calls]
    observed_count = sum(all_metrics)
    if observed_count == 3:
        confidence = "high"
    elif observed_count >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    # Telemetry coverage for reporting
    coverage = {
        "has_token_data": has_token_data,
        "has_cost_data": has_cost_data,
        "has_tool_calls": has_tool_calls,
        "has_latency": has_latency,
    }

    # Friction flags
    flags: list[FrictionFlag] = []
    if has_token_data and total_tokens > 25000:
        flags.append(
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="Reduce token usage with more focused prompts",
            )
        )
    if has_cost_data and cost_estimate > 1.0:
        flags.append(
            FrictionFlag(
                id="efficiency_high_cost",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="Cost exceeded $1 — consider cheaper model",
            )
        )
    if has_tool_calls and tool_call_count > 25:
        flags.append(
            FrictionFlag(
                id="efficiency_high_tool_calls",
                severity="low",
                dimension="efficiency",
                event_index=None,
                suggestion="Excessive tool calls detected",
            )
        )

    # Build explanation noting which metrics were observed vs missing
    missing = []
    if not has_token_data:
        missing.append("tokens")
    if not has_cost_data:
        missing.append("cost")
    missing_str = f" Missing: {', '.join(missing)}" if missing else ""

    return JudgeResult(
        score=score,
        confidence=confidence,
        friction_flags=flags,
        explanation=(
            f"Total tokens: {total_tokens}. Cost: ${cost_estimate:.4f}. "
            f"Tool calls: {tool_call_count}. Latency: {total_latency_ms}ms.{missing_str}"
        ),
        raw_metrics={
            "total_tokens": total_tokens,
            "cost_estimate": cost_estimate,
            "tool_call_count": tool_call_count,
            "total_latency_ms": total_latency_ms,
            **coverage,
        },
        scorable=True,
    )
