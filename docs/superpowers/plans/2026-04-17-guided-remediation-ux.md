# Guided Remediation + UX Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop from diagnosis → recommendation → approval → improvement. Add trace discovery, clearer scoring, guided remediation, and safe approval-based autofix generation.

**Architecture:** All changes are additive. New modules: `locate.py` (trace discovery), `remediation.py` (rule-based suggestion engine), `autofix.py` (report/config/patch generation). New CLI commands: `locate`, `remediate`. New flags: `--next-steps` on `run`. Existing `--summary` enhanced for agent consumption.

**Tech Stack:** Python 3.11+, trace-eval v0.3.0 codebase, no new dependencies

---

### Task 1: Add `trace-eval locate` Command

**Files:**
- Create: `trace_eval/locate.py` — trace file discovery engine
- Modify: `trace_eval/cli.py` — add `locate` subparser + `cmd_locate()`
- Create: `tests/test_locate.py` — tests for locate command

- [ ] **Step 1: Create `trace_eval/locate.py` with locate_engine()**

```python
"""Locate common agent trace files on the filesystem."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AgentType = Literal["claude-code", "cursor", "openclaw", "all"]


@dataclass
class TraceLocation:
    path: str
    agent_type: str
    size_bytes: int
    modified_time: str  # ISO 8601
    project_name: str


# Common trace directory patterns
SEARCH_PATHS: dict[str, list[str]] = {
    "claude-code": [
        os.path.expanduser("~/.claude/projects"),
    ],
    "cursor": [
        os.path.expanduser("~/.cursor/projects"),
    ],
    "openclaw": [
        os.path.expanduser("~/.openclaw"),
    ],
}


def _find_files(base_dir: str, pattern: str = "*.jsonl", max_depth: int = 5) -> list[Path]:
    """Find files matching pattern within max_depth levels."""
    base = Path(base_dir)
    if not base.exists():
        return []
    results = []
    for depth in range(max_depth + 1):
        for p in base.glob(f"{'*/' * depth}{pattern}"):
            if p.is_file():
                results.append(p)
    return results


def _is_valid_trace(path: Path, agent_type: str) -> bool:
    """Quick validation: read first line and check for recognizable type signatures."""
    try:
        with open(path) as f:
            first_line = f.readline(4096)
        if not first_line:
            return False
        data = json.loads(first_line)
        if agent_type == "claude-code":
            return "type" in data and data["type"] in (
                "permission-mode", "user", "assistant", "tool_result",
                "file-history-snapshot",
            )
        elif agent_type == "cursor":
            return "role" in data and data["role"] in (
                "user", "assistant", "toolResult",
            )
        elif agent_type == "openclaw":
            return "type" in data and data["type"] in (
                "session", "message", "model_change",
            )
        return True
    except (json.JSONDecodeError, OSError):
        return False


def _get_agent_type_for_file(path: Path) -> str:
    """Determine agent type from file content."""
    try:
        with open(path) as f:
            first_line = f.readline(4096)
        if not first_line:
            return "unknown"
        data = json.loads(first_line)
        if "role" in data:
            return "cursor"
        if data.get("type") == "session" and "cwd" in data:
            return "openclaw"
        if "type" in data:
            return "claude-code"
        return "unknown"
    except (json.JSONDecodeError, OSError):
        return "unknown"


def _time_ago(timestamp: float) -> str:
    """Human-readable time ago string."""
    diff = time.time() - timestamp
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff // 60)}m ago"
    elif diff < 86400:
        return f"{int(diff // 3600)}h ago"
    else:
        return f"{int(diff // 86400)}d ago"


def locate(
    agent_type: AgentType = "all",
    limit: int = 20,
    hours: int = 48,
) -> list[TraceLocation]:
    """Locate agent trace files on the filesystem.

    Args:
        agent_type: Which agent traces to find. "all" searches all known agents.
        limit: Maximum number of results to return.
        hours: Only return files modified within the last N hours.

    Returns:
        List of TraceLocation objects, sorted by modification time (newest first).
    """
    results: list[TraceLocation] = []
    cutoff = time.time() - (hours * 3600)

    agents_to_search = (
        ["claude-code", "cursor", "openclaw"]
        if agent_type == "all"
        else [agent_type]
    )

    for agent in agents_to_search:
        base_dirs = SEARCH_PATHS.get(agent, [])
        for base_dir in base_dirs:
            if not os.path.isdir(base_dir):
                continue

            for path in _find_files(base_dir, "*.jsonl", max_depth=5):
                try:
                    stat = path.stat()
                except OSError:
                    continue

                if stat.st_mtime < cutoff:
                    continue

                # Validate it's a real trace
                if not _is_valid_trace(path, agent):
                    continue

                # Extract project name from path
                rel = path.relative_to(base_dir)
                project_name = rel.parts[0] if rel.parts else str(path.parent.name)

                results.append(TraceLocation(
                    path=str(path),
                    agent_type=agent,
                    size_bytes=stat.st_size,
                    modified_time=_time_ago(stat.st_mtime),
                    project_name=project_name,
                ))

    # Sort by modification time (newest first) — use actual mtime for sorting
    results_with_mtime = []
    for r in results:
        try:
            mtime = Path(r.path).stat().st_mtime
        except OSError:
            mtime = 0
        results_with_mtime.append((mtime, r))

    results_with_mtime.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in results_with_mtime[:limit]]


def format_locate(locations: list[TraceLocation]) -> str:
    """Format locate results for display."""
    if not locations:
        return "No recent trace files found."

    lines = [f"Found {len(locations)} recent trace file(s):\n"]

    # Group by agent type for readability
    by_agent: dict[str, list[TraceLocation]] = {}
    for loc in locations:
        by_agent.setdefault(loc.agent_type, []).append(loc)

    for agent, locs in sorted(by_agent.items()):
        lines.append(f"  {agent}:")
        for loc in locs:
            size_kb = loc.size_bytes // 1024
            lines.append(f"    {loc.modified_time:>10s}  {size_kb:>6d}KB  {loc.project_name}")
            lines.append(f"               {loc.path}")

    lines.append("")
    lines.append("To score a trace: trace-eval run <path>")
    lines.append("To convert first: trace-eval convert <path> -o trace.jsonl")
    return "\n".join(lines)
```

