"""Tool Discipline judge: Retries, redundancy, timeouts, fallbacks."""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult


def judge_tool_discipline(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="No events to evaluate", raw_metrics={}, scorable=False,
        )

    # Count tool retries: consecutive events with same tool_name, error then success
    tool_retries = 0
    tool_calls = [e for e in events if e.event_type is not None and e.event_type.value == "tool_call"]
    for i in range(1, len(tool_calls)):
        if (tool_calls[i].tool_name == tool_calls[i - 1].tool_name
                and tool_calls[i - 1].status is not None
                and tool_calls[i - 1].status.value == "error"
                and tool_calls[i].status is not None
                and tool_calls[i].status.value == "success"):
            tool_retries += 1

    # Count redundant calls: adjacent same tool_name + identical tool_args
    # Exclude retry pairs (error→success) — those are counted as retries, not redundant
    redundant_calls = 0
    for i in range(1, len(tool_calls)):
        prev_is_error = (
            tool_calls[i - 1].status is not None
            and tool_calls[i - 1].status.value == "error"
        )
        if (tool_calls[i].tool_name == tool_calls[i - 1].tool_name
                and tool_calls[i].tool_args == tool_calls[i - 1].tool_args
                and not prev_is_error):
            redundant_calls += 1

    # Count tool timeouts
    tool_timeouts = sum(
        1 for e in events
        if e.status is not None and e.status.value == "timeout"
        and e.event_type is not None and e.event_type.value == "tool_call"
    )

    # Count fallback events
    fallback_events = sum(
        1 for e in events
        if e.event_type is not None and e.event_type.value == "search_fallback"
    )

    score = 100.0
    score -= min(30, 10 * tool_retries)
    score -= min(30, 8 * redundant_calls)
    score -= min(30, 15 * tool_timeouts)
    score -= min(15, 5 * fallback_events)
    score = max(0.0, score)

    # Friction flags
    flags: list[FrictionFlag] = []
    if tool_retries > 0:
        flags.append(FrictionFlag(
            id="tool_retries", severity="medium",
            dimension="tool_discipline", event_index=tool_calls[0].event_index,
            suggestion=f"{tool_retries} tool retry(ies) detected",
        ))
    if redundant_calls > 0:
        flags.append(FrictionFlag(
            id="tool_redundant", severity="low",
            dimension="tool_discipline", event_index=tool_calls[0].event_index,
            suggestion=f"{redundant_calls} redundant tool call(s)",
        ))
    if tool_timeouts > 0:
        timeout_events = [e for e in events if e.status and e.status.value == "timeout" and e.event_type and e.event_type.value == "tool_call"]
        flags.append(FrictionFlag(
            id="tool_timeout", severity="high",
            dimension="tool_discipline",
            event_index=timeout_events[0].event_index if timeout_events else None,
            suggestion=f"{tool_timeouts} tool call(s) timed out",
        ))

    return JudgeResult(
        score=score,
        confidence="high",
        friction_flags=flags,
        explanation=(
            f"Retries: {tool_retries}. Redundant: {redundant_calls}. "
            f"Timeouts: {tool_timeouts}. Fallbacks: {fallback_events}."
        ),
        raw_metrics={
            "tool_retries": tool_retries,
            "redundant_calls": redundant_calls,
            "tool_timeouts": tool_timeouts,
            "fallback_events": fallback_events,
        },
        scorable=True,
    )
