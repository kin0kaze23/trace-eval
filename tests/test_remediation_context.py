"""Tests for remediation context enrichment."""

from trace_eval.remediation import analyze_with_context
from trace_eval.schema import Event, EventType, FrictionFlag, Status
from trace_eval.scoring import Scorecard


def _make_card(flags=None, dim_scores=None, unscorable=None, profile="default", total_score=50):
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


def _make_event(
    idx,
    event_type=None,
    status=None,
    tool_name=None,
    error_type=None,
    tokens_in=None,
    tokens_out=None,
):
    return Event(
        event_index=idx,
        actor="tool" if tool_name else "assistant",
        event_type=event_type,
        timestamp="2026-04-20T00:00:00Z",
        status=status,
        tool_name=tool_name,
        error_type=error_type,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def test_enriched_fix_errors_shows_tool_names():
    """When error events have tool_name, remediation should reference specific tools."""
    events = [
        _make_event(0, event_type=EventType.tool_call, tool_name="Bash"),
        _make_event(
            1,
            event_type=EventType.tool_result,
            status=Status.error,
            tool_name="Bash",
            error_type="exit_code_1",
        ),
        _make_event(2, event_type=EventType.tool_call, tool_name="Bash"),
        _make_event(
            3,
            event_type=EventType.tool_result,
            status=Status.error,
            tool_name="Bash",
            error_type="exit_code_1",
        ),
        _make_event(4, event_type=EventType.tool_call, tool_name="Write"),
        _make_event(
            5,
            event_type=EventType.tool_result,
            status=Status.error,
            tool_name="Write",
            error_type="file_not_found",
        ),
    ]

    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=1,
                suggestion="Review errors",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, events)
    error_action = next((a for a in actions if a.action_type == "fix_errors"), None)
    assert error_action is not None
    assert "3" in error_action.label
    # Label should reference specific tools
    assert "Bash" in error_action.description or "Write" in error_action.description


def test_enriched_token_context():
    """When events have token data, remediation should show token counts."""
    events = [
        _make_event(0, EventType.llm_call, tokens_in=50000, tokens_out=30000),
        _make_event(1, EventType.llm_call, tokens_in=40000, tokens_out=20000),
    ]

    card = _make_card(
        flags=[
            FrictionFlag(
                id="efficiency_high_tokens",
                severity="medium",
                dimension="efficiency",
                event_index=None,
                suggestion="Reduce tokens",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, events)
    token_action = next((a for a in actions if a.action_type == "reduce_prompt_size"), None)
    assert token_action is not None
    assert "140,000" in token_action.label or "140000" in token_action.label


def test_enriched_tool_call_context():
    """When events have many tool calls, remediation should show tool usage."""
    events = [
        _make_event(0, EventType.tool_call, tool_name="Read"),
        _make_event(1, EventType.tool_call, tool_name="Read"),
        _make_event(2, EventType.tool_call, tool_name="Read"),
        _make_event(3, EventType.tool_call, tool_name="Read"),
        _make_event(4, EventType.tool_call, tool_name="Read"),
        _make_event(5, EventType.tool_call, tool_name="Bash"),
        _make_event(6, EventType.tool_call, tool_name="Bash"),
        _make_event(7, EventType.tool_call, tool_name="Bash"),
        _make_event(8, EventType.tool_call, tool_name="Bash"),
        _make_event(9, EventType.tool_call, tool_name="Bash"),
        _make_event(10, EventType.tool_call, tool_name="Bash"),
    ]

    card = _make_card(
        flags=[
            FrictionFlag(
                id="efficiency_high_tool_calls",
                severity="low",
                dimension="efficiency",
                event_index=None,
                suggestion="Too many tool calls",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, events)
    tool_action = next((a for a in actions if a.action_type == "reduce_tool_calls"), None)
    assert tool_action is not None
    assert "11" in tool_action.label or "11" in tool_action.label


def test_enriched_retry_context():
    """When tool retries are detected, remediation should show which tools retried."""
    events = [
        _make_event(0, EventType.tool_call, tool_name="Bash", status=Status.error),
        _make_event(1, EventType.tool_call, tool_name="Bash", status=Status.success),
        _make_event(2, EventType.tool_call, tool_name="Write", status=Status.error),
        _make_event(3, EventType.tool_call, tool_name="Write", status=Status.success),
    ]

    card = _make_card(
        flags=[
            FrictionFlag(
                id="tool_retries",
                severity="medium",
                dimension="tool_discipline",
                event_index=0,
                suggestion="Tool retries detected",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, events)
    retry_action = next((a for a in actions if a.action_type == "reduce_retries"), None)
    assert retry_action is not None
    # Should mention specific tools that retried
    assert "Bash" in retry_action.description or "Write" in retry_action.description


def test_fallback_to_legacy_when_no_events():
    """When no events are provided, should fall back to generic action templates."""
    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=None,
                suggestion="Review errors",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, [])
    error_action = next((a for a in actions if a.action_type == "fix_errors"), None)
    assert error_action is not None
    # Should still have an action, just using generic template
    assert error_action.label == "Fix command errors"


def test_error_patterns_included():
    """Error patterns (like exit_code, file_not_found) should appear in description."""
    events = [
        _make_event(
            0,
            event_type=EventType.tool_result,
            status=Status.error,
            tool_name="Bash",
            error_type="exit_code_1",
        ),
        _make_event(
            1,
            event_type=EventType.tool_result,
            status=Status.error,
            tool_name="Write",
            error_type="file_not_found",
        ),
    ]

    card = _make_card(
        flags=[
            FrictionFlag(
                id="reliability_errors",
                severity="medium",
                dimension="reliability",
                event_index=0,
                suggestion="Review errors",
            ),
        ],
        total_score=30,
    )

    actions = analyze_with_context(card, events)
    error_action = next((a for a in actions if a.action_type == "fix_errors"), None)
    assert error_action is not None
    # Should reference error patterns
    assert "exit_code" in error_action.description.lower() or "file_not_found" in error_action.description.lower()
