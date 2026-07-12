"""Tests for the CI command contract."""

import json
import subprocess
import sys
from pathlib import Path

TRACE_EVAL_DIR = Path(__file__).resolve().parent.parent


def _make_trace(tmp_path, name, lines):
    p = tmp_path / f"{name}.jsonl"
    p.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return p


GOOD_LINES = [
    {
        "event_index": 0,
        "actor": "user",
        "event_type": "session_start",
        "timestamp": "2026-01-01T00:00:00Z",
        "status": "success",
    },
    {
        "event_index": 1,
        "actor": "assistant",
        "event_type": "llm_call",
        "timestamp": "2026-01-01T00:00:05Z",
        "status": "success",
        "tokens_in": 100,
        "tokens_out": 50,
    },
    {
        "event_index": 2,
        "actor": "assistant",
        "event_type": "session_end",
        "timestamp": "2026-01-01T00:00:10Z",
        "status": "success",
    },
]

BAD_LINES = [
    {
        "event_index": 0,
        "actor": "user",
        "event_type": "session_start",
        "timestamp": "2026-01-01T00:00:00Z",
        "status": "success",
    },
    {
        "event_index": 1,
        "actor": "assistant",
        "event_type": "tool_call",
        "timestamp": "2026-01-01T00:00:05Z",
        "status": "error",
        "tool_name": "write",
    },
    {
        "event_index": 2,
        "actor": "assistant",
        "event_type": "session_end",
        "timestamp": "2026-01-01T00:00:10Z",
        "status": "error",
    },
]


def _run(args):
    return subprocess.run(
        [sys.executable, "-m", "trace_eval.cli"] + args,
        capture_output=True,
        text=True,
        cwd=str(TRACE_EVAL_DIR),
    )


class TestCIExplicitPath:
    def test_explicit_path_pass(self, tmp_path):
        trace = _make_trace(tmp_path, "good", GOOD_LINES)
        result = _run(["ci", str(trace), "--min-score", "0"])
        assert result.returncode == 0

    def test_explicit_path_fail(self, tmp_path):
        trace = _make_trace(tmp_path, "bad", BAD_LINES)
        result = _run(["ci", str(trace), "--min-score", "99"])
        assert result.returncode != 0
        assert "FAIL" in result.stderr

    def test_explicit_path_json(self, tmp_path):
        trace = _make_trace(tmp_path, "good", GOOD_LINES)
        result = _run(["ci", str(trace), "--min-score", "0", "--format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_score" in data


class TestCIMutualExclusivity:
    def test_neither_path_nor_latest(self):
        result = _run(["ci", "--min-score", "80"])
        assert result.returncode != 0
        assert "must specify" in result.stderr.lower() or "either" in result.stderr.lower()

    def test_both_path_and_latest(self, tmp_path):
        trace = _make_trace(tmp_path, "good", GOOD_LINES)
        result = _run(["ci", str(trace), "--latest", "--min-score", "80"])
        assert result.returncode != 0
        assert "cannot specify both" in result.stderr.lower()


class TestCILatestOption:
    def test_latest_with_no_sessions_fails(self):
        result = _run(["ci", "--latest", "--hours", "1", "--min-score", "80"])
        assert result.returncode != 0
        assert (
            "no recent" in result.stderr.lower()
            or "not found" in result.stderr.lower()
            or "locate" in result.stderr.lower()
        )

    def test_hours_without_latest_accepted(self, tmp_path):
        trace = _make_trace(tmp_path, "good", GOOD_LINES)
        result = _run(["ci", str(trace), "--hours", "168", "--min-score", "0"])
        assert result.returncode == 0
