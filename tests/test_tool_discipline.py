"""Tests for the tool discipline judge with correlation-based scoring."""

from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event


def _make_call(index, tool_name="grep", tool_call_id=None, tool_args=None):
    return Event.from_dict(
        {
            "event_index": index,
            "actor": "assistant",
            "event_type": "tool_call",
            "timestamp": "2026-04-15T10:00:00Z",
            "status": None,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "tool_args": tool_args,
        }
    )


def _make_result(index, tool_call_id=None, status="success", tool_name="grep"):
    return Event.from_dict(
        {
            "event_index": index,
            "actor": "tool",
            "event_type": "tool_result",
            "timestamp": "2026-04-15T10:00:01Z",
            "status": status,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
        }
    )


def test_perfect_tool_discipline():
    events = [
        _make_call(0, tool_call_id="tc1"),
        _make_result(1, tool_call_id="tc1", status="success"),
    ]
    result = judge_tool_discipline(events)
    assert result.score == 100.0
    assert result.scorable


def test_no_tool_activity_is_scorable():
    events = [
        Event.from_dict(
            {
                "event_index": 0,
                "actor": "user",
                "event_type": "session_start",
                "timestamp": "2026-01-01T00:00:00Z",
                "status": "success",
            }
        )
    ]
    result = judge_tool_discipline(events)
    assert result.scorable
    assert result.score == 100.0


def test_tool_retry_penalty():
    """Error followed by successful retry of same tool."""
    events = [
        _make_call(0, tool_call_id="tc1"),
        _make_result(1, tool_call_id="tc1", status="error"),
        _make_call(2, tool_call_id="tc2"),
        _make_result(3, tool_call_id="tc2", status="success"),
    ]
    result = judge_tool_discipline(events)
    # 1 retry -> -10
    assert result.score == 90.0
    assert result.raw_metrics["tool_retries"] == 1


def test_redundant_call_penalty():
    """Same tool, same args, after a successful call."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_args={"pattern": "auth"}),
        _make_result(1, tool_call_id="tc1", status="success"),
        _make_call(2, tool_call_id="tc2", tool_args={"pattern": "auth"}),
        _make_result(3, tool_call_id="tc2", status="success"),
    ]
    result = judge_tool_discipline(events)
    # 1 redundant -> -8
    assert result.score == 92.0
    assert result.raw_metrics["redundant_calls"] == 1


def test_tool_timeout_penalty():
    """Timeout in tool_result status."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="slow_tool"),
        _make_result(1, tool_call_id="tc1", status="timeout", tool_name="slow_tool"),
    ]
    result = judge_tool_discipline(events)
    # 1 timeout -> -15
    assert result.score == 85.0
    assert result.raw_metrics["tool_timeouts"] == 1


def test_floor_at_zero():
    """Many retries should floor at 0."""
    events = []
    for i in range(5):
        events.append(_make_call(i * 2, tool_call_id=f"tc{i + 1}"))
        events.append(_make_result(i * 2 + 1, tool_call_id=f"tc{i + 1}", status="error"))
    events.append(_make_call(10, tool_call_id="tc6"))
    events.append(_make_result(11, tool_call_id="tc6", status="success"))
    result = judge_tool_discipline(events)
    assert result.score >= 0.0


def test_exact_id_correlation():
    """Exact tool_call_id matching produces high confidence."""
    events = [
        _make_call(0, tool_call_id="abc-123"),
        _make_result(1, tool_call_id="abc-123", status="success"),
    ]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["exact_pairs"] == 1
    assert result.confidence == "high"


def test_heuristic_matching_when_no_ids():
    """Heuristic matching when both call and result lack IDs."""
    events = [
        _make_call(0, tool_call_id=None, tool_name="grep"),
        _make_result(1, tool_call_id=None, status="success", tool_name="grep"),
    ]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["heuristic_pairs"] == 1
    assert result.raw_metrics["exact_pairs"] == 0


def test_unmatched_call():
    """Call with no result is reported as unmatched."""
    events = [_make_call(0, tool_call_id="tc1")]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["unmatched_calls"] == 1


