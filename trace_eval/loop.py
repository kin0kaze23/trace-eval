"""Main loop orchestration: locate -> convert -> score -> remediate -> optional steps.

The loop command chains the full trace-eval pipeline with optional
apply-safe, compare, and report steps.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trace_eval.autofix import apply_safe_fixes, generate_remediation_report
from trace_eval.convert import _detect_format, convert
from trace_eval.judges.context import judge_context
from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.locate import locate
from trace_eval.loader import load_trace_with_report
from trace_eval.remediation import analyze
from trace_eval.scoring import compute_scorecard

JUDGES = {
    "reliability": judge_reliability,
    "efficiency": judge_efficiency,
    "retrieval": judge_retrieval,
    "tool_discipline": judge_tool_discipline,
    "context": judge_context,
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def run_loop(
    agent_type: str = "all",
    hours: int = 48,
    profile: str | None = None,
    compare_path: str | None = None,
    apply_safe: bool = False,
    report: bool = False,
    output_dir: str | None = None,
) -> dict:
    """Run the full loop pipeline: locate -> convert -> score -> remediate -> optional.

    Returns a result dict with all data needed for formatting. Never raises;
    returns an error key on failure at any step.
    """
    result: dict = {
        "trace": "",
        "trace_name": "",
        "trace_size": "",
        "trace_age": "",
        "trace_agent": "",
        "scorecard": None,
        "actions": [],
        "adapter_report": {},
        "safe_fixes_applied": [],
        "compare": None,
        "report_path": None,
        "error": None,
    }

    # Step 1: Locate
    try:
        locations = locate(agent_type=agent_type, limit=1, hours=hours)
    except Exception as e:
        result["error"] = f"Locate failed: {e}"
        return result

    if not locations:
        result["error"] = "No recent traces found."
        result["hint"] = "Try: trace-eval loop --hours 72"
        return result

    loc = locations[0]
    trace_path = loc.path
    result["trace"] = trace_path
    result["trace_name"] = Path(trace_path).name
    result["trace_size"] = _human_size(loc.size_bytes)
    result["trace_age"] = loc.modified_time
    result["trace_agent"] = loc.agent_type

    # Step 2: Convert if needed
    canonical_path = trace_path
    try:
        fmt = _detect_format(Path(trace_path))
        if fmt != "canonical":
            events = convert(Path(trace_path), fmt=fmt)
            if output_dir:
                out = Path(output_dir) / f"{Path(trace_path).stem}_canonical.jsonl"
                out.parent.mkdir(parents=True, exist_ok=True)
                with open(out, "w") as f:
                    for ev in events:
                        f.write(json.dumps(ev) + "\n")
                canonical_path = str(out)
            else:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix="_canonical.jsonl",
                    delete=False,
                )
                for ev in events:
                    tmp.write(json.dumps(ev) + "\n")
                tmp.close()
                canonical_path = tmp.name
    except ValueError as e:
        result["error"] = f"Could not convert trace: {e}"
        return result
    except Exception as e:
        result["error"] = f"Conversion failed: {e}"
        return result

    # Step 3: Score
    try:
        trace, adapter_report = load_trace_with_report(Path(canonical_path))
        result["adapter_report"] = adapter_report
    except Exception as e:
        result["error"] = f"Could not load trace: {e}"
        return result

    try:
        judge_results = {name: judge_fn(trace.events) for name, judge_fn in JUDGES.items()}
        card = compute_scorecard(judge_results, profile=profile)
        result["scorecard"] = card
    except Exception as e:
        result["error"] = "Score computation failed."
        return result

    # Step 4: Remediate
    try:
        actions = analyze(card)
        result["actions"] = actions
    except Exception as e:
        result["error"] = f"Remediation analysis failed: {e}"
        return result

    # Step 5: Apply-safe (if flagged)
    if apply_safe:
        try:
            fixes = apply_safe_fixes(actions, card, Path(canonical_path))
            result["safe_fixes_applied"] = fixes
        except Exception as e:
            result.setdefault("_warnings", []).append(f"apply_safe failed: {e}")

    # Step 6: Compare (if compare_path provided)
    if compare_path:
        try:
            before_path = Path(compare_path)
            before_trace, _ = load_trace_with_report(before_path)
            before_judges = {name: judge_fn(before_trace.events) for name, judge_fn in JUDGES.items()}
            before_card = compute_scorecard(before_judges, profile=profile)
            delta = round(card.total_score - before_card.total_score, 1)
            result["compare"] = {
                "before_score": before_card.total_score,
                "after_score": card.total_score,
                "delta": delta,
                "before_name": before_path.name,
            }
        except FileNotFoundError:
            result.setdefault("_warnings", []).append(
                f"Compare file not found: {compare_path}"
            )
        except Exception as e:
            result.setdefault("_warnings", []).append(f"Compare failed: {e}")

    # Step 7: Report (if flagged)
    if report:
        try:
            if output_dir:
                report_out = Path(output_dir) / f"{Path(trace_path).stem}_report.md"
            else:
                report_out = None
            report_path = generate_remediation_report(
                actions, card, Path(canonical_path), output_path=report_out
            )
            result["report_path"] = report_path
        except Exception as e:
            result.setdefault("_warnings", []).append(f"Report generation failed: {e}")

    return result


def format_loop_text(result: dict) -> str:
    """Human-readable text formatter for loop results (under 15 lines)."""
    if result.get("error"):
        lines = [f"LOOP ERROR: {result['error']}"]
        if "hint" in result:
            lines.append(result["hint"])
        return "\n".join(lines)

    card = result["scorecard"]
    actions = result["actions"]
    parts = [
        "=" * 60,
        "  TRACE-EVAL LOOP  v0.5.0",
        "=" * 60,
        "",
        f"  Trace: {result['trace_name']} ({result['trace_size']}, {result['trace_agent']}, {result['trace_age']})",
        f"  Score: {card.total_score:.1f}/100  [{card.rating}]",
    ]

    # Top 3 issues from all_flags sorted by severity
    flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
    top_flags = flags[:3]
    if top_flags:
        parts.append("  TOP 3 ISSUES:")
        for f in top_flags:
            prefix = "[!]" if f.severity in ("critical", "high") else "[-]" if f.severity == "medium" else "[~]"
            summary = f.suggestion[:60] + "..." if len(f.suggestion) > 60 else f.suggestion
            parts.append(f"  {prefix} {f.id} ({f.severity}) \u2014 {summary}")
    else:
        parts.append("  No issues detected.")

    # Next actions
    if actions:
        parts.append("  NEXT ACTIONS:")
        for i, a in enumerate(actions[:3], 1):
            tag = "[AUTO-SAFE]" if (a.safe_to_automate and not a.requires_approval) else "[REQUIRES APPROVAL]"
            parts.append(f"  {i}. {tag} {a.label}")
    else:
        parts.append("  No recommended actions. Score looks good.")

    # Optional sections
    if result.get("safe_fixes_applied"):
        labels = ", ".join(fx.get("label", "?") for fx in result["safe_fixes_applied"])
        parts.append("")
        parts.append(f"  Safe fixes applied: [{labels}]")

    if result.get("compare"):
        c = result["compare"]
        delta_str = f"+{c['delta']}" if c["delta"] >= 0 else str(c["delta"])
        parts.append(f"  Delta vs {c['before_name']}: {delta_str} ({c['before_score']:.0f} -> {c['after_score']:.0f})")

    if result.get("report_path"):
        parts.append(f"  Report: {result['report_path']}")

    if result.get("_warnings"):
        for w in result["_warnings"]:
            parts.append(f"  WARN: {w}")

    return "\n".join(parts)


def format_loop_json(result: dict) -> str:
    """JSON formatter for agents."""
    card = result["scorecard"]
    flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))[:3]

    top_issues = [
        {"id": f.id, "severity": f.severity, "suggestion": f.suggestion}
        for f in flags
    ]

    actions = result["actions"][:3]
    top_actions = [
        {
            "label": a.label,
            "safe_to_automate": a.safe_to_automate,
            "requires_approval": a.requires_approval,
        }
        for a in actions
    ]

    output = {
        "trace": result["trace_name"],
        "score": card.total_score,
        "rating": card.rating,
        "top_issues": top_issues,
        "top_actions": top_actions,
        "safe_fixes_applied": [fx.get("label", "?") for fx in result.get("safe_fixes_applied", [])],
        "delta": result.get("compare"),
        "report_path": result.get("report_path"),
    }
    return json.dumps(output, indent=2)


def _human_size(size_bytes: int) -> str:
    """Return human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024}KB"
    else:
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.0f}MB" if mb >= 10 else f"{mb:.1f}MB"
