"""Context hygiene judge: Context pressure, warnings, compression."""

from __future__ import annotations

from trace_eval.schema import Event, EventType, FrictionFlag, JudgeResult


def judge_context(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="No events to evaluate", raw_metrics={}, scorable=False,
        )

    pressure_values = [e.context_pressure_pct for e in events if e.context_pressure_pct is not None]
    if not pressure_values:
        return JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="No context_pressure_pct data available",
            raw_metrics={}, scorable=False,
        )

    max_pressure = max(pressure_values)
    warning_count = sum(
        1 for e in events
        if e.event_type is not None and e.event_type.value == "context_warning"
    )
    compression_count = sum(
        1 for e in events
        if e.event_type is not None and e.event_type.value == "context_compress"
    )

    score = 100.0
    if max_pressure > 90:
        score -= 50
    elif max_pressure > 70:
        score -= 20
    elif max_pressure > 50:
        score -= 5

    score -= min(20, 10 * warning_count)
    score -= min(20, 8 * compression_count)
    score = max(0.0, score)

    # Friction flags
    flags: list[FrictionFlag] = []
    if max_pressure > 90:
        flags.append(FrictionFlag(
            id="context_pressure_critical", severity="critical",
            dimension="context", event_index=None,
            suggestion="Context pressure exceeded 90% — reduce prompt size",
        ))
    elif max_pressure > 70:
        flags.append(FrictionFlag(
            id="context_pressure_high", severity="high",
            dimension="context", event_index=None,
            suggestion="Context pressure exceeded 70%",
        ))

    if compression_count > 0:
        flags.append(FrictionFlag(
            id="context_compression", severity="medium",
            dimension="context", event_index=None,
            suggestion=f"Context compression triggered {compression_count} time(s)",
        ))

    return JudgeResult(
        score=score,
        confidence="high",
        friction_flags=flags,
        explanation=(
            f"Max context pressure: {max_pressure:.1f}%. "
            f"Warnings: {warning_count}. Compressions: {compression_count}."
        ),
        raw_metrics={
            "max_context_pressure_pct": max_pressure,
            "context_warning_count": warning_count,
            "compression_event_count": compression_count,
        },
        scorable=True,
    )
