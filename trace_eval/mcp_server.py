"""MCP server for trace-eval.

This is the primary interface for AI agents. The CLI is the substrate; MCP is the UX.

Strategy §4.1: "Primary interface is MCP server. CLI is the substrate, not the UX."
Strategy §7.3: Namespace is vibedev.trace.*

Tools exposed:
- vibedev.trace.score: Score the latest agent session
- vibedev.trace.compare: Compare two session files
- vibedev.trace.check: Quality gate — fails if score below threshold
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from trace_eval import __version__
from trace_eval.loop import format_loop_json, run_loop

# MCP server instance
# Namespace: vibedev.trace.* (per strategy §7.3)
mcp = FastMCP(
    "trace-eval",
    instructions="Evaluate AI agent sessions. Score quality, compare runs, and enforce quality gates.",
)


@mcp.tool()
async def score(
    agent: str = "all",
    hours: int = 48,
    preset: str | None = None,
) -> str:
    """Score the latest AI agent session.

    Call this after any meaningful agent task to check session quality.

    Args:
        agent: Which agent to check. One of: "claude-code", "cursor",
               "openclaw", or "all" to find the most recent across all.
        hours: How far back to search for sessions (default: 48 hours).
        preset: Scoring preset. One of: "default", "coding_agent", "rag_agent".
                If None, auto-detected from the session.

    Returns:
        JSON with: score, rating, top_issues, top_actions, trace info.
        If score < 80, review top_issues and consider applying top_actions.

    Example:
        After a coding task, the agent calls score() to self-evaluate.
        If the score is good (80+), report completion.
        If not, show issues to the user and fix them.
    """
    result = run_loop(
        agent_type=agent,
        hours=hours,
        profile=preset,
        compare_path=None,
        apply_safe=False,
        report=False,
        output_dir=None,
    )

    if result.get("error"):
        return json.dumps(
            {
                "error": result["error"],
                "hint": result.get("hint", ""),
            },
            indent=2,
        )

    # Return the JSON output that agents already know how to parse
    output = json.loads(format_loop_json(result))
    output["_version"] = __version__
    return json.dumps(output, indent=2)


@mcp.tool()
async def compare(
    before: str,
    after: str,
) -> str:
    """Compare two session files to measure improvement.

    Use this when you want to see if changes made the agent perform better.

    Args:
        before: Path to the earlier session file (.jsonl).
        after: Path to the later session file (.jsonl).

    Returns:
        JSON with: before/after scores, per-area deltas, flag changes.
        Positive delta means improvement. Check "resolved" for fixed issues.

    Example:
        After fixing a problem the agent had, compare the old session
        to the new one to verify the fix worked.
    """
    from trace_eval.judges.context import judge_context
    from trace_eval.judges.efficiency import judge_efficiency
    from trace_eval.judges.reliability import judge_reliability
    from trace_eval.judges.retrieval import judge_retrieval
    from trace_eval.judges.tool_discipline import judge_tool_discipline
    from trace_eval.loader import load_trace_with_report
    from trace_eval.scoring import compute_scorecard

    judges = {
        "reliability": judge_reliability,
        "efficiency": judge_efficiency,
        "retrieval": judge_retrieval,
        "tool_discipline": judge_tool_discipline,
        "context": judge_context,
    }

    before_trace, _ = load_trace_with_report(Path(before))
    after_trace, _ = load_trace_with_report(Path(after))

    before_judges = {n: jf(before_trace.events) for n, jf in judges.items()}
    after_judges = {n: jf(after_trace.events) for n, jf in judges.items()}

    before_card = compute_scorecard(before_judges)
    after_card = compute_scorecard(after_judges)

    delta = after_card.total_score - before_card.total_score
    before_flag_ids = {f.id for f in before_card.all_flags}
    after_flag_ids = {f.id for f in after_card.all_flags}

    dim_deltas = {}
    for dim in before_card.dimension_scores:
        b = before_card.dimension_scores.get(dim)
        a = after_card.dimension_scores.get(dim)
        if b is not None and a is not None:
            dim_deltas[dim] = round(a - b, 2)
        else:
            dim_deltas[dim] = None

    return json.dumps(
        {
            "before": {
                "score": before_card.total_score,
                "rating": before_card.rating,
                "score_areas": before_card.dimension_scores,
            },
            "after": {
                "score": after_card.total_score,
                "rating": after_card.rating,
                "score_areas": after_card.dimension_scores,
            },
            "delta": round(delta, 2),
            "improved": delta > 0,
            "dim_deltas": dim_deltas,
            "flag_changes": {
                "resolved": sorted(before_flag_ids - after_flag_ids),
                "new": sorted(after_flag_ids - before_flag_ids),
            },
        },
        indent=2,
    )


@mcp.tool()
async def check(
    session_file: str,
    min_score: float = 80,
    preset: str | None = None,
) -> str:
    """Quality gate — check if a session meets a minimum score threshold.

    Use this in CI/CD pipelines or before merging agent work.
    Returns pass/fail with the score and threshold.

    Args:
        session_file: Path to the session file (.jsonl) to check.
        min_score: Minimum acceptable score (default: 80).
        preset: Scoring preset. One of: "default", "coding_agent", "rag_agent".

    Returns:
        JSON with: passed (bool), score, threshold, issues if failed.
        Exit behavior: The caller should check "passed" field.

    Example:
        In a CI pipeline, call check() after an agent generates code.
        If passed is false, fail the build and show the user the issues.
    """
    from trace_eval.judges.context import judge_context
    from trace_eval.judges.efficiency import judge_efficiency
    from trace_eval.judges.reliability import judge_reliability
    from trace_eval.judges.retrieval import judge_retrieval
    from trace_eval.judges.tool_discipline import judge_tool_discipline
    from trace_eval.loader import load_trace_with_report
    from trace_eval.scoring import compute_scorecard

    judges = {
        "reliability": judge_reliability,
        "efficiency": judge_efficiency,
        "retrieval": judge_retrieval,
        "tool_discipline": judge_tool_discipline,
        "context": judge_context,
    }

    trace, _ = load_trace_with_report(Path(session_file))
    judge_results = {n: jf(trace.events) for n, jf in judges.items()}
    card = compute_scorecard(judge_results, profile=preset)

    passed = card.total_score >= min_score

    result = {
        "passed": passed,
        "score": card.total_score,
        "rating": card.rating,
        "threshold": min_score,
        "score_areas": card.dimension_scores,
    }

    if not passed:
        sorted_flags = sorted(
            card.all_flags, key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 9)
        )
        result["issues"] = [{"id": f.id, "severity": f.severity, "summary": f.suggestion} for f in sorted_flags[:5]]

    return json.dumps(result, indent=2)
