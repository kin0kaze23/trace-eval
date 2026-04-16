import pytest
from trace_eval.scoring import Scorecard, DEFAULT_PROFILE, REQUIRED_JUDGES, compute_scorecard
from trace_eval.schema import JudgeResult, FrictionFlag


def _make_result(score, scorable=True, confidence="high"):
    return JudgeResult(
        score=score, confidence=confidence, friction_flags=[],
        explanation="", raw_metrics={}, scorable=scorable,
    )


def test_compute_all_scorable():
    judges = {
        "reliability": _make_result(80),
        "efficiency": _make_result(90),
        "retrieval": _make_result(70),
        "tool_discipline": _make_result(85),
        "context": _make_result(75),
    }
    card = compute_scorecard(judges)
    # 80*0.35 + 90*0.20 + 70*0.20 + 85*0.15 + 75*0.10
    # = 28 + 18 + 14 + 12.75 + 7.5 = 80.25
    assert abs(card.total_score - 80.25) < 0.01


def test_unscorable_optional_redistributes():
    # Context unscorable (10% weight) -> redistributed to others
    judges = {
        "reliability": _make_result(80),
        "efficiency": _make_result(90),
        "retrieval": _make_result(70),
        "tool_discipline": _make_result(85),
        "context": JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="", raw_metrics={}, scorable=False,
        ),
    }
    card = compute_scorecard(judges)
    # Total weight of scorable = 0.35+0.20+0.20+0.15 = 0.90
    # reliability: 0.35/0.90 * 80 = 31.11...
    # efficiency: 0.20/0.90 * 90 = 20
    # retrieval: 0.20/0.90 * 70 = 15.56...
    # tool_discipline: 0.15/0.90 * 85 = 14.17...
    # Total ~ 80.84
    assert abs(card.total_score - 80.83) < 0.1
    assert "context" in card.unscorable_dimensions


def test_unscorable_required_still_fails():
    """Reliability and tool_discipline are required — retrieval is optional."""
    judges = {
        "reliability": _make_result(80),
        "efficiency": _make_result(90),
        "retrieval": JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="", raw_metrics={}, scorable=False,
        ),
        "tool_discipline": _make_result(85),
        "context": _make_result(75),
    }
    card = compute_scorecard(judges)
    assert "retrieval" in card.unscorable_dimensions
    # Retrieval is no longer required — weight redistributes
    assert "retrieval" not in card.missing_required_judges

    # If reliability is unscorable (required), it should show up
    judges2 = {
        "reliability": JudgeResult(
            score=None, confidence="low", friction_flags=[],
            explanation="", raw_metrics={}, scorable=False,
        ),
        "efficiency": _make_result(90),
        "retrieval": _make_result(70),
        "tool_discipline": _make_result(85),
        "context": _make_result(75),
    }
    card2 = compute_scorecard(judges2)
    assert "reliability" in card2.missing_required_judges


def test_friction_flags_collected():
    flag = FrictionFlag(
        id="test", severity="high", dimension="reliability",
        event_index=None, suggestion="fix it",
    )
    judges = {
        "reliability": JudgeResult(
            score=80, confidence="high", friction_flags=[flag],
            explanation="", raw_metrics={}, scorable=True,
        ),
        "efficiency": _make_result(90),
        "retrieval": _make_result(70),
        "tool_discipline": _make_result(85),
        "context": _make_result(75),
    }
    card = compute_scorecard(judges)
    assert len(card.all_flags) == 1
    assert card.all_flags[0].id == "test"
