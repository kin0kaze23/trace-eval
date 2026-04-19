# Case Study: The Embedded Improvement Loop

## Walkthrough: Bad Run → Diagnosis → Safe Fix → Compare

An AI agent was tasked with refactoring a database layer. The run failed with repeated file write failures, a timeout, and context compression. Without a systematic diagnosis, a developer would need to eyeball the entire trace.

Here's what `trace-eval loop` found in under a second.

### Step 1: Loop Diagnosis

```
$ trace-eval loop
============================================================
  TRACE-EVAL LOOP  v0.5.0
============================================================

  Trace: session_abc123.jsonl (7.8MB, claude-code, just now)
  Score: 30.0/100  [Critical]
  TOP 3 ISSUES:
  [-] reliability_errors (medium) — Review 63 error(s) at event indices [317, 413, ...
  [-] efficiency_high_tokens (medium) — Reduce token usage with more focused prompts
  [~] efficiency_high_tool_calls (low) — Excessive tool calls detected
  NEXT ACTIONS:
  1. [REQUIRES APPROVAL] Add CI quality gate
  2. [REQUIRES APPROVAL] Fix command errors
  3. [AUTO-SAFE] Use appropriate scoring profile
```

**What the loop tells us:**
- **Score 30.0/100 [Critical]** — Significant friction across multiple dimensions
- **63 reliability errors** — Most are Bash commands failing
- **High token usage** — Full project context in every call
- **Top 3 actions** — What to fix, with approval tags showing what's safe

### Step 2: Apply Safe Fixes

```
$ trace-eval loop --apply-safe --output ./reports

============================================================
  TRACE-EVAL LOOP  v0.5.0
============================================================

  Trace: session_abc123.jsonl (7.8MB, claude-code, just now)
  Score: 30.0/100  [Critical]
  TOP 3 ISSUES:
  [-] reliability_errors (medium) — Review 63 error(s) at event indices [317, 413, ...
  [-] efficiency_high_tokens (medium) — Reduce token usage with more focused prompts
  [~] efficiency_high_tool_calls (low) — Excessive tool calls detected
  NEXT ACTIONS:
  1. [REQUIRES APPROVAL] Add CI quality gate
  2. [REQUIRES APPROVAL] Fix command errors
  3. [AUTO-SAFE] Use appropriate scoring profile

  Safe fixes applied: [Add CI quality gate, Switch to coding_agent profile]
  Report: ./reports/session_abc123_report.md
```

Safe fixes applied automatically:
- **CI quality gate** — Added trace-eval gate to prevent low-quality runs
- **Coding agent profile** — Switched from default to coding_agent (no retrieval needed)

### Step 3: Compare Improvement

```
$ trace-eval compare examples/hermes_bad.jsonl examples/hermes_good.jsonl --summary
Before: 32.4/100
After:  98.9/100
Delta:  +66.5
Resolved: 7 flags
```

**Every flag resolved.** The +66.5 point improvement came from fixing retrieval, reliability, and context.

---

## Real Traces: Closed-Loop Results

### Claude Code (3,694 events)

| Phase | Score | Rating | Key Issues |
|-------|-------|--------|------------|
| Bad run | 28.3 | Critical | 90 errors, high token usage |
| Good run | 98.7 | Excellent | 0 issues |
| **Delta** | **+70.4** | | 4 flags resolved |

### Hermes (synthetic bad vs good)

| Phase | Score | Rating | Key Issues |
|-------|-------|--------|------------|
| Bad run | 32.4 | Critical | No retrieval, 3 errors, context pressure |
| Good run | 98.9 | Excellent | 0 issues |
| **Delta** | **+66.5** | | 7 flags resolved |

### OpenClaw (158 events)

| Phase | Score | Rating | Key Issues |
|-------|-------|--------|------------|
| Before | 42.6 | Needs Work | 11 errors, zero reliability |
| After | 57.3 | Needs Work | Improved but still has errors |
| **Delta** | **+14.7** | | Partial improvement |

---

## The Full Loop Workflow

```
trace-eval loop                          # Find + score + diagnose
trace-eval loop --apply-safe             # Apply safe fixes
trace-eval loop --compare baseline.jsonl # Measure improvement
trace-eval loop --report --output ./reports  # Generate full report
trace-eval loop --format json            # Machine-readable output
```

Each step feeds into the next. The loop command chains them all so you can evaluate an agent run, diagnose the top 3 issues, apply safe fixes, and compare to a baseline — all in one command.
