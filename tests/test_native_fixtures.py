"""Native provider golden fixture tests.

Tests the complete public pipeline for each provider:
  native conversion -> canonical loading -> all judges -> total score

Expected outputs are literal (committed to the repo), NOT produced
at test runtime by the production converter or scoring implementation.
"""

import json
from pathlib import Path

from trace_eval.convert import convert
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event

NATIVE_DIR = Path(__file__).parent / "fixtures" / "native"


def _load_jsonl(path):
    """Load a JSONL file as a list of dicts."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_json(path):
    """Load a JSON file."""
    with open(path) as f:
        return json.load(f)


def _events_from_dicts(dicts):
    return [Event.from_dict(d) for d in dicts]


def _assert_canonical_matches(actual, expected, fields):
    """Assert that each actual event matches expected for given fields."""
    assert len(actual) == len(expected), f"Event count mismatch: actual={len(actual)}, expected={len(expected)}"
    for i, (a, e) in enumerate(zip(actual, expected, strict=False)):
        for field in fields:
            av = a.get(field)
            ev = e.get(field)
            assert av == ev, f"Event {i} field '{field}': actual={av!r}, expected={ev!r}"


def _assert_scores_match(actual_result, expected_scores):
    """Assert tool discipline metrics match expected scores."""
    td = expected_scores["tool_discipline"]
    for key, expected_val in td.items():
        if key == "score":
            actual_val = actual_result.score
        elif key == "confidence":
            actual_val = actual_result.confidence
        else:
            actual_val = actual_result.raw_metrics.get(key)
        assert actual_val == expected_val, f"Metric '{key}': actual={actual_val!r}, expected={expected_val!r}"


# ---------------------------------------------------------------------------
# Claude Code native fixture
# ---------------------------------------------------------------------------


class TestClaudeCodeNativeFixture:
    """Sanitized Claude Code recording -> canonical -> score."""

    def test_conversion_produces_expected_canonical(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "claude_code_expected.jsonl")

        actual = convert(native_path, fmt="claude-code")

        fields = [
            "event_index",
            "actor",
            "event_type",
            "status",
            "session_id",
            "tool_name",
            "tool_call_id",
        ]
        _assert_canonical_matches(actual, expected, fields)

    def test_conversion_preserves_tool_call_ids(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        actual = convert(native_path, fmt="claude-code")

        tool_calls = [e for e in actual if e["event_type"] == "tool_call"]
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]

        for tc in tool_calls:
            assert tc["tool_call_id"] is not None, f"Tool call at index {tc['event_index']} missing tool_call_id"
        for tr in tool_results:
            assert tr["tool_call_id"] is not None, f"Tool result at index {tr['event_index']} missing tool_call_id"

    def test_conversion_emits_success_status(self):
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        actual = convert(native_path, fmt="claude-code")

        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]

        assert len(successes) == 3, f"Expected 3 successes, got {len(successes)}"
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"
        # No None statuses for tool results
        nones = [e for e in tool_results if e["status"] is None]
        assert len(nones) == 0, "Tool results should not have None status"

    def test_scoring_matches_expected_manifest(self):
        expected_path = NATIVE_DIR / "claude_code_expected.jsonl"
        expected_scores = _load_json(NATIVE_DIR / "claude_code_expected_scores.json")

        events = _events_from_dicts(_load_jsonl(expected_path))
        result = judge_tool_discipline(events)

        _assert_scores_match(result, expected_scores)
        assert result.score == expected_scores["tool_discipline"]["score"]
        assert result.confidence == expected_scores["tool_discipline"]["confidence"]

    def test_full_pipeline_native_to_score(self):
        """Complete pipeline: native -> convert -> load -> judge -> score."""
        native_path = NATIVE_DIR / "claude_code_native.jsonl"
        expected_scores = _load_json(NATIVE_DIR / "claude_code_expected_scores.json")

        canonical = convert(native_path, fmt="claude-code")
        events = _events_from_dicts(canonical)
        result = judge_tool_discipline(events)

        td = expected_scores["tool_discipline"]
        assert result.score == td["score"]
        assert result.raw_metrics["exact_pairs"] == td["exact_pairs"]
        assert result.raw_metrics["tool_retries"] == td["tool_retries"]
        assert result.raw_metrics["successful_attempts"] == td["successful_attempts"]
        assert result.confidence == td["confidence"]


# ---------------------------------------------------------------------------
# Cursor native fixture
# ---------------------------------------------------------------------------


class TestCursorNativeFixture:
    """Sanitized Cursor recording -> canonical -> score."""

    def test_conversion_produces_expected_canonical(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "cursor_expected.jsonl")

        actual = convert(native_path, fmt="cursor")

        fields = [
            "event_index",
            "actor",
            "event_type",
            "status",
            "session_id",
            "tool_name",
            "tool_call_id",
        ]
        _assert_canonical_matches(actual, expected, fields)

    def test_conversion_emits_success_status(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        actual = convert(native_path, fmt="cursor")

        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]

        assert len(successes) == 3, f"Expected 3 successes, got {len(successes)}"
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"
        nones = [e for e in tool_results if e["status"] is None]
        assert len(nones) == 0, "Tool results should not have None status"

    def test_heuristic_matching_for_no_id_events(self):
        """Cursor fixture has no tool_call_ids — all matching is heuristic."""
        expected_path = NATIVE_DIR / "cursor_expected.jsonl"
        expected_scores = _load_json(NATIVE_DIR / "cursor_expected_scores.json")

        events = _events_from_dicts(_load_jsonl(expected_path))
        result = judge_tool_discipline(events)

        td = expected_scores["tool_discipline"]
        assert result.raw_metrics["heuristic_pairs"] == td["heuristic_pairs"]
        assert result.raw_metrics["exact_pairs"] == td["exact_pairs"]
        assert result.confidence == td["confidence"]

    def test_full_pipeline_native_to_score(self):
        native_path = NATIVE_DIR / "cursor_native.jsonl"
        expected_scores = _load_json(NATIVE_DIR / "cursor_expected_scores.json")

        canonical = convert(native_path, fmt="cursor")
        events = _events_from_dicts(canonical)
        result = judge_tool_discipline(events)

        td = expected_scores["tool_discipline"]
        assert result.score == td["score"]
        assert result.raw_metrics["heuristic_pairs"] == td["heuristic_pairs"]
        assert result.raw_metrics["tool_retries"] == td["tool_retries"]
        assert result.confidence == td["confidence"]


# ---------------------------------------------------------------------------
# OpenClaw native fixture
# ---------------------------------------------------------------------------


class TestOpenClawNativeFixture:
    """Sanitized OpenClaw recording -> canonical -> score."""

    def test_conversion_produces_expected_canonical(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected = _load_jsonl(NATIVE_DIR / "openclaw_expected.jsonl")

        actual = convert(native_path, fmt="openclaw")

        fields = [
            "event_index",
            "actor",
            "event_type",
            "status",
            "session_id",
            "tool_name",
            "tool_call_id",
        ]
        _assert_canonical_matches(actual, expected, fields)

    def test_conversion_preserves_tool_call_ids(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        actual = convert(native_path, fmt="openclaw")

        tool_calls = [e for e in actual if e["event_type"] == "tool_call"]
        tool_results = [e for e in actual if e["event_type"] == "tool_result"]

        for tc in tool_calls:
            assert tc["tool_call_id"] is not None
        for tr in tool_results:
            assert tr["tool_call_id"] is not None

    def test_conversion_emits_success_status(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        actual = convert(native_path, fmt="openclaw")

        tool_results = [e for e in actual if e["event_type"] == "tool_result"]
        successes = [e for e in tool_results if e["status"] == "success"]
        errors = [e for e in tool_results if e["status"] == "error"]

        assert len(successes) == 2
        assert len(errors) == 1
        nones = [e for e in tool_results if e["status"] is None]
        assert len(nones) == 0

    def test_full_pipeline_native_to_score(self):
        native_path = NATIVE_DIR / "openclaw_native.jsonl"
        expected_scores = _load_json(NATIVE_DIR / "openclaw_expected_scores.json")

        canonical = convert(native_path, fmt="openclaw")
        events = _events_from_dicts(canonical)
        result = judge_tool_discipline(events)

        td = expected_scores["tool_discipline"]
        assert result.score == td["score"]
        assert result.raw_metrics["exact_pairs"] == td["exact_pairs"]
        assert result.raw_metrics["tool_retries"] == td["tool_retries"]
        assert result.confidence == td["confidence"]
