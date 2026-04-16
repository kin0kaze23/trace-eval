# Sprint 5: Adoption + UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship trace-eval v0.3.0 with public case study, `--summary` flag, Cursor converter, and tightened README onboarding.

**Architecture:** All changes are additive — no existing APIs change. The `--summary` flag adds a compact output path to `cmd_run` and `cmd_compare`. The Cursor converter follows the established pattern in `convert.py`. The case study is a documentation update.

**Tech Stack:** Python 3.11+, trace-eval v0.2.0 codebase

---

### Task 1: Publish Public Case Study

**Files:**
- Modify: `examples/case_study.md` — update to include real Claude Code + OpenClaw evidence
- Modify: `README.md` — add link to case study in prominent position

- [ ] **Step 1: Update case study with real trace evidence**

The current case study has a synthetic bad→good example (good for demonstrating compare) and a real Claude Code section. Update it to be a public-ready document with three sections:

```markdown
# Case Study: Debugging Bad Agent Runs with trace-eval

## Part 1: Synthetic Walkthrough — Bad Run → Diagnosis → Fix → Compare
[Keep existing synthetic bad→good example — it shows the full workflow clearly]

## Part 2: Real Claude Code Session (3,694 events)
[Use the real claude_code_real.jsonl results — 60.3/100, 144 errors]

## Part 3: Real OpenClaw Session (158 events)
[Use the real openclaw_before.jsonl results — 44.3/100]

## Summary Table
| Trace | Source | Events | Score | Top Issue |
|-------|--------|--------|-------|-----------|
| Bad run (synthetic) | Modeled after Hermes | 11 | 32.4 | No retrieval, 3 errors, context pressure |
| Good run (synthetic) | Modeled after Hermes | 8 | 98.9 | All clear |
| Claude Code (real) | Stillness project | 3,694 | 60.3 | 144 tool errors, no retrieval entrypoint |
| OpenClaw (real) | Real session | 158 | 44.3 | High error rate, low efficiency |
```

Write the full content to `examples/case_study.md`.

- [ ] **Step 2: Update README to reference case study prominently**

In the README, after the "See It in Action" section, add:

```markdown
## Case Study

See [examples/case_study.md](examples/case_study.md) for a complete walkthrough:
- Bad run → diagnosis → fix → before/after comparison
- Real Claude Code session (3,694 events, 144 errors diagnosed in under 1 second)
- Real OpenClaw session scoring with actionable flags
```

- [ ] **Step 3: Commit**

```bash
cd trace-eval
git add examples/case_study.md README.md
git commit -m "docs: update case study with real Claude Code + OpenClaw evidence"
```

---

### Task 2: Implement `--summary` Flag

**Files:**
- Modify: `trace_eval/report.py` — add `format_summary()` function
- Modify: `trace_eval/cli.py` — add `--summary` to `run` and `compare` subparsers, wire to `cmd_run`/`cmd_compare`
- Modify: `tests/test_report.py` — add tests for summary format
- Modify: `tests/test_cli.py` — add test for `--summary` CLI

- [ ] **Step 1: Write tests for summary format**

Add to `tests/test_report.py`:

```python
from trace_eval.report import format_summary
from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag


def _make_card_for_summary():
    return Scorecard(
        total_score=28.3,
        dimension_scores={
            "reliability": 0.0,
            "efficiency": 30.0,
            "retrieval": None,
            "tool_discipline": 92.0,
            "context": None,
        },
        dimension_confidence={
            "reliability": "high", "efficiency": "high",
            "retrieval": "low", "tool_discipline": "high", "context": "low",
        },
        all_flags=[
            FrictionFlag(
                id="reliability_errors", severity="medium",
                dimension="reliability", event_index=None,
                suggestion="Review 90 error(s) at event indices [...]",
            ),
            FrictionFlag(
                id="efficiency_high_tokens", severity="medium",
                dimension="efficiency", event_index=None,
                suggestion="High token usage detected",
            ),
            FrictionFlag(
                id="tool_redundant", severity="low",
                dimension="tool_discipline", event_index=3,
                suggestion="1 redundant tool call detected",
            ),
        ],
        scorable_dimensions=["reliability", "efficiency", "tool_discipline"],
        unscorable_dimensions=["retrieval", "context"],
        missing_required_judges=[],
        profile="default",
    )


def test_summary_has_score():
    card = _make_card_for_summary()
    text = format_summary(card)
    assert "28.3" in text


def test_summary_has_top_flags():
    card = _make_card_for_summary()
    text = format_summary(card)
    assert "reliability_errors" in text


def test_summary_has_diagnosis():
    card = _make_card_for_summary()
    text = format_summary(card)
    assert "Diagnosis" in text or "diagnosis" in text


def test_summary_is_concise():
    """Summary should be under 10 lines — designed for quick scanning."""
    card = _make_card_for_summary()
    text = format_summary(card)
    lines = [l for l in text.split("\n") if l.strip()]
    assert len(lines) <= 10
```

