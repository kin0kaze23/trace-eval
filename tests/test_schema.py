import pytest
from trace_eval.schema import (
    EventType, Status, FrictionFlag, JudgeResult, Event, Trace, FieldCoverage
)


def test_event_type_enum_values():
    expected = [
        "message", "llm_call", "tool_call", "tool_result",
        "vault_read", "memory_read", "memory_write", "search_fallback",
        "context_warning", "context_compress", "system",
        "session_start", "session_end",
    ]
    assert sorted(e.value for e in EventType) == sorted(expected)


def test_status_enum_values():
    expected = ["success", "error", "partial", "timeout"]
    assert sorted(s.value for s in Status) == sorted(expected)


def test_friction_flag_dataclass():
    flag = FrictionFlag(
        id="test_flag",
        severity="high",
        dimension="reliability",
        event_index=5,
        suggestion="Fix the thing",
    )
    assert flag.id == "test_flag"
    assert flag.severity == "high"
    assert flag.event_index == 5


def test_judge_result_unscorable():
    result = JudgeResult(
        score=None,
        confidence="low",
        friction_flags=[],
        explanation="Not enough data",
        raw_metrics={},
        scorable=False,
    )
    assert result.score is None
    assert result.scorable is False


def test_event_from_dict_minimal():
    data = {
        "event_index": 0,
        "actor": "user",
        "event_type": "message",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    }
    event = Event.from_dict(data)
    assert event.event_index == 0
    assert event.actor == "user"
    assert event.event_type == EventType.message
    assert event.status == Status.success


def test_event_from_dict_full():
    data = {
        "schema_version": "v1",
        "trace_id": "abc-123",
        "task_id": "task-001",
        "task_label": "Fix auth bug",
        "session_id": "sess-001",
        "event_index": 1,
        "actor": "assistant",
        "event_type": "llm_call",
        "timestamp": "2026-04-15T10:00:05Z",
        "status": "success",
        "model": "claude-opus-4-6",
        "tokens_in": 1200,
        "tokens_out": 350,
        "cost_estimate": 0.05,
        "latency_ms": 2500,
    }
    event = Event.from_dict(data)
    assert event.trace_id == "abc-123"
    assert event.tokens_in == 1200
    assert event.cost_estimate == 0.05


def test_event_from_dict_unknown_event_type():
    data = {
        "event_index": 0,
        "actor": "user",
        "event_type": "unknown_type",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    }
    event = Event.from_dict(data)
    assert event.event_type is None


def test_trace_from_events():
    events = [
        Event.from_dict({
            "event_index": 0, "actor": "user", "event_type": "message",
            "timestamp": "2026-04-15T10:00:00Z", "status": "success",
            "trace_id": "abc-123", "task_id": "t-1", "session_id": "s-1",
        }),
    ]
    trace = Trace.from_events(events)
    assert trace.trace_id == "abc-123"
    assert len(trace.events) == 1


def test_field_coverage_compute():
    events = [
        Event.from_dict({
            "event_index": 0, "actor": "user", "event_type": "message",
            "timestamp": "2026-04-15T10:00:00Z", "status": "success",
            "tokens_in": 100, "latency_ms": 500,
        }),
        Event.from_dict({
            "event_index": 1, "actor": "assistant", "event_type": "llm_call",
            "timestamp": "2026-04-15T10:00:05Z", "status": "success",
            "tokens_in": 200, "tokens_out": 50,
        }),
    ]
    coverage = FieldCoverage.compute(events)
    assert coverage.fields["tokens_in"].present == 2
    assert coverage.fields["tokens_in"].total == 2
    assert coverage.fields["tokens_out"].present == 1
    assert coverage.fields["tokens_out"].total == 2
    assert coverage.fields["latency_ms"].present == 1
