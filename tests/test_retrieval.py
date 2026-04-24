from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.schema import Event


def _make_event(index, **extra):
    data = {
        "event_index": index,
        "actor": "assistant",
        "event_type": "tool_call",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    }
    data.update(extra)
    return Event.from_dict(data)


def test_perfect_retrieval():
    events = [
        _make_event(0, retrieval_entrypoint="canonical_read", retrieval_steps=["step1", "step2"]),
    ]
    result = judge_retrieval(events)
    assert result.score == 100.0


def test_no_entrypoint_penalty():
    events = [_make_event(0, retrieval_steps=["step1"])]
    result = judge_retrieval(events)
    # 100 - 40 = 60
    assert result.score == 60.0


def test_deprecated_file_penalty():
    events = [
        _make_event(0, retrieval_entrypoint="canonical_read", deprecated_file_touched=True, retrieval_steps=["step1"]),
    ]
    result = judge_retrieval(events)
    # 100 - 30 = 70
    assert result.score == 70.0


def test_fallback_search_penalty():
    events = [
        _make_event(0, retrieval_entrypoint="canonical_read", fallback_search_used=True, retrieval_steps=["step1"]),
    ]
    result = judge_retrieval(events)
    # 100 - 20 = 80
    assert result.score == 80.0


def test_no_retrieval_steps_penalty():
    events = [
        _make_event(0, retrieval_entrypoint="canonical_read", retrieval_steps=[]),
    ]
    result = judge_retrieval(events)
    # 100 - 10 = 90
    assert result.score == 90.0


def test_combined_penalties():
    events = [
        _make_event(0, deprecated_file_touched=True, fallback_search_used=True),
    ]
    result = judge_retrieval(events)
    # 100 - 40 (no entrypoint) - 30 (deprecated) - 20 (fallback) - 10 (no steps) = 0
    assert result.score == 0.0


def test_bonus_for_multiple_steps():
    events = [
        _make_event(0, retrieval_entrypoint="canonical_read", retrieval_steps=["step1", "step2"]),
    ]
    result = judge_retrieval(events)
    # 100 + 5 capped at 100
    assert result.score == 100.0
