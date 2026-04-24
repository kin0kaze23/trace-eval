from pathlib import Path

from trace_eval.autofix import apply_safe_fixes, generate_remediation_report
from trace_eval.remediation import RemediationAction
from trace_eval.scoring import Scorecard


def _make_card(unscorable=None, profile="default", total_score=50):
    return Scorecard(
        total_score=total_score,
        dimension_scores={
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
        all_flags=[],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=unscorable or [],
        missing_required_judges=[],
        profile=profile,
        rating="Needs Work",
    )


def _make_action(action_type, safe_to_automate=True, requires_approval=False):
    return RemediationAction(
        action_type=action_type,
        label=f"{action_type} label",
        description=f"{action_type} description",
        confidence="high",
        safe_to_automate=safe_to_automate,
        requires_approval=requires_approval,
        triggered_by="test_trigger",
    )


class TestApplySafeFixes:
    def test_applies_profile_switch_fix(self, tmp_path):
        trace_file = tmp_path / "test.jsonl"
        trace_file.write_text("")
        card = _make_card(unscorable=["retrieval"], profile="default")
        actions = [_make_action("switch_profile", safe_to_automate=True)]
        fixes = apply_safe_fixes(actions, card, trace_file)
        assert len(fixes) == 1
        assert fixes[0]["label"] == "Switch to coding_agent profile"
        assert "coding_agent" in fixes[0]["content"]

    def test_applies_ci_gate_fix(self, tmp_path):
        trace_file = tmp_path / "test.jsonl"
        trace_file.write_text("")
        card = _make_card()
        actions = [_make_action("add_ci_gate", safe_to_automate=True)]
        fixes = apply_safe_fixes(actions, card, trace_file)
        assert len(fixes) == 1
        assert fixes[0]["label"] == "Add CI quality gate"
        assert fixes[0]["path"] == ".github/workflows/agent-quality.yml"
        assert "Agent Quality Gate" in fixes[0]["content"]

    def test_skips_unsafe_actions(self, tmp_path):
        trace_file = tmp_path / "test.jsonl"
        trace_file.write_text("")
        card = _make_card()
        actions = [
            _make_action("fix_errors", safe_to_automate=False, requires_approval=True),
            _make_action("switch_profile", safe_to_automate=True),
        ]
        fixes = apply_safe_fixes(actions, card, trace_file)
        assert len(fixes) == 1
        assert fixes[0]["label"] == "Switch to default profile"
        assert "default" in fixes[0]["content"]

    def test_skips_non_matching_actions(self, tmp_path):
        trace_file = tmp_path / "test.jsonl"
        trace_file.write_text("")
        card = _make_card()
        actions = [
            _make_action("reduce_retries", safe_to_automate=True),
        ]
        fixes = apply_safe_fixes(actions, card, trace_file)
        assert len(fixes) == 0

    def test_uses_default_profile_when_retrieval_scorable(self, tmp_path):
        trace_file = tmp_path / "test.jsonl"
        trace_file.write_text("")
        card = _make_card(unscorable=[])
        actions = [_make_action("switch_profile", safe_to_automate=True)]
        fixes = apply_safe_fixes(actions, card, trace_file)
        assert len(fixes) == 1
        assert fixes[0]["label"] == "Switch to default profile"
        assert "--profile default" in fixes[0]["content"]


class TestGenerateRemediationReport:
    def test_generates_file(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(unscorable=["retrieval"], total_score=30)
        actions = [
            _make_action("switch_profile", safe_to_automate=True),
            _make_action("add_ci_gate", safe_to_automate=True),
        ]
        report_path = generate_remediation_report(actions, card, trace_file)
        assert Path(report_path).exists()

    def test_report_contains_score_and_rating(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=30, unscorable=["retrieval"])
        actions = [_make_action("switch_profile", safe_to_automate=True)]
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "30.0" in content
        assert "[Needs Work]" in content

    def test_report_contains_dimension_table(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50)
        actions = []
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "Dimension" in content
        assert "reliability" in content

    def test_report_contains_actions(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50)
        actions = [
            RemediationAction(
                action_type="fix_errors",
                label="Fix command errors",
                description="Review and fix failed commands.",
                confidence="high",
                safe_to_automate=False,
                requires_approval=True,
                triggered_by="reliability_errors",
            ),
        ]
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "Fix command errors" in content
        assert "Requires approval" in content

    def test_report_contains_suggested_commands(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50, unscorable=["retrieval"])
        actions = []
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "trace-eval run" in content
        assert "trace-eval ci" in content
        assert "--profile coding_agent" in content

    def test_report_contains_ci_workflow(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50)
        actions = []
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "name: Agent Quality Gate" in content
        assert "actions/checkout@v4" in content

    def test_uses_custom_output_path(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50)
        output = tmp_path / "custom_report.md"
        actions = []
        report_path = generate_remediation_report(actions, card, trace_file, output_path=output)
        assert Path(report_path) == output
        assert output.exists()

    def test_auto_safe_actions_labeled(self, tmp_path):
        trace_file = tmp_path / "agent-trace.jsonl"
        trace_file.write_text("")
        card = _make_card(total_score=50)
        actions = [
            _make_action("switch_profile", safe_to_automate=True, requires_approval=False),
        ]
        report_path = generate_remediation_report(actions, card, trace_file)
        content = Path(report_path).read_text()
        assert "Auto-safe" in content
