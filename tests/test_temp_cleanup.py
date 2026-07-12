"""Test that run_loop() cleans up temporary canonical files."""

import os
import tempfile

from trace_eval.loop import _cleanup_temp_file


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