- [ ] **Step 2: Add locate command to CLI**

In `trace_eval/cli.py`, add `cmd_locate()`:

```python
def cmd_locate(args: argparse.Namespace) -> int:
    from trace_eval.locate import locate, format_locate
    locations = locate(
        agent_type=getattr(args, "agent_type", "all"),
        limit=getattr(args, "limit", 20),
        hours=getattr(args, "hours", 48),
    )
    print(format_locate(locations))
    return 0
```

Add subparser in `main()`:

```python
p_locate = sub.add_parser("locate", help="Find recent agent trace files")
p_locate.add_argument("agent_type", nargs="?", default="all",
                      choices=["claude-code", "cursor", "openclaw", "all"],
                      help="Agent type to search for (default: all)")
p_locate.add_argument("--limit", type=int, default=20,
                      help="Maximum results (default: 20)")
p_locate.add_argument("--hours", type=int, default=48,
                      help="Search window in hours (default: 48)")
```

Add to commands dict:

```python
"locate": cmd_locate,
```

- [ ] **Step 3: Write locate tests**

Create `tests/test_locate.py`:

```python
import json
import pytest
from pathlib import Path
from trace_eval.locate import locate, _is_valid_trace, format_locate


def test_is_valid_trace_claude_code(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    assert _is_valid_trace(f, "claude-code") is True


def test_is_valid_trace_cursor(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"role": "user", "message": {"content": []}}) + "\n")
    assert _is_valid_trace(f, "cursor") is True


def test_is_valid_trace_openclaw(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"type": "session", "cwd": "/tmp"}) + "\n")
    assert _is_valid_trace(f, "openclaw") is True


def test_is_valid_trace_invalid(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text("not json\n")
    assert _is_valid_trace(f, "claude-code") is False


def test_format_locate_empty():
    text = format_locate([])
    assert "No recent trace files" in text


def test_format_locate_with_results(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text(json.dumps({"type": "user"}) + "\n")
    locs = [
        type("TraceLocation", (), {
            "agent_type": "claude-code",
            "path": str(f),
            "size_bytes": 1024,
            "modified_time": "5m ago",
            "project_name": "my-project",
        })()
    ]
    text = format_locate(locs)
    assert "my-project" in text
    assert "claude-code" in text
```

- [ ] **Step 4: Run tests**

```bash
cd trace-eval
python -m pytest tests/test_locate.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd trace-eval
git add trace_eval/locate.py trace_eval/cli.py tests/test_locate.py
git commit -m "feat: add trace-eval locate for discovering agent trace files"
```

---

### Task 2: Clearer Score Interpretation

**Files:**
- Modify: `trace_eval/report.py` — add `ScoreRating` enum, rating labels to format_text and format_summary
- Modify: `trace_eval/scoring.py` — add `Rating` to Scorecard dataclass
- Modify: `trace_eval/cli.py` — wire rating to output
- Modify: `tests/test_report.py` — add rating tests
- Modify: `tests/test_scoring.py` — add rating computation tests

