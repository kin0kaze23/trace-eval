"""Tool call/result correlation and attempt pairing.

Transforms a flat event list into paired tool attempts, matching by
tool_call_id first with optional heuristic fallback.

Session safety:
  - Exact ID matching uses (session_id, tool_call_id) composite keys.
  - Heuristic matching requires same session_id.
  - Matched events are tracked by (session_id, event_index) composite keys.
  - No correlation crosses session boundaries.
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


def _event_key(e: Event) -> tuple[str | None, int]:
    """Composite identity for an event: (session_id, event_index).

    This prevents collisions when events from different sessions
    share the same event_index.
    """
    return (e.session_id, e.event_index or 0)


def _normalize_tool_name(name: str | None) -> str:
    """Normalize tool name for comparison (lowercase, strip)."""
    if name is None:
        return ""
    return name.strip().lower()


def pair_tool_attempts(events: list[Event]) -> list[ToolAttempt]:
    """Pair tool_call and tool_result events into ToolAttempt objects.

    Matching priority:
    1. Exact (session_id, tool_call_id) match.
       Never correlates across sessions.
    2. Heuristic: same session, same tool_name, both missing IDs,
       call precedes result, and the pairing is unambiguous
       (exactly one candidate call for the result AND exactly one
       candidate result for the call).

    Each call and result may participate in at most one pair.
    Duplicate IDs are reported but not silently overwritten.
    """
    # Sort by event_index to ensure deterministic ordering
    sorted_events = sorted(events, key=lambda e: e.event_index or 0)

    calls = [e for e in sorted_events if e.event_type == EventType.tool_call]
    results = [e for e in sorted_events if e.event_type == EventType.tool_result]

    attempts: list[ToolAttempt] = []
    matched_calls: set[tuple[str | None, int]] = set()
    matched_results: set[tuple[str | None, int]] = set()

    # Phase 1: Exact ID matching using (session_id, tool_call_id) composite key
    # Build a map from (session_id, tool_call_id) to results
    results_by_composite: dict[tuple[str | None, str], list[Event]] = {}
    for r in results:
        if r.tool_call_id:
            key = (r.session_id, r.tool_call_id)
            results_by_composite.setdefault(key, []).append(r)

    for call in calls:
        if _event_key(call) in matched_calls:
            continue
        cid = call.tool_call_id
        if cid:
            composite_key = (call.session_id, cid)
            if composite_key in results_by_composite:
                # Find the first unmatched result with this composite key
                for r in results_by_composite[composite_key]:
                    if _event_key(r) not in matched_results:
                        attempts.append(
                            ToolAttempt(
                                call=call,
                                result=r,
                                tool_call_id=cid,
                                match_kind="exact",
                            )
                        )
                        matched_calls.add(_event_key(call))
                        matched_results.add(_event_key(r))
                        break

    # Phase 2: Heuristic matching for calls without IDs
    # A result without an ID may be heuristically paired only when:
    # - Call and result are in the same session
    # - Both lack IDs
    # - Tool names are compatible
    # - The call precedes the result
    # - Exactly one unmatched prior call can correspond to that result
    # - Exactly one unmatched result can correspond to that call
    for call in calls:
        if _event_key(call) in matched_calls:
            continue
        if call.tool_call_id is not None:
            continue  # Has ID but no match — leave unmatched

        # Find unmatched results with the same tool_name in the same session
        candidate_results = [
            r
            for r in results
            if _event_key(r) not in matched_results
            and r.tool_call_id is None
            and r.session_id == call.session_id
            and (_normalize_tool_name(r.tool_name) == _normalize_tool_name(call.tool_name) or r.tool_name is None)
            and (r.event_index or 0) > (call.event_index or 0)
        ]

        if len(candidate_results) != 1:
            continue  # Ambiguous or no candidates — leave unmatched

        candidate = candidate_results[0]

        # Bidirectional uniqueness: verify this result has exactly one
        # candidate call (which must be our call)
        candidate_calls_for_result = [
            c
            for c in calls
            if _event_key(c) not in matched_calls
            and c.tool_call_id is None
            and c.session_id == candidate.session_id
            and (
                _normalize_tool_name(c.tool_name) == _normalize_tool_name(candidate.tool_name)
                or candidate.tool_name is None
            )
            and (c.event_index or 0) < (candidate.event_index or 0)
        ]

        if len(candidate_calls_for_result) != 1:
            continue  # Ambiguous — leave unmatched

        # Unambiguous pairing
        attempts.append(
            ToolAttempt(
                call=call,
                result=candidate,
                tool_call_id=None,
                match_kind="heuristic",
            )
        )
        matched_calls.add(_event_key(call))
        matched_results.add(_event_key(candidate))

    # Phase 3: Record unmatched calls
    for call in calls:
        if _event_key(call) not in matched_calls:
            attempts.append(
                ToolAttempt(
                    call=call,
                    result=None,
                    tool_call_id=call.tool_call_id,
                    match_kind="unmatched_call",
                )
            )
            matched_calls.add(_event_key(call))

    # Phase 4: Record orphan results
    for r in results:
        if _event_key(r) not in matched_results:
            attempts.append(
                ToolAttempt(
                    call=_dummy_call(),
                    result=r,
                    tool_call_id=r.tool_call_id,
                    match_kind="orphan_result",
                )
            )
            matched_results.add(_event_key(r))

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
    """Compute raw metrics from paired attempts.

    Retry detection is per (session_id, normalized tool_name), not by
    global adjacency. A retry is detected when a call to a tool occurs
    after a failed attempt to the same tool in the same session, even
    when unrelated tools were called in between.
    """
    total = len(attempts)
    exact_pairs = sum(1 for a in attempts if a.match_kind == "exact")
    heuristic_pairs = sum(1 for a in attempts if a.match_kind == "heuristic")
    unmatched_calls = sum(1 for a in attempts if a.match_kind == "unmatched_call")
    orphan_results = sum(1 for a in attempts if a.match_kind == "orphan_result")

    paired = exact_pairs + heuristic_pairs
    # Only count real attempts (not orphan results)
    real_attempts = total - orphan_results

    # Detect duplicate tool_call_ids (within the same session)
    id_counts: dict[tuple[str | None, str], int] = {}
    for a in attempts:
        if a.tool_call_id:
            key = (a.call.session_id, a.tool_call_id)
            id_counts[key] = id_counts.get(key, 0) + 1
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
        # else: no result or no status — count as unknown (not success)

    # Retry detection: per (session_id, normalized tool_name)
    # Track the most recent outcome for each tool in each session
    tool_retries = 0
    redundant_calls = 0

    # Sort by event_index for ordering
    sorted_attempts = sorted(attempts, key=lambda a: a.call.event_index or 0)
    real = [a for a in sorted_attempts if a.match_kind not in ("orphan_result",)]

    # Track last outcome per (session_id, normalized_tool_name)
    last_outcome: dict[tuple[str | None, str], dict] = {}

    for a in real:
        session = a.call.session_id
        tool = _normalize_tool_name(a.call.tool_name)
        key = (session, tool)

        # Determine current attempt outcome
        curr_failed = False
        curr_succeeded = False
        if a.result and a.result.status:
            sv = a.result.status.value
            if sv in ("error", "timeout", "partial"):
                curr_failed = True
            elif sv == "success":
                curr_succeeded = True

        # Check against last outcome for this tool in this session
        if key in last_outcome:
            prev = last_outcome[key]
            if prev.get("failed"):
                # Previous attempt to this tool failed — this is a retry
                tool_retries += 1
            elif prev.get("succeeded"):
                # Previous attempt succeeded — check for redundant call
                if a.call.tool_args is not None and prev.get("args") is not None and a.call.tool_args == prev["args"]:
                    redundant_calls += 1

        # Update last outcome for this tool
        last_outcome[key] = {
            "failed": curr_failed,
            "succeeded": curr_succeeded,
            "args": a.call.tool_args,
        }

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
    if coverage >= 100 and not has_anomalies and metrics["heuristic_pairs"] == 0:
        return "high"
    if coverage >= 50 or metrics["heuristic_pairs"] > 0:
        return "medium"
    return "low"