- [ ] **Step 2: Implement `format_summary()` in report.py**

Add to `trace_eval/report.py`:

```python
def format_summary(card: Scorecard) -> str:
    """Concise, agent-friendly summary output.

    Designed for both human quick-scanning and agent programmatic parsing.
    Always under 10 lines of output.
    """
    lines: list[str] = []

    # Line 1: Score
    lines.append(f"Score: {card.total_score:.1f}/100")

    # Line 2: Top 3 flags by severity
    sorted_flags = sorted(
        card.all_flags,
        key=lambda f: SEVERITY_ORDER.get(f.severity, 99),
    )
    top_flags = sorted_flags[:3]
    if top_flags:
        flag_parts = []
        for f in top_flags:
            if "error" in f.id:
                # Extract error count from suggestion if possible
                flag_parts.append(f"{f.id}")
            else:
                flag_parts.append(f.id)
        lines.append(f"Flags: {', '.join(flag_parts)}")

    # Line 3: Key dimension scores (only scorable ones that scored < 50)
    weak_dims = [
        dim for dim in card.scorable_dimensions
        if (card.dimension_scores.get(dim) or 100) < 50
    ]
    if weak_dims:
        dim_strs = [
            f"{dim}={card.dimension_scores[dim]:.0f}"
            for dim in weak_dims[:3]
        ]
        lines.append(f"Weak: {', '.join(dim_strs)}")

    # Line 4: Diagnosis
    diagnosis = _build_diagnosis(card, top_flags, weak_dims)
    lines.append(f"Diagnosis: {diagnosis}")

    return "\n".join(lines)


def _build_diagnosis(
    card: Scorecard,
    top_flags: list[FrictionFlag],
    weak_dims: list[str],
) -> str:
    """Build a 1-2 sentence diagnosis from scorecard signals."""
    parts: list[str] = []

    if card.total_score < 40:
        parts.append("Agent run with significant friction")
    elif card.total_score < 70:
        parts.append("Agent completed with notable issues")
    elif card.total_score < 90:
        parts.append("Agent run mostly healthy with minor issues")

    if "reliability" in weak_dims:
        rel_score = card.dimension_scores.get("reliability", 0) or 0
        error_flags = [f for f in card.all_flags if "error" in f.id]
        if error_flags:
            parts.append(f"fix errors ({rel_score:.0f}/100 reliability)")
        else:
            parts.append(f"low reliability ({rel_score:.0f}/100)")

    if "efficiency" in weak_dims:
        parts.append("reduce token/tool usage")

    if "retrieval" in card.unscorable_dimensions:
        parts.append("no retrieval strategy detected")

    if not parts:
        return "Run looks good"

    return ". ".join(parts) + "."
```

- [ ] **Step 3: Wire `--summary` to CLI**

In `trace_eval/cli.py`, modify `cmd_run`:

```python
def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    trace, adapter_report = load_trace_with_report(path)

    profile = getattr(args, "profile", None)
    judge_results = {name: fn(trace.events) for name, fn in JUDGES.items()}
    card = compute_scorecard(judge_results, profile=profile)

    if getattr(args, "summary", False):
        from trace_eval.report import format_summary
        print(format_summary(card))
    elif args.format == "json":
        print(format_json(card, adapter_report=adapter_report))
    else:
        print(format_text(card, adapter_report=adapter_report))

    return 0
```

Add `--summary` to the `run` subparser in `main()`:

