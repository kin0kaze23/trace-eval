"""Efficiency judge: Token usage, cost, latency, tool density."""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult


def judge_efficiency(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="No events to evaluate", raw_metrics={}, scorable=False,
        )

    total_tokens = sum(
        (e.tokens_in or 0) + (e.tokens_out or 0) for e in events
    )
    cost_estimate = sum(e.cost_estimate or 0 for e in events)
    tool_call_count = sum(
        1 for e in events
        if e.event_type is not None and e.event_type.value == "tool_call"
    )
    total_latency_ms = sum(e.latency_ms or 0 for e in events)

    # Sub-scores
    token_sub = max(0, 100 - total_tokens / 500)
    cost_sub = max(0, 100 - cost_estimate * 100)
    tool_density_sub = max(0, 100 - tool_call_count * 2)

    score = (token_sub * 0.4) + (cost_sub * 0.3) + (tool_density_sub * 0.3)

    # Latency penalty (only if latency data exists)
    has_latency = any(e.latency_ms is not None for e in events)
    if has_latency and total_latency_ms > 0:
        score -= min(20, total_latency_ms / 60000)

    score = max(0.0, score)

    # Friction flags
    flags: list[FrictionFlag] = []
    if total_tokens > 25000:
        flags.append(FrictionFlag(
            id="efficiency_high_tokens", severity="medium",
            dimension="efficiency", event_index=None,
            suggestion="Reduce token usage with more focused prompts",
        ))
    if cost_estimate > 1.0:
        flags.append(FrictionFlag(
            id="efficiency_high_cost", severity="medium",
            dimension="efficiency", event_index=None,
            suggestion="Cost exceeded $1 — consider cheaper model",
        ))
    if tool_call_count > 25:
        flags.append(FrictionFlag(
            id="efficiency_high_tool_calls", severity="low",
            dimension="efficiency", event_index=None,
            suggestion="Excessive tool calls detected",
        ))

    return JudgeResult(
        score=score,
        confidence="medium" if has_latency else "high",
        friction_flags=flags,
        explanation=(
            f"Total tokens: {total_tokens}. Cost: ${cost_estimate:.4f}. "
            f"Tool calls: {tool_call_count}. Latency: {total_latency_ms}ms."
        ),
        raw_metrics={
            "total_tokens": total_tokens,
            "cost_estimate": cost_estimate,
            "tool_call_count": tool_call_count,
            "total_latency_ms": total_latency_ms,
        },
        scorable=True,
    )
