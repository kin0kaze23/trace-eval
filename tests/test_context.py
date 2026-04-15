import pytest
from trace_eval.judges.context import judge_context
from trace_eval.schema import Event


def _make_event(index, **extra):
    data = {
        "event_index": index,
        "actor": "assistant",
        "event_type": "llm_call",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    }
    data.update(extra)
    return Event.from_dict(data)


def test_no_pressure_perfect():
    events = [_make_event(0, context_pressure_pct=30.0)]
    result = judge_context(events)
    assert result.score == 100.0


def test_pressure_above_90():
    events = [_make_event(0, context_pressure_pct=95.0)]
    result = judge_context(events)
    # 100 - 50 = 50
    assert result.score == 50.0


def test_pressure_above_70():
    events = [_make_event(0, context_pressure_pct=75.0)]
    result = judge_context(events)
    # 100 - 20 = 80
    assert result.score == 80.0


def test_pressure_above_50():
    events = [_make_event(0, context_pressure_pct=55.0)]
    result = judge_context(events)
    # 100 - 5 = 95
    assert result.score == 95.0


def test_compression_penalty():
    events = [
        _make_event(0, context_pressure_pct=30),
        _make_event(1, event_type="context_compress"),
        _make_event(2, event_type="context_compress"),
    ]
    result = judge_context(events)
    # 100 - 8*2 = 84
    assert result.score == 84.0


def test_unscorable_no_data():
    events = [_make_event(0)]
    result = judge_context(events)
    assert result.scorable is False
    assert result.score is None
