"""Locate common agent trace files on the filesystem."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

AgentType = Literal["claude-code", "cursor", "openclaw", "all"]


@dataclass
class TraceLocation:
    path: str
    agent_type: str
    size_bytes: int
    modified_time: str
    project_name: str


SEARCH_PATHS: dict[str, list[str]] = {
    "claude-code": [
        os.path.expanduser("~/.claude/projects"),
    ],
    "cursor": [
        os.path.expanduser("~/.cursor/projects"),
    ],
    "openclaw": [
        os.path.expanduser("~/.openclaw"),
    ],
}


def _find_files(base_dir: str, pattern: str = "*.jsonl", max_depth: int = 5) -> list[Path]:
    """Find files matching pattern within max_depth levels."""
    base = Path(base_dir)
    if not base.exists():
        return []
    results = []
    for depth in range(max_depth + 1):
        for p in base.glob(f"{'*/' * depth}{pattern}"):
            if p.is_file():
                results.append(p)
    return results


def _is_valid_trace(path: Path, agent_type: str) -> bool:
    """Quick validation: read first line and check for recognizable type signatures."""
    try:
        with open(path) as f:
            first_line = f.readline(4096)
        if not first_line:
            return False
        data = json.loads(first_line)
        if agent_type == "claude-code":
            return "type" in data and data["type"] in (
                "permission-mode", "user", "assistant", "tool_result",
                "file-history-snapshot",
            )
        elif agent_type == "cursor":
            return "role" in data and data["role"] in (
                "user", "assistant", "toolResult",
            )
        elif agent_type == "openclaw":
            return "type" in data and data["type"] in (
                "session", "message", "model_change",
            )
        return True
    except (json.JSONDecodeError, OSError):
        return False


def _time_ago(timestamp: float) -> str:
    """Human-readable time ago string."""
    diff = time.time() - timestamp
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff // 60)}m ago"
    elif diff < 86400:
        return f"{int(diff // 3600)}h ago"
    else:
        return f"{int(diff // 86400)}d ago"


def locate(
    agent_type: AgentType = "all",
    limit: int = 20,
    hours: int = 48,
) -> list[TraceLocation]:
    """Locate agent trace files on the filesystem."""
    results: list[TraceLocation] = []
    cutoff = time.time() - (hours * 3600)

    agents_to_search = (
        ["claude-code", "cursor", "openclaw"]
        if agent_type == "all"
        else [agent_type]
    )

    for agent in agents_to_search:
        base_dirs = SEARCH_PATHS.get(agent, [])
        for base_dir in base_dirs:
            if not os.path.isdir(base_dir):
                continue

            for path in _find_files(base_dir, "*.jsonl", max_depth=5):
                try:
                    stat = path.stat()
                except OSError:
                    continue

                if stat.st_mtime < cutoff:
                    continue

                if not _is_valid_trace(path, agent):
                    continue

                rel = path.relative_to(base_dir)
                project_name = rel.parts[0] if rel.parts else str(path.parent.name)

                results.append(TraceLocation(
                    path=str(path),
                    agent_type=agent,
                    size_bytes=stat.st_size,
                    modified_time=_time_ago(stat.st_mtime),
                    project_name=project_name,
                ))

    results_with_mtime = []
    for r in results:
        try:
            mtime = Path(r.path).stat().st_mtime
        except OSError:
            mtime = 0
        results_with_mtime.append((mtime, r))

    results_with_mtime.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in results_with_mtime[:limit]]


def format_locate(locations: list[TraceLocation]) -> str:
    """Format locate results for display."""
    if not locations:
        return "No recent trace files found."

    lines = [f"Found {len(locations)} recent trace file(s):\n"]

    by_agent: dict[str, list[TraceLocation]] = {}
    for loc in locations:
        by_agent.setdefault(loc.agent_type, []).append(loc)

    for agent, locs in sorted(by_agent.items()):
        lines.append(f"  {agent}:")
        for loc in locs:
            size_kb = loc.size_bytes // 1024
            lines.append(f"    {loc.modified_time:>10s}  {size_kb:>6d}KB  {loc.project_name}")
            lines.append(f"               {loc.path}")

    lines.append("")
    lines.append("To score a trace: trace-eval run <path>")
    lines.append("To convert first: trace-eval convert <path> -o trace.jsonl")
    return "\n".join(lines)