- [ ] **Step 1: Add ScoreRating enum and computation**

In `trace_eval/report.py`, add at top:

```python
class ScoreRating(Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    NEEDS_WORK = "Needs Work"
    CRITICAL = "Critical"


def compute_rating(score: float) -> ScoreRating:
    """Map a 0-100 score to a human-readable rating."""
    if score >= 90:
        return ScoreRating.EXCELLENT
    elif score >= 70:
        return ScoreRating.GOOD
    elif score >= 40:
        return ScoreRating.NEEDS_WORK
    else:
        return ScoreRating.CRITICAL
```

Add to imports at top: `from enum import Enum`

- [ ] **Step 2: Add rating field to Scorecard**

In `trace_eval/scoring.py`, add to `Scorecard` dataclass:

```python
rating: str  # "Excellent", "Good", "Needs Work", "Critical"
```

In `compute_scorecard()`, add rating computation before the return:

```python
from trace_eval.report import compute_rating

rating = compute_rating(round(total_score, 2))

return Scorecard(
    ...existing fields...
    rating=rating.value,
)
```

- [ ] **Step 3: Update format_text to show rating**

In `trace_eval/report.py`, `format_text()`, change the header line:

```python
lines.append(f"  TRACE-EVAL SCORECARD  Total: {card.total_score:.1f}/100  [{card.rating}]")
```

- [ ] **Step 4: Update format_summary to show rating**

In `format_summary()`, change line 1:

```python
lines.append(f"Score: {card.total_score:.1f}/100 [{card.rating}]")
```

- [ ] **Step 5: Update test_report.py for rating**

In `tests/test_report.py`, update `_make_card()` and `_make_bad_card()` and `_make_good_card()` to include `rating` field. Add `rating="Needs Work"` or `rating="Excellent"` as appropriate.

Add a test:

```python
from trace_eval.report import compute_rating, ScoreRating


def test_rating_thresholds():
    assert compute_rating(95) == ScoreRating.EXCELLENT
    assert compute_rating(90) == ScoreRating.EXCELLENT
    assert compute_rating(89) == ScoreRating.GOOD
    assert compute_rating(70) == ScoreRating.GOOD
    assert compute_rating(69) == ScoreRating.NEEDS_WORK
    assert compute_rating(40) == ScoreRating.NEEDS_WORK
    assert compute_rating(39) == ScoreRating.CRITICAL
    assert compute_rating(0) == ScoreRating.CRITICAL
```

- [ ] **Step 6: Update test_scoring.py for rating**

In `tests/test_scoring.py`, update `_make_result()` helper tests to include rating in expected Scorecard. Update all `compute_scorecard` call assertions to expect `rating` field.

- [ ] **Step 7: Run tests**

```bash
cd trace-eval
python -m pytest tests/test_report.py tests/test_scoring.py tests/test_cli.py -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
cd trace-eval
git add trace_eval/report.py trace_eval/scoring.py tests/test_report.py tests/test_scoring.py
git commit -m "feat: add score rating labels (Excellent/Good/Needs Work/Critical)"
```

---

### Task 3: Add Guided Remediation

**Files:**
- Create: `trace_eval/remediation.py` — rule-based suggestion engine
- Modify: `trace_eval/cli.py` — add `remediate` subparser + `cmd_remediate()`, add `--next-steps` to `run`
- Create: `tests/test_remediation.py` — tests for remediation engine

- [ ] **Step 1: Create `trace_eval/remediation.py`**

