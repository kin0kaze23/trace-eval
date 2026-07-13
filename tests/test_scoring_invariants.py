"""Strengthened scoring invariant tests.

Tests for:
- Cross-session ID reuse cannot pair
- Ambiguous heuristic data remains unmatched
- Non-adjacent retry is detected
- Real converted successful results contribute to successful_attempts
- Real converted redundant calls are penalized
- Provider-supported timeouts reach the tool-discipline timeout metric
- Removing valid IDs cannot increase confidence or exact-pair count
- Duplicate IDs cannot silently pair with high confidence
"""

from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event, EventType, Status
from trace_eval.tool_correlation import compute_correlation_metrics, pair_tool_attempts


def _ev(idx, etype, status=None, tool_name=None, tool_call_id=None, tool_args=None, session_id=None):
    return Event(
        event_index=idx,
        actor="assistant",
        event_type=etype,
        timestamp="2026-01-01T00:00:00Z",
        status=status,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_args=tool_args,
        session_id=session_id,
    )


class TestCrossSessionSafety:
    """Cross-session ID reuse cannot pair."""

    def test_same_tool_call_id_different_sessions_no_pairing(self):
        """Same tool_call_id in two sessions must not cross-pair."""
        events = [
            # Session A
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc-001", session_id="sess-A"),
            # Session B (same ID, different session)
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id="tc-001", session_id="sess-B"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc-001", session_id="sess-B"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        # Session A's call should be unmatched (no result in session A)
        assert metrics["unmatched_calls"] == 1
        # Session B's call should be exact-paired with session B's result
        assert metrics["exact_pairs"] == 1
        # No cross-session pairing
        assert metrics["paired_attempts"] == 1

    def test_duplicate_event_indices_across_sessions(self):
        """Duplicate event_index values across sessions must not collide."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc-A", session_id="sess-A"),
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc-B", session_id="sess-B"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc-A", session_id="sess-A"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc-B", session_id="sess-B"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        assert metrics["exact_pairs"] == 2
        assert metrics["unmatched_calls"] == 0
        assert metrics["orphan_results"] == 0

    def test_result_from_one_session_never_pairs_with_call_from_another(self):
        """A result in session A must never pair with a call in session B."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc-X", session_id="sess-A"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc-X", session_id="sess-B"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        # The call in sess-A has no matching result in sess-A
        assert metrics["unmatched_calls"] == 1
        # The result in sess-B has no matching call in sess-B
        assert metrics["orphan_results"] == 1
        assert metrics["exact_pairs"] == 0


class TestAmbiguousHeuristic:
    """Ambiguous heuristic data remains unmatched."""

    def test_two_calls_one_result_ambiguous(self):
        """Two calls without IDs followed by one result — ambiguous."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        # Should NOT pair — ambiguous which call the result belongs to
        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 2
        assert metrics["orphan_results"] == 1

    def test_one_call_two_results_ambiguous(self):
        """One call without ID followed by two results — ambiguous."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        # Should NOT pair — ambiguous which result the call belongs to
        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 1
        assert metrics["orphan_results"] == 2

    def test_interleaved_no_id_calls_ambiguous(self):
        """Interleaved no-ID calls of the same tool — ambiguous."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        # Ambiguous — no heuristic pairing
        assert metrics["heuristic_pairs"] == 0

    def test_cross_session_no_id_events_no_heuristic(self):
        """No-ID events in different sessions must not heuristically pair."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s2"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)

        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 1
        assert metrics["orphan_results"] == 1


