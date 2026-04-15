import json
import pytest
from trace_eval.report import format_text, format_json
from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag


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
            "reliability": "high", "efficiency": "medium",
            "retrieval": "high", "tool_discipline": "high", "context": "low",
        },
        all_flags=[
            FrictionFlag(
                id="reliability_errors", severity="medium",
                dimension="reliability", event_index=3,
                suggestion="Review errors at event indices [3, 5]",
            ),
        ],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=[],
        missing_required_judges=[],
    )


def test_text_format_has_score():
    card = _make_card()
    text = format_text(card)
    assert "72.5" in text
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
    card = _make_card()
    data = json.loads(format_json(card, adapter_report={"has_token_data": True}))
    # Spec-mandated fields that must always be present
    assert "total_score" in data
    assert "dimension_scores" in data
    assert "friction_flags" in data
    assert "likely_causes" in data
    assert "suggestions" in data
    assert "scorable_dimensions" in data
    assert "unscorable_dimensions" in data
    assert "judge_coverage" in data
    assert "adapter_capability_report" in data
    assert "failed_thresholds" in data
