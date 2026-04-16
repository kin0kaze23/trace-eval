# Case Study: Debugging Bad Agent Runs with trace-eval

## Part 1: Walkthrough — Bad Run → Diagnosis → Fix → Compare

An AI agent was tasked with refactoring a database layer. The run failed with repeated file write failures, a timeout, and context compression. Without a systematic diagnosis, a developer would need to eyeball the entire trace.

Here's what trace-eval found in under a second.

### Step 1: Run the Scorecard

```
$ trace-eval run examples/hermes_bad.jsonl
============================================================
  TRACE-EVAL SCORECARD  Total: 32.4/100
============================================================

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

FRICTION FLAGS (sorted by severity):
  [CRITICAL] retrieval_no_entrypoint
  [CRITICAL] retrieval_deprecated_file @event 9
  [CRITICAL] context_pressure_critical
  [HIGH] retrieval_fallback_search
  [HIGH] tool_timeout @event 5
  [MEDIUM] reliability_errors @event 3
  [MEDIUM] context_compression
```

**What the score tells us immediately:**
- **Reliability 5.0/100** — 3 errors + 1 timeout. The agent didn't complete.
- **Retrieval 0.0/100** — No retrieval strategy, deprecated files accessed, fallback search triggered.
- **Context 32.0/100** — Context pressure hit 92%, triggering compression.
- **Efficiency 77.4** and **Tool Discipline 80.0** — The agent wasn't wasteful, just stuck.

### Step 2: Fix the Issues

Based on the friction flags:
1. **Fixed retrieval** — Added canonical entrypoint, stopped accessing deprecated files
2. **Reduced context pressure** — Broke task into smaller steps
3. **Eliminated errors** — Better retrieval + less context pressure = no tool failures

### Step 3: Compare Before vs After

```
$ trace-eval compare examples/hermes_bad.jsonl examples/hermes_good.jsonl
COMPARISON: before vs after
=======================================================
  Total score:   32.4 ->   98.9
  Change:      +66.5 (improved)

  reliability             5.0 ->  100.0  ^ +95.0
  efficiency             77.4 ->   94.5  ^ +17.1
  retrieval               0.0 ->  100.0  ^ +100.0
  tool_discipline        80.0 ->  100.0  ^ +20.0
  context                32.0 ->  100.0  ^ +68.0

  FLAG CHANGES:
    [RESOLVED] context_compression
    [RESOLVED] context_pressure_critical
    [RESOLVED] reliability_errors
    [RESOLVED] retrieval_deprecated_file
    [RESOLVED] retrieval_fallback_search
    [RESOLVED] retrieval_no_entrypoint
    [RESOLVED] tool_timeout
```

**Every flag resolved.** The +66.5 point improvement came from fixing retrieval, reliability, and context.

---

## Part 2: Real Claude Code Session — 3,694 Events, 90 Errors

Source: Real Claude Code session working on the Stillness project. The agent completed its task but with significant friction.

```
$ trace-eval run examples/claude_code_real.jsonl
============================================================
  TRACE-EVAL SCORECARD  Total: 28.3/100
============================================================

DIMENSION SCORES:
  reliability             0.0  (high)
  efficiency             30.0  (high)
  retrieval               N/A  (low) * (not applicable to this workflow)
  tool_discipline        92.0  (high)
  context                 N/A  (low) *

FRICTION FLAGS:
  [MEDIUM] reliability_errors @event 23
    -> Review 90 error(s) at event indices [23, 32, 61, ...]
  [MEDIUM] efficiency_high_tokens
    -> Reduce token usage with more focused prompts
  [LOW] efficiency_high_tool_calls
    -> Excessive tool calls detected
  [LOW] tool_redundant @event 3
    -> 1 redundant tool call(s)
```

**Diagnosis:** 90 tool errors across a complex coding session. Most from Bash commands failing (exit code 1). Efficiency at 30.0 reflects high token usage (54K+ input tokens per call with full project context). Tool discipline at 92.0 is strong — the agent used tools well, just hit many command failures. Retrieval marked N/A because this is a coding agent without retrieval workflows.

```
$ trace-eval run examples/claude_code_real.jsonl --summary
Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens, tool_redundant
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. Fix errors (0/100 reliability). Reduce token/tool usage.
```

---

## Part 3: Real OpenClaw Session — 158 Events

Source: Real OpenClaw session. Smaller trace but similarly problematic.

```
$ trace-eval run examples/openclaw_before.jsonl
============================================================
  TRACE-EVAL SCORECARD  Total: 42.6/100
============================================================

DIMENSION SCORES:
  reliability             0.0  (high)
  efficiency             74.2  (high)
  retrieval               N/A  (low) * (not applicable to this workflow)
  tool_discipline       100.0  (high)
  context                 N/A  (low) *

FRICTION FLAGS:
  [MEDIUM] reliability_errors @event 9
    -> Review 11 error(s) at event indices [9, 12, 15, ...]
  [LOW] efficiency_high_tool_calls
    -> Excessive tool calls detected
```

**Diagnosis:** 11 errors across 158 events. The agent had good tool discipline (100.0) and decent efficiency (74.2), but zero reliability — every error was significant enough to tank the overall score.

---

## Summary Table

| Trace | Source | Events | Score | Top Issue |
|-------|--------|--------|-------|-----------|
| Bad run (synthetic) | Modeled after Hermes | 11 | 32.4 | No retrieval, 3 errors, context pressure |
| Good run (synthetic) | Modeled after Hermes | 8 | 98.9 | All clear |
| Claude Code (real) | Stillness project | 3,694 | 28.3 | 90 tool errors, high token usage |
| OpenClaw (real) | Real session | 158 | 42.6 | 11 errors, zero reliability |

**Time to diagnose:** under 1 second for all traces.
**What trace-eval tells you:** which dimension to fix first, and exactly what changed.
