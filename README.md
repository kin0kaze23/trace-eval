# trace-eval

> Tell me why this agent run went wrong and what to change next.

A deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency. Built for solo builders and small AI-native teams using coding/CLI agents.

## What It Does

Run `trace-eval` on an agent trace file and get:

- **A scorecard** — 0-100 across 5 dimensions
- **Root causes** — critical and high-severity issues surfaced first
- **Actionable suggestions** — what to fix, not just that something broke
- **Before/after comparison** — see if your changes actually improved things

## Quick Start

```bash
# 1. Install
pip install trace-eval

# 2. Convert your agent trace (auto-detects: Claude Code, OpenClaw, Cursor)
trace-eval convert ~/.claude/projects/.../session.jsonl -o trace.jsonl

# 3. Score it
trace-eval run trace.jsonl

# 4. Compare before/after a fix
trace-eval compare before.jsonl after.jsonl

# 5. Gate your CI
trace-eval ci trace.jsonl --min-score 80
```

For a complete walkthrough with real examples, see [examples/case_study.md](examples/case_study.md).

## See It in Action

### Bad Run → Diagnosis

```
$ trace-eval run examples/hermes_bad.jsonl
============================================================
  TRACE-EVAL SCORECARD  Total: 32.4/100
============================================================

LIKELY ROOT CAUSES:
  - Use canonical retrieval entrypoint
  - Stop accessing deprecated files
  - Context pressure exceeded 90% — reduce prompt size
```

### Quick Summary (`--summary`)

```
$ trace-eval run examples/hermes_bad.jsonl --summary
Score: 32.4/100
Flags: retrieval_no_entrypoint, retrieval_deprecated_file, context_pressure_critical
Weak: reliability=5, retrieval=0, context=32
Diagnosis: Agent run with significant friction.
```

### Compare Before vs After

```
$ trace-eval compare examples/hermes_bad.jsonl examples/hermes_good.jsonl
COMPARISON: before vs after
=======================================================
  Total score:   32.4 ->   98.9
  Change:      +66.5 (improved)

  FLAG CHANGES:
    [RESOLVED] context_compression
    [RESOLVED] context_pressure_critical
    [RESOLVED] reliability_errors
    ...
```

## Case Study

See [examples/case_study.md](examples/case_study.md) for a complete walkthrough:
- **Bad run → diagnosis → fix → before/after comparison** (synthetic traces)
- **Real Claude Code session** (3,694 events, 90 errors diagnosed in under 1 second)
- **Real OpenClaw session** (158 events, 11 errors with actionable flags)

## Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Reliability | 35% | Did it succeed? Errors, timeouts, partial results |
| Efficiency | 20% | Token usage, cost, tool call density |
| Retrieval | 20% | Canonical entrypoint, deprecated files, fallback search |
| Tool Discipline | 15% | Retries, redundant calls, timeouts |
| Context | 10% | Context pressure, warnings, compression events |

Weights are configurable via profiles. Unscorable dimensions redistribute proportionally.

## Scoring Profiles

| Profile | Reliability | Efficiency | Retrieval | Tool Discipline | Context |
|---------|------------|------------|-----------|-----------------|---------|
| **default** | 35% | 20% | 20% | 15% | 10% |
| **coding_agent** | 40% | 25% | 0% | 25% | 10% |
| **rag_agent** | 30% | 15% | 30% | 15% | 10% |

```bash
trace-eval run trace.jsonl --profile coding_agent
```

Unscorable dimensions (e.g., retrieval for coding agents) are automatically excluded and their weight redistributed to scorable dimensions.

## Examples

| Trace | Source | Events | Score | File |
|-------|--------|--------|-------|------|
| Good run (synthetic) | Modeled after Hermes | 8 | 98.9 | `examples/hermes_good.jsonl` |
| Bad run (synthetic) | Modeled after Hermes | 11 | 32.4 | `examples/hermes_bad.jsonl` |
| Real Claude Code | Stillness project | 3,694 | 28.3 | `examples/claude_code_real.jsonl` |
| Real Claude Code #2 | AutomationHub project | 1,969 | 28.3 | `examples/claude_code_real_2.jsonl` |
| OpenClaw | Real session | 158 | 42.6 | `examples/openclaw_before.jsonl` |
| Cursor sample | Synthetic coding session | 18 | 59.8 | `examples/cursor_sample.jsonl` |

## Convert Your Traces

Don't have canonical JSONL? `trace-eval convert` handles native trace formats:

```bash
# Auto-detect format
trace-eval convert ~/.claude/projects/.../session.jsonl -o trace.jsonl
trace-eval convert ~/.openclaw/.../session.jsonl -o trace.jsonl
trace-eval convert .cursor/.../transcript.jsonl -o trace.jsonl

# Explicit format
trace-eval convert cursor session.jsonl -o trace.jsonl

# Then score
trace-eval run trace.jsonl
```

| Format | Auto-detect | File Extension |
|--------|------------|---------------|
| Claude Code | Yes | `.jsonl` |
| OpenClaw | Yes | `.jsonl` |
| Cursor | Yes | `.jsonl` |
| Canonical | Yes (passthrough) | `.jsonl` |
| Hermes SQLite | N/A (load directly) | `.db` |

## Agent Integration

### Machine-readable output (`--format json`)

```bash
trace-eval run trace.jsonl --format json
```

Produces stable JSON output designed for agent self-diagnosis and remediation:

```json
{
  "total_score": 32.43,
  "dimension_scores": { "reliability": 5.0, "efficiency": 77.42, ... },
  "friction_flags": [...],
  "likely_causes": ["Use canonical retrieval entrypoint", ...],
  "suggestions": ["Use canonical retrieval entrypoint", ...]
}
```

**Agent remediation pattern:**
1. Run `trace-eval run trace.jsonl --format json`
2. Parse `likely_causes` — root-cause hypotheses
3. Parse `suggestions` — each maps to a concrete fix
4. Apply fixes, re-run the agent, compare the new trace

### Quick summary (`--summary`)

For concise output designed for both humans and agents:

```
$ trace-eval run trace.jsonl --summary
Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens, tool_redundant
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. fix errors (0/100 reliability). reduce token/tool usage.
```

## Adapters

| Format | Adapter | Capability |
|--------|---------|-----------|
| JSONL (`.jsonl`) | Generic JSONL | Full — all fields available if present in file |
| Hermes SQLite (`.db`) | Hermes | Honest/lossy — populates what exists, nulls what doesn't |

Adding your own adapter? Implement `load(path) -> Trace` and `capability_report(trace) -> dict`.

## What's Coming

- More adapters (OpenAI traces, LangSmith, LangGraph, custom formats)
- Baseline comparison (cost vs similar tasks)
- Parallelization analysis in Tool Discipline

## What This Is NOT

- A dashboard — CLI-first, local-first
- An LLM judge — all scoring is deterministic
- An auto-fix tool — it tells you what to fix, not how
- A broad observability platform — focused on agent trace evaluation

## License

MIT
