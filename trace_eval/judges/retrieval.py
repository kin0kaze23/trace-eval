"""Retrieval discipline judge: Did it search before writing?"""

from __future__ import annotations

from trace_eval.schema import Event, FrictionFlag, JudgeResult


def judge_retrieval(events: list[Event]) -> JudgeResult:
    if not events:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation="No events to evaluate",
            raw_metrics={},
            scorable=False,
        )

    canonical_entrypoint_used = any(e.retrieval_entrypoint for e in events)
    deprecated_file_touched = any(e.deprecated_file_touched for e in events)
    fallback_search_used = any(
        e.fallback_search_used or (e.event_type is not None and e.event_type.value == "search_fallback") for e in events
    )
    retrieval_steps_count = sum(1 for e in events if e.retrieval_steps and len(e.retrieval_steps) > 0)

    # If no retrieval behavior is present at all (no entrypoint, no steps, no
    # deprecated file, no fallback search, and no retrieval-relevant event types),
    # the judge is not scorable for this trace. This is common for coding agents
    # that don't use retrieval workflows.
    has_any_retrieval_signal = (
        canonical_entrypoint_used
        or deprecated_file_touched
        or fallback_search_used
        or retrieval_steps_count > 0
        or any(
            e.event_type is not None
            and e.event_type.value in ("search_fallback", "vault_read", "memory_read", "memory_write")
            for e in events
        )
    )

    if not has_any_retrieval_signal:
        return JudgeResult(
            score=None,
            confidence="low",
            friction_flags=[],
            explanation=(
                "No retrieval behavior detected in trace. "
                "Retrieval fields (entrypoint, steps, deprecated file, fallback) are all absent. "
                "This dimension is not applicable to this agent workflow."
            ),
            raw_metrics={
                "canonical_entrypoint_used": False,
                "deprecated_file_touched": False,
                "fallback_search_used": False,
                "retrieval_steps_count": 0,
                "not_applicable": True,
            },
            scorable=False,
        )

    score = 100.0

    if not canonical_entrypoint_used:
        score -= 40
    if deprecated_file_touched:
        score -= 30
    if fallback_search_used:
        score -= 20
    if retrieval_steps_count == 0:
        score -= 10
    if retrieval_steps_count >= 2:
        score += 5

    score = max(0.0, min(100.0, score))

    # Friction flags
    flags: list[FrictionFlag] = []
    if not canonical_entrypoint_used:
        flags.append(
            FrictionFlag(
                id="retrieval_no_entrypoint",
                severity="critical",
                dimension="retrieval",
                event_index=None,
                suggestion="Use canonical retrieval entrypoint",
            )
        )

    if deprecated_file_touched:
        dep_idx = next((e.event_index for e in events if e.deprecated_file_touched), None)
        flags.append(
            FrictionFlag(
                id="retrieval_deprecated_file",
                severity="critical",
                dimension="retrieval",
                event_index=dep_idx,
                suggestion="Stop accessing deprecated files",
            )
        )

    if fallback_search_used:
        flags.append(
            FrictionFlag(
                id="retrieval_fallback_search",
                severity="high",
                dimension="retrieval",
                event_index=None,
                suggestion="Avoid fallback search -- use primary retrieval",
            )
        )

    return JudgeResult(
        score=score,
        confidence="high",
        friction_flags=flags,
        explanation=(
            f"Entrypoint used: {canonical_entrypoint_used}. "
            f"Deprecated files: {deprecated_file_touched}. "
            f"Fallback search: {fallback_search_used}. "
            f"Retrieval steps: {retrieval_steps_count}."
        ),
        raw_metrics={
            "canonical_entrypoint_used": canonical_entrypoint_used,
            "deprecated_file_touched": deprecated_file_touched,
            "fallback_search_used": fallback_search_used,
            "retrieval_steps_count": retrieval_steps_count,
        },
        scorable=True,
    )
