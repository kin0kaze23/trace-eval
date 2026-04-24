from trace_eval.judges.efficiency import judge_efficiency
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


def test_low_usage_perfect_score():
    events = [_make_event(0, tokens_in=100, tokens_out=50, cost_estimate=0.01)]
    result = judge_efficiency(events)
    assert result.score >= 90.0


def test_high_tokens_penalty():
    # 25000 tokens → token_sub = max(0, 100 - 25000/500) = 50
    events = [_make_event(i, tokens_in=5000, tokens_out=0) for i in range(5)]
    result = judge_efficiency(events)
    # total_tokens = 25000, token_sub = 50
    # cost_sub = 100 (no cost), tool_density_sub = 100 (no tool calls)
    # composite = 50*0.4 + 100*0.3 + 100*0.3 = 20 + 30 + 30 = 80
    assert result.score == 80.0


def test_high_cost_penalty():
    events = [_make_event(0, cost_estimate=0.50)]
    result = judge_efficiency(events)
    # cost_sub = max(0, 100 - 0.50*100) = 50
    # token_sub = 100, tool_density = 100
    # composite = 100*0.4 + 50*0.3 + 100*0.3 = 40 + 15 + 30 = 85
    assert result.score == 85.0


def test_unscorable_no_data():
    events = [_make_event(0)]
    result = judge_efficiency(events)
    # No tokens, cost, or tool data — but we can still compute (all zeros = good)
    assert result.scorable is True