```python
p_run.add_argument("--summary", action="store_true",
                   help="Concise output: score, top flags, diagnosis (for humans + agents)")
```

- [ ] **Step 4: Add `--summary` to `compare` command**

In `cmd_compare`, when `--summary` is set, output a compact diff:

```python
def cmd_compare(args: argparse.Namespace) -> int:
    # ... existing setup code ...

    before_card = compute_scorecard(before_results)
    after_card = compute_scorecard(after_results)

    if getattr(args, "summary", False):
        from trace_eval.report import format_summary
        delta = after_card.total_score - before_card.total_score
        print(f"Before: {before_card.total_score:.1f}/100")
        print(f"After:  {after_card.total_score:.1f}/100")
        print(f"Delta:  {'+' if delta > 0 else ''}{delta:.1f}")
        # Show resolved/new flag counts
        before_flag_ids = {f.id for f in before_card.all_flags}
        after_flag_ids = {f.id for f in after_card.all_flags}
        resolved = before_flag_ids - after_flag_ids
        new = after_flag_ids - before_flag_ids
        if resolved:
            print(f"Resolved: {len(resolved)} flags")
        if new:
            print(f"New: {len(new)} flags")
        return 0

    # ... rest of existing compare logic ...
```

Add `--summary` to the compare subparser:

```python
p_compare.add_argument("--summary", action="store_true",
                       help="Concise before/after comparison")
```

- [ ] **Step 5: Add CLI test for `--summary`**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify**

```bash
cd trace-eval
python -m pytest tests/test_report.py tests/test_cli.py -v
```

Expected: All existing tests pass + 5 new tests pass.

- [ ] **Step 7: Commit**

```bash
cd trace-eval
git add trace_eval/report.py trace_eval/cli.py tests/test_report.py tests/test_cli.py
git commit -m "feat: add --summary flag for concise human/agent output"
```

---

### Task 3: Add Cursor Converter

**Files:**
- Modify: `trace_eval/convert.py` — add `convert_cursor()` function, register in CONVERTERS dict
- Modify: `trace_eval/cli.py` — add `cursor` to format_type choices
- Create: `tests/test_convert_cursor.py` — test Cursor converter
- Create: `examples/cursor_sample.jsonl` — sample Cursor session for testing

- [ ] **Step 1: Create sample Cursor session for testing**

Cursor agent transcripts use this format:
```jsonl
{"role":"user","message":{"content":[{"type":"text","text":"<user_query>\nBuild a REST API\n</user_query>"}]}}
{"role":"assistant","message":{"content":[{"type":"text","text":"I'll help you build a REST API."}]}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"read_file","arguments":{"path":"src/app.py"}},{"type":"toolCall","name":"bash","arguments":{"command":"ls -la"}}]}}
{"role":"toolResult","message":{"toolName":"read_file","content":[{"type":"text","text":"# app.py content"}]}}
{"role":"toolResult","message":{"toolName":"bash","isError":true,"content":[{"type":"text","text":"exit code 1\ncommand not found: foo"}]}}
{"role":"assistant","message":{"content":[{"type":"text","text":"Done."}],"usage":{"input":5000,"output":200},"stopReason":"end_turn"}}
```

Create `examples/cursor_sample.jsonl`:

```jsonl
{"role":"user","message":{"content":[{"type":"text","text":"<user_query>\nRefactor the database layer to use connection pooling\n</user_query>"}]}}
{"role":"assistant","message":{"content":[{"type":"text","text":"I'll refactor the database layer to use connection pooling."}],"usage":{"input":3200,"output":80},"stopReason":"end_turn"}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"read_file","arguments":{"path":"src/db.py"}}]}}
{"role":"toolResult","message":{"toolName":"read_file","content":[{"type":"text","text":"import sqlite3\n\ndef get_connection():\n    return sqlite3.connect('app.db')"}]}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"edit","arguments":{"path":"src/db.py","oldText":"import sqlite3","newText":"import sqlite3\nfrom queue import Queue"}}]}}
{"role":"toolResult","message":{"toolName":"edit","content":[{"type":"text","text":"File edited successfully"}]}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"bash","arguments":{"command":"python -m pytest tests/test_db.py"}}]}}
{"role":"toolResult","message":{"toolName":"bash","isError":true,"content":[{"type":"text","text":"exit code 1\nModuleNotFoundError: No module named 'pytest'"}]}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"bash","arguments":{"command":"pip install pytest"}}]}}
{"role":"toolResult","message":{"toolName":"bash","content":[{"type":"text","text":"Successfully installed pytest-8.0.0"}]}}
{"role":"assistant","message":{"content":[{"type":"toolCall","name":"bash","arguments":{"command":"python -m pytest tests/test_db.py"}}]}}
{"role":"toolResult","message":{"toolName":"bash","content":[{"type":"text","text":"2 passed in 0.3s"}]}}
{"role":"assistant","message":{"content":[{"type":"text","text":"Done! Database now uses connection pooling."}],"usage":{"input":4500,"output":120},"stopReason":"end_turn"}}
```

