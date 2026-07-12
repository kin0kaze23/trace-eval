"""Tests for missing-telemetry handling in the efficiency judge."""

from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.schema import Event, EventType, Status


def _make_event(
    event_index=0,
    event_type=None,
    status=None,
    tokens_in=None,
    tokens_out=None,
    cost_estimate=None,
    latency_ms=None,
    tool_name=None,
):
    return Event(
        event_index=event_index,
        actor="assistant",
        event_type=event_type,
        timestamp="2026-01-01T00:00:00Z",
        status=status,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=cost_estimate,
        latency_ms=latency_ms,
        tool_name=tool_name,
    )


class TestMissingTelemetry:
    def test_no_telemetry_is_unscorable(self):
        events = [
            _make_event(event_index=0, event_type=EventType.message, status=Status.success),
            _make_event(event_index=1, event_type=EventType.message, status=Status.success),
        ]
        result = judge_efficiency(events)
        assert not result.scorable
        assert result.score is None

    def test_missing_tokens_not_treated_as_zero(self):
        events = [
            _make_event(event_index=0, event_type=EventType.tool_call, status=Status.success, tool_name="read"),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="write"),
        ]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.score is not None
        assert result.score < 100
        assert result.confidence == "medium"
        assert result.raw_metrics["has_token_data"] is False
        assert result.raw_metrics["has_tool_calls"] is True

    def test_missing_telemetry_not_treated_as_zero(self):
        """Missing telemetry should not be treated as observed zero."""
        events = [
            _make_event(event_index=0, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.raw_metrics["has_token_data"] is False
        assert result.raw_metrics["has_cost_data"] is False
        assert result.score == 98.0  # only tool_density active

    def test_missing_telemetry_reduces_confidence(self):
        """Partial telemetry should produce reduced confidence."""
        events_full = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=500,
                tokens_out=200,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="read"),
        ]
        result_full = judge_efficiency(events_full)
        assert result_full.confidence == "high"

        events_partial = [
            _make_event(
                event_index=0, event_type=EventType.llm_call, status=Status.success, tokens_in=500, tokens_out=200
            ),
        ]
        result_partial = judge_efficiency(events_partial)
        assert result_partial.confidence == "medium"

    def test_partial_telemetry_produces_valid_score(self):
        events = [
            _make_event(
                event_index=0, event_type=EventType.llm_call, status=Status.success, tokens_in=500, tokens_out=200
            ),
        ]
        result = judge_efficiency(events)
        assert result.scorable
        assert 0 <= result.score <= 100
        assert result.confidence == "medium"

    def test_all_telemetry_present_high_confidence(self):
        events = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=500,
                tokens_out=200,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="read"),
        ]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.confidence == "high"

    def test_score_always_in_0_to_100(self):
        events = [
            _make_event(
                event_index=i,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=100000,
                tokens_out=50000,
                cost_estimate=10.0,
            )
            for i in range(10)
        ]
        result = judge_efficiency(events)
        assert 0 <= result.score <= 100

    def test_empty_events_unscorable(self):
        result = judge_efficiency([])
        assert not result.scorable
