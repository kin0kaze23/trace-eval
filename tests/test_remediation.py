import pytest
from trace_eval.remediation import analyze, ACTION_TYPES, format_remediation, format_next_steps
from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag


def _make_card(flags=None, dim_scores=None, unscorable=None, profile="default", total_score=50):
    return Scorecard(
        total_score=total_score,
        dimension_scores=dim_scores or {
            "reliability": 50.0, "efficiency": 50.0, "retrieval": 50.0,
            "tool_discipline": 50.0, "context": 50.0,
        },
        dimension_confidence={
            "reliability": "high", "efficiency": "high", "retrieval": "high",
            "tool_discipline": "high", "context": "high",
        },
        all_flags=flags or [],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=unscorable or [],
        missing_required_judges=[],
        profile=profile,
        rating="Needs Work",
    )


def test_fix_errors_when_reliability_flag_present():
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium",
                     dimension="reliability", event_index=None,
                     suggestion="Review errors"),
    ])
    actions = analyze(card)
    assert any(a.action_type == "fix_errors" for a in actions)


def test_switch_profile_when_retrieval_unscorable():
    card = _make_card(unscorable=["retrieval"], profile="default")
    actions = analyze(card)
    assert any(a.action_type == "switch_profile" for a in actions)


def test_no_switch_profile_when_already_coding_agent():
    card = _make_card(unscorable=["retrieval"], profile="coding_agent")
    actions = analyze(card)
    assert not any(a.action_type == "switch_profile" for a in actions)


def test_reduce_prompt_size_when_high_tokens():
    card = _make_card(flags=[
        FrictionFlag(id="efficiency_high_tokens", severity="medium",
                     dimension="efficiency", event_index=None,
                     suggestion="Reduce tokens"),
    ])
    actions = analyze(card)
    assert any(a.action_type == "reduce_prompt_size" for a in actions)


def test_actions_sorted_by_confidence():
    card = _make_card(flags=[
        FrictionFlag(id="efficiency_high_tool_calls", severity="low",
                     dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="reliability_errors", severity="medium",
                     dimension="reliability", event_index=None, suggestion=""),
    ], total_score=30)
    actions = analyze(card)
    confidences = [a.confidence for a in actions]
    # High confidence actions should come first
    assert confidences.index("high") < confidences.index("medium")


def test_max_5_actions():
    # Create card that triggers many rules
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium", dimension="reliability", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tokens", severity="medium", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tool_calls", severity="low", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="tool_redundant", severity="low", dimension="tool_discipline", event_index=None, suggestion=""),
        FrictionFlag(id="retrieval_no_entrypoint", severity="critical", dimension="retrieval", event_index=None, suggestion=""),
    ], dim_scores={"reliability": 10.0, "efficiency": 20.0, "retrieval": 0.0, "tool_discipline": 30.0, "context": 40.0}, total_score=20)
    actions = analyze(card)
    assert len(actions) <= 5


def test_safe_to_automate_actions():
    card = _make_card(unscorable=["retrieval"], profile="default", total_score=30)
    actions = analyze(card)
    profile_action = next(a for a in actions if a.action_type == "switch_profile")
    assert profile_action.safe_to_automate is True
    assert profile_action.requires_approval is False


def test_no_actions_for_good_score():
    card = _make_card(total_score=95, dim_scores={
        "reliability": 100.0, "efficiency": 95.0, "retrieval": 100.0,
        "tool_discipline": 100.0, "context": 100.0,
    })
    actions = analyze(card)
    assert len(actions) == 0


def test_remediation_top_3_format():
    """Asserts 'TOP 3 ACTIONS:' appears when there are >= 3 actions."""
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium", dimension="reliability", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tokens", severity="medium", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tool_calls", severity="low", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="tool_redundant", severity="low", dimension="tool_discipline", event_index=None, suggestion=""),
        FrictionFlag(id="retrieval_no_entrypoint", severity="critical", dimension="retrieval", event_index=None, suggestion=""),
    ], dim_scores={"reliability": 10.0, "efficiency": 20.0, "retrieval": 0.0, "tool_discipline": 30.0, "context": 40.0}, total_score=20)
    actions = analyze(card)
    output = format_remediation(actions, card)
    assert "TOP 3 ACTIONS:" in output


def test_remediation_approval_tag_placement():
    """Asserts approval tags appear BEFORE the action label on each line."""
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium", dimension="reliability", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tokens", severity="medium", dimension="efficiency", event_index=None, suggestion=""),
    ], unscorable=["retrieval"], profile="default",
    dim_scores={"reliability": 10.0, "efficiency": 20.0, "retrieval": 50.0, "tool_discipline": 50.0, "context": 50.0}, total_score=30)
    actions = analyze(card)
    output = format_remediation(actions, card)
    # switch_profile is AUTO-SAFE; fix_errors/reduce_prompt_size/add_ci_gate are REQUIRES APPROVAL
    assert "[AUTO-SAFE]" in output
    assert "[REQUIRES APPROVAL]" in output
    # Verify tag position: tag should appear before the label text on each numbered line
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and stripped[0].isdigit() and ". " in stripped:
            after_number = stripped.split(". ", 1)[1]
            assert "[AUTO-SAFE]" in after_number or "[REQUIRES APPROVAL]" in after_number


def test_next_steps_compact_format():
    """Tests format_next_steps: compact, has approval tags, no footer links."""
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium", dimension="reliability", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tokens", severity="medium", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="tool_redundant", severity="low", dimension="tool_discipline", event_index=None, suggestion=""),
    ], dim_scores={"reliability": 10.0, "efficiency": 20.0, "retrieval": 50.0, "tool_discipline": 30.0, "context": 50.0}, total_score=30)
    actions = analyze(card)
    output = format_next_steps(actions, card)
    assert "Next steps:" in output
    assert "trace-eval remediate" not in output
    assert "[AUTO-SAFE]" in output or "[REQUIRES APPROVAL]" in output
