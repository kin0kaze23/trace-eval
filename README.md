# trace-eval

> Tell me why this agent run went wrong and what to change next.

A deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency. Built for solo builders and small AI-native teams using coding/CLI agents.

## What It Does

Run `trace-eval` on an agent trace file and get:

- **A scorecard** — 0-100 across 5 dimensions
- **Root causes** — critical and high-severity issues surfaced first
- **Actionable suggestions** — what to fix, not just that something broke
- **Before/after comparison** — see if your changes actually improved things

## See It in Action

```bash
# 1. Install (uv or pip)
uv sync --all-extras

# 2. Validate a trace file
trace-eval validate trace.jsonl
# Schema validation PASSED — 8 events, field coverage bars printed

# 3. Run a scorecard
trace-eval run trace.jsonl
# ============================================================
#   TRACE-EVAL SCORECARD  Total: 32.4/100
# ============================================================
#
# LIKELY ROOT CAUSES:
#   - Use canonical retrieval entrypoint
#   - Stop accessing deprecated files
#   - Context pressure exceeded 90% — reduce prompt size
#
# DIMENSION SCORES:
#   reliability             5.0  (high)
#   efficiency             77.4  (medium)
#   retrieval               0.0  (high)
#   tool_discipline        80.0  (high)
#   context                32.0  (high)

# 4. Compare before vs after a fix
trace-eval compare before.jsonl after.jsonl
# Total score: 67.5 -> 99.3  Change: +31.9 (improved)
#
# FLAG CHANGES:
#   [RESOLVED] reliability_errors
#   [RESOLVED] retrieval_no_entrypoint
#   [RESOLVED] tool_retries

# 5. CI gate — fails the build below a threshold
trace-eval ci trace.jsonl --min-score 80
# PASS (exit 0) or FAIL (exit 1)
```

### Good Run

```
trace-eval run examples/hermes_good.jsonl
============================================================
  TRACE-EVAL SCORECARD  Total: 98.9/100
============================================================

DIMENSION SCORES:
  reliability           100.0  (high)
  efficiency             94.5  (medium)
  retrieval             100.0  (high)
  tool_discipline       100.0  (high)
  context               100.0  (high)
```

### Bad Run

```
trace-eval run examples/hermes_bad.jsonl
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
    -> Use canonical retrieval entrypoint
  [CRITICAL] retrieval_deprecated_file @event 9
    -> Stop accessing deprecated files
  [CRITICAL] context_pressure_critical
    -> Context pressure exceeded 90% — reduce prompt size
  [HIGH] retrieval_fallback_search
    -> Avoid fallback search -- use primary retrieval
  [HIGH] tool_timeout @event 5
    -> 1 tool call(s) timed out
  [MEDIUM] reliability_errors @event 3
    -> Review 3 error(s) at event indices [3, 4, 8]
  [MEDIUM] context_compression
    -> Context compression triggered 1 time(s)
```

### Compare

```
trace-eval compare examples/before.jsonl examples/after.jsonl
COMPARISON: before vs after
=======================================================
  Total score:   67.5 ->   99.3
  Change:      +31.9 (improved)

  reliability            45.0 ->  100.0  ^ +55.0
  efficiency             93.5 ->   96.8  ^ +3.2
  retrieval              50.0 ->  100.0  ^ +50.0
  tool_discipline        90.0 ->  100.0  ^ +10.0
  context                95.0 ->  100.0  ^ +5.0

  FLAG CHANGES:
    [RESOLVED] reliability_errors
    [RESOLVED] reliability_terminal_partial
    [RESOLVED] retrieval_no_entrypoint
    [RESOLVED] tool_retries
```

## Quick Start

```bash
# Install
pip install -e .
# Or with uv:
uv sync --all-extras

# Validate a trace
trace-eval validate examples/hermes_good.jsonl

# Run a scorecard
trace-eval run examples/hermes_good.jsonl

# Machine-readable output (for agents)
trace-eval run examples/hermes_bad.jsonl --format json

# Compare before/after
trace-eval compare examples/before.jsonl examples/after.jsonl

# CI gate
trace-eval ci examples/hermes_good.jsonl --min-score 80
```

## Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Reliability | 35% | Did it succeed? Errors, timeouts, partial results |
| Efficiency | 20% | Token usage, cost, tool call density |
| Retrieval | 20% | Canonical entrypoint, deprecated files, fallback search |
| Tool Discipline | 15% | Retries, redundant calls, timeouts |
| Context | 10% | Context pressure, warnings, compression events |

Weights are configurable. Unscorable dimensions redistribute proportionally.

## Adapters

| Format | Adapter | Capability |
|--------|---------|-----------|
| JSONL (`.jsonl`) | Generic JSONL | Full — all fields available if present in file |
| Hermes SQLite (`.db`) | Hermes | Honest/lossy — populates what exists, nulls what doesn't |

Adding your own adapter? The adapter interface is simple: implement `load(path) -> Trace` and `capability_report(trace) -> dict`.

## Agent Integration (`--format json`)

The `--format json` flag produces stable, machine-readable output designed for agent consumption. An AI agent that just completed a task can pipe its trace through trace-eval and use the results to self-diagnose and guide remediation.

### How an agent uses it

```json
{
  "total_score": 32.43,
  "dimension_scores": {
    "reliability": 5.0,
    "efficiency": 77.42,
    "retrieval": 0.0,
    "tool_discipline": 80.0,
    "context": 32.0
  },
  "friction_flags": [
    {
      "id": "retrieval_no_entrypoint",
      "severity": "critical",
      "dimension": "retrieval",
      "event_index": null,
      "suggestion": "Use canonical retrieval entrypoint"
    }
  ],
  "likely_causes": [
    "Use canonical retrieval entrypoint",
    "Stop accessing deprecated files"
  ],
  "suggestions": [
    "Use canonical retrieval entrypoint",
    "Stop accessing deprecated files"
  ],
  "scorable_dimensions": ["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
  "unscorable_dimensions": [],
  "judge_coverage": { "...": "per-judge scorable + confidence" },
  "adapter_capability_report": { "...": "field availability from adapter" },
  "failed_thresholds": []
}
```

### Agent remediation pattern

1. Run `trace-eval run trace.jsonl --format json`
2. Parse `likely_causes` — these are the root-cause hypotheses
3. Parse `suggestions` — each one maps to a concrete fix
4. Apply fixes, re-run the agent, compare the new trace
5. Use `trace-eval compare old.jsonl new.jsonl --format json` to quantify improvement

Fields are stable and typed. `suggestions` is a plain string array designed for direct use in agent prompts or remediation logic.

## What's Coming

- More adapters (OpenAI traces, LangSmith, LangGraph, custom formats)
- Score profiles (balanced, reliability_first, cost_conscious)
- Baseline comparison (cost vs similar tasks)
- Parallelization analysis in Tool Discipline

## What This Is NOT

- A dashboard — CLI-first, local-first
- An LLM judge — all scoring is deterministic
- An auto-fix tool — it tells you what to fix, not how
- A broad observability platform — focused on agent trace evaluation

## License

MIT
