# Embedded Workflow + Approval Loop Design

**Goal:** Make trace-eval a closed-loop improvement tool that works smoothly while users are actively using AI agents.

**Architecture:** Two-phase approach — first fix output gaps (JSON fields, top-3 prioritization, approval clarity), then add a `loop` command that composes all steps into a single entrypoint with human-readable default output.

---

## Part 1: Output Improvements

### 1.1 JSON Output — Lean New Fields

Add to the existing JSON output from `format_json()`:

```json
{
  "rating": "Critical",
  "top_issues": [
    {"id": "reliability_errors", "severity": "medium", "summary": "31 errors at event indices [68, 149, ...]"},
    {"id": "efficiency_high_tokens", "severity": "medium", "summary": "Reduce token usage"},
    {"id": "efficiency_high_tool_calls", "severity": "low", "summary": "Excessive tool calls"}
  ],
  "top_actions": [
    {"action_type": "fix_errors", "label": "Fix command errors", "safe_to_automate": false, "requires_approval": true},
    {"action_type": "reduce_retries", "label": "Reduce tool call retries", "safe_to_automate": true, "requires_approval": true},
    {"action_type": "switch_profile", "label": "Use appropriate scoring profile", "safe_to_automate": true, "requires_approval": false}
  ]
}
```

**Implementation:** `format_json()` in `report.py` gets two new optional parameters: `actions` (list of RemediationAction) and the card already has `rating`. When `actions` is provided, adds `top_actions` (top 3). `top_issues` is derived from `card.all_flags` (top 3 by severity). `rating` comes from `card.rating` and is always included.

Signature change:
```python
def format_json(card: Scorecard, adapter_report: dict | None = None,
                failed_thresholds: list[dict] | None = None,
                actions: list[RemediationAction] | None = None) -> str:
```

### 1.2 Text Remediation — Top 3 Highlight

Change `format_remediation()` to:
- Lead with "TOP 3 ACTIONS:" header showing the 3 highest-priority items
- Show approval status inline: `[AUTO-SAFE]` vs `[REQUIRES APPROVAL]`
- List remaining actions below (if any beyond 3)

```
============================================================
  REMEDIATION RECOMMENDATIONS  Score: 28.3/100 [Critical]
============================================================

  TOP 3 ACTIONS:
  1. [REQUIRES APPROVAL] Fix command errors
     Review and fix failed commands.
  2. [REQUIRES APPROVAL] Reduce tool call retries
     Add branch guards before tool calls.
  3. [AUTO-SAFE] Use appropriate scoring profile
     Switch to 'coding_agent' profile.

  Additional actions:
  4. Reduce prompt scope [REQUIRES APPROVAL]
  5. Reduce tool call volume [REQUIRES APPROVAL]
```

### 1.3 Fix: `add_ci_gate` Approval Tag

The action template says `safe_to_automate: true` but `requires_approval: true`. The CLI output shows `[REQUIRES APPROVAL]` which is correct — the `safe_to_automate` field means the *artifact generation* is safe, but applying it still needs approval. The `format_remediation()` display is correct; the confusion is in `ACTION_TYPES` metadata. We'll keep `requires_approval: true` for CI gate (user must review before adding a file to their repo).

---

## Part 2: The `loop` Command

### 2.1 Command Signature

```
trace-eval loop [agent-type] [options]

Positional:
  agent-type              claude-code, cursor, openclaw, all (default: all)

Options:
  --hours N               Search window (default: 48)
  --profile PROFILE       Scoring profile (default: auto-detect)
  --compare PATH          Compare against this previous trace
  --apply-safe            Apply safe fixes automatically
  --report                Generate markdown remediation report
  --output DIR            Directory for generated files (default: cwd)
  --format text|json      Output format (default: text)
```

### 2.2 What It Does (Step by Step)

1. **Locate** — finds the most recent trace matching agent-type and hours filter
2. **Convert** — if the trace is not canonical JSONL, converts it (auto-detect)
3. **Score** — runs the scorecard with `--summary` style output
4. **Remediate** — shows top 3 issues + top 3 actions with approval tags
5. **Apply-safe** (if flagged) — applies profile switches, generates CI gate
6. **Compare** (if flagged) — scores the previous trace and shows delta
7. **Report** (if flagged) — writes markdown report to output dir

