"""Doctor command: diagnose installation, trace availability, and readiness.

This is the recommended first command for new users.
It answers: is it installed? which agents? where are traces? what next?
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from trace_eval import __version__
from trace_eval.convert import _detect_format
from trace_eval.locate import SEARCH_PATHS, locate


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _check_agent_directory(agent: str) -> dict:
    """Check if an agent's trace directory exists and count traces."""
    dirs = SEARCH_PATHS.get(agent, [])
    if not dirs:
        return {
            "agent": agent,
            "status": "unknown",
            "message": "No known search path for this agent",
            "trace_count": 0,
        }

    base_dir = dirs[0]
    path = Path(base_dir)

    if not path.exists():
        return {
            "agent": agent,
            "status": "not_found",
            "message": f"Directory not found: {base_dir}",
            "trace_count": 0,
            "path": base_dir,
        }

    # Count traces in last 48 hours
    try:
        traces = locate(agent_type=agent, limit=100, hours=48)
    except Exception:
        traces = []

    return {
        "agent": agent,
        "status": "found",
        "message": f"{len(traces)} trace(s) found in last 48h",
        "trace_count": len(traces),
        "path": base_dir,
        "recent_traces": [
            {
                "name": Path(t.path).name,
                "size": t.size_bytes,
                "age": t.modified_time,
                "project": t.project_name,
                "path": t.path,
            }
            for t in traces[:3]
        ],
    }


def _validate_sample_trace(result: dict) -> dict:
    """Try to locate and validate a sample trace for readability."""
    # Find the first agent with traces
    for agent_result in result.get("agents", []):
        if agent_result.get("trace_count", 0) > 0 and agent_result.get("recent_traces"):
            sample = agent_result["recent_traces"][0]
            sample_path = Path(sample["path"])

            if not sample_path.exists():
                return {
                    "status": "error",
                    "message": f"Sample trace not accessible: {sample_path}",
                }

            try:
                fmt = _detect_format(sample_path)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Could not detect format: {e}",
                    "path": str(sample_path),
                }

            if fmt == "unknown":
                return {
                    "status": "warning",
                    "message": "Format not recognized — may need a converter update",
                    "path": str(sample_path),
                }

            return {
                "status": "ok",
                "message": f"Readable, format: {fmt}",
                "path": str(sample_path),
                "format": fmt,
                "size": _human_size(sample.get("size", 0)),
            }

    return {
        "status": "none",
        "message": "No traces available to validate",
    }


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024}KB"
    else:
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.1f}MB"


def run_doctor() -> dict:
    """Run the full doctor diagnostic pipeline.

    Returns a result dict with all diagnostic data.
    """
    result: dict = {
        "version": __version__,
        "python": _python_version(),
        "agents": [],
        "sample_trace": {},
        "recommendation": "",
        "total_traces": 0,
    }

    # Check each supported agent
    for agent in ["claude-code", "openclaw", "cursor"]:
        agent_result = _check_agent_directory(agent)
        result["agents"].append(agent_result)
        result["total_traces"] += agent_result.get("trace_count", 0)

    # Validate a sample trace
    result["sample_trace"] = _validate_sample_trace(result)

    # Build recommendation
    result["recommendation"] = _build_recommendation(result)

    return result


def _build_recommendation(result: dict) -> str:
    """Build a recommendation string based on doctor findings."""
    if result["total_traces"] > 0:
        return "trace-eval loop"

    # No traces found — check why
    agents_with_dir = [a for a in result["agents"] if a["status"] == "found"]
    agents_without_dir = [a for a in result["agents"] if a["status"] == "not_found"]

    if agents_with_dir:
        return "Agent directories found but no recent traces. Try: trace-eval loop --hours 168 (search wider window)"

    if agents_without_dir:
        missing = ", ".join(a["agent"] for a in agents_without_dir)
        return (
            f"No agent directories found ({missing}). "
            "Install an agent and run a task, or use: trace-eval convert <trace_file>"
        )

    return "No supported agents detected. Install Claude Code, OpenClaw, or Cursor."


def format_doctor_text(result: dict) -> str:
    """Format doctor results as human-readable text."""
    lines = [
        "=" * 60,
        f"  TRACE-EVAL DOCTOR  v{result['version']}",
        "=" * 60,
        "",
    ]

    # Installation status
    lines.append("INSTALLATION:")
    lines.append(f"  Version:  {result['version']}")
    lines.append(f"  Python:   {result['python']}")
    lines.append("  Status:   OK")
    lines.append("")

    # Agent detection
    lines.append("AGENT DETECTION:")
    for agent in result["agents"]:
        status_icon = _agent_status_icon(agent["status"])
        name = agent["agent"].ljust(14)
        lines.append(f"  {status_icon} {name} — {agent['message']}")

        # Show recent traces if available
        if agent.get("recent_traces"):
            for trace in agent["recent_traces"]:
                lines.append(f"       {trace['age']:>10s}  {_human_size(trace['size']):>8s}  {trace['project']}")
    lines.append("")

    # Sample trace validation
    sample = result["sample_trace"]
    lines.append("SAMPLE TRACE:")
    sample_icon = "✓" if sample["status"] == "ok" else "?" if sample["status"] == "warning" else "X"
    lines.append(f"  {sample_icon} {sample['message']}")
    if sample.get("path"):
        lines.append(f"    Path: {sample['path']}")
    if sample.get("size"):
        lines.append(f"    Size: {sample['size']}")
    lines.append("")

    # Recommendation
    lines.append("RECOMMENDED:")
    lines.append(f"  $ {result['recommendation']}")
    lines.append("")

    # Contextual help based on situation
    if result["total_traces"] == 0:
        lines.append("TROUBLESHOOTING:")
        has_any_dir = any(a["status"] in ("found", "not_found") for a in result["agents"])
        if has_any_dir:
            lines.append("  • Agent directories exist but no recent traces found")
            lines.append("  • Try a wider search: trace-eval loop --hours 168")
            lines.append("  • Or convert a specific file: trace-eval convert <path>")
        else:
            lines.append("  • No supported agent directories detected")
            lines.append("  • Install Claude Code, OpenClaw, or Cursor")
            lines.append("  • Or convert a trace file: trace-eval convert <path>")
        lines.append("")

    return "\n".join(lines)


def _agent_status_icon(status: str) -> str:
    if status == "found":
        return "[+]"
    elif status == "not_found":
        return "[-]"
    elif status == "unknown":
        return "[?]"
    return "[ ]"


def format_doctor_json(result: dict) -> str:
    """Format doctor results as JSON for agent consumption."""
    output = {
        "version": result["version"],
        "python": result["python"],
        "installation": "ok",
        "agents": [
            {
                "name": a["agent"],
                "status": a["status"],
                "message": a["message"],
                "trace_count": a.get("trace_count", 0),
            }
            for a in result["agents"]
        ],
        "total_traces": result["total_traces"],
        "sample_trace": {
            "status": result["sample_trace"].get("status"),
            "message": result["sample_trace"].get("message"),
            "path": result["sample_trace"].get("path"),
            "format": result["sample_trace"].get("format"),
        },
        "recommendation": result["recommendation"],
    }
    return json.dumps(output, indent=2)