def test_orphan_result():
    """Result with no call is reported as orphan."""
    events = [_make_result(0, tool_call_id="orphan", status="success")]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["orphan_results"] == 1


def test_interleaved_same_tool_different_ids():
    """Two interleaved calls with same tool but different IDs should not create false retries."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="grep"),
        _make_call(1, tool_call_id="tc2", tool_name="grep"),
        _make_result(2, tool_call_id="tc1", status="success", tool_name="grep"),
        _make_result(3, tool_call_id="tc2", status="success", tool_name="grep"),
    ]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["tool_retries"] == 0
    assert result.raw_metrics["exact_pairs"] == 2


# --- Friction flag event_index attribution tests ---


def test_retry_flag_points_to_retry_call_event_index():
    """Retry friction flag should point to the retry call's event_index."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="grep"),
        _make_result(1, tool_call_id="tc1", status="error"),
        _make_call(2, tool_call_id="tc2", tool_name="grep"),
        _make_result(3, tool_call_id="tc2", status="success"),
    ]
    result = judge_tool_discipline(events)
    retry_flags = [f for f in result.friction_flags if f.id == "tool_retries"]
    assert len(retry_flags) == 1
    # The retry flag should point to event_index 2 (the retry call)
    assert retry_flags[0].event_index == 2


def test_timeout_flag_points_to_timed_out_result_event_index():
    """Timeout friction flag should point to the timed-out result's event_index."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="bash"),
        _make_result(1, tool_call_id="tc1", status="timeout", tool_name="bash"),
    ]
    result = judge_tool_discipline(events)
    timeout_flags = [f for f in result.friction_flags if f.id == "tool_timeout"]
    assert len(timeout_flags) == 1
    # The timeout flag should point to event_index 1 (the timed-out result)
    assert timeout_flags[0].event_index == 1


def test_redundant_flag_points_to_redundant_call_event_index():
    """Redundant call friction flag should point to the redundant call's event_index."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="grep", tool_args={"pattern": "auth"}),
        _make_result(1, tool_call_id="tc1", status="success"),
        _make_call(2, tool_call_id="tc2", tool_name="grep", tool_args={"pattern": "auth"}),
        _make_result(3, tool_call_id="tc2", status="success"),
    ]
    result = judge_tool_discipline(events)
    redundant_flags = [f for f in result.friction_flags if f.id == "tool_redundant"]
    assert len(redundant_flags) == 1
    # The redundant flag should point to event_index 2 (the redundant call)
    assert redundant_flags[0].event_index == 2


def test_unmatched_call_flag_points_to_unmatched_call_event_index():
    """Unmatched call friction flag should point to the unmatched call's event_index."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="grep"),
        # No result for tc1
    ]
    result = judge_tool_discipline(events)
    unmatched_flags = [f for f in result.friction_flags if f.id == "tool_unmatched_calls"]
    assert len(unmatched_flags) == 1
    # The unmatched flag should point to event_index 0 (the unmatched call)
    assert unmatched_flags[0].event_index == 0


def test_multiple_retries_point_to_first_retry():
    """With multiple retries, the flag points to the first retry call."""
    events = [
        _make_call(0, tool_call_id="tc1", tool_name="grep"),
        _make_result(1, tool_call_id="tc1", status="error"),
        _make_call(2, tool_call_id="tc2", tool_name="grep"),
        _make_result(3, tool_call_id="tc2", status="error"),
        _make_call(4, tool_call_id="tc3", tool_name="grep"),
        _make_result(5, tool_call_id="tc3", status="success"),
    ]
    result = judge_tool_discipline(events)
    assert result.raw_metrics["tool_retries"] == 2
    retry_flags = [f for f in result.friction_flags if f.id == "tool_retries"]
    assert len(retry_flags) == 1
    # Points to the first retry (event_index 2)
    assert retry_flags[0].event_index == 2


def test_no_flags_when_perfect_discipline():
    """No friction flags when tool discipline is perfect."""
    events = [
        _make_call(0, tool_call_id="tc1"),
        _make_result(1, tool_call_id="tc1", status="success"),
    ]
    result = judge_tool_discipline(events)
    assert len(result.friction_flags) == 0