```python
"""Rule-based guided remediation: diagnose → recommend → assess automation safety."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag

ACTION_TYPES = {
    "reduce_retries": {
        "label": "Reduce tool call retries",
        "description": "Add branch guards or pre-conditions before tool calls to avoid repeated failures.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": True,
    },
    "reduce_prompt_size": {
        "label": "Reduce prompt scope",
        "description": "Break tasks into smaller steps to reduce token usage and context pressure.",
        "confidence": "medium",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "fix_errors": {
        "label": "Fix command errors",
        "description": "Review and fix failed commands. Common causes: missing dependencies, wrong paths, permission issues.",
        "confidence": "high",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "switch_profile": {
        "label": "Use appropriate scoring profile",
        "description": "Switch to 'coding_agent' profile if retrieval is not applicable to your workflow.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": False,
    },
    "reduce_tool_calls": {
        "label": "Reduce tool call volume",
        "description": "Batch operations where possible. Combine multiple file reads/writes into single calls.",
        "confidence": "medium",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "improve_retrieval": {
        "label": "Improve retrieval strategy",
        "description": "Use canonical retrieval entrypoint instead of fallback search.",
        "confidence": "high",
        "safe_to_automate": False,
        "requires_approval": True,
    },
    "add_ci_gate": {
        "label": "Add CI quality gate",
        "description": "Add trace-eval CI gate to prevent low-quality agent runs from being merged.",
        "confidence": "high",
        "safe_to_automate": True,
        "requires_approval": True,
    },
}


@dataclass
class RemediationAction:
    action_type: str
    label: str
    description: str
    confidence: str  # "high", "medium", "low"
    safe_to_automate: bool
    requires_approval: bool
    triggered_by: str  # flag ID or dimension that triggered this


def analyze(card: Scorecard) -> list[RemediationAction]:
    """Analyze a scorecard and return recommended remediation actions.

    Rules are deterministic: specific flag patterns and dimension scores
    map to specific recommended actions.
    """
    actions: list[RemediationAction] = []
    flag_ids = {f.id for f in card.all_flags}
    dim_scores = card.dimension_scores

    # Rule 1: reliability errors → fix_errors
    if "reliability_errors" in flag_ids:
        actions.append(_make_action("fix_errors", "reliability_errors"))

    # Rule 2: low reliability score → fix_errors (broader catch)
    if dim_scores.get("reliability") is not None and dim_scores["reliability"] < 50:
        if not any(a.action_type == "fix_errors" for a in actions):
            actions.append(_make_action("fix_errors", "low_reliability_score"))

    # Rule 3: high token usage → reduce_prompt_size
    if "efficiency_high_tokens" in flag_ids:
        actions.append(_make_action("reduce_prompt_size", "efficiency_high_tokens"))

    # Rule 4: high tool calls → reduce_tool_calls
    if "efficiency_high_tool_calls" in flag_ids:
        actions.append(_make_action("reduce_tool_calls", "efficiency_high_tool_calls"))

    # Rule 5: tool retries/redundant → reduce_retries
    if "tool_retries" in flag_ids or "tool_redundant" in flag_ids:
        actions.append(_make_action("reduce_retries", "tool_discipline_issue"))

    # Rule 6: retrieval issues → improve_retrieval
    retrieval_flags = {"retrieval_no_entrypoint", "retrieval_deprecated_file", "retrieval_fallback_search"}
    if flag_ids & retrieval_flags:
        actions.append(_make_action("improve_retrieval", "retrieval_issue"))

    # Rule 7: retrieval N/A for coding agent → suggest profile switch
    if "retrieval" in card.unscorable_dimensions and card.profile == "default":
        actions.append(_make_action("switch_profile", "retrieval_not_applicable"))

    # Rule 8: no CI gate suggestion if score < 80
    if card.total_score < 80 and "add_ci_gate" not in {a.action_type for a in actions}:
        actions.append(_make_action("add_ci_gate", "low_overall_score"))

    # Sort by confidence (high first), then by action type
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: confidence_order.get(a.confidence, 9))

    return actions[:5]  # Top 5 actions


def _make_action(action_type: str, triggered_by: str) -> RemediationAction:
    template = ACTION_TYPES[action_type]
    return RemediationAction(
        action_type=action_type,
        label=template["label"],
        description=template["description"],
        confidence=template["confidence"],
        safe_to_automate=template["safe_to_automate"],
        requires_approval=template["requires_approval"],
        triggered_by=triggered_by,
    )


def format_remediation(actions: list[RemediationAction], card: Scorecard) -> str:
    """Format remediation actions for display."""
    if not actions:
        return "No recommended actions. Score looks good."

    lines = [
        "=" * 60,
        f"  REMEDIATION RECOMMENDATIONS  Score: {card.total_score:.1f}/100 [{card.rating}]",
        "=" * 60,
        "",
    ]

    for i, action in enumerate(actions, 1):
        approval_note = " [AUTO-SAFE]" if action.safe_to_automate and not action.requires_approval else ""
        approval_note += " [REQUIRES APPROVAL]" if action.requires_approval else ""
        lines.append(f"  {i}. {action.label}{approval_note}")
        lines.append(f"     {action.description}")
        lines.append(f"     Confidence: {action.confidence}")
        lines.append("")

    lines.append("To auto-apply safe fixes: trace-eval remediate trace.jsonl --apply-safe")
    lines.append("To generate full report: trace-eval remediate trace.jsonl --report")
    return "\n".join(lines)
```

