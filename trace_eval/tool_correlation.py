"""Tool call/result correlation and attempt pairing.

Transforms a flat event list into paired tool attempts, matching by
tool_call_id first with optional heuristic fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from trace_eval.schema import Event, EventType


@dataclass
class ToolAttempt:
    """A paired tool call and its result (if any)."""

    call: Event
    result: Event | None
    tool_call_id: str | None
    match_kind: str  # "exact", "heuristic", "unmatched_call", "orphan_result"


def pair_tool_attempts(events: list[Event]) -> list[ToolAttempt]:
    """Pair tool_call and tool_result events into ToolAttempt objects.

    Matching priority:
    1. Exact tool_call_id match within the same session.
    2. Heuristic: same tool_name, adjacent in event order, both missing IDs.
       Only used when unambiguous (exactly one unmatched prior call of the
       same tool in the same session).

    Each call and result may participate in at most one pair.
    Duplicate IDs are reported but not silently overwritten.
    """
    # Sort by event_index to ensure deterministic ordering
    sorted_events = sorted(events, key=lambda e: e.event_index or 0)

    calls = [e for e in sorted_events if e.event_type == EventType.tool_call]
    results = [e for e in sorted_events if e.event_type == EventType.tool_result]

    attempts: list[ToolAttempt] = []
    matched_calls: set[int] = set()  # event_index of matched calls
    matched_results: set[int] = set()  # event_index of matched results

    # Phase 1: Exact ID matching
    # Build a map from tool_call_id to results
    results_by_id: dict[str, list[Event]] = {}
    for r in results:
        if r.tool_call_id:
            results_by_id.setdefault(r.tool_call_id, []).append(r)

    for call in calls:
        if call.event_index in matched_calls:
            continue
        cid = call.tool_call_id
        if cid and cid in results_by_id:
            # Find the first unmatched result with this ID
            for r in results_by_id[cid]:
                if r.event_index not in matched_results:
                    attempts.append(
                        ToolAttempt(
                            call=call,
                            result=r,
                            tool_call_id=cid,
                            match_kind="exact",
                        )
                    )
                    matched_calls.add(call.event_index)
                    matched_results.add(r.event_index)
                    break

    # Phase 2: Heuristic matching for calls without IDs
    # Only match if there is exactly one unmatched result with the same
    # tool_name that appears after the call in event order.
    for call in calls:
        if call.event_index in matched_calls:
            continue
        if call.tool_call_id is not None:
            continue  # Has ID but no match — leave unmatched

        # Find unmatched results with the same tool_name
        candidates = [
            r
            for r in results
            if r.event_index not in matched_results
            and r.tool_call_id is None
            and (r.tool_name == call.tool_name or r.tool_name is None)
            and (r.event_index or 0) > (call.event_index or 0)
        ]
        if len(candidates) == 1:
            r = candidates[0]
            attempts.append(
                ToolAttempt(
                    call=call,
                    result=r,
                    tool_call_id=None,
                    match_kind="heuristic",
                )
            )
            matched_calls.add(call.event_index)
            matched_results.add(r.event_index)

    # Phase 3: Record unmatched calls
    for call in calls:
        if call.event_index not in matched_calls:
            attempts.append(
                ToolAttempt(
                    call=call,
                    result=None,
                    tool_call_id=call.tool_call_id,
                    match_kind="unmatched_call",
                )
            )
            matched_calls.add(call.event_index)

    # Phase 4: Record orphan results
    for r in results:
        if r.event_index not in matched_results:
            attempts.append(
                ToolAttempt(
                    call=_dummy_call(),
                    result=r,
                    tool_call_id=r.tool_call_id,
                    match_kind="orphan_result",
                )
            )
            matched_results.add(r.event_index)

    # Sort attempts by call event_index for deterministic output
    attempts.sort(key=lambda a: a.call.event_index or 0)
    return attempts


def _dummy_call() -> Event:
    """Create a placeholder Event for orphan results."""
    return Event(
        event_index=-1,
        actor="",
        event_type=None,
        timestamp="",
        status=None,
    )


def compute_correlation_metrics(attempts: list[ToolAttempt]) -> dict:
    """Compute raw metrics from paired attempts."""
    total = len(attempts)
    exact_pairs = sum(1 for a in attempts if a.match_kind == "exact")
    heuristic_pairs = sum(1 for a in attempts if a.match_kind == "heuristic")
    unmatched_calls = sum(1 for a in attempts if a.match_kind == "unmatched_call")
    orphan_results = sum(1 for a in attempts if a.match_kind == "orphan_result")

    paired = exact_pairs + heuristic_pairs
    # Only count real attempts (not orphan results)
    real_attempts = total - orphan_results

    # Detect duplicate tool_call_ids
    id_counts: dict[str, int] = {}
    for a in attempts:
        if a.tool_call_id:
            id_counts[a.tool_call_id] = id_counts.get(a.tool_call_id, 0) + 1
    duplicate_ids = sum(1 for v in id_counts.values() if v > 1)

    # Count outcomes
    failed_attempts = 0
    successful_attempts = 0
    tool_timeouts = 0
    for a in attempts:
        if a.match_kind in ("unmatched_call", "orphan_result"):
            continue
        if a.result and a.result.status:
            status_val = a.result.status.value
            if status_val == "error":
                failed_attempts += 1
            elif status_val == "timeout":
                tool_timeouts += 1
                failed_attempts += 1
            elif status_val == "success":
                successful_attempts += 1
            elif status_val == "partial":
                failed_attempts += 1
        else:
            # No result or no status — count as unknown
            pass

    # Count retries: a failed attempt followed by a later attempt of the same tool
    tool_retries = 0
    redundant_calls = 0
    # Sort by event_index for ordering
    sorted_attempts = sorted(attempts, key=lambda a: a.call.event_index or 0)
    real = [a for a in sorted_attempts if a.match_kind not in ("orphan_result",)]

    for i in range(1, len(real)):
        prev = real[i - 1]
        curr = real[i]
        if prev.call.tool_name == curr.call.tool_name:
            # Check if previous attempt failed
            prev_failed = (
                prev.result and prev.result.status and prev.result.status.value in ("error", "timeout", "partial")
            )
            if prev_failed:
                tool_retries += 1
            else:
                # Check for redundant call (same tool, same args, previous succeeded)
                if (
                    prev.result
                    and prev.result.status
                    and prev.result.status.value == "success"
                    and prev.call.tool_args is not None
                    and prev.call.tool_args == curr.call.tool_args
                ):
                    redundant_calls += 1

    # Correlation coverage
    if real_attempts > 0:
        coverage_pct = (paired / real_attempts) * 100
    else:
        coverage_pct = 100.0

    return {
        "tool_attempts": real_attempts,
        "paired_attempts": paired,
        "exact_pairs": exact_pairs,
        "heuristic_pairs": heuristic_pairs,
        "unmatched_calls": unmatched_calls,
        "orphan_results": orphan_results,
        "duplicate_tool_call_ids": duplicate_ids,
        "failed_attempts": failed_attempts,
        "successful_attempts": successful_attempts,
        "tool_retries": tool_retries,
        "redundant_calls": redundant_calls,
        "tool_timeouts": tool_timeouts,
        "correlation_coverage_pct": round(coverage_pct, 1),
    }


def correlation_confidence(metrics: dict) -> str:
    """Determine confidence level from correlation metrics."""
    if metrics["tool_attempts"] == 0:
        return "low"
    coverage = metrics["correlation_coverage_pct"]
    has_anomalies = (
        metrics["duplicate_tool_call_ids"] > 0 or metrics["unmatched_calls"] > 0 or metrics["orphan_results"] > 0
    )
    if coverage >= 100 and not has_anomalies:
        return "high"
    if coverage >= 50 or metrics["heuristic_pairs"] > 0:
        return "medium"
    return "low"
