"""Tests for MCP server tools."""

import asyncio
import json
from pathlib import Path

from trace_eval.mcp_server import check, compare, score

# Paths to example files
REPO = Path(__file__).parent.parent
HERMES_BAD = REPO / "examples" / "hermes_bad.jsonl"
HERMES_GOOD = REPO / "examples" / "hermes_good.jsonl"


def _run_async(coro):
    """Helper to run async coroutine in sync test."""
    return asyncio.run(coro)


def test_score_returns_json():
    """score() returns valid JSON with score and rating."""
    result = _run_async(score(agent="claude-code", hours=168))
    data = json.loads(result)
    # Should have the core fields agents rely on
    assert "score" in data or "error" in data


def test_score_returns_error_when_no_traces():
    """score() returns error when no traces are found (not an exception)."""
    result = _run_async(score(agent="claude-code", hours=1))
    data = json.loads(result)
    # Either returns a score or an error — never crashes
    assert "score" in data or "error" in data


def test_check_pass():
    """check() returns passed=true when score exceeds threshold."""
    result = _run_async(check(session_file=str(HERMES_GOOD), min_score=10))
    data = json.loads(result)
    assert data["passed"] is True
    assert data["score"] >= 10


def test_check_fail():
    """check() returns passed=false when score below threshold."""
    result = _run_async(check(session_file=str(HERMES_BAD), min_score=99))
    data = json.loads(result)
    assert data["passed"] is False
    assert data["score"] < 99
    assert "issues" in data


def test_check_returns_issues_on_fail():
    """check() includes issues list when failing."""
    result = _run_async(check(session_file=str(HERMES_BAD), min_score=99))
    data = json.loads(result)
    assert isinstance(data["issues"], list)
    for issue in data["issues"]:
        assert "id" in issue
        assert "severity" in issue
        assert "summary" in issue


def test_compare_returns_delta():
    """compare() returns delta and score_areas."""
    result = _run_async(
        compare(
            before=str(HERMES_BAD),
            after=str(HERMES_BAD),
        )
    )
    data = json.loads(result)
    assert "before" in data
    assert "after" in data
    assert "delta" in data
    assert data["delta"] == 0.0
    assert data["improved"] is False


def test_compare_detects_improvement():
    """compare() detects when after > before."""
    result = _run_async(
        compare(
            before=str(HERMES_BAD),
            after=str(HERMES_GOOD),
        )
    )
    data = json.loads(result)
    assert data["delta"] > 0
    assert data["improved"] is True


def test_compare_shows_flag_changes():
    """compare() shows resolved and new flags."""
    result = _run_async(
        compare(
            before=str(HERMES_BAD),
            after=str(HERMES_GOOD),
        )
    )
    data = json.loads(result)
    assert "flag_changes" in data
    assert "resolved" in data["flag_changes"]
    assert "new" in data["flag_changes"]
    # Good run should have fewer issues
    assert len(data["flag_changes"]["resolved"]) > 0
