"""Native provider golden fixture tests — end-to-end pipeline.

Tests the complete public pipeline for each provider:
  native conversion -> canonical loading -> all judges -> scorecard -> total score + rating

Expected outputs are literal (committed to the repo), NOT produced
at test runtime by the production converter or scoring implementation.

Fixture provenance:
  All native fixtures are manually constructed provider-shaped fixtures.
  They are NOT sanitized extracts from actual provider recordings.
  They follow the documented format structure of each provider but use
  synthetic content (fake file paths, fake tool names, fake session IDs).
  The Claude Code fixture uses the official Anthropic is_error field name.
"""

import json
import subprocess
import sys
from pathlib import Path

from trace_eval.convert import convert
from trace_eval.judges.context import judge_context
from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event
from trace_eval.scoring import compute_scorecard

NATIVE_DIR = Path(__file__).parent / "fixtures" / "native"

JUDGES = {
    "reliability": judge_reliability,
    "efficiency": judge_efficiency,
    "retrieval": judge_retrieval,
    "tool_discipline": judge_tool_discipline,
    "context": judge_context,
}


def _load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _events_from_dicts(dicts):
    return [Event.from_dict(d) for d in dicts]


def _assert_canonical_complete(actual, expected, provider):
    """Compare complete canonical dictionaries against committed expected JSONL.

    No field normalizations — the expected JSONL is a literal snapshot
    of the converter output. If the converter changes, the expected
    JSONL must be regenerated and re-committed.
    """
    assert len(actual) == len(expected), (
        f"[{provider}] Event count mismatch: actual={len(actual)}, expected={len(expected)}"
    )
    for i, (a, e) in enumerate(zip(actual, expected, strict=False)):
        # Compare all keys from both dicts
        all_keys = set(a.keys()) | set(e.keys())
        for key in all_keys:
            av = a.get(key)
            ev = e.get(key)
            assert av == ev, f"[{provider}] Event {i} field '{key}': actual={av!r}, expected={ev!r}"


def _assert_full_scorecard(actual_manifest, expected_manifest, provider):
    """Assert all dimension scores, total score, and rating match."""
    # Check each judge
    for judge_name in JUDGES:
        assert judge_name in expected_manifest, f"[{provider}] Expected manifest missing judge '{judge_name}'"
        assert judge_name in actual_manifest, f"[{provider}] Actual manifest missing judge '{judge_name}'"
        exp_j = expected_manifest[judge_name]
        act_j = actual_manifest[judge_name]
        assert act_j["score"] == exp_j["score"], (
            f"[{provider}] {judge_name} score: actual={act_j['score']!r}, expected={exp_j['score']!r}"
        )
        assert act_j["confidence"] == exp_j["confidence"], (
            f"[{provider}] {judge_name} confidence: actual={act_j['confidence']!r}, expected={exp_j['confidence']!r}"
        )
        assert act_j["scorable"] == exp_j["scorable"], (
            f"[{provider}] {judge_name} scorable: actual={act_j['scorable']!r}, expected={exp_j['scorable']!r}"
        )

    # Check total score and rating
    assert actual_manifest["total_score"] == expected_manifest["total_score"], (
        f"[{provider}] total_score: actual={actual_manifest['total_score']!r}, "
        f"expected={expected_manifest['total_score']!r}"
    )
    assert actual_manifest["rating"] == expected_manifest["rating"], (
        f"[{provider}] rating: actual={actual_manifest['rating']!r}, expected={expected_manifest['rating']!r}"
    )


def _run_full_pipeline(native_path, fmt):
    """Run the complete pipeline and return the manifest."""
    canonical = convert(native_path, fmt=fmt)
    events = _events_from_dicts(canonical)
    judge_results = {name: fn(events) for name, fn in JUDGES.items()}
    card = compute_scorecard(judge_results)

    manifest = {}
    for name, result in judge_results.items():
        manifest[name] = {
            "score": result.score,
            "confidence": result.confidence,
            "scorable": result.scorable,
        }
        if name == "tool_discipline":
            manifest[name]["raw_metrics"] = result.raw_metrics

    manifest["total_score"] = card.total_score
    manifest["rating"] = card.rating
    manifest["scorable_dimensions"] = card.scorable_dimensions
    manifest["unscorable_dimensions"] = card.unscorable_dimensions

    return canonical, manifest


# ---------------------------------------------------------------------------
# Claude Code native fixture
# ---------------------------------------------------------------------------


