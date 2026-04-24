import json

from trace_eval.report import ScoreRating, compute_rating, format_json, format_summary, format_text
from trace_eval.schema import FrictionFlag
from trace_eval.scoring import Scorecard


def _make_card():
    return Scorecard(
        total_score=72.5,
        dimension_scores={
            "reliability": 60.0,
            "efficiency": 80.0,
            "retrieval": 70.0,
            "tool_discipline": 85.0,
            "context": 75.0,
        },
        dimension_confidence={
            "reliability": "high",
            "efficiency": "medium",
            "retrieval": "high",
            "tool_discipline": "high",
            "context": "low",
        },
        all_flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=3,
                suggestion="Review errors at event indices [3, 5]",
            ),
        ],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=[],
        missing_required_judges=[],
        profile="default",
        rating="Good",
    )


def test_text_format_has_score():
    card = _make_card()
    text = format_text(card)
    assert "72.5" in text
    assert "[Good]" in text
    assert "reliability" in text.lower()


def test_text_format_has_flags():
    card = _make_card()
    text = format_text(card)
    assert "reliability_errors" in text


def test_json_format_is_valid():
    card = _make_card()
    json_str = format_json(card)
    data = json.loads(json_str)
    assert abs(data["total_score"] - 72.5) < 0.01
    assert "friction_flags" in data


def test_json_has_required_fields():
    """JSON output must always include spec-mandated fields."""
    from trace_eval.remediation import RemediationAction

    card = _make_card()
    actions = [
        RemediationAction(
            action_type="fix_errors",
            label="Fix errors",
            description="Fix.",
            confidence="high",
            safe_to_automate=False,
            requires_approval=True,
            triggered_by="test",
        ),
    ]
    data = json.loads(format_json(card, adapter_report={"has_token_data": True}, actions=actions))
    # Spec-mandated fields that must always be present
    assert "total_score" in data
    assert "rating" in data
    assert "dimension_scores" in data
    assert "friction_flags" in data
    assert "likely_causes" in data
    assert "suggestions" in data
    assert "scorable_dimensions" in data
    assert "unscorable_dimensions" in data
    assert "judge_coverage" in data
    assert "adapter_capability_report" in data
    assert "failed_thresholds" in data
    assert "top_issues" in data
    assert "top_actions" in data


def _make_bad_card():
    """Scorecard with low scores for testing summary output."""
    return Scorecard(
        total_score=28.3,
        dimension_scores={
            "reliability": 0.0,
            "efficiency": 30.0,
            "retrieval": None,
            "tool_discipline": 92.0,
            "context": None,
        },
        dimension_confidence={
            "reliability": "high",
            "efficiency": "high",
            "retrieval": "low",
            "tool_discipline": "high",
            "context": "low",
        },
        all_flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="Review 90 error(s)",
            ),
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="High token usage detected",
            ),
            FrictionFlag(
                id="tool_redundant",
                severity="low",
                dimension="tool_discipline",
                event_index=3,
                suggestion="1 redundant tool call",
            ),
        ],
        scorable_dimensions=["reliability", "efficiency", "tool_discipline"],
        unscorable_dimensions=["retrieval", "context"],
        missing_required_judges=[],
        profile="default",
        rating="Critical",
    )


def _make_good_card():
    """Scorecard with high scores for testing summary output."""
    return Scorecard(
        total_score=98.9,
        dimension_scores={
            "reliability": 100.0,
            "efficiency": 94.5,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
        dimension_confidence={
            "reliability": "high",
            "efficiency": "medium",
            "retrieval": "high",
            "tool_discipline": "high",
            "context": "high",
        },
        all_flags=[],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=[],
        missing_required_judges=[],
        profile="default",
        rating="Excellent",
    )


def test_summary_has_score():
    card = _make_bad_card()
    text = format_summary(card)
    assert "28.3" in text
    assert "/100" in text


def test_summary_has_top_flags():
    card = _make_bad_card()
    text = format_summary(card)
    assert "reliability_errors" in text


def test_summary_has_diagnosis():
    card = _make_bad_card()
    text = format_summary(card)
    assert "Diagnosis:" in text
    assert "friction" in text.lower()


def test_summary_is_concise():
    """Summary should be under 10 lines — designed for quick scanning."""
    card = _make_bad_card()
    text = format_summary(card)
    lines = [l for l in text.split("\n") if l.strip()]
    assert len(lines) <= 10


def test_summary_good_run():
    """Good runs should have minimal output."""
    card = _make_good_card()
    text = format_summary(card)
    assert "98.9" in text
    assert "looks good" in text.lower()


def test_rating_thresholds():
    assert compute_rating(95) == ScoreRating.EXCELLENT
    assert compute_rating(90) == ScoreRating.EXCELLENT
    assert compute_rating(89) == ScoreRating.GOOD
    assert compute_rating(70) == ScoreRating.GOOD
    assert compute_rating(69) == ScoreRating.NEEDS_WORK
    assert compute_rating(40) == ScoreRating.NEEDS_WORK
    assert compute_rating(39) == ScoreRating.CRITICAL
    assert compute_rating(0) == ScoreRating.CRITICAL


def test_json_has_rating():
    """JSON output must include a rating field."""
    card = _make_card()
    data = json.loads(format_json(card))
    assert data["rating"] == "Good"


def test_json_has_top_issues():
    """JSON output must include top_issues — up to 3 friction flags sorted by severity."""
    card = _make_card()
    data = json.loads(format_json(card))
    assert "top_issues" in data
    assert isinstance(data["top_issues"], list)
    assert len(data["top_issues"]) <= 3
    for issue in data["top_issues"]:
        assert "id" in issue
        assert "severity" in issue
        assert "summary" in issue


def test_json_has_top_actions():
    """JSON output must include top_actions — up to 3 actions sorted deterministically."""
    card = _make_card()
    from trace_eval.remediation import analyze

    actions = analyze(card)
    data = json.loads(format_json(card, actions=actions))
    assert "top_actions" in data
    assert isinstance(data["top_actions"], list)
    assert len(data["top_actions"]) <= 3
    for action in data["top_actions"]:
        assert "action_type" in action
        assert "label" in action
        assert "description" in action
        assert "confidence" in action
        assert "safe_to_automate" in action
        assert "requires_approval" in action
