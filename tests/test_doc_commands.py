"""Documentation command validation using the real argparse parser."""

import re
import shlex
from pathlib import Path

from trace_eval.cli import build_parser

TRACE_EVAL_DIR = Path(__file__).resolve().parent.parent

# Files to scan for command examples
DOC_FILES = ["README.md", "CLAUDE.md", "CONTRIBUTING.md"]
DOC_FILES += [str(p) for p in (TRACE_EVAL_DIR / "docs").glob("*.md")]

# Commands that intentionally contain placeholders or shell syntax
ALLOWLIST_PATTERNS = [
    "--details",
    "path/to",
    "session.jsonl",
    "trace.jsonl",
    "$",
    "|",
    ">",
    "head ",
]


def _is_allowlisted(cmd):
    return any(p in cmd for p in ALLOWLIST_PATTERNS)


def _extract_commands(filepath):
    path = TRACE_EVAL_DIR / filepath if not filepath.startswith("/") else Path(filepath)
    if not path.exists():
        return []
    content = path.read_text()
    commands = []
    for line in content.split("\n"):
        if line.strip().startswith("#") or "alias" in line.lower():
            continue
        if "tev=" in line or "tevd=" in line or "tevs=" in line:
            continue
        matches = re.findall(
            r"trace-eval\s+(?:validate|run|compare|ci|convert|locate|doctor|remediate|loop)\b[^`]*",
            line,
        )
        for cmd in matches:
            cmd = cmd.strip().rstrip(chr(96))
            parts = cmd.split()
            if len(parts) <= 2:
                continue
            # Skip prose matches where first arg is a conjunction
            if parts[2] in ("and", "or", "to", "for"):
                continue
            commands.append((filepath, cmd))
    return commands


def _validate_with_parser(cmd_str):
    """Validate a command against the real argparse parser.

    Returns (is_valid, error_message).
    Uses parser.parse_args() which raises SystemExit on error.
    """
    # Strip inline comments (everything after #)
    cmd_str = cmd_str.split("#")[0].strip()
    if not cmd_str:
        return True, None
    parts = shlex.split(cmd_str)
    if parts[0] != "trace-eval":
        return True, None
    if len(parts) < 2:
        return True, None

    parser = build_parser()
    # Remove "trace-eval" prefix
    args_to_parse = parts[1:]

    try:
        parser.parse_args(args_to_parse)
    except SystemExit:
        return False, f"Parser rejected: {cmd_str}"
    return True, None


def _get_all_doc_commands():
    commands = []
    for doc_file in DOC_FILES:
        commands.extend(_extract_commands(doc_file))
    return commands


class TestDocCommandsValid:
    def test_claude_md_is_included(self):
        assert "CLAUDE.md" in DOC_FILES
        assert "CAUDE.md" not in DOC_FILES
        assert (TRACE_EVAL_DIR / "CLAUDE.md").exists()

    def test_all_doc_commands_valid(self):
        commands = _get_all_doc_commands()
        assert len(commands) > 0, "No commands found in docs"
        failures = []
        for doc_file, cmd in commands:
            if _is_allowlisted(cmd):
                continue
            is_valid, error = _validate_with_parser(cmd)
            if not is_valid:
                failures.append(f"{doc_file}: {error}")
        assert not failures, chr(10).join(failures)

    def test_no_ci_without_path_or_latest(self):
        commands = _get_all_doc_commands()
        for doc_file, cmd in commands:
            if not cmd.startswith("trace-eval ci"):
                continue
            if _is_allowlisted(cmd):
                continue
            is_valid, error = _validate_with_parser(cmd)
            assert is_valid, f"{doc_file}: {error}"

    def test_option_values_not_mistaken_for_paths(self):
        """Parser accepts coding_agent as positional, but runtime rejects it."""
        import subprocess
        import sys

        is_valid, _ = _validate_with_parser("trace-eval ci trace.jsonl --profile coding_agent --min-score 80")
        assert is_valid
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "trace_eval.cli",
                "ci",
                "coding_agent",
                "--profile",
                "coding_agent",
                "--min-score",
                "75",
            ],
            capture_output=True,
            text=True,
            cwd=str(TRACE_EVAL_DIR),
        )
        assert result.returncode != 0, "Should fail: coding_agent is not a file"

    def test_unknown_option_fails(self):
        is_valid, _ = _validate_with_parser("trace-eval ci trace.jsonl --unknown-option")
        assert not is_valid

    def test_option_on_wrong_subcommand_fails(self):
        # --latest is only on ci, not on run
        is_valid, _ = _validate_with_parser("trace-eval run trace.jsonl --latest")
        assert not is_valid

    def test_docs_glob_scanned(self):
        """Verify docs/*.md files are included in the scan list."""
        doc_paths = [f for f in DOC_FILES if f.startswith("docs/") or "/docs/" in f]
        assert len(doc_paths) > 0, "No docs/*.md files in scan list"
