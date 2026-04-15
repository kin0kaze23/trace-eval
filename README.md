# trace-eval

> Tell me why this agent run went wrong and what to change next.

A deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency. Built for solo builders and small AI-native teams using coding/CLI agents.

## What It Does

Run `trace-eval` on an agent trace file and get:

- **A scorecard** — 0-100 across 5 dimensions
- **Root causes** — critical and high-severity issues surfaced first
- **Actionable suggestions** — what to fix, not just that something broke
- **Before/after comparison** — see if your changes actually improved things

```
trace-eval run trace.jsonl
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
  ...
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

## JSON Output for Agents

The `--format json` flag produces stable, structured output designed for agent consumption:

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
  "dimension_confidence": {
    "reliability": "high",
    "efficiency": "medium",
    "retrieval": "high",
    "tool_discipline": "high",
    "context": "high"
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
    "Stop accessing deprecated files",
    "Avoid fallback search -- use primary retrieval"
  ],
  "scorable_dimensions": ["reliability", "efficiency", "retrieval", "tool_discipline", "context"],
  "unscorable_dimensions": [],
  "judge_coverage": { "...": "per-judge scorable + confidence" },
  "adapter_capability_report": { "...": "field availability from adapter" },
  "failed_thresholds": []
}
```

Fields like `likely_causes` and `suggestions` are derived from friction flags and designed for direct use by agent remediation logic.

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
