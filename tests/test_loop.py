import pytest
from pathlib import Path
from trace_eval.loop import run_loop, format_loop_text, format_loop_json
from trace_eval.scoring import Scorecard
from trace_eval.remediation import RemediationAction


def _make_scorecard(total_score=50, unscorable=None, profile="default"):
    """Create a minimal Scorecard for testing."""
    return Scorecard(
        total_score=total_score,
        dimension_scores={
            "reliability": 50.0, "efficiency": 50.0, "retrieval": 50.0,
            "tool_discipline": 50.0, "context": 50.0,
        },
        dimension_confidence={
            "reliability": "high", "efficiency": "high", "retrieval": "high",
            "tool_discipline": "high", "context": "high",
        },
        all_flags=[],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=unscorable or [],
        missing_required_judges=[],
        profile=profile,
        rating="Needs Work",
    )


class TestFormatLoopText:
    """Tests for format_loop_text()."""

    def test_error_output(self):
        """Error results should show LOOP ERROR with optional hint."""
        result = {"error": "No recent traces found.", "hint": "Try: trace-eval loop --hours 72"}
        text = format_loop_text(result)
        assert "LOOP ERROR: No recent traces found." in text
        assert "Try: trace-eval loop --hours 72" in text

    def test_error_without_hint(self):
        result = {"error": "Score computation failed."}
        text = format_loop_text(result)
        assert "LOOP ERROR: Score computation failed." in text
        assert "hint" not in text


class TestFormatLoopJson:
    """Tests for format_loop_json()."""

    def test_json_structure(self):
        """JSON output should have all required top-level keys."""
        import json
        from trace_eval.schema import FrictionFlag

        card = _make_scorecard(total_score=30, unscorable=["retrieval"])
        card.all_flags = [
            FrictionFlag(id="reliability_errors", severity="medium",
                         dimension="reliability", event_index=None, suggestion="Review errors"),
        ]
        actions = [
            RemediationAction(
                action_type="fix_errors", label="Fix command errors",
                description="Fix errors.", confidence="high",
                safe_to_automate=False, requires_approval=True,
                triggered_by="test",
            ),
        ]
        result = {
            "trace": "/tmp/test.jsonl",
            "trace_name": "test.jsonl",
            "trace_size": "5MB",
            "trace_age": "4m ago",
            "trace_agent": "claude-code",
            "scorecard": card,
            "actions": actions,
            "adapter_report": {},
            "safe_fixes_applied": [{"label": "Switch profile"}],
            "compare": {"before_score": 25.0, "after_score": 30.0, "delta": 5.0, "before_name": "before.jsonl"},
            "report_path": "/tmp/test_report.md",
            "error": None,
        }
        text = format_loop_json(result)
        data = json.loads(text)

        assert "trace" in data
        assert "score" in data
        assert "rating" in data
        assert "top_issues" in data
        assert "top_actions" in data
        assert "safe_fixes_applied" in data
        assert "delta" in data
        assert "report_path" in data
        assert data["rating"] == "Needs Work"
        assert len(data["top_issues"]) == 1
        assert len(data["top_actions"]) == 1
        assert data["top_actions"][0]["safe_to_automate"] is False
        assert data["top_actions"][0]["requires_approval"] is True


class TestFormatLoopTextSuccess:
    """Tests for format_loop_text() on success cases."""

    def test_shows_score_and_rating(self):
        from trace_eval.schema import FrictionFlag
        card = _make_scorecard(total_score=30)
        card.all_flags = [
            FrictionFlag(id="reliability_errors", severity="medium",
                         dimension="reliability", event_index=None, suggestion="Review errors"),
        ]
        result = {
            "trace": "/tmp/test.jsonl",
            "trace_name": "test.jsonl",
            "trace_size": "5MB",
            "trace_age": "4m ago",
            "trace_agent": "claude-code",
            "scorecard": card,
            "actions": [],
            "adapter_report": {},
            "safe_fixes_applied": [],
            "compare": None,
            "report_path": None,
            "error": None,
        }
        text = format_loop_text(result)
        assert "30" in text
        assert "[Needs Work]" in text

    def test_shows_issues_with_severity_prefix(self):
        from trace_eval.schema import FrictionFlag
        card = _make_scorecard(total_score=30)
        card.all_flags = [
            FrictionFlag(id="reliability_errors", severity="medium",
                         dimension="reliability", event_index=None, suggestion="Review errors"),
        ]
        result = {
            "trace": "/tmp/test.jsonl", "trace_name": "test.jsonl",
            "trace_size": "5MB", "trace_age": "4m ago", "trace_agent": "claude-code",
            "scorecard": card, "actions": [], "adapter_report": {},
            "safe_fixes_applied": [], "compare": None, "report_path": None, "error": None,
        }
        text = format_loop_text(result)
        assert "TOP 3 ISSUES:" in text
        assert "reliability_errors" in text

    def test_shows_safe_fixes_applied(self):
        card = _make_scorecard(total_score=30)
        result = {
            "trace": "/tmp/test.jsonl", "trace_name": "test.jsonl",
            "trace_size": "5MB", "trace_age": "4m ago", "trace_agent": "claude-code",
            "scorecard": card, "actions": [], "adapter_report": {},
            "safe_fixes_applied": [{"label": "Switch profile"}],
            "compare": None, "report_path": None, "error": None,
        }
        text = format_loop_text(result)
        assert "Safe fixes applied:" in text
        assert "Switch profile" in text

    def test_shows_delta_when_compare_provided(self):
        card = _make_scorecard(total_score=50)
        result = {
            "trace": "/tmp/test.jsonl", "trace_name": "test.jsonl",
            "trace_size": "5MB", "trace_age": "4m ago", "trace_agent": "claude-code",
            "scorecard": card, "actions": [], "adapter_report": {},
            "safe_fixes_applied": [],
            "compare": {"before_score": 25.0, "after_score": 50.0, "delta": 25.0, "before_name": "before.jsonl"},
            "report_path": None, "error": None,
        }
        text = format_loop_text(result)
        assert "Delta vs before.jsonl:" in text
        assert "+25.0" in text

    def test_shows_report_path(self):
        card = _make_scorecard(total_score=30)
        result = {
            "trace": "/tmp/test.jsonl", "trace_name": "test.jsonl",
            "trace_size": "5MB", "trace_age": "4m ago", "trace_agent": "claude-code",
            "scorecard": card, "actions": [], "adapter_report": {},
            "safe_fixes_applied": [], "compare": None,
            "report_path": "/tmp/test_report.md", "error": None,
        }
        text = format_loop_text(result)
        assert "Report:" in text
        assert "test_report.md" in text

    def test_no_issues_when_no_flags(self):
        card = _make_scorecard(total_score=95)
        result = {
            "trace": "/tmp/test.jsonl", "trace_name": "test.jsonl",
            "trace_size": "1MB", "trace_age": "1h ago", "trace_agent": "claude-code",
            "scorecard": card, "actions": [], "adapter_report": {},
            "safe_fixes_applied": [], "compare": None, "report_path": None, "error": None,
        }
        text = format_loop_text(result)
        assert "No issues detected." in text
