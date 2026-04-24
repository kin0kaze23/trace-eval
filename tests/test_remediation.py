import pytest
from trace_eval.remediation import (
    analyze,
    analyze_with_context,
    ACTION_TYPES,
    format_remediation,
    format_next_steps,
)
from trace_eval.scoring import Scorecard
from trace_eval.schema import Event, EventType, Status, FrictionFlag


def _make_card(
    flags=None, dim_scores=None, unscorable=None, profile="default", total_score=50
):
    return Scorecard(
        total_score=total_score,
        dimension_scores=dim_scores
        or {
            "reliability": 50.0,
            "efficiency": 50.0,
            "retrieval": 50.0,
            "tool_discipline": 50.0,
            "context": 50.0,
        },
        dimension_confidence={
            "reliability": "high",
            "efficiency": "high",
            "retrieval": "high",
            "tool_discipline": "high",
            "context": "high",
        },
        all_flags=flags or [],
        scorable_dimensions=[
            "reliability",
            "efficiency",
            "retrieval",
            "tool_discipline",
            "context",
        ],
        unscorable_dimensions=unscorable or [],
        missing_required_judges=[],
        profile=profile,
        rating="Needs Work",
    )


def test_fix_errors_when_reliability_flag_present():
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="Review errors",
            ),
        ]
    )
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
    card = _make_card(
        flags=[
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="Reduce tokens",
            ),
        ]
    )
    actions = analyze(card)
    assert any(a.action_type == "reduce_prompt_size" for a in actions)


def test_actions_sorted_by_confidence():
    card = _make_card(
        flags=[
            FrictionFlag(
                id="efficiency_high_tool_calls",
                severity="low",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="",
            ),
        ],
        total_score=30,
    )
    actions = analyze(card)
    confidences = [a.confidence for a in actions]
    # High confidence actions should come first
    assert confidences.index("high") < confidences.index("medium")


def test_max_5_actions():
    # Create card that triggers many rules
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tool_calls",
                severity="low",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="tool_redundant",
                severity="low",
                dimension="tool_discipline",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="retrieval_no_entrypoint",
                severity="critical",
                dimension="retrieval",
                event_index=None,
                suggestion="",
            ),
        ],
        dim_scores={
            "reliability": 10.0,
            "efficiency": 20.0,
            "retrieval": 0.0,
            "tool_discipline": 30.0,
            "context": 40.0,
        },
        total_score=20,
    )
    actions = analyze(card)
    assert len(actions) <= 5


def test_safe_to_automate_actions():
    card = _make_card(unscorable=["retrieval"], profile="default", total_score=30)
    actions = analyze(card)
    profile_action = next(a for a in actions if a.action_type == "switch_profile")
    assert profile_action.safe_to_automate is True
    assert profile_action.requires_approval is False


def test_no_actions_for_good_score():
    card = _make_card(
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 95.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze(card)
    assert len(actions) == 0


def test_remediation_top_3_format():
    """Asserts 'TOP 3 ACTIONS:' appears when there are >= 3 actions."""
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tool_calls",
                severity="low",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="tool_redundant",
                severity="low",
                dimension="tool_discipline",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="retrieval_no_entrypoint",
                severity="critical",
                dimension="retrieval",
                event_index=None,
                suggestion="",
            ),
        ],
        dim_scores={
            "reliability": 10.0,
            "efficiency": 20.0,
            "retrieval": 0.0,
            "tool_discipline": 30.0,
            "context": 40.0,
        },
        total_score=20,
    )
    actions = analyze(card)
    output = format_remediation(actions, card)
    assert "TOP 3 ACTIONS:" in output


def test_remediation_approval_tag_placement():
    """Asserts approval tags appear BEFORE the action label on each line."""
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
        ],
        unscorable=["retrieval"],
        profile="default",
        dim_scores={
            "reliability": 10.0,
            "efficiency": 20.0,
            "retrieval": 50.0,
            "tool_discipline": 50.0,
            "context": 50.0,
        },
        total_score=30,
    )
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
            assert (
                "[AUTO-SAFE]" in after_number or "[REQUIRES APPROVAL]" in after_number
            )


