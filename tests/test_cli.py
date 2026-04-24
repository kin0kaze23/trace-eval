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
        "schema_version": "v1",
        "trace_id": "g-1",
        "task_id": "t-1",
        "session_id": "s-1",
        "event_index": 0,
        "actor": "user",
        "event_type": "session_start",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    },
    {
        "schema_version": "v1",
        "trace_id": "g-1",
        "task_id": "t-1",
        "session_id": "s-1",
        "event_index": 1,
        "actor": "assistant",
        "event_type": "llm_call",
        "timestamp": "2026-04-15T10:00:05Z",
        "status": "success",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_estimate": 0.01,
    },
    {
        "schema_version": "v1",
        "trace_id": "g-1",
        "task_id": "t-1",
        "session_id": "s-1",
        "event_index": 2,
        "actor": "assistant",
        "event_type": "session_end",
        "timestamp": "2026-04-15T10:00:10Z",
        "status": "success",
    },
]

BAD_LINES = [
    {
        "schema_version": "v1",
        "trace_id": "b-1",
        "task_id": "t-2",
        "session_id": "s-2",
        "event_index": 0,
        "actor": "user",
        "event_type": "session_start",
        "timestamp": "2026-04-15T10:00:00Z",
        "status": "success",
    },
    {
        "schema_version": "v1",
        "trace_id": "b-1",
        "task_id": "t-2",
        "session_id": "s-2",
        "event_index": 1,
        "actor": "assistant",
        "event_type": "tool_call",
        "timestamp": "2026-04-15T10:00:05Z",
        "status": "error",
        "tool_name": "write",
    },
    {
        "schema_version": "v1",
        "trace_id": "b-1",
        "task_id": "t-2",
        "session_id": "s-2",
        "event_index": 2,
        "actor": "assistant",
        "event_type": "session_end",
        "timestamp": "2026-04-15T10:00:10Z",
        "status": "error",
    },
]


def _run(args, expect_fail=False):
    result = subprocess.run(
        [sys.executable, "-m", "trace_eval.cli"] + args,
        capture_output=True,
        text=True,
        cwd=str(TRACE_EVAL_DIR),
    )
    if not expect_fail:
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    return result


def test_validate_good(tmp_path):
    trace = _make_trace(tmp_path, "good", GOOD_LINES)
    result = _run(["validate", str(trace)])
    assert "PASSED" in result.stdout


def test_run_text(tmp_path):
    trace = _make_trace(tmp_path, "good", GOOD_LINES)
    result = _run(["run", str(trace)])
    assert "SCORECARD" in result.stdout


def test_run_json(tmp_path):
    trace = _make_trace(tmp_path, "good", GOOD_LINES)
    result = _run(["run", str(trace), "--format", "json"])
    data = json.loads(result.stdout)
    assert "total_score" in data
    # Verify stable structure
    assert "dimension_scores" in data
    assert "friction_flags" in data
    assert "adapter_capability_report" in data


def test_ci_pass(tmp_path):
    trace = _make_trace(tmp_path, "good", GOOD_LINES)
    result = _run(["ci", str(trace), "--min-score", "0"])
    assert result.returncode == 0


def test_ci_fail(tmp_path):
    trace = _make_trace(tmp_path, "bad", BAD_LINES)
    result = _run(["ci", str(trace), "--min-score", "99"], expect_fail=True)
    assert result.returncode != 0
    assert "FAIL" in result.stderr


def test_compare(tmp_path):
    before = _make_trace(tmp_path, "before", BAD_LINES)
    after = _make_trace(tmp_path, "after", GOOD_LINES)
    result = _run(["compare", str(before), str(after)])
    assert "COMPARISON" in result.stdout
    assert "improved" in result.stdout.lower() or "regressed" in result.stdout.lower()


def test_compare_json(tmp_path):
    before = _make_trace(tmp_path, "before", BAD_LINES)
    after = _make_trace(tmp_path, "after", GOOD_LINES)
    result = _run(["compare", str(before), str(after), "--format", "json"])
    data = json.loads(result.stdout)
    assert "before" in data
    assert "after" in data
    assert "delta" in data


def test_run_summary(tmp_path):
    trace = _make_trace(tmp_path, "good", GOOD_LINES)
    result = _run(["run", str(trace), "--summary"])
    assert "Score:" in result.stdout
    assert "/100" in result.stdout


def test_compare_summary(tmp_path):
    before = _make_trace(tmp_path, "before", BAD_LINES)
    after = _make_trace(tmp_path, "after", GOOD_LINES)
    result = _run(["compare", str(before), str(after), "--summary"])
    assert "Before:" in result.stdout
    assert "After:" in result.stdout
    assert "Delta:" in result.stdout
