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
    def test_empty_events_unscorable(self):
        """Empty events list is unscorable."""
        result = judge_efficiency([])
        assert not result.scorable
        assert result.score is None

    def test_no_token_cost_but_scorable_via_tool_density(self):
        """A trace with events but no token/cost data is scorable via tool_density.

        Zero tool calls is observed, not missing.
        """
        events = [_make_event(event_index=0, event_type=EventType.message, status=Status.success)]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.score is not None
        assert result.raw_metrics["has_token_data"] is False
        assert result.raw_metrics["has_cost_data"] is False
        assert result.raw_metrics["has_tool_calls"] is True
        assert result.raw_metrics["tool_call_count"] == 0

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
        events = [_make_event(event_index=0, event_type=EventType.tool_call, status=Status.success, tool_name="bash")]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.raw_metrics["has_token_data"] is False
        assert result.raw_metrics["has_cost_data"] is False
        # tool_density_sub = max(0, 100 - 1*2) = 98
        # score = 0.3 * 98 = 29.4 (only tool_density weight contributes)
        assert result.score == 29.4

    def test_missing_telemetry_reduces_confidence(self):
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


class TestTelemetryMonotonicity:
    """Removing telemetry must never improve the efficiency score."""

    def test_removing_token_telemetry_cannot_improve_score(self):
        """A trace with poor token sub-score must not improve when tokens are removed."""
        # High token usage produces a poor token sub-score
        events_with_tokens = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=50000,
                tokens_out=10000,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_with = judge_efficiency(events_with_tokens)
        # Same trace but with token data removed
        events_without = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=None,
                tokens_out=None,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_without = judge_efficiency(events_without)
        assert result_without.score <= result_with.score, (
            f"Score without tokens ({result_without.score}) should not exceed score with tokens ({result_with.score})"
        )

    def test_removing_cost_telemetry_cannot_improve_score(self):
        """A trace with poor cost sub-score must not improve when cost is removed."""
        events_with_cost = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=100,
                tokens_out=50,
                cost_estimate=5.0,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_with = judge_efficiency(events_with_cost)
        events_without = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=100,
                tokens_out=50,
                cost_estimate=None,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_without = judge_efficiency(events_without)
        assert result_without.score <= result_with.score, (
            f"Score without cost ({result_without.score}) should not exceed score with cost ({result_with.score})"
        )

    def test_zero_observed_tool_calls_gets_appropriate_score(self):
        """Zero tool calls is observed, not missing. Should get full tool_density sub-score."""
        events = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=100,
                tokens_out=50,
                cost_estimate=0.01,
            ),
        ]
        result = judge_efficiency(events)
        assert result.scorable
        assert result.raw_metrics["has_tool_calls"] is True
        assert result.raw_metrics["tool_call_count"] == 0
        # tool_density_sub = max(0, 100 - 0*2) = 100
        # score = 0.4 * token_sub + 0.3 * cost_sub + 0.3 * 100
        # token_sub = max(0, 100 - 150/500) = 99.7
        # cost_sub = max(0, 100 - 0.01*100) = 99.0
        # score = 0.4*99.7 + 0.3*99.0 + 0.3*100 = 39.88 + 29.7 + 30 = 99.58
        assert result.score == 99.58

    def test_pathological_case_low_component_removed(self):
        """Removing a low-scoring component must not increase the score."""
        # Token sub-score is very low (high usage)
        # Cost and tool density are high
        events_with = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=50000,
                tokens_out=10000,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_with = judge_efficiency(events_with)
        # Remove token data — with fixed weights, the token weight (0.4)
        # now contributes 0 instead of a low sub-score
        events_without = [
            _make_event(
                event_index=0,
                event_type=EventType.llm_call,
                status=Status.success,
                tokens_in=None,
                tokens_out=None,
                cost_estimate=0.01,
            ),
            _make_event(event_index=1, event_type=EventType.tool_call, status=Status.success, tool_name="bash"),
        ]
        result_without = judge_efficiency(events_without)
        assert result_without.score <= result_with.score, (
            f"Removing low-scoring telemetry improved score: with={result_with.score}, without={result_without.score}"
        )