class TestClaudeCodeNativeFixture:
    """Manually constructed Claude Code fixture -> full pipeline."""

    def test_conversion_complete_canonical_match(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "claude_code_expected.jsonl")
        actual = convert(native_path, fmt="claude-code")
        _assert_canonical_complete(actual, expected, "claude_code")

    def test_conversion_preserves_tool_call_ids(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        actual = convert(native_path, fmt="claude-code")
        tool_calls = [e for e in actual if e["event_type"] == "tool_call"]
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        for tc in tool_calls:
            assert tc["tool_call_id"] is not None
        for tr in tool_results:
            assert tr["tool_call_id"] is not None

    def test_conversion_emits_provider_backed_statuses(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        actual = convert(native_path, fmt="claude-code")
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]
        nones = [e for e in tool_results if e["status"] is None]
        assert len(successes) == 3
        assert len(errors) == 1
        assert len(nones) == 0

    def test_full_scorecard_matches_expected_manifest(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "claude_code_expected_scores.json")
        _, actual_manifest = _run_full_pipeline(native_path, "claude-code")
        _assert_full_scorecard(actual_manifest, expected_manifest, "claude_code")

    def test_full_pipeline_native_to_score(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "claude_code_expected_scores.json")
        canonical, manifest = _run_full_pipeline(native_path, "claude-code")
        assert manifest["total_score"] == expected_manifest["total_score"]
        assert manifest["rating"] == expected_manifest["rating"]
        assert manifest["tool_discipline"]["raw_metrics"]["exact_pairs"] == 4
        assert manifest["tool_discipline"]["raw_metrics"]["tool_retries"] == 1


# ---------------------------------------------------------------------------
# Cursor native fixture
# ---------------------------------------------------------------------------


class TestCursorNativeFixture:
    """Manually constructed Cursor fixture -> full pipeline."""

    def test_conversion_complete_canonical_match(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "cursor_expected.jsonl")
        actual = convert(native_path, fmt="cursor")
        _assert_canonical_complete(actual, expected, "cursor")

    def test_conversion_emits_provider_backed_statuses(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        actual = convert(native_path, fmt="cursor")
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]
        nones = [e for e in tool_results if e["status"] is None]
        assert len(successes) == 3
        assert len(errors) == 1
        assert len(nones) == 0

    def test_full_scorecard_matches_expected_manifest(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "cursor_expected_scores.json")
        _, actual_manifest = _run_full_pipeline(native_path, "cursor")
        _assert_full_scorecard(actual_manifest, expected_manifest, "cursor")

    def test_full_pipeline_native_to_score(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "cursor_expected_scores.json")
        canonical, manifest = _run_full_pipeline(native_path, "cursor")
        assert manifest["total_score"] == expected_manifest["total_score"]
        assert manifest["rating"] == expected_manifest["rating"]
        assert manifest["tool_discipline"]["raw_metrics"]["heuristic_pairs"] == 4
        assert manifest["tool_discipline"]["confidence"] == "medium"


# ---------------------------------------------------------------------------
# OpenClaw native fixture
# ---------------------------------------------------------------------------


class TestOpenClawNativeFixture:
    """Manually constructed OpenClaw fixture -> full pipeline."""

    def test_conversion_complete_canonical_match(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "openclaw_expected.jsonl")
        actual = convert(native_path, fmt="openclaw")
        _assert_canonical_complete(actual, expected, "openclaw")

    def test_conversion_preserves_tool_call_ids(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        actual = convert(native_path, fmt="openclaw")
        tool_calls = [e for e in actual if e["event_type"] == "tool_call"]
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        for tc in tool_calls:
            assert tc["tool_call_id"] is not None
        for tr in tool_results:
            assert tr["tool_call_id"] is not None

    def test_conversion_emits_provider_backed_statuses(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        actual = convert(native_path, fmt="openclaw")
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]
        nones = [e for e in tool_results if e["status"] is None]
        assert len(successes) == 2
        assert len(errors) == 1
        assert len(nones) == 0

    def test_full_scorecard_matches_expected_manifest(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "openclaw_expected_scores.json")
        _, actual_manifest = _run_full_pipeline(native_path, "openclaw")
        _assert_full_scorecard(actual_manifest, expected_manifest, "openclaw")

    def test_full_pipeline_native_to_score(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "openclaw_expected_scores.json")
        canonical, manifest = _run_full_pipeline(native_path, "openclaw")
        assert manifest["total_score"] == expected_manifest["total_score"]
        assert manifest["rating"] == expected_manifest["rating"]
        assert manifest["tool_discipline"]["raw_metrics"]["exact_pairs"] == 3
        assert manifest["tool_discipline"]["raw_metrics"]["tool_retries"] == 1


# ---------------------------------------------------------------------------
# Subprocess / public-interface test
# ---------------------------------------------------------------------------


class TestPublicInterfacePipeline:
    """Test the CLI pipeline: convert -> run --format json."""

    def test_claude_code_cli_pipeline(self, tmp_path):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "claude_code_expected_scores.json")
        canonical_path = tmp_path / "claude_canonical.jsonl"

        # Step 1: convert
        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "convert", str(native_path), "-o", str(canonical_path)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Convert failed: {result.stderr}"
        assert canonical_path.exists()

        # Step 2: run with JSON output
        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "run", str(canonical_path), "--format", "json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Run failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "total_score" in data
        assert data["total_score"] == expected_manifest["total_score"]
        assert data["rating"] == expected_manifest["rating"]

    def test_cursor_cli_pipeline(self, tmp_path):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "cursor_expected_scores.json")
        canonical_path = tmp_path / "cursor_canonical.jsonl"

        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "convert", str(native_path), "-o", str(canonical_path)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Convert failed: {result.stderr}"
        assert canonical_path.exists()

        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "run", str(canonical_path), "--format", "json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Run failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["total_score"] == expected_manifest["total_score"]
        assert data["rating"] == expected_manifest["rating"]

    def test_openclaw_cli_pipeline(self, tmp_path):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected_manifest = _load_json(NATIVE_DIR / "openclaw_expected_scores.json")
        canonical_path = tmp_path / "openclaw_canonical.jsonl"

        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "convert", str(native_path), "-o", str(canonical_path)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Convert failed: {result.stderr}"
        assert canonical_path.exists()

        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "run", str(canonical_path), "--format", "json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Run failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["total_score"] == expected_manifest["total_score"]
        assert data["rating"] == expected_manifest["rating"]


