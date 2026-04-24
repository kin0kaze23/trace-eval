from trace_eval.judges.reliability import judge_reliability
from trace_eval.schema import Event


def _make_event(index, status="success", event_type="message"):
    return Event.from_dict(
        {
            "event_index": index,
            "actor": "assistant",
            "event_type": event_type,
            "timestamp": "2026-04-15T10:00:00Z",
            "status": status,
        }
    )


def test_perfect_reliability():
    events = [_make_event(0), _make_event(1), _make_event(2, event_type="session_end")]
    result = judge_reliability(events)
    assert result.score == 100.0
    assert result.scorable is True
    assert result.confidence == "high"


def test_terminal_error():
    events = [
        _make_event(0),
        _make_event(1, event_type="session_end", status="error"),
    ]
    result = judge_reliability(events)
    assert result.score == 30.0  # base for error, no double-penalty


def test_errors_deduct():
    events = [
        _make_event(0),
        _make_event(1, status="error"),
        _make_event(2, status="error"),
        _make_event(3, event_type="session_end", status="success"),
    ]
    result = judge_reliability(events)
    # base 100 - 5*2 = 90 (2 non-terminal errors)
    assert result.score == 90.0


def test_timeouts_deduct():
    events = [
        _make_event(0),
        _make_event(1, status="timeout"),
        _make_event(2, event_type="session_end", status="success"),
    ]
    result = judge_reliability(events)
    # base 100 - 10*1 = 90
    assert result.score == 90.0


def test_terminal_timeout():
    events = [
        _make_event(0),
        _make_event(1, event_type="session_end", status="timeout"),
    ]
    result = judge_reliability(events)
    # base 30 for timeout terminal
    assert result.score == 30.0


def test_partial_terminal():
    events = [
        _make_event(0),
        _make_event(1, event_type="session_end", status="partial"),
    ]
    result = judge_reliability(events)
    assert result.score == 50.0


def test_floor_at_zero():
    events = [_make_event(i, status="error") for i in range(7)] + [
        _make_event(7, event_type="session_end", status="error"),
    ]
    result = judge_reliability(events)
    assert result.score >= 0.0
