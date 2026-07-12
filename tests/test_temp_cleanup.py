"""Test that run_loop() cleans up temporary canonical files.

These are full-pipeline integration tests that verify the temp file
survives through all downstream operations and is cleaned up afterward.
"""

import json
import os
import tempfile
from unittest.mock import patch

from trace_eval.loop import _cleanup_temp_file, run_loop


class TestCleanupTempFile:
    def test_cleanup_none_is_noop(self):
        _cleanup_temp_file(None)

    def test_cleanup_existing_file(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
        tmp.write(b"test")
        tmp.close()
        assert os.path.exists(tmp.name)
        _cleanup_temp_file(tmp.name)
        assert not os.path.exists(tmp.name)

    def test_cleanup_nonexistent_file_is_noop(self):
        _cleanup_temp_file("/nonexistent/path/file.jsonl")


class _FakeLocation:
    def __init__(self, path):
        self.path = str(path)
        self.size_bytes = 1000
        self.modified_time = "2026-01-01T00:00:00Z"
        self.agent_type = "canonical"


def _make_canonical_trace(tmp_path):
    """Create a canonical JSONL trace file."""
    p = tmp_path / "trace.jsonl"
    events = [
        {
            "event_index": 0,
            "actor": "user",
            "event_type": "session_start",
            "timestamp": "2026-01-01T00:00:00Z",
            "status": "success",
            "schema_version": "v1",
            "trace_id": "test",
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
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return p


class TestRunLoopTempCleanup:
    """Test that run_loop cleans up temp files after completion."""

    def test_temp_file_cleaned_after_success(self, tmp_path):
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
        ):
            run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=False,
                report=False,
                output_dir=None,
            )
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_temp_file_survives_during_apply_safe(self, tmp_path):
        """Temp file must exist when apply_safe_fixes is called."""
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile
        path_exists_during_apply_safe = []

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        def checking_apply_safe(actions, card, trace_path):
            # Check if the trace_path exists at this point
            path_exists_during_apply_safe.append(os.path.exists(str(trace_path)))
            return []

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.apply_safe_fixes", checking_apply_safe),
        ):
            run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=True,
                report=False,
                output_dir=None,
            )
        # The temp file should have existed during apply_safe_fixes
        assert any(path_exists_during_apply_safe), "Temp file did not exist during apply_safe_fixes"
        # And should be cleaned up afterward
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_temp_file_survives_during_report_generation(self, tmp_path):
        """Temp file must exist when generate_remediation_report is called."""
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile
        path_exists_during_report = []

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        def checking_report(actions, card, trace_path, output_path=None):
            path_exists_during_report.append(os.path.exists(str(trace_path)))
            # Write a dummy report
            if output_path:
                output_path.write_text("# Report")
                return str(output_path)
            return str(trace_path)

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.generate_remediation_report", checking_report),
        ):
            run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=False,
                report=True,
                output_dir=None,
            )
        assert any(path_exists_during_report), "Temp file did not exist during report generation"
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_temp_file_cleaned_on_scoring_failure(self, tmp_path):
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.load_trace_with_report", side_effect=Exception("forced error")),
        ):
            result = run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=False,
                report=False,
                output_dir=None,
            )
        assert result.get("error")
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up on error: {tf}"
