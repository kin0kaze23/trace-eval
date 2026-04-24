import json

import pytest

from trace_eval.adapters.generic_jsonl import GenericJsonlAdapter
from trace_eval.loader import detect_adapter, load_trace, load_trace_with_report
from trace_eval.schema import EventType


@pytest.fixture
def sample_jsonl(tmp_path):
    p = tmp_path / "trace.jsonl"
    lines = [
        {
            "event_index": 0,
            "actor": "user",
            "event_type": "message",
            "timestamp": "2026-04-15T10:00:00Z",
            "status": "success",
            "trace_id": "abc-123",
            "task_id": "t-1",
            "session_id": "s-1",
        },
        {
            "event_index": 1,
            "actor": "assistant",
            "event_type": "llm_call",
            "timestamp": "2026-04-15T10:00:05Z",
            "status": "success",
            "trace_id": "abc-123",
            "tokens_in": 1200,
            "tokens_out": 350,
        },
        {
            "event_index": 2,
            "actor": "tool",
            "event_type": "tool_call",
            "timestamp": "2026-04-15T10:00:06Z",
            "status": "success",
            "tool_name": "grep",
            "tool_args": {"pattern": "auth"},
        },
    ]
    p.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return p


def test_detect_adapter_jsonl(sample_jsonl):
    adapter = detect_adapter(sample_jsonl)
    assert isinstance(adapter, GenericJsonlAdapter)


def test_generic_adapter_load(sample_jsonl):
    adapter = GenericJsonlAdapter()
    trace = adapter.load(sample_jsonl)
    assert len(trace.events) == 3
    assert trace.trace_id == "abc-123"
    assert trace.events[0].event_type == EventType.message
    assert trace.events[1].tokens_in == 1200
    assert trace.events[2].tool_name == "grep"


def test_load_trace_helper(sample_jsonl):
    trace = load_trace(sample_jsonl)
    assert len(trace.events) == 3
    assert trace.events[0].event_index == 0


def test_adapter_capability_report_observed(sample_jsonl):
    adapter = GenericJsonlAdapter()
    trace = adapter.load(sample_jsonl)
    cap = adapter.capability_report(trace)
    # sample_jsonl has tokens_in/tokens_out but no span_ids or latency
    assert cap["has_token_data"] is True
    assert cap["has_tool_calls"] is True  # has tool_name field
    assert cap["has_span_ids"] is False  # no span_id in sample data


def test_load_trace_with_report(sample_jsonl):
    trace, report = load_trace_with_report(sample_jsonl)
    assert len(trace.events) == 3
    assert report["has_token_data"] is True