# ---------------------------------------------------------------------------
# Claude Code is_error field handling
# ---------------------------------------------------------------------------


class TestClaudeCodeErrorFieldHandling:
    """Test that the converter handles both is_error and isError fields."""

    def test_is_error_true_emits_error_status(self, tmp_path):
        """is_error: true must produce status='error'."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "tc1", "name": "Bash", "input": {"command": "ls"}}],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tc1",
                            "is_error": True,
                            "content": [{"type": "text", "text": "command failed"}],
                        }
                    ],
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        events = convert(p, fmt="claude-code")
        results = [e for e in events if e["event_type"] == "tool_result"]
        assert len(results) == 1
        assert results[0]["status"] == "error"

    def test_is_error_false_emits_success_status(self, tmp_path):
        """is_error: false must produce status='success'."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "tc1", "name": "Bash", "input": {"command": "ls"}}],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tc1",
                            "is_error": False,
                            "content": [{"type": "text", "text": "file1.py"}],
                        }
                    ],
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        events = convert(p, fmt="claude-code")
        results = [e for e in events if e["event_type"] == "tool_result"]
        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_isError_backward_compatibility(self, tmp_path):
        """isError (camelCase) must still work for backward compatibility."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "tc1", "name": "Bash", "input": {"command": "ls"}}],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tc1",
                            "isError": True,
                            "content": [{"type": "text", "text": "command failed"}],
                        }
                    ],
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        events = convert(p, fmt="claude-code")
        results = [e for e in events if e["event_type"] == "tool_result"]
        assert len(results) == 1
        assert results[0]["status"] == "error"

    def test_error_status_without_error_text_pattern(self, tmp_path):
        """is_error: true must emit error even without error-text patterns."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "tc1", "name": "Read", "input": {"file_path": "/src/app.py"}}
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tc1",
                            "is_error": True,
                            "content": [{"type": "text", "text": "Permission denied"}],
                        }
                    ],
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        events = convert(p, fmt="claude-code")
        results = [e for e in events if e["event_type"] == "tool_result"]
        assert results[0]["status"] == "error"

    def test_top_level_tool_result_preserves_tool_call_id(self, tmp_path):
        """Top-level type=tool_result must extract and preserve tool_call_id."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "tc_top_001", "name": "Bash", "input": {"command": "echo hello"}}
                    ],
                },
            },
            {
                "type": "tool_result",
                "message": {
                    "role": "tool",
                    "content": [{"type": "text", "text": "hello"}],
                    "is_error": False,
                    "tool_use_id": "tc_top_001",
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        events = convert(p, fmt="claude-code")
        results = [e for e in events if e["event_type"] == "tool_result"]
        assert len(results) == 1
        assert results[0]["tool_call_id"] == "tc_top_001"
        assert results[0]["status"] == "success"

    def test_top_level_tool_result_exact_pairing(self, tmp_path):
        """Top-level tool_result with tool_call_id must exact-pair with its call."""
        native = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "tc_pair_001", "name": "Bash", "input": {"command": "echo hello"}}
                    ],
                },
            },
            {
                "type": "tool_result",
                "message": {
                    "role": "tool",
                    "content": [{"type": "text", "text": "hello"}],
                    "is_error": False,
                    "tool_use_id": "tc_pair_001",
                },
            },
        ]
        p = tmp_path / "test.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in native) + "\n")
        canonical = convert(p, fmt="claude-code")
        events = _events_from_dicts(canonical)
        result = judge_tool_discipline(events)
        assert result.raw_metrics["exact_pairs"] == 1
        assert result.raw_metrics["unmatched_calls"] == 0
        assert result.raw_metrics["orphan_results"] == 0
