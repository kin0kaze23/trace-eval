# Launch Demo Assets — trace-eval v0.1.0

## Asset 1: Real Bad-Run Teardown

Source: `examples/hermes_bad.jsonl` (synthetic trace modeling real failure patterns)

```
$ trace-eval run examples/hermes_bad.jsonl

  TRACE-EVAL SCORECARD  Total: 32.4/100

LIKELY ROOT CAUSES:
  - Use canonical retrieval entrypoint
  - Stop accessing deprecated files
  - Context pressure exceeded 90% — reduce prompt size

DIMENSION SCORES:
  reliability             5.0  (high)
  efficiency             77.4  (medium)
  retrieval               0.0  (high)
  tool_discipline        80.0  (high)
  context                32.0  (high)

FRICTION FLAGS:
  [CRITICAL] retrieval_no_entrypoint
  [CRITICAL] retrieval_deprecated_file @event 9
  [CRITICAL] context_pressure_critical
  [HIGH] retrieval_fallback_search
  [HIGH] tool_timeout @event 5
  [MEDIUM] reliability_errors @event 3
  [MEDIUM] context_compression
```

**Diagnosis:** This run failed on 3 axes simultaneously:
- Reliability (5.0): 3 errors + 1 timeout → agent didn't complete cleanly
- Retrieval (0.0): no entrypoint, touched deprecated file, fell back to search
- Context (32.0): hit 90% context pressure → compression triggered

**Actionable fixes:** 3 critical + 2 high severity issues, each with a concrete suggestion.

---

## Asset 2: Before/After Compare

Scenario: Fixed the errors, removed deprecated file access, reduced context pressure.

```
$ trace-eval compare before.jsonl after.jsonl

COMPARISON: before vs after
  Total score:   32.4 ->   70.8
  Change:      +38.4 (improved)

  reliability             5.0 ->   90.0  ^ +85.0
  efficiency             77.4 ->   77.4  =  0.0
  retrieval               0.0 ->   30.0  ^ +30.0
  tool_discipline        80.0 ->   64.0  v -16.0
  context                32.0 ->   82.0  ^ +50.0

FLAG CHANGES:
  [RESOLVED] context_pressure_critical
  [RESOLVED] reliability_errors
  [RESOLVED] retrieval_deprecated_file
  [NEW] [LOW] tool_redundant
```

**Key insight:** +38.4 improvement. The fix resolved 3 flags (errors, deprecated file, context pressure). The only regression is a new LOW tool_redundant flag — a minor tradeoff worth accepting.

---

## Asset 3: "See It in Action" — 5-Minute Flow

```bash
# Step 1: Install (30 seconds)
pip install trace-eval

# Step 2: Validate your trace (1 second)
trace-eval validate trace.jsonl
# → Schema validation PASSED, field coverage bars, adapter report

# Step 3: Get your scorecard (1 second)
trace-eval run trace.jsonl
# → Score: 32.4/100, 7 friction flags, 3 root causes identified

# Step 4: Fix the issues, re-run your agent, compare
trace-eval compare old_trace.jsonl new_trace.jsonl
# → Score improved +38.4, 3 flags resolved

# Step 5: Gate your CI
trace-eval ci new_trace.jsonl --min-score 80
# → PASS (exit 0)
```

**Total time from install to CI gate:** under 5 minutes.
**No cloud setup, no API keys, no dashboard config.**

---

## Asset 4: Non-Hermes Trace (Generic JSONL)

Source: `examples/claude_code_good.jsonl` — modeled after a Claude Code agent session.

```
$ trace-eval run examples/claude_code_good.jsonl

  TRACE-EVAL SCORECARD  Total: 87.9/100

DIMENSION SCORES:
  reliability           100.0  (high)
  efficiency             95.4  (high)
  retrieval              50.0  (high)
  tool_discipline       100.0  (high)
  context                 N/A  (low) *

FRICTION FLAGS:
  [CRITICAL] retrieval_no_entrypoint
    -> Use canonical retrieval entrypoint
```

**What this validates:** The generic JSONL adapter works end-to-end for non-Hermes traces. It correctly scores reliability (100%), efficiency (95.4%), and tool discipline (100%) when the canonical fields are present. The retrieval score (50.0) is the expected floor when no retrieval fields are provided.

---

## Asset Locations

| Asset | File |
|-------|------|
| Good run output | `examples/demo/good-run.txt` |
| Bad run output | `examples/demo/bad-run.txt` |
| Compare output | `examples/demo/compare.txt` |
| CI pass output | `examples/demo/ci-pass.txt` |
| Non-Hermes trace | `examples/claude_code_good.jsonl` |
| Validation report | `VALIDATION_REPORT.md` |
