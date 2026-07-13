"""Binary smoke test: build and verify the standalone binary."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
BINARY_PATH = REPO_DIR / "dist" / "trace-eval"


def _pyinstaller_available():
    try:
        import importlib

        importlib.import_module("PyInstaller")
        return True
    except ImportError:
        return False


def _build_binary():
    """Build the binary using the build script."""
    result = subprocess.run(
        ["bash", str(REPO_DIR / "scripts" / "build-binary.sh")],
        capture_output=True,
        text=True,
        cwd=str(REPO_DIR),
        timeout=120,
    )
    return result


class TestBinarySmoke:
    """Build the binary and verify basic commands work."""

    @pytest.fixture(scope="class")
    def built_binary(self):
        """Build the binary once for all tests in this class."""
        if not _pyinstaller_available():
            pytest.skip("PyInstaller not installed")
        # Clean previous build
        shutil.rmtree(REPO_DIR / "dist", ignore_errors=True)
        result = _build_binary()
        if result.returncode != 0:
            pytest.fail(f"Binary build failed: {result.stderr}")
        assert BINARY_PATH.exists(), "Binary not found after build"
        return BINARY_PATH

    def test_version(self, built_binary):
        result = subprocess.run(
            [str(built_binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "trace-eval" in result.stdout.lower()

    def test_doctor(self, built_binary):
        result = subprocess.run(
            [str(built_binary), "doctor"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_run_fixture_json(self, built_binary):
        fixture = REPO_DIR / "examples" / "hermes_good.jsonl"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")
        result = subprocess.run(
            [str(built_binary), "run", str(fixture), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_score" in data
        assert "rating" in data

    @classmethod
    def teardown_class(cls):
        """Clean up build artifacts."""
        shutil.rmtree(REPO_DIR / "dist", ignore_errors=True)
        shutil.rmtree(REPO_DIR / "build", ignore_errors=True)