- [ ] **Step 2: Write Cursor converter tests**

Create `tests/test_convert_cursor.py`:

```python
import json
import pytest
from pathlib import Path
from trace_eval.convert import convert_cursor, _detect_format


def test_convert_cursor_basic(tmp_path):
    """Test basic Cursor session conversion."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}) + "\n"
        + json.dumps({"role": "assistant", "message": {"content": [{"type": "text", "text": "hi"}], "usage": {"input": 100, "output": 50}, "stopReason": "end_turn"}}) + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 2
    assert events[0]["actor"] == "user"
    assert events[0]["event_type"] == "message"
    assert events[1]["actor"] == "assistant"
    assert events[1]["event_type"] == "llm_call"
    assert events[1]["tokens_in"] == 100
    assert events[1]["tokens_out"] == 50


def test_convert_cursor_tool_calls(tmp_path):
    """Test Cursor tool_call extraction."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "assistant", "message": {"content": [{"type": "toolCall", "name": "read_file", "arguments": {"path": "app.py"}}]}}) + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_call"
    assert events[0]["tool_name"] == "read_file"
    assert events[0]["tool_args"] == {"path": "app.py"}


def test_convert_cursor_tool_result_error(tmp_path):
    """Test Cursor error detection in tool results."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "toolResult", "message": {"toolName": "bash", "isError": True, "content": [{"type": "text", "text": "exit code 1\ncommand not found"}]}}) + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_result"
    assert events[0]["status"] == "error"


def test_convert_cursor_tool_result_success(tmp_path):
    """Test Cursor successful tool result."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "toolResult", "message": {"toolName": "edit", "content": [{"type": "text", "text": "File edited successfully"}]}}) + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_result"
    assert events[0]["status"] is None


def test_cursor_auto_detect(tmp_path):
    """Test auto-detection of Cursor format."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}) + "\n"
    )
    fmt = _detect_format(sample)
    assert fmt == "cursor"
```

- [ ] **Step 3: Implement `convert_cursor()` in convert.py**

Add to `trace_eval/convert.py`:

```python
def convert_cursor(input_path: Path) -> list[dict]:
    """Convert a Cursor agent transcript JSONL to canonical events."""
    with open(input_path) as f:
        raw_events = [json.loads(l) for l in f if l.strip()]

    # Extract session ID from file path or first event
    session_id = input_path.stem  # Use filename as session ID

    trace_id = f"cursor_{session_id[:8]}"

    canonical = []
    idx = 0

    for e in raw_events:
        role = e.get("role", "")
        msg = e.get("message", {})
        content_items = msg.get("content", [])
        usage = msg.get("usage", {})
        stop_reason = msg.get("stopReason")

        if role == "user":
            # User message
            text_parts = [
                c.get("text", "") for c in content_items
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            if text_parts:
                canonical.append({
                    "event_index": idx,
                    "actor": "user",
                    "event_type": "message",
                    "timestamp": e.get("timestamp", ""),
                    "status": None,
                    "session_id": session_id,
                    "schema_version": "v1",
                    "trace_id": trace_id,
                })
                idx += 1

        elif role == "assistant":
            # Emit tool_call events
            for c in content_items:
                if isinstance(c, dict) and c.get("type") == "toolCall":
                    tool_name = c.get("name", "unknown")
                    tool_args = c.get("arguments", {})
                    canonical.append({
                        "event_index": idx,
                        "actor": "assistant",
                        "event_type": "tool_call",
                        "timestamp": e.get("timestamp", ""),
                        "status": None,
                        "session_id": session_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args if isinstance(tool_args, dict) else None,
                    })
                    idx += 1

            # Emit LLM call event
            status = None
            if stop_reason == "error":
                status = "error"

            tokens_in = None
            tokens_out = None
            if isinstance(usage, dict):
                ti = usage.get("input")
                to = usage.get("output")
                if ti is not None and ti > 0:
                    tokens_in = int(ti)
                if to is not None and to > 0:
                    tokens_out = int(to)

            canonical.append({
                "event_index": idx,
                "actor": "assistant",
                "event_type": "llm_call",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            })
            idx += 1

        elif role == "toolResult":
            tool_name = msg.get("toolName", "unknown")
            content_texts = []
            for c in content_items:
                if isinstance(c, dict):
                    content_texts.append(c.get("text", ""))

            content = "\n".join(content_texts)
            is_error = msg.get("isError", False)

            has_error = is_error or _cc_detect_error(content)
            status = "error" if has_error else None

            tool_args = None
            if content.strip().startswith("{"):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        tool_args = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            canonical.append({
                "event_index": idx,
                "actor": "tool",
                "event_type": "tool_result",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            })
            idx += 1

    return canonical
```

