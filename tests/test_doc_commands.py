"""Documentation command validation tests using shlex + argparse."""

import re
import shlex
from pathlib import Path

TRACE_EVAL_DIR = Path(__file__).resolve().parent.parent

# Files to scan for command examples
DOC_FILES = [
    "README.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "docs/CI_INTEGRATION.md",
    "docs/AGENT_INTEGRATION.md",
    "docs/TROUBLESHOOTING.md",
]


def _extract_commands(filepath):
    path = TRACE_EVAL_DIR / filepath
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
            r"trace-eval\s+(?:validate|run|compare|ci|convert|locate|doctor|remediate|loop)\b[^`]*", line
        )
        for cmd in matches:
            cmd = cmd.strip().rstrip("`")
            # Skip bare command mentions (no arguments after subcommand)
            parts = cmd.split()
            if len(parts) <= 2:
                continue
            commands.append((filepath, cmd))
    return commands


def _parse_and_validate(cmd_str):
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        # Commands with shell variables or unclosed quotes can't be parsed
        return True, None
    if parts[0] != "trace-eval":
        return True, None
    if len(parts) < 2:
        return True, None
    subcommand = parts[1]
    args = parts[2:]
    known_subcommands = {"validate", "run", "compare", "ci", "convert", "locate", "doctor", "remediate", "loop"}
    if subcommand not in known_subcommands:
        return False, f"Unknown subcommand: {subcommand}"

    if subcommand == "ci":
        has_latest = "--latest" in args
        option_takes_value = {"--min-score", "--min-dimension", "--profile", "--format", "--hours"}
        positional = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg in option_takes_value:
                skip_next = True
                continue
            if arg.startswith("--"):
                continue
            positional.append(arg)
        has_path = len(positional) > 0
        if not has_path and not has_latest:
            return False, f"ci requires a trace path or --latest: {cmd_str}"
        if has_path and has_latest:
            return False, f"ci cannot have both path and --latest: {cmd_str}"
        if "--hours" in args and not has_latest:
            return False, f"--hours only valid with --latest: {cmd_str}"

    if subcommand == "run":
        option_takes_value = {"--format", "--profile"}
        positional = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg in option_takes_value:
                skip_next = True
                continue
            if arg.startswith("--"):
                continue
            positional.append(arg)
        if not positional:
            return False, f"run requires a trace path: {cmd_str}"

    if subcommand in ("validate", "remediate"):
        option_takes_value = {"--profile"}
        positional = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg in option_takes_value:
                skip_next = True
                continue
            if arg.startswith("--"):
                continue
            positional.append(arg)
        if not positional:
            return False, f"{subcommand} requires a trace path: {cmd_str}"

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
            if "$" + "{{" in cmd or "path/to" in cmd or "session.jsonl" in cmd:
                continue
            # Skip commands with shell variables or pipes
            if "$(" in cmd or "|" in cmd or ">" in cmd:
                continue
            try:
                is_valid, error = _parse_and_validate(cmd)
            except Exception:
                continue
            if not is_valid:
                failures.append(f"{doc_file}: {error}")
        assert not failures, chr(10).join(failures)

    def test_no_ci_without_path_or_latest(self):
        commands = _get_all_doc_commands()
        for doc_file, cmd in commands:
            if not cmd.startswith("trace-eval ci"):
                continue
            if "$" + "{{" in cmd or "path/to" in cmd or "session.jsonl" in cmd:
                continue
            if "$(" in cmd or "|" in cmd or ">" in cmd:
                continue
            try:
                is_valid, error = _parse_and_validate(cmd)
            except Exception:
                continue
            assert is_valid, f"{doc_file}: {error}"

    def test_option_values_not_mistaken_for_paths(self):
        is_valid, _ = _parse_and_validate("trace-eval ci trace.jsonl --profile coding_agent --min-score 80")
        assert is_valid
        is_valid, _ = _parse_and_validate("trace-eval ci --latest --profile coding_agent --min-score 80")
        assert is_valid
        is_valid, error = _parse_and_validate("trace-eval ci --profile coding_agent --min-score 75")
        assert not is_valid, f"Should fail: {error}"