def test_next_steps_compact_format():
    """Tests format_next_steps: compact, has approval tags, no footer links."""
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="",
            ),
            FrictionFlag(
                id="tool_redundant",
                severity="low",
                dimension="tool_discipline",
                event_index=None,
                suggestion="",
            ),
        ],
        dim_scores={
            "reliability": 10.0,
            "efficiency": 20.0,
            "retrieval": 50.0,
            "tool_discipline": 30.0,
            "context": 50.0,
        },
        total_score=30,
    )
    actions = analyze(card)
    output = format_next_steps(actions, card)
    assert "Next steps:" in output
    assert "trace-eval remediate" not in output
    assert "[AUTO-SAFE]" in output or "[REQUIRES APPROVAL]" in output


# ---------------------------------------------------------------------------
# install_capability action tests (issue #1 — agent-ready integration)
# ---------------------------------------------------------------------------


def _make_event(
    idx,
    event_type=None,
    status=None,
    tool_name=None,
    error_type=None,
):
    return Event(
        event_index=idx,
        actor="tool" if tool_name else "assistant",
        event_type=event_type,
        timestamp="2026-04-24T00:00:00Z",
        status=status,
        tool_name=tool_name,
        error_type=error_type,
    )


def test_install_capability_hit_from_error_type():
    """When an event error_type matches a missing-tool pattern, install_capability is emitted."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: vercel",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 1
    assert install_actions[0].context["capability_id"] == "vercel_cli"


def test_install_capability_hit_from_fixture():
    """Synthetic fixture trace_missing_vercel.jsonl triggers install_capability."""
    from pathlib import Path
    from trace_eval.loader import load_trace

    fixture = Path(__file__).parent / "fixtures" / "trace_missing_vercel.jsonl"
    trace = load_trace(fixture)
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, trace.events)
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 1
    assert install_actions[0].context["capability_id"] == "vercel_cli"


def test_install_capability_dedup_same_capability():
    """Multiple patterns mapping to the same capability produce ONE action."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: vercel",
        ),
        _make_event(
            1,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="vercel: command not found",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 1
    assert install_actions[0].context["capability_id"] == "vercel_cli"


def test_install_capability_two_distinct_capabilities():
    """Two different missing tools produce TWO separate actions."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: vercel",
        ),
        _make_event(
            1,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: gh",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 2
    cap_ids = {a.context["capability_id"] for a in install_actions}
    assert cap_ids == {"vercel_cli", "github_cli"}


def test_install_capability_payload_shape():
    """Action payload has correct fields: safe_to_automate, requires_approval, context."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: vercel",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    action = next(a for a in actions if a.action_type == "install_capability")
    assert action.safe_to_automate is False
    assert action.requires_approval is True
    assert action.confidence == "high"
    assert action.context["capability_id"] == "vercel_cli"
    assert (
        action.context["suggested_command"] == "agent-ready fix --capability vercel_cli"
    )
    assert action.triggered_by == "command not found: vercel"


def test_install_capability_no_false_positive():
    """Normal error patterns without missing-tool text do NOT trigger install_capability."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="exit_code_1",
        ),
        _make_event(
            1,
            EventType.tool_call,
            status=Status.error,
            tool_name="Write",
            error_type="file_not_found",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 0


def test_install_capability_no_events_no_trigger():
    """When no events are provided, install_capability is NOT triggered."""
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, [])
    install_actions = [a for a in actions if a.action_type == "install_capability"]
    assert len(install_actions) == 0


def test_install_capability_sorted_with_high_confidence():
    """install_capability has confidence=high and sorts with other high-confidence actions."""
    events = [
        _make_event(
            0,
            EventType.tool_call,
            status=Status.error,
            tool_name="Bash",
            error_type="command not found: vercel",
        ),
    ]
    card = _make_card(
        flags=[],
        total_score=95,
        dim_scores={
            "reliability": 100.0,
            "efficiency": 100.0,
            "retrieval": 100.0,
            "tool_discipline": 100.0,
            "context": 100.0,
        },
    )
    actions = analyze_with_context(card, events)
    # install_capability is the only action (score 95 = no CI gate, no other flags)
    assert len(actions) == 1
    assert actions[0].confidence == "high"
    assert actions[0].action_type == "install_capability"