- [ ] **Step 4: Register Cursor converter**

In `convert.py`, update the CONVERTERS dict:

```python
CONVERTERS = {
    "claude-code": convert_claude_code,
    "claude_code": convert_claude_code,
    "openclaw": convert_openclaw,
    "cursor": convert_cursor,
}
```

Update `_detect_format()` to detect Cursor:

```python
def _detect_format(input_path: Path) -> str:
    """Auto-detect trace format from the file content."""
    with open(input_path) as f:
        lines = []
        for i, line in enumerate(f):
            if i >= 5:
                break
            line = line.strip()
            if line:
                lines.append(line)

    for line in lines:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("type") == "session" and "cwd" in data:
            return "openclaw"
        if data.get("type") in ("permission-mode", "user", "assistant", "tool_result"):
            return "claude_code"
        if "event_type" in data:
            return "canonical"
        # Cursor format: has "role" field with "user", "assistant", or "toolResult"
        if "role" in data and data["role"] in ("user", "assistant", "toolResult"):
            return "cursor"

    return "unknown"
```

- [ ] **Step 5: Update CLI to accept cursor format**

In `cli.py`, update the convert subparser:

```python
p_convert.add_argument("format_type", nargs="?", default=None,
                       choices=["claude-code", "openclaw", "cursor"],
                       help="Trace format (auto-detected if omitted)")
```

- [ ] **Step 6: Run tests and verify**

```bash
cd trace-eval
python -m pytest tests/test_convert_cursor.py -v
```

Also verify the converter works end-to-end:

```bash
cd trace-eval
python -m trace_eval.cli convert examples/cursor_sample.jsonl -o /tmp/cursor_canonical.jsonl
python -m trace_eval.cli run /tmp/cursor_canonical.jsonl
```

- [ ] **Step 7: Commit**

```bash
cd trace-eval
git add trace_eval/convert.py trace_eval/cli.py tests/test_convert_cursor.py examples/cursor_sample.jsonl
git commit -m "feat: add Cursor agent transcript converter"
```

---

### Task 4: Tighten README Onboarding

**Files:**
- Modify: `README.md` — restructure Quick Start for first-run clarity

- [ ] **Step 1: Rewrite README Quick Start section**

Replace the current "Quick Start" section with a clearer 5-step flow:

```markdown
## Quick Start

```bash
# 1. Install
pip install trace-eval

# 2. Convert your agent trace (auto-detects format: Claude Code, OpenClaw, Cursor)
trace-eval convert ~/.claude/projects/.../session.jsonl -o trace.jsonl

# 3. Score it
trace-eval run trace.jsonl

# 4. Compare before/after a fix
trace-eval compare before.jsonl after.jsonl

# 5. Gate your CI
trace-eval ci trace.jsonl --min-score 80
```

For a complete walkthrough with real examples, see [examples/case_study.md](examples/case_study.md).
```

- [ ] **Step 2: Update "What's Coming" section**