### 2.3 Output Format (Default: Human-Readable Text)

```
============================================================
  TRACE-EVAL LOOP  v0.5.0
============================================================

  Trace: 9b711cee-cf3f-46dd-b7ce-ad66ca338318.jsonl (33MB, claude-code, 4m ago)
  Score: 28.3/100  [Critical]

  TOP 3 ISSUES:
  [!] reliability_errors (medium) — 31 errors at event indices [68, 149, ...]
  [!] efficiency_high_tokens (medium) — Reduce token usage
  [-] efficiency_high_tool_calls (low) — Excessive tool calls

  TOP 3 ACTIONS:
  1. [REQUIRES APPROVAL] Fix command errors
     Review and fix failed commands.
  2. [REQUIRES APPROVAL] Reduce tool call retries
     Add branch guards before tool calls.
  3. [AUTO-SAFE] Use appropriate scoring profile
     Switch to 'coding_agent' profile.

  Safe fixes applied:
  [+] Switch to coding_agent profile

  Delta vs before.jsonl: +66.5 (32.4 -> 98.9)
```

### 2.4 Output Format (JSON)

```json
{
  "trace": "9b711cee.jsonl",
  "score": 28.3,
  "rating": "Critical",
  "top_issues": [...],
  "top_actions": [...],
  "safe_fixes_applied": ["Switch to coding_agent profile"],
  "delta": {"before": 32.4, "after": 98.9, "change": 66.5}
}
```

---

## Implementation Details

### Files to Create

1. **`trace_eval/loop.py`** — Main loop orchestration
   - `run_loop()` function that chains locate → convert → score → remediate
   - Returns a structured result dict for both text and JSON formatting
   - Handles errors at each step gracefully (trace not found, convert fails, etc.)
   - `format_loop_result()` — text formatter for the loop output

### Files to Modify

1. **`trace_eval/report.py`** — `format_json()` gets 3 new parameters
   - `rating: str` — adds `rating` field to JSON
   - `actions: list[RemediationAction]` — adds `top_actions` field
   - Adds `top_issues` from friction_flags (top 3)

2. **`trace_eval/remediation.py`** — `format_remediation()` gets top-3 highlight
   - Reorders: top 3 first, rest below
   - Approval tag moves to front of each line

3. **`trace_eval/cli.py`** — Add `cmd_loop()` function + `loop` subparser
   - Imports from locate, convert, scoring, remediation, autofix, loop
   - Wires all steps together

### Files to Test

1. **`tests/test_loop.py`** — Tests for the loop orchestration
   - `test_loop_finds_and_scores_trace`
   - `test_loop_with_compare`
   - `test_loop_with_apply_safe`
   - `test_loop_no_traces_found`
   - `test_loop_json_output`

2. **`tests/test_report.py`** — Add tests for new JSON fields
   - `test_json_has_rating`
   - `test_json_has_top_issues`
   - `test_json_has_top_actions`

3. **`tests/test_remediation.py`** — Add test for top-3 format
   - `test_remediation_top_3_format`

---

## Error Handling

- **No traces found:** Clear message: "No recent traces found. Try: trace-eval loop --hours 72"
- **Convert fails:** "Could not convert trace — try: trace-eval convert --help"
- **Score fails:** Fallback: "Score computation failed" with exit code 1
- **Compare file not found:** Warning but continue (don't fail the whole loop)
- **Apply-safe fails:** Warning but continue (the score + remediation still useful)

---

## What This Does NOT Add

- No LLM-as-judge
- No dashboards
- No new trace adapters
- No autonomous self-modification
- No new scoring dimensions
- No database or persistence layer

---

## Success Criteria

1. `trace-eval loop` runs end-to-end on a real trace without errors
2. Output is under 15 lines for the default text summary
3. JSON output includes `rating`, `top_issues`, `top_actions`
4. Remediation shows top 3 actions with approval tags prominently
5. `--compare` shows delta vs a previous trace in the summary
6. `--apply-safe` applies safe fixes and reports them in the summary
7. All 110+ existing tests pass + 8+ new tests
