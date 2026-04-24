"""Main loop orchestration: locate -> convert -> score -> remediate -> optional steps.

The loop command chains the full trace-eval pipeline with optional
apply-safe, compare, and report steps.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC
from pathlib import Path

from trace_eval import __version__
from trace_eval.autofix import apply_safe_fixes, generate_remediation_report
from trace_eval.convert import _detect_format, convert
from trace_eval.judges.context import judge_context
from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.loader import load_trace_with_report
from trace_eval.locate import locate
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
        "task_label": None,
        "task_id": None,
        "session_duration": None,
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
        result["error"] = _no_traces_error(agent_type, hours)
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
    except Exception:
        result["error"] = "Score computation failed."
        return result

    # Step 4: Remediate
    try:
        from trace_eval.remediation import analyze_with_context

        actions = analyze_with_context(card, trace.events)
        result["actions"] = actions
    except Exception as e:
        result["error"] = f"Remediation analysis failed: {e}"
        return result

    # Step 4b: Extract context for plain-English output
    result["token_info"] = _extract_token_summary(trace.events)
    result["tool_info"] = _extract_tool_summary(trace.events)
    result["retry_info"] = _extract_retry_summary(trace.events)
    result["error_summary"] = _extract_error_summary(trace.events, card.all_flags)
    result["task_label"] = _extract_task_label(trace.events)
    result["task_id"] = _extract_task_id(trace.events)
    result["session_duration"] = _extract_session_duration(trace.events)

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
            result.setdefault("_warnings", []).append(f"Compare file not found: {compare_path}")
        except Exception as e:
            result.setdefault("_warnings", []).append(f"Compare failed: {e}")

    # Step 7: Report (if flagged)
    if report:
        try:
            if output_dir:
                report_out = Path(output_dir) / f"{Path(trace_path).stem}_report.md"
            else:
                report_out = None
            report_path = generate_remediation_report(actions, card, Path(canonical_path), output_path=report_out)
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

    # Score icon
    score_icon = (
        "✓" if card.total_score >= 80 else "~" if card.total_score >= 60 else "!" if card.total_score >= 40 else "✗"
    )

    parts = [
        "=" * 60,
        f"  TRACE-EVAL  v{__version__}  |  Score: {score_icon} {card.total_score:.0f}/100 [{card.rating}]",
        "=" * 60,
        "",
    ]

    # Task context
    task_label = result.get("task_label")
    task_agent = result.get("trace_agent", "")
    session_duration = result.get("session_duration")
    context_parts = []
    if task_agent:
        names = {"claude-code": "Claude Code", "openclaw": "OpenClaw", "cursor": "Cursor"}
        context_parts.append(names.get(task_agent, task_agent.title()))
    if task_label:
        context_parts.append(task_label)
    if session_duration:
        context_parts.append(session_duration)
    if context_parts:
        parts.append(f"  {result['trace_name']} ({result['trace_size']})")
        parts.append(f"  {' | '.join(context_parts)}")
    else:
        parts.append(f"  {result['trace_name']} ({result['trace_size']}, {task_agent}, {result['trace_age']})")

    # Top 3 issues from all_flags sorted by severity
    flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
    top_flags = flags[:3]
    if top_flags:
        parts.append("")
        parts.append("  Issues found:")
        for f in top_flags:
            icon = "✗" if f.severity in ("critical", "high") else "~" if f.severity == "medium" else "."
            summary = f.suggestion[:70] + "..." if len(f.suggestion) > 70 else f.suggestion
            parts.append(f"  {icon} {summary}")
    else:
        parts.append("")
        parts.append("  ✓ No issues detected.")

    # Next actions
    if actions:
        parts.append("")
        parts.append("  Recommended actions:")
        for i, a in enumerate(actions[:3], 1):
            tag = "[auto-fix]" if (a.safe_to_automate and not a.requires_approval) else "[needs your OK]"
            parts.append(f"  {i}. {tag} {a.label}")
    else:
        parts.append("")
        parts.append("  ✓ No recommended actions. Score looks good.")

    # Optional sections
    if result.get("safe_fixes_applied"):
        labels = ", ".join(fx.get("label", "?") for fx in result["safe_fixes_applied"])
        parts.append("")
        parts.append(f"  Safe fixes applied: [{labels}]")

    if result.get("compare"):
        c = result["compare"]
        delta_str = f"+{c['delta']}" if c["delta"] >= 0 else str(c["delta"])
        parts.append("")
        parts.append(f"  Delta vs {c['before_name']}: {delta_str} ({c['before_score']:.0f} → {c['after_score']:.0f})")

    if result.get("report_path"):
        parts.append(f"  Report: {result['report_path']}")

    if result.get("_warnings"):
        for w in result["_warnings"]:
            parts.append(f"  WARN: {w}")

    return "\n".join(parts)


def format_loop_json(result: dict) -> str:
    """JSON formatter for agents."""
    if result.get("error"):
        output = {
            "error": result["error"],
        }
        return json.dumps(output, indent=2)

    card = result["scorecard"]
    flags = sorted(card.all_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))[:3]

    top_issues = [{"id": f.id, "severity": f.severity, "suggestion": f.suggestion} for f in flags]

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


def _no_traces_error(agent_type: str, hours: int) -> str:
    """Build a helpful error message when no traces are found."""
    import os

    from trace_eval.locate import SEARCH_PATHS

    agents_to_search = ["claude-code", "cursor", "openclaw"] if agent_type == "all" else [agent_type]

    # Check which agent directories exist
    missing_agents = []
    found_agents = []
    for agent in agents_to_search:
        dirs = SEARCH_PATHS.get(agent, [])
        if dirs and os.path.isdir(dirs[0]):
            found_agents.append(agent)
        else:
            missing_agents.append(agent)

    names = {"claude-code": "Claude Code", "openclaw": "OpenClaw", "cursor": "Cursor"}
    parts = ["No recent agent sessions found."]
    parts.append("")

    if missing_agents:
        agent_display = ", ".join(names.get(a, a) for a in missing_agents)
        parts.append(f"Agent not installed: {agent_display}")
        parts.append("  Install one, then run a task with it.")

    if found_agents:
        agent_display = ", ".join(names.get(a, a) for a in found_agents)
        parts.append(f"Agent found: {agent_display}")
        parts.append(f"  But no sessions in the last {hours}h.")
        parts.append("  → Try: run a task with your AI agent, then try again.")

    parts.append("")
    parts.append("Try:")
    parts.append("  • Widen search: trace-eval --hours 168")
    parts.append("  • Check setup:   trace-eval doctor")
    parts.append("  • Convert a specific file: trace-eval convert <path>")
    parts.append("  • Diagnose setup: trace-eval doctor")

    return "\n".join(parts)


def _extract_token_summary(events):
    """Extract token usage for plain-English output."""
    total_tokens = sum((e.tokens_in or 0) + (e.tokens_out or 0) for e in events)
    llm_calls = sum(1 for e in events if e.event_type is not None and e.event_type.value == "llm_call")
    return {"total_tokens": total_tokens, "llm_calls": llm_calls}


def _extract_tool_summary(events):
    """Extract tool call counts for plain-English output."""
    total = sum(1 for e in events if e.event_type is not None and e.event_type.value == "tool_call")
    return {"total": total}


def _extract_retry_summary(events):
    """Extract tool retry counts for plain-English output."""
    tool_calls = [e for e in events if e.event_type is not None and e.event_type.value == "tool_call"]
    retries = 0
    for i in range(1, len(tool_calls)):
        prev = tool_calls[i - 1]
        curr = tool_calls[i]
        if (
            curr.tool_name == prev.tool_name
            and prev.status is not None
            and prev.status.value == "error"
            and curr.status is not None
            and curr.status.value == "success"
        ):
            retries += 1
    return {"total": retries}


def _extract_error_summary(events, flags):
    """Extract error counts by tool for plain-English output."""
    error_tools: dict[str, int] = {}
    for e in events:
        if e.status is not None and e.status.value == "error":
            tool = e.tool_name or "unknown"
            error_tools[tool] = error_tools.get(tool, 0) + 1
    return error_tools


def _extract_task_label(events) -> str | None:
    """Extract the human-readable task label from trace events."""
    for e in events:
        if e.task_label:
            return e.task_label
    return None


def _extract_task_id(events) -> str | None:
    """Extract the task ID from trace events."""
    for e in events:
        if e.task_id:
            return e.task_id
    return None


def _extract_session_duration(events) -> str | None:
    """Compute session duration from first to last event timestamp."""
    timestamps = []
    for e in events:
        if e.timestamp:
            try:
                from datetime import datetime

                ts = e.timestamp
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                timestamps.append(dt)
            except (ValueError, TypeError):
                continue
    if len(timestamps) < 2:
        return None
    duration = max(timestamps) - min(timestamps)
    total_seconds = int(duration.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m {total_seconds % 60}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
