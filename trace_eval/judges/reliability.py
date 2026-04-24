"""Reliability judge: Did the run succeed?"""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult


def judge_reliability(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation="No events to evaluate",
            raw_metrics={},
            scorable=False,
        )

    # Find terminal event (session_end or last event)
    terminal_event = None
    for e in reversed(events):
        if e.event_type is not None and e.event_type.value == "session_end":
            terminal_event = e
            break
    if terminal_event is None:
        terminal_event = events[-1]

    terminal_status = terminal_event.status
    terminal_value = terminal_status.value if terminal_status else "unknown"

    # Count NON-TERMINAL events by status (exclude terminal to avoid double-penalizing)
    non_terminal = [e for e in events if e is not terminal_event]

    error_count = sum(1 for e in non_terminal if e.status and e.status.value == "error")
    timeout_count = sum(1 for e in non_terminal if e.status and e.status.value == "timeout")
    partial_count = sum(1 for e in non_terminal if e.status and e.status.value == "partial")

    # Base score from terminal outcome
    base_scores = {
        "success": 100,
        "partial": 50,
        "error": 30,
        "timeout": 30,
    }
    score = float(base_scores.get(terminal_value, 30))

    # Deductions (only from non-terminal events)
    error_deduction = min(30, 5 * error_count)
    timeout_deduction = min(30, 10 * timeout_count)
    partial_deduction = min(15, 3 * partial_count)

    score -= error_deduction
    score -= timeout_deduction
    score -= partial_deduction
    score = max(0.0, score)

    # Friction flags
    flags: list[FrictionFlag] = []
    if terminal_value == "timeout":
        flags.append(
            FrictionFlag(
                id="reliability_terminal_timeout",
                severity="critical",
                dimension="reliability",
                event_index=None,
                suggestion="Investigate timeout root cause in tool or LLM calls",
            )
        )
    elif terminal_value == "partial":
        flags.append(
            FrictionFlag(
                id="reliability_terminal_partial",
                severity="high",
                dimension="reliability",
                event_index=None,
                suggestion="Agent did not produce a complete result",
            )
        )

    if error_count > 0:
        error_indices = [e.event_index for e in non_terminal if e.status and e.status.value == "error"]
        flags.append(
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=error_indices[0],
                suggestion=f"Review {error_count} error(s) at event indices {error_indices}",
            )
        )

    return JudgeResult(
        score=score,
        confidence="high",
        friction_flags=flags,
        explanation=f"Terminal outcome: {terminal_value}. {error_count} non-terminal errors, {timeout_count} timeouts, {partial_count} partials.",
        raw_metrics={
            "terminal_outcome": terminal_value,
            "error_count": error_count,
            "timeout_count": timeout_count,
            "partial_count": partial_count,
        },
        scorable=True,
    )