Remove items that are already done (profiles, score profiles):

```markdown
## What's Coming

- More adapters (OpenAI traces, LangSmith, LangGraph, custom formats)
- Baseline comparison (cost vs similar tasks)
- Parallelization analysis in Tool Discipline
```

- [ ] **Step 3: Update Scoring Profiles table**

Add a "Scoring Profiles" section to document the profiles that now exist:

```markdown
## Scoring Profiles

| Profile | Reliability | Efficiency | Retrieval | Tool Discipline | Context |
|---------|------------|------------|-----------|-----------------|---------|
| **default** | 35% | 20% | 20% | 15% | 10% |
| **coding_agent** | 40% | 25% | 0% | 25% | 10% |
| **rag_agent** | 30% | 15% | 30% | 15% | 10% |

```bash
trace-eval run trace.jsonl --profile coding_agent
```

Unscorable dimensions (e.g., retrieval for coding agents) are automatically excluded and their weight redistributed.
```

- [ ] **Step 4: Add `--summary` documentation**

Add to the Agent Integration section:

```markdown
### Quick Summary (`--summary`)

For a concise output designed for both humans and agents:

```bash
$ trace-eval run trace.jsonl --summary
Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens, tool_redundant
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. Fix errors (0/100 reliability). Reduce token/tool usage.
```

```

- [ ] **Step 5: Bump version to 0.3.0**

```python
# In pyproject.toml
version = "0.3.0"
```

- [ ] **Step 6: Run full test suite**

```bash
cd trace-eval
python -m pytest tests/ -v
```

Expected: All tests pass (68 + new tests from Tasks 2 and 3).

- [ ] **Step 7: Commit**

```bash
cd trace-eval
git add README.md pyproject.toml
git commit -m "docs: tighten README onboarding for v0.3.0"
```

---

### Task 5: Next 3 Highest-Leverage Adoption Moves

**Files:**
- Modify: `SPRINT5_DELIVERABLES.md` — document recommendations

- [ ] **Step 1: Write Sprint 5 Deliverables Report**

Create `SPRINT5_DELIVERABLES.md` with:

```markdown
# Sprint 5 Deliverable Report
Date: 2026-04-17

## Deliverables

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| Public case study | DONE | examples/case_study.md — synthetic bad→good + real Claude Code + real OpenClaw |
| --summary flag | DONE | trace-eval run --summary, trace-eval compare --summary |
| Cursor converter | DONE | convert_cursor(), auto-detect, tests pass |
| README onboarding | DONE | 5-step quick start: install → convert → run → compare → ci |
| v0.3.0 PyPI ready | DONE | version bumped, all tests pass |

## Next 3 Highest-Leverage Adoption Moves

### Move 1: Publish the case study publicly (1-2 hours)

Post the case study as:
- A README section that links to examples/case_study.md
- A blog post or social thread showing "144 errors diagnosed in under 1 second"
- A GitHub issue or discussion that people can reference

**Why:** Proof of value is the #1 adoption driver. People need to see real results before they try.

### Move 2: Get 3-5 external users to run `pip install trace-eval` (1-3 days)

**Why:** Watching real users hit friction is the best product feedback. Set up:
- Share the PyPI link with 3-5 people who use AI coding agents
- Ask them to run `trace-eval convert` on a recent session + `trace-eval run`
- Watch where they get stuck — that tells you the next real product move

### Move 3: Add CI/CD integration example (1 hour)

**Why:** Teams want to gate their agent runs. A `.github/workflows/trace-eval.yml` example showing how to run trace-eval in CI would be a concrete, copy-pasteable adoption driver.

```yaml
name: Agent Quality Gate
on: [push]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install trace-eval
      - run: trace-eval convert agent-trace.jsonl -o trace.jsonl
      - run: trace-eval ci trace.jsonl --min-score 70 --profile coding_agent
```

## What NOT to do next

- LLM-as-judge
- Dashboards
- Auto-fix
- Major framework redesign
- Many new profiles
- Broad adapter expansion ("support everything")
```

- [ ] **Step 2: Commit**

```bash
cd trace-eval
git add SPRINT5_DELIVERABLES.md
git commit -m "docs: Sprint 5 deliverable report + next adoption moves"
```