- [ ] **Step 2: Wire remediation to CLI**

In `trace_eval/cli.py`, add `cmd_remediate()`:

```python
def cmd_remediate(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    trace, adapter_report = load_trace_with_report(path)
    profile = getattr(args, "profile", None)
    judge_results = {name: fn(trace.events) for name, fn in JUDGES.items()}
    card = compute_scorecard(judge_results, profile=profile)

    from trace_eval.remediation import analyze, format_remediation
    actions = analyze(card)
    print(format_remediation(actions, card))

    # If --apply-safe flag, also generate safe fixes
    if getattr(args, "apply_safe", False):
        from trace_eval.autofix import apply_safe_fixes
        fixes = apply_safe_fixes(actions, card, path)
        print("\n" + "=" * 60)
        print("  SAFE FIXES APPLIED")
        print("=" * 60)
        for fix in fixes:
            print(f"  [+] {fix['label']}: {fix['path']}")

    # If --report flag, generate markdown report
    if getattr(args, "report", False):
        from trace_eval.autofix import generate_remediation_report
        report_path = generate_remediation_report(actions, card, path)
        print(f"\n  Report saved: {report_path}")

    return 0
```

Add subparsers in `main()`:

```python
# remediate
p_remediate = sub.add_parser("remediate", help="Get recommended actions to improve agent run quality")
p_remediate.add_argument("trace", help="Path to trace file")
p_remediate.add_argument("--profile", choices=list(PROFILES.keys()), default=None,
                         help="Scoring profile")
p_remediate.add_argument("--apply-safe", action="store_true",
                         help="Apply safe fixes automatically")
p_remediate.add_argument("--report", action="store_true",
                         help="Generate full markdown remediation report")
```

Also add `--next-steps` to the `run` subparser as a shortcut:

```python
p_run.add_argument("--next-steps", action="store_true",
                   help="Show remediation recommendations after scorecard")
```

In `cmd_run()`, after printing the scorecard:

```python
if getattr(args, "next_steps", False):
    from trace_eval.remediation import analyze, format_remediation
    actions = analyze(card)
    print("\n" + format_remediation(actions, card))
```

- [ ] **Step 3: Write remediation tests**

Create `tests/test_remediation.py`:

```python
import pytest
from trace_eval.remediation import analyze, ACTION_TYPES
from trace_eval.scoring import Scorecard
from trace_eval.schema import FrictionFlag


def _make_card(flags=None, dim_scores=None, unscorable=None, profile="default", total_score=50):
    return Scorecard(
        total_score=total_score,
        dimension_scores=dim_scores or {
            "reliability": 50.0, "efficiency": 50.0, "retrieval": 50.0,
            "tool_discipline": 50.0, "context": 50.0,
        },
        dimension_confidence={
            "reliability": "high", "efficiency": "high", "retrieval": "high",
            "tool_discipline": "high", "context": "high",
        },
        all_flags=flags or [],
        scorable_dimensions=["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
        unscorable_dimensions=unscorable or [],
        missing_required_judges=[],
        profile=profile,
        rating="Needs Work",
    )


def test_fix_errors_when_reliability_flag_present():
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium",
                     dimension="reliability", event_index=None,
                     suggestion="Review errors"),
    ])
    actions = analyze(card)
    assert any(a.action_type == "fix_errors" for a in actions)


def test_switch_profile_when_retrieval_unscorable():
    card = _make_card(unscorable=["retrieval"], profile="default")
    actions = analyze(card)
    assert any(a.action_type == "switch_profile" for a in actions)


def test_no_switch_profile_when_already_coding_agent():
    card = _make_card(unscorable=["retrieval"], profile="coding_agent")
    actions = analyze(card)
    assert not any(a.action_type == "switch_profile" for a in actions)


def test_reduce_prompt_size_when_high_tokens():
    card = _make_card(flags=[
        FrictionFlag(id="efficiency_high_tokens", severity="medium",
                     dimension="efficiency", event_index=None,
                     suggestion="Reduce tokens"),
    ])
    actions = analyze(card)
    assert any(a.action_type == "reduce_prompt_size" for a in actions)


def test_actions_sorted_by_confidence():
    card = _make_card(flags=[
        FrictionFlag(id="efficiency_high_tool_calls", severity="low",
                     dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="reliability_errors", severity="medium",
                     dimension="reliability", event_index=None, suggestion=""),
    ], total_score=30)
    actions = analyze(card)
    confidences = [a.confidence for a in actions]
    # High confidence actions should come first
    assert confidences.index("high") < confidences.index("medium")


def test_max_5_actions():
    # Create card that triggers many rules
    card = _make_card(flags=[
        FrictionFlag(id="reliability_errors", severity="medium", dimension="reliability", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tokens", severity="medium", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="efficiency_high_tool_calls", severity="low", dimension="efficiency", event_index=None, suggestion=""),
        FrictionFlag(id="tool_redundant", severity="low", dimension="tool_discipline", event_index=None, suggestion=""),
        FrictionFlag(id="retrieval_no_entrypoint", severity="critical", dimension="retrieval", event_index=None, suggestion=""),
    ], dim_scores={"reliability": 10.0, "efficiency": 20.0, "retrieval": 0.0, "tool_discipline": 30.0, "context": 40.0}, total_score=20)
    actions = analyze(card)
    assert len(actions) <= 5


def test_safe_to_automate_actions():
    card = _make_card(unscorable=["retrieval"], profile="default", total_score=30)
    actions = analyze(card)
    profile_action = next(a for a in actions if a.action_type == "switch_profile")
    assert profile_action.safe_to_automate is True
```

