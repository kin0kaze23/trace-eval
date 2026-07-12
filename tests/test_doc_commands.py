"""Documentation command validation tests."""

import re
from pathlib import Path

import pytest

TRACE_EVAL_DIR = Path(__file__).resolve().parent.parent

DOC_FILES = [
    "README.md",
    "docs/CI_INTEGRATION.md",
    "docs/AGENT_INTEGRATION.md",
    "CAUDE.md",
]


def _extract_commands(filepath):
    path = TRACE_EVAL_DIR / filepath
    if not path.exists():
        return []
    content = path.read_text()
    commands = []
    for line in content.split("\\n"):
        matches = re.findall(r"trace-eval\s+\S+[^|`\n]*", line)
        for cmd in matches:
            cmd = cmd.strip().rstrip("`")
            if cmd.startswith("trace-eval #") or "alias" in line.lower():
                continue
            if "tev=" in line or "tevd=" in line or "tevs=" in line:
                continue
            commands.append(cmd)
    return commands


class TestDocCommandsValid:
    def test_no_bare_ci_without_path_or_latest(self):
        for doc_file in DOC_FILES:
            path = TRACE_EVAL_DIR / doc_file
            if not path.exists():
                continue
            content = path.read_text()
            bad_pattern = re.findall(
                r"trace-eval ci (?!--latest)(?!\S+.jsonl)(?!path/to)(?!session)\S*--min-score", content
            )
            actual_bad = [p for p in bad_pattern if "--latest" not in p]
            assert not actual_bad, (
                f"{doc_file} contains 'trace-eval ci --min-score' without a trace path or --latest: {actual_bad}"
            )

    def test_ci_command_has_path_or_latest(self):
        for doc_file in DOC_FILES:
            path = TRACE_EVAL_DIR / doc_file
            if not path.exists():
                continue
            content = path.read_text()
            ci_commands = re.findall(r"trace-eval ci\s+[^\n|`]+", content)
            for cmd in ci_commands:
                cmd = cmd.strip().rstrip("`")
                parts = cmd.split()
                has_path = any(not p.startswith("-") and p != "ci" for p in parts[2:])
                has_latest = "--latest" in parts
                if "${{" in cmd or "path/to" in cmd or "session.jsonl" in cmd:
                    continue
                if not has_path and not has_latest:
                    if cmd.strip() != "trace-eval ci":
                        pytest.fail(f"{doc_file}: 'trace-eval ci' command without path or --latest: {cmd}")

    def test_run_command_has_path(self):
        for doc_file in DOC_FILES:
            path = TRACE_EVAL_DIR / doc_file
            if not path.exists():
                continue
            content = path.read_text()
            run_commands = re.findall(r"trace-eval run\s+[^\n|`]+", content)
            for cmd in run_commands:
                cmd = cmd.strip().rstrip("`")
                parts = cmd.split()
                has_path = any(not p.startswith("-") and p != "run" for p in parts[2:])
                if not has_path and "path/to" not in cmd and "session.jsonl" not in cmd and "trace.jsonl" not in cmd:
                    if cmd.strip() != "trace-eval run":
                        pytest.fail(f"{doc_file}: 'trace-eval run' without trace path: {cmd}")
