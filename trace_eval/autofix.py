"""Approval-based autofix: generate safe fixes for user review and approval.

This module generates actionable artifacts (reports, configs, CI files, patches)
that users can review before applying. It does NOT modify core scoring logic
or make autonomous changes to the codebase.

Safe to automate:
- Config/profile generation
- CI snippet generation
- Remediation report generation
- Converter command generation

NOT safe to automate:
- Judge formula changes
- Scoring weight modifications
- Core agent policy file changes
"""

from __future__ import annotations

from pathlib import Path

from trace_eval.scoring import Scorecard
from trace_eval.remediation import RemediationAction


def apply_safe_fixes(
    actions: list[RemediationAction],
    card: Scorecard,
    trace_path: Path,
) -> list[dict[str, str]]:
    """Apply safe fixes that don't require approval.

    Returns list of applied fixes with labels and paths.
    """
    fixes: list[dict[str, str]] = []

    for action in actions:
        if action.action_type == "switch_profile" and action.safe_to_automate:
            fix = _generate_profile_switch(trace_path, card)
            fixes.append(fix)
        elif action.action_type == "add_ci_gate" and action.safe_to_automate:
            fix = _generate_ci_gate(trace_path)
            fixes.append(fix)

    return fixes


def _generate_profile_switch(trace_path: Path, card: Scorecard) -> dict[str, str]:
    """Generate a run command with the correct profile."""
    profile = "coding_agent" if "retrieval" in card.unscorable_dimensions else "default"
    cmd = f"trace-eval run {trace_path.name} --profile {profile}"
    return {
        "label": f"Switch to {profile} profile",
        "path": "command",
        "content": cmd,
    }


def _generate_ci_gate(trace_path: Path) -> dict[str, str]:
    """Generate GitHub Actions CI workflow."""
    ci_content = """name: Agent Quality Gate

on: [push]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install trace-eval
      - run: trace-eval ci agent-trace.jsonl --min-score 70 --profile coding_agent
"""
    return {
        "label": "Add CI quality gate",
        "path": ".github/workflows/agent-quality.yml",
        "content": ci_content,
    }


def generate_remediation_report(
    actions: list[RemediationAction],
    card: Scorecard,
    trace_path: Path,
    output_path: Path | None = None,
) -> str:
    """Generate a full markdown remediation report.

    Args:
        actions: List of recommended actions from analyze().
        card: The scorecard to report on.
        trace_path: Path to the trace file.
        output_path: Where to save the report. Defaults to trace_path stem + _remediation.md.

    Returns:
        Path to the generated report.
    """
    if output_path is None:
        output_path = trace_path.parent / f"{trace_path.stem}_remediation.md"

    lines = [
        "# Trace Evaluation Remediation Report",
        "",
        f"**Trace:** `{trace_path.name}`",
        f"**Score:** {card.total_score:.1f}/100 [{card.rating}]",
        f"**Profile:** {card.profile}",
        "",
    ]

    # Dimension scores
    lines.append("## Dimension Scores")
    lines.append("")
    lines.append("| Dimension | Score | Status |")
    lines.append("|-----------|-------|--------|")
    for dim, score in sorted(card.dimension_scores.items()):
        if dim in card.unscorable_dimensions:
            lines.append(f"| {dim} | N/A | Not applicable |")
        else:
            status = "OK" if (score or 0) >= 70 else "Needs attention"
            lines.append(f"| {dim} | {score:.1f}/100 | {status} |")
    lines.append("")

    # Recommended actions
    lines.append("## Recommended Actions")
    lines.append("")
    for i, action in enumerate(actions, 1):
        approval_tag = "Auto-safe" if action.safe_to_automate and not action.requires_approval else "Requires approval"
        lines.append(f"### {i}. {action.label} ({approval_tag})")
        lines.append("")
        lines.append(f"**Description:** {action.description}")
        lines.append(f"**Confidence:** {action.confidence}")
        lines.append(f"**Triggered by:** {action.triggered_by}")
        lines.append("")

    # Suggested commands
    lines.append("## Suggested Commands")
    lines.append("")
    lines.append("```bash")
    lines.append("# Score with recommended profile")
    if "retrieval" in card.unscorable_dimensions:
        lines.append(f"trace-eval run {trace_path.name} --profile coding_agent")
    else:
        lines.append(f"trace-eval run {trace_path.name}")
    lines.append("")
    lines.append("# Quick summary")
    lines.append(f"trace-eval run {trace_path.name} --summary")
    lines.append("")
    lines.append("# CI gate")
    lines.append(f"trace-eval ci {trace_path.name} --min-score 70 --profile coding_agent")
    lines.append("```")
    lines.append("")

    # CI workflow
    lines.append("## CI Workflow")
    lines.append("")
    lines.append("Add `.github/workflows/agent-quality.yml`:")
    lines.append("```yaml")
    lines.append("name: Agent Quality Gate")
    lines.append("on: [push]")
    lines.append("jobs:")
    lines.append("  eval:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append("      - uses: actions/checkout@v4")
    lines.append("      - run: pip install trace-eval")
    lines.append("      - run: trace-eval ci agent-trace.jsonl --min-score 70 --profile coding_agent")
    lines.append("```")
    lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content)
    return str(output_path)