- [ ] **Step 4: Run tests**

```bash
cd trace-eval
python -m pytest tests/test_remediation.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
cd trace-eval
git add trace_eval/remediation.py trace_eval/cli.py tests/test_remediation.py
git commit -m "feat: add guided remediation with rule-based recommendations"
```

---

### Task 4: Add Approval-Based Autofix

**Files:**
- Create: `trace_eval/autofix.py` — safe fix generation (report, config, CI, patches)
- Modify: `trace_eval/cli.py` — wire `--apply-safe` and `--report` in `cmd_remediate`
- Create: `tests/test_autofix.py` — tests for autofix generation

- [ ] **Step 1: Create `trace_eval/autofix.py`**

```python
"""Approval-based autofix: generate safe fixes for user review and approval.

This module generates actionable artifacts (reports, configs, CI files, patches)
that users can review before applying. It does NOT modify core scoring logic
or make autonomous changes to the codebase.

Safe to automate:
- Config/profile generation
- CI snippet generation
- Remediation report generation
- Converter command generation

NOT safe to automate:
- Judge formula changes
- Scoring weight modifications
- Core agent policy file changes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trace_eval.scoring import Scorecard
from trace_eval.remediation import RemediationAction


def apply_safe_fixes(
    actions: list[RemediationAction],
    card: Scorecard,
    trace_path: Path,
) -> list[dict[str, str]]:
    """Apply safe fixes that don't require approval.

    Returns list of applied fixes with labels and paths.
    """
    fixes: list[dict[str, str]] = []

    for action in actions:
        if action.action_type == "switch_profile" and action.safe_to_automate:
            fix = _generate_profile_switch(trace_path, card)
            fixes.append(fix)
        elif action.action_type == "add_ci_gate" and action.safe_to_automate:
            fix = _generate_ci_gate(trace_path)
            fixes.append(fix)

    return fixes


def _generate_profile_switch(trace_path: Path, card: Scorecard) -> dict[str, str]:
    """Generate a run command with the correct profile."""
    # If retrieval is N/A, suggest coding_agent profile
    profile = "coding_agent" if "retrieval" in card.unscorable_dimensions else "default"
    cmd = f"trace-eval run {trace_path.name} --profile {profile}"
    return {
        "label": f"Switch to {profile} profile",
        "path": "command",
        "content": cmd,
    }


def _generate_ci_gate(trace_path: Path) -> dict[str, str]:
    """Generate GitHub Actions CI workflow."""
    ci_content = """name: Agent Quality Gate

on: [push]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install trace-eval
      - run: trace-eval ci agent-trace.jsonl --min-score 70 --profile coding_agent
"""
    return {
        "label": "Add CI quality gate",
        "path": ".github/workflows/agent-quality.yml",
        "content": ci_content,
    }


def generate_remediation_report(
    actions: list[RemediationAction],
    card: Scorecard,
    trace_path: Path,
    output_path: Path | None = None,
) -> str:
    """Generate a full markdown remediation report.

    Args:
        actions: List of recommended actions from analyze().
        card: The scorecard to report on.
        trace_path: Path to the trace file.
        output_path: Where to save the report. Defaults to trace_path.with_suffix('.md').

    Returns:
        Path to the generated report.
    """
    if output_path is None:
        output_path = trace_path.parent / f"{trace_path.stem}_remediation.md"

    lines = [
        f"# Trace Evaluation Remediation Report",
        f"",
        f"**Trace:** `{trace_path.name}`",
        f"**Score:** {card.total_score:.1f}/100 [{card.rating}]",
        f"**Profile:** {card.profile}",
        f"",
    ]

    # Dimension scores
    lines.append("## Dimension Scores")
    lines.append("")
    lines.append("| Dimension | Score | Status |")
    lines.append("|-----------|-------|--------|")
    for dim, score in sorted(card.dimension_scores.items()):
        if dim in card.unscorable_dimensions:
            lines.append(f"| {dim} | N/A | Not applicable |")
        else:
            status = "OK" if (score or 0) >= 70 else "Needs attention"
            lines.append(f"| {dim} | {score:.1f}/100 | {status} |")
    lines.append("")

    # Recommended actions
    lines.append("## Recommended Actions")
    lines.append("")
    for i, action in enumerate(actions, 1):
        approval_tag = "Auto-safe" if action.safe_to_automate and not action.requires_approval else "Requires approval"
        lines.append(f"### {i}. {action.label} ({approval_tag})")
        lines.append("")
        lines.append(f"**Description:** {action.description}")
        lines.append(f"**Confidence:** {action.confidence}")
        lines.append(f"**Triggered by:** {action.triggered_by}")
        lines.append("")

    # Suggested commands
    lines.append("## Suggested Commands")
    lines.append("")
    lines.append("```bash")
    lines.append(f"# Score with recommended profile")
    if "retrieval" in card.unscorable_dimensions:
        lines.append(f"trace-eval run {trace_path.name} --profile coding_agent")
    else:
        lines.append(f"trace-eval run {trace_path.name}")
    lines.append(f"")
    lines.append(f"# Quick summary")
    lines.append(f"trace-eval run {trace_path.name} --summary")
    lines.append(f"")
    lines.append(f"# CI gate")
    lines.append(f"trace-eval ci {trace_path.name} --min-score 70 --profile coding_agent")
    lines.append("```")
    lines.append("")

    # CI workflow
    lines.append("## CI Workflow")
    lines.append("")
    lines.append("Add `.github/workflows/agent-quality.yml`:")
    lines.append("```yaml")
    lines.append("name: Agent Quality Gate")
    lines.append("on: [push]")
    lines.append("jobs:")
    lines.append("  eval:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append("      - uses: actions/checkout@v4")
    lines.append("      - run: pip install trace-eval")
    lines.append("      - run: trace-eval ci agent-trace.jsonl --min-score 70 --profile coding_agent")
    lines.append("```")

    content = "\n".join(lines) + "\n"
    output_path.write_text(content)
    return str(output_path)
```

- [ ] **Step 2: Write autofix tests**

Create `tests/test_autofix.py`:

```python
import json
import pytest
from pathlib import Path
from trace_eval.autofix import (
    apply_safe_fixes,
    generate_remediation_report,
    _generate_profile_switch,
    _generate_ci_gate,
)
from trace_eval.scoring import Scorecard
from trace_eval.remediation import RemediationAction


def _make_card(unscorable=None, profile="default"):
    return Scorecard(
        total_score=30.0,
        dimension_scores={
            "reliability": 20.0, "efficiency": 30.0, "retrieval": None,
            "tool_discipline": 80.0, "context": None,
        },
        dimension_confidence={
            "reliability": "high", "efficiency": "high", "retrieval": "low",
            "tool_discipline": "high", "context": "low",
        },
        all_flags=[],
        scorable_dimensions=["reliability", "efficiency", "tool_discipline"],
        unscorable_dimensions=unscorable or ["retrieval", "context"],
        missing_required_judges=[],
        profile=profile,
        rating="Critical",
    )


def _make_action(action_type, safe=True, requires_approval=False):
    return RemediationAction(
        action_type=action_type,
        label=f"Test {action_type}",
        description="Test action",
        confidence="high",
        safe_to_automate=safe,
        requires_approval=requires_approval,
        triggered_by="test",
    )


def test_generate_profile_switch(tmp_path):
    card = _make_card(unscorable=["retrieval"])
    fix = _generate_profile_switch(tmp_path / "trace.jsonl", card)
    assert "coding_agent" in fix["content"]
    assert fix["path"] == "command"


def test_generate_ci_gate():
    fix = _generate_ci_gate(Path("trace.jsonl"))
    assert "trace-eval ci" in fix["content"]
    assert ".github/workflows" in fix["path"]


def test_apply_safe_fixes_only_safe_actions(tmp_path):
    card = _make_card(unscorable=["retrieval"])
    actions = [
        _make_action("switch_profile", safe=True, requires_approval=False),
        _make_action("add_ci_gate", safe=True, requires_approval=False),
        _make_action("fix_errors", safe=False, requires_approval=True),
    ]
    fixes = apply_safe_fixes(actions, card, tmp_path / "trace.jsonl")
    # Only switch_profile and add_ci_gate are safe
    assert len(fixes) == 2
    assert fixes[0]["label"] == "Switch to coding_agent profile"


def test_generate_remediation_report(tmp_path):
    card = _make_card(unscorable=["retrieval"])
    actions = [_make_action("switch_profile")]
    report_path = generate_remediation_report(actions, card, tmp_path / "trace.jsonl")
    assert Path(report_path).exists()
    content = Path(report_path).read_text()
    assert "Critical" in content
    assert "30.0" in content
    assert "Recommended Actions" in content
    assert "Suggested Commands" in content
    assert "CI Workflow" in content
```

- [ ] **Step 3: Run tests**

```bash
cd trace-eval
python -m pytest tests/test_autofix.py -v
```

Expected: 4 tests pass.

- [ ] **Step 4: Commit**

```bash
cd trace-eval
git add trace_eval/autofix.py tests/test_autofix.py trace_eval/cli.py
git commit -m "feat: add approval-based autofix (reports, CI, profile switches)"
```

---

### Task 5: Update Alpha-User Flow

**Files:**
- Modify: `ALPHA_QUICKSTART.md` — update flow to include locate, remediate, approval
- Modify: `ALPHA_FRICTION.md` — update friction points with new commands
- Modify: `ALPHA_CASE_STUDY_POST.md` — add remediation section to case study
- Bump version to 0.4.0 in `pyproject.toml`

- [ ] **Step 1: Update ALPHA_QUICKSTART.md with new commands**

Add sections for `locate`, `remediate`, and the new approval flow:

```markdown
## Step 0: Find Your Trace (optional)

Don't know where your trace file is? Let trace-eval find it:

```bash
# Find recent traces from all agents
trace-eval locate

# Find only Claude Code traces from last 24 hours
trace-eval locate claude-code --hours 24

# Find Cursor traces, show top 5
trace-eval locate cursor --limit 5
```

Output:
```
Found 3 recent trace file(s):

  claude-code:
      5m ago    1430KB  my-project
               /Users/you/.claude/projects/my-project/session.jsonl
     2h ago     788KB  other-project
               /Users/you/.claude/projects/other-project/session.jsonl
```

## New: Guided Remediation

After scoring, get specific recommendations:

```bash
# Score + get recommendations in one command
trace-eval run trace.jsonl --next-steps

# Or use the dedicated remediation command
trace-eval remediate trace.jsonl
```

Output:
```
============================================================
  REMEDIATION RECOMMENDATIONS  Score: 28.3/100 [Critical]
============================================================

  1. Fix command errors [REQUIRES APPROVAL]
     Review and fix failed commands. Common causes: missing dependencies, wrong paths, permission issues.
     Confidence: high

  2. Use appropriate scoring profile [AUTO-SAFE]
     Switch to 'coding_agent' profile if retrieval is not applicable to your workflow.
     Confidence: high

  3. Reduce prompt scope [REQUIRES APPROVAL]
     Break tasks into smaller steps to reduce token usage and context pressure.
     Confidence: medium

To auto-apply safe fixes: trace-eval remediate trace.jsonl --apply-safe
To generate full report: trace-eval remediate trace.jsonl --report
```

## The Full Loop

```bash
# 1. Find your trace
trace-eval locate

# 2. Convert (if needed)
trace-eval convert <path> -o trace.jsonl

# 3. Score + get recommendations
trace-eval run trace.jsonl --next-steps

# 4. Apply safe fixes
trace-eval remediate trace.jsonl --apply-safe

# 5. Generate full report
trace-eval remediate trace.jsonl --report

# 6. Re-run agent, score again, compare
trace-eval compare before.jsonl after.jsonl --summary
```
```

- [ ] **Step 2: Bump version to 0.4.0**

```python
# In pyproject.toml
version = "0.4.0"
```

- [ ] **Step 3: Run full test suite**

```bash
cd trace-eval
python -m pytest tests/ -v
```

Expected: All tests pass (81 existing + 6 locate + 7 remediation + 4 autofix + rating tests = ~100+ tests).

- [ ] **Step 4: Commit**

```bash
cd trace-eval
git add ALPHA_QUICKSTART.md ALPHA_FRICTION.md ALPHA_CASE_STUDY_POST.md pyproject.toml
git commit -m "docs: update alpha flow for v0.4.0 with locate, remediate, autofix"
```
