"""Test that run_loop() cleans up temporary canonical files."""

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
        self.agent_type = "claude-code"


def _make_canonical_trace(tmp_path):
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


def _fake_convert_events():
    return [
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


class TestRunLoopTempCleanup:
    "Full-pipeline tests that force conversion to create a temp file."

    def test_temp_file_created_and_cleaned_after_success(self, tmp_path):
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
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
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

        assert len(temp_files_created) > 0, "No temp file was created"
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_temp_file_survives_during_apply_safe(self, tmp_path):
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
            path_exists_during_apply_safe.append(os.path.exists(str(trace_path)))
            # Also assert that all tracked temp files still exist
            for tf in temp_files_created:
                assert os.path.exists(tf), f"Temp file deleted before apply_safe: {tf}"
            return []

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
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

        assert len(temp_files_created) > 0, "No temp file was created"
        assert any(path_exists_during_apply_safe), "Temp file did not exist during apply_safe"
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_temp_file_survives_during_report_generation(self, tmp_path):
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
            # Also assert that all tracked temp files still exist
            for tf in temp_files_created:
                assert os.path.exists(tf), f"Temp file deleted before report: {tf}"
            if output_path:
                output_path.write_text("# Report")
                return str(output_path)
            return str(trace_path)

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
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

        assert len(temp_files_created) > 0, "No temp file was created"
        assert any(path_exists_during_report), "Temp file did not exist during report"
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
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
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
        assert len(temp_files_created) > 0, "No temp file was created"
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up on error: {tf}"

    def test_temp_file_cleaned_on_remediation_failure(self, tmp_path):
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
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.remediation.analyze_with_context", side_effect=Exception("remediation error")),
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
        assert len(temp_files_created) > 0, "No temp file was created"
        for tf in temp_files_created:
            assert not os.path.exists(tf), f"Temp file not cleaned up: {tf}"

    def test_no_temp_file_for_canonical_input(self, tmp_path):
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

        assert len(temp_files_created) == 0, "Should not create temp file for canonical input"

    def test_user_output_file_preserved(self, tmp_path):
        trace = _make_canonical_trace(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
        ):
            run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=False,
                report=False,
                output_dir=str(output_dir),
            )

        # When output_dir is provided, canonical file goes to output dir, not temp
        # So no temp file should be created
        assert len(temp_files_created) == 0, "Should not create temp file when output_dir is provided"
        assert output_dir.exists(), "User output dir should be preserved"
        canonical_files = list(output_dir.glob("*_canonical.jsonl"))
        assert len(canonical_files) > 0, "Output canonical file should be preserved"


class TestArtifactCommandPostprocessing:
    """Verify generated commands are executable for auto-located sessions."""

    def test_safe_fix_commands_use_loop_not_run(self, tmp_path):
        """Generated fix commands should use 'trace-eval loop' not 'trace-eval run <basename>'."""
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        # Mock apply_safe_fixes to return a fix with old-style command
        def mock_apply_safe(actions, card, trace_path):
            return [
                {
                    "label": "Switch to coding_agent profile",
                    "path": "command",
                    "content": f"trace-eval run {trace_path.name} --profile coding_agent",
                }
            ]

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.apply_safe_fixes", mock_apply_safe),
        ):
            result = run_loop(
                agent_type="all",
                hours=1,
                profile="coding_agent",
                compare_path=None,
                apply_safe=True,
                report=False,
                output_dir=None,
            )

        assert "safe_fixes_applied" in result
        fixes = result["safe_fixes_applied"]
        assert len(fixes) > 0
        for fix in fixes:
            content = fix.get("content", "")
            # Should NOT contain 'trace-eval run <basename>'
            assert "trace-eval run" not in content, f"Command uses 'run' instead of 'loop': {content}"
            # Should contain 'trace-eval loop'
            assert "trace-eval loop" in content, f"Command should use 'loop': {content}"

    def test_no_temp_filename_in_commands(self, tmp_path):
        """Generated commands must not contain any temporary filename."""
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        def mock_apply_safe(actions, card, trace_path):
            return [
                {
                    "label": "Switch to coding_agent profile",
                    "path": "command",
                    "content": f"trace-eval run {trace_path.name} --profile coding_agent",
                }
            ]

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.apply_safe_fixes", mock_apply_safe),
        ):
            result = run_loop(
                agent_type="all",
                hours=1,
                profile=None,
                compare_path=None,
                apply_safe=True,
                report=False,
                output_dir=None,
            )

        fixes = result.get("safe_fixes_applied", [])
        for fix in fixes:
            content = fix.get("content", "")
            for tf in temp_files_created:
                tf_basename = os.path.basename(tf)
                assert tf_basename not in content, f"Temp filename in command: {content}"

    def test_report_uses_loop_for_auto_located(self, tmp_path):
        """Report should use 'trace-eval loop' for auto-located sessions."""
        trace = _make_canonical_trace(tmp_path)
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("delete") is False:
                temp_files_created.append(f.name)
            return f

        # Mock generate_remediation_report to write a report with old-style command
        def mock_report(actions, card, trace_path, output_path=None):
            report_content = f"# Report\ntrace-eval run {trace_path.name} --profile coding_agent\n"
            if output_path:
                output_path.write_text(report_content)
                return str(output_path)
            return str(trace_path)

        with (
            patch("trace_eval.loop.locate", return_value=[_FakeLocation(trace)]),
            patch("trace_eval.loop._detect_format", return_value="claude-code"),
            patch("trace_eval.loop.convert", return_value=_fake_convert_events()),
            patch("trace_eval.loop.tempfile.NamedTemporaryFile", tracking_named_temp),
            patch("trace_eval.loop.generate_remediation_report", mock_report),
        ):
            result = run_loop(
                agent_type="all",
                hours=1,
                profile="coding_agent",
                compare_path=None,
                apply_safe=False,
                report=True,
                output_dir=None,
            )

        report_path = result.get("report_path")
        assert report_path is not None
        # Read the report and verify commands
        report_content = open(report_path).read()
        assert "trace-eval run" not in report_content, "Report uses 'run' instead of 'loop'"
        assert "trace-eval loop" in report_content, "Report should use 'loop'"
