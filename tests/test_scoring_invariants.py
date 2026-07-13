"""Scoring invariant tests for tool correlation and reliability."""

from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event, EventType, Status
from trace_eval.tool_correlation import compute_correlation_metrics, pair_tool_attempts


def _ev(idx, etype, status=None, tool_name=None, tool_call_id=None, tool_args=None):
    return Event(
        event_index=idx,
        actor="assistant",
        event_type=etype,
        timestamp="2026-01-01T00:00:00Z",
        status=status,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_args=tool_args,
    )


class TestReliabilityInvariants:
    """Reliability score must not improve when errors are added."""

    def test_adding_error_cannot_improve_reliability(self):
        base = [_ev(0, EventType.session_start, Status.success), _ev(1, EventType.session_end, Status.success)]
        base_score = judge_reliability(base).score
        with_error = [
            _ev(0, EventType.session_start, Status.success),
            _ev(1, EventType.tool_result, Status.error),
            _ev(2, EventType.session_end, Status.success),
        ]
        error_score = judge_reliability(with_error).score
        assert error_score <= base_score

    def test_adding_timeout_cannot_improve_reliability(self):
        base = [_ev(0, EventType.session_start, Status.success), _ev(1, EventType.session_end, Status.success)]
        base_score = judge_reliability(base).score
        with_timeout = [
            _ev(0, EventType.session_start, Status.success),
            _ev(1, EventType.tool_result, Status.timeout),
            _ev(2, EventType.session_end, Status.success),
        ]
        timeout_score = judge_reliability(with_timeout).score
        assert timeout_score <= base_score


class TestToolDisciplineInvariants:
    """Tool discipline invariants for correlation-based scoring."""

    def test_adding_timeout_cannot_improve_tool_discipline(self):
        base = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
        ]
        base_score = judge_tool_discipline(base).score
        with_timeout = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.timeout, tool_name="grep", tool_call_id="tc1"),
        ]
        timeout_score = judge_tool_discipline(with_timeout).score
        assert timeout_score <= base_score

    def test_interleaving_does_not_create_false_retries(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tcA"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id="tcB"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tcA"),
            _ev(3, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tcB"),
        ]
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 0

    def test_adding_success_to_unmatched_does_not_worsen(self):
        unmatched = [_ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1")]
        unmatched_score = judge_tool_discipline(unmatched).score
        matched = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
        ]
        matched_score = judge_tool_discipline(matched).score
        assert matched_score >= unmatched_score

    def test_removing_ids_cannot_increase_confidence(self):
        with_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
        ]
        without_ids = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id=None),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id=None),
        ]
        with_result = judge_tool_discipline(with_ids)
        without_result = judge_tool_discipline(without_ids)
        # With IDs should have >= confidence than without
        conf_order = {"high": 3, "medium": 2, "low": 1}
        assert conf_order[with_result.confidence] >= conf_order[without_result.confidence]

    def test_duplicate_ids_cannot_produce_high_confidence(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="dup"),
            _ev(1, EventType.tool_call, tool_name="grep", tool_call_id="dup"),
            _ev(2, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="dup"),
        ]
        result = judge_tool_discipline(events)
        assert result.confidence != "high"

    def test_reordering_does_not_change_score(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
            _ev(2, EventType.tool_call, tool_name="write", tool_call_id="tc2"),
            _ev(3, EventType.tool_result, Status.success, tool_name="write", tool_call_id="tc2"),
        ]
        score1 = judge_tool_discipline(events).score
        # Reorder (keeping event_index values)
        reordered = [events[2], events[0], events[3], events[1]]
        score2 = judge_tool_discipline(reordered).score
        assert score1 == score2


class TestCorrelationMetrics:
    """Direct tests for the pairing logic."""

    def test_exact_pairing(self):
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["exact_pairs"] == 1
        assert metrics["paired_attempts"] == 1

    def test_out_of_order_input(self):
        events = [
            _ev(1, EventType.tool_result, Status.success, tool_name="grep", tool_call_id="tc1"),
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
        ]
        attempts = pair_tool_attempts(events)
        metrics = compute_correlation_metrics(attempts)
        assert metrics["exact_pairs"] == 1

    def test_no_double_counting_failures(self):
        """One failed tool operation should contribute one failure."""
        events = [
            _ev(0, EventType.tool_call, tool_name="grep", tool_call_id="tc1"),
            _ev(1, EventType.tool_result, Status.error, tool_name="grep", tool_call_id="tc1"),
            _ev(2, EventType.session_end, Status.success),
        ]
        rel = judge_reliability(events)
        # Only the tool_result has error status, not the tool_call
        assert rel.raw_metrics["error_count"] == 1