class TestNonAdjacentRetry:
    """Non-adjacent retry is detected (per-tool tracking)."""

    def test_error_then_other_tool_then_retry(self):
        """A error -> B success -> A retry: A retry must be detected."""
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.error, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(2, EventType.tool_call, tool_name="grep", tool_call_id="tc2", session_id="s1"),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
            _ev(4, EventType.tool_call, tool_name="bash", tool_call_id="tc3", session_id="s1"),
            _ev(5, EventType.tool_result, Status.success, tool_name="bash", tool_call_id="tc3", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1, (
            f"Expected 1 retry (bash after bash error), got {result.raw_metrics['tool_retries']}"
        )

    def test_error_then_error_then_retry(self):
        """A error -> B error -> A retry: A retry must be detected."""
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.error, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(2, EventType.tool_call, tool_name="grep", tool_call_id="tc2", session_id="s1"),
            _ev(3, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc2", session_id="s1"),
            _ev(4, EventType.tool_call, tool_name="bash", tool_call_id="tc3", session_id="s1"),
            _ev(5, EventType.tool_result, Status.success, tool_name="bash", tool_call_id="tc3", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1, (
            f"Expected 1 retry (bash after bash error), got {result.raw_metrics['tool_retries']}"
        )

    def test_successful_then_same_args_is_redundant_not_retry(self):
        """Successful A followed by A with identical args is redundant, not retry."""
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 0
        assert result.raw_metrics["redundant_calls"] == 1

    def test_failed_then_changed_args_is_new_operation_not_retry(self):
        """Failed A followed by A with changed args is a new operation, not a retry.

        Retry detection requires compatible arguments. Different arguments
        indicate the user moved on to a different search/operation.
        """
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args={"pattern": "login"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        # Different args = new operation, not a retry
        assert result.raw_metrics["tool_retries"] == 0
        assert result.raw_metrics["redundant_calls"] == 0

    def test_failed_then_same_args_is_retry(self):
        """Failed A followed by A with same args is a retry."""
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1
        assert result.raw_metrics["redundant_calls"] == 0

    def test_failed_then_no_args_not_retry(self):
        """Failed A (with args) followed by A (no args) is NOT a retry.

        When one side has args and the other doesn't, there is insufficient
        evidence to classify as retry. The next call may be a different
        operation entirely.
        """
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args=None,
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        # One side missing args = insufficient evidence = NOT retry
        assert result.raw_metrics["tool_retries"] == 0

    def test_no_args_then_failed_with_args_not_retry(self):
        """A (no args) fails, then A (with args) — NOT a retry.

        One side missing args = insufficient evidence.
        """
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args=None,
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 0

    def test_both_no_args_is_retry(self):
        """Both calls have no args — compatible (weak evidence)."""
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args=None,
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args=None,
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1

    def test_timeout_then_same_args_is_retry(self):
        """Timeout followed by same args is a retry."""
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="bash",
                tool_call_id="tc1",
                tool_args={"command": "build"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.timeout, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="bash",
                tool_call_id="tc2",
                tool_args={"command": "build"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="bash", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1


class TestConvertedSuccessStatus:
    """Real converted successful results contribute to successful_attempts."""

    def test_converted_success_contributes_to_successful_attempts(self):
        """A tool result with status='success' must count as successful_attempts."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["successful_attempts"] == 1

    def test_none_status_does_not_count_as_success(self):
        """A tool result with status=None must NOT count as successful_attempts.

        Status=None means unknown — the provider did not explicitly indicate
        the outcome. This is NOT the same as success.
        """
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, status=None, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["successful_attempts"] == 0
        # Also verify it doesn't count as failure
        assert metrics["failed_attempts"] == 0

    def test_explicit_error_counts_as_failure(self):
        """A tool result with status='error' must count as failed_attempts."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["failed_attempts"] == 1
        assert metrics["successful_attempts"] == 0

    def test_explicit_timeout_counts_as_failure(self):
        """A tool result with status='timeout' must count as failed_attempts."""
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.timeout, tool_name="bash", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["failed_attempts"] == 1
        assert metrics["tool_timeouts"] == 1

    def test_explicit_partial_counts_as_failure(self):
        """A tool result with status='partial' must count as failed_attempts."""
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.partial, tool_name="bash", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["failed_attempts"] == 1

    def test_redundant_call_after_success_is_penalized(self):
        """Redundant call after a successful call with same args is penalized."""
        events = [
            _ev(
                0,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc1",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(
                2,
                EventType.tool_call,
                tool_name="grep",
                tool_call_id="tc2",
                tool_args={"pattern": "auth"},
                session_id="s1",
            ),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["redundant_calls"] == 1
        assert result.score < 100.0


class TestTimeoutCorrelation:
    """Provider-supported timeouts reach the tool-discipline timeout metric."""

    def test_timeout_in_tool_result_reaches_timeout_metric(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.timeout, tool_name="bash", tool_call_id="tc1", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_timeouts"] == 1
        assert result.score < 100.0

    def test_timeout_then_retry_detected(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.timeout, tool_name="bash", tool_call_id="tc1", session_id="s1"),
            _ev(2, EventType.tool_call, tool_name="bash", tool_call_id="tc2", session_id="s1"),
            _ev(3, EventType.tool_result, Status.success, tool_name="bash", tool_call_id="tc2", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_timeouts"] == 1
        assert result.raw_metrics["tool_retries"] == 1


class TestIdRemovalAndDuplicate:
    """Removing valid IDs cannot increase confidence or exact-pair count.
    Duplicate IDs cannot silently pair with high confidence."""

    def test_removing_ids_cannot_increase_confidence(self):
        with_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        without_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        with_result = judge_tool_discipline(with_ids)
        without_result = judge_tool_discipline(without_ids)
        conf_order = {"high": 3, "medium": 2, "low": 1}
        assert conf_order[with_result.confidence] >= conf_order[without_result.confidence]

    def test_removing_ids_cannot_increase_exact_pairs(self):
        with_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        without_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        with_metrics = compute_correlation_metrics(pair_tool_attempts(with_ids))
        without_metrics = compute_correlation_metrics(pair_tool_attempts(without_ids))
        assert with_metrics["exact_pairs"] >= without_metrics["exact_pairs"]

    def test_duplicate_ids_cannot_produce_high_confidence(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="dup", session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id="dup", session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="dup", session_id="s1"),
        ]
        result = judge_tool_discipline(events)
        assert result.confidence != "high"
        assert result.raw_metrics["duplicate_tool_call_ids"] >= 1

    def test_no_double_counting_failures(self):
        """One failed tool operation contributes one failure."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["failed_attempts"] == 1


class TestPairingInvariants:
    """Additional pairing invariant tests for edge cases."""

    def test_result_before_call_not_paired(self):
        """A result appearing before its call should not be paired via heuristic."""
        events = [
            _ev(0, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        # Result is before call — cannot be paired
        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 1
        assert metrics["orphan_results"] == 1

    def test_duplicate_result_ids_not_paired(self):
        """Duplicate result IDs should not silently pair with wrong calls."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id="tc2", session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        # tc1 result duplicated — first one pairs with tc1 call, second is orphan
        # tc2 call has no matching result
        assert metrics["exact_pairs"] == 1
        assert metrics["unmatched_calls"] == 1
        assert metrics["orphan_results"] == 1

    def test_interleaved_no_id_same_tool_ambiguous(self):
        """Interleaved no-ID calls of same tool with results — ambiguous."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        # Ambiguous — no heuristic pairing
        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 2
        assert metrics["orphan_results"] == 2

    def test_one_call_one_result_unambiguous(self):
        """One call and one result without IDs — unambiguous pairing."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["heuristic_pairs"] == 1
        assert metrics["unmatched_calls"] == 0
        assert metrics["orphan_results"] == 0

    def test_cross_session_no_id_not_paired(self):
        """No-ID events in different sessions must not pair."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None, session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None, session_id="s2"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["heuristic_pairs"] == 0
        assert metrics["unmatched_calls"] == 1
        assert metrics["orphan_results"] == 1

    def test_exact_id_takes_priority_over_heuristic(self):
        """Exact ID matching takes priority over heuristic matching."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["exact_pairs"] == 1
        assert metrics["heuristic_pairs"] == 0

    def test_each_event_pairs_at_most_once(self):
        """Each call and result can participate in at most one pair."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1", session_id="s1"),
        ]
        attempts = pair_tool_attempts(events)
        # tc1 call pairs with first tc1 result
        # Second tc1 result is orphan
        paired_attempts = [a for a in attempts if a.match_kind in ("exact", "heuristic")]
        orphan_attempts = [a for a in attempts if a.match_kind == "orphan_result"]
        assert len(paired_attempts) == 1
        assert len(orphan_attempts) == 1
        assert paired_attempts[0].match_kind == "exact"
        assert orphan_attempts[0].match_kind == "orphan_result"
