import pytest
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event


def _make_event(index, **extra):
    data = {
        "event_index": index,
        "actor": "tool",
        "event_type": "tool_call",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    }
    data.update(extra)
    return Event.from_dict(data)


def test_perfect_tool_discipline():
    events = [_make_event(0, tool_name="grep")]
    result = judge_tool_discipline(events)
    assert result.score == 100.0


def test_tool_retry_penalty():
    # error then success with same tool = retry
    events = [
        _make_event(0, tool_name="grep", status="error"),
        _make_event(1, tool_name="grep", status="success"),
    ]
    result = judge_tool_discipline(events)
    # 1 retry → -10
    assert result.score == 90.0


def test_redundant_call_penalty():
    # adjacent same tool with same args
    events = [
        _make_event(0, tool_name="grep", tool_args={"pattern": "auth"}),
        _make_event(1, tool_name="grep", tool_args={"pattern": "auth"}),
    ]
    result = judge_tool_discipline(events)
    # 1 redundant → -8
    assert result.score == 92.0


def test_tool_timeout_penalty():
    events = [
        _make_event(0, tool_name="slow_tool", status="timeout"),
    ]
    result = judge_tool_discipline(events)
    # 1 timeout → -15
    assert result.score == 85.0


def test_floor_at_zero():
    events = [
        _make_event(i, tool_name="grep", status="error") for i in range(5)
    ] + [
        _make_event(5, tool_name="grep", status="success"),
    ]
    result = judge_tool_discipline(events)
    assert result.score >= 0.0
