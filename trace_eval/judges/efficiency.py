"""Efficiency judge: Token usage, cost, latency, tool density."""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult


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

    # Track which telemetry sources are actually observed (not missing)
    has_token_data = any(e.tokens_in is not None or e.tokens_out is not None for e in events)
    has_cost_data = any(e.cost_estimate is not None for e in events)
    has_tool_calls = any(e.event_type is not None and e.event_type.value == "tool_call" for e in events)
    has_latency = any(e.latency_ms is not None for e in events)

    # Compute observed values (only from events that actually have the data)
    total_tokens = sum(
        (e.tokens_in or 0) + (e.tokens_out or 0) for e in events if e.tokens_in is not None or e.tokens_out is not None
    )
    cost_estimate = sum(e.cost_estimate or 0 for e in events if e.cost_estimate is not None)
    tool_call_count = sum(1 for e in events if e.event_type is not None and e.event_type.value == "tool_call")
    total_latency_ms = sum(e.latency_ms or 0 for e in events if e.latency_ms is not None)

    # Build sub-scores only from observed telemetry
    DEFAULT_WEIGHTS = {
        "tokens": 0.4,
        "cost": 0.3,
        "tool_density": 0.3,
    }

    sub_scores: dict[str, float] = {}
    active_weights: dict[str, float] = {}

    if has_token_data:
        sub_scores["tokens"] = max(0, 100 - total_tokens / 500)
        active_weights["tokens"] = DEFAULT_WEIGHTS["tokens"]

    if has_cost_data:
        sub_scores["cost"] = max(0, 100 - cost_estimate * 100)
        active_weights["cost"] = DEFAULT_WEIGHTS["cost"]

    if has_tool_calls:
        sub_scores["tool_density"] = max(0, 100 - tool_call_count * 2)
        active_weights["tool_density"] = DEFAULT_WEIGHTS["tool_density"]

    # If no efficiency metrics are available at all, the judge is not scorable
    if not sub_scores:
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

    # Proportionally redistribute weights across available sub-scores
    total_active_weight = sum(active_weights.values())
    score = 0.0
    for name, sub_score in sub_scores.items():
        weight = active_weights[name] / total_active_weight if total_active_weight > 0 else 0
        score += weight * sub_score

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
    if not has_tool_calls:
        missing.append("tool_calls")
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
            "has_token_data": has_token_data,
            "has_cost_data": has_cost_data,
            "has_tool_calls": has_tool_calls,
            "has_latency": has_latency,
        },
        scorable=True,
    )
