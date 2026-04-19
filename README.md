# trace-eval

> Evaluate AI agent runs. Fix the right thing. See if it improved.

A deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency. Built for solo builders and small AI-native teams using coding/CLI agents.

## Quick Start

```bash
pip install trace-eval
```

One command to evaluate, diagnose, and remediate:

```bash
trace-eval loop
```

That's it. `trace-eval loop` finds your most recent agent trace, scores it, identifies the top 3 issues, recommends the top 3 actions, and tells you what's safe to auto-fix.

### Full Workflow

```bash
# 1. Locate + score your latest agent trace (auto-detects: Claude Code, OpenClaw, Cursor)
trace-eval loop

# 2. Apply safe fixes automatically
trace-eval loop --apply-safe

# 3. Compare to a previous run to measure improvement
trace-eval loop --compare before.jsonl

# 4. Generate a detailed remediation report
trace-eval loop --report --output ./reports
```

## The Loop Command

`trace-eval loop` chains the full evaluation pipeline: **locate → convert → score → remediate**. It finds your most recent agent trace, scores it across 5 dimensions, identifies the top 3 issues with severity, recommends the top 3 actions, and optionally applies safe fixes or compares to a baseline.

### Example Output

```
$ trace-eval loop
============================================================
  TRACE-EVAL LOOP  v0.5.0
============================================================

  Trace: session_abc123.jsonl (7.8MB, claude-code, just now)
  Score: 30.0/100  [Critical]
  TOP 3 ISSUES:
  [-] reliability_errors (medium) — Review 31 error(s) at event indices [68, 149, ...
  [-] efficiency_high_tokens (medium) — Reduce token usage with more focused prompts
  [~] efficiency_high_tool_calls (low) — Excessive tool calls detected
  NEXT ACTIONS:
  1. [REQUIRES APPROVAL] Add CI quality gate
  2. [REQUIRES APPROVAL] Fix command errors
  3. [AUTO-SAFE] Use appropriate scoring profile
```

### Closed-Loop Example

```
# Bad run diagnosis
$ trace-eval run examples/hermes_bad.jsonl --summary
Score: 32.4/100 [Critical]
Diagnosis: Agent run with significant friction.

# Apply safe fixes
$ trace-eval loop --apply-safe --output ./reports
...
  Safe fixes applied: [Add CI quality gate, Switch to coding_agent profile]

# Compare to measure improvement
$ trace-eval compare examples/hermes_bad.jsonl examples/hermes_good.jsonl --summary
Before: 32.4/100
After:  98.9/100
Delta:  +66.5
Resolved: 7 flags
```

### Command Reference

```
trace-eval loop [agent_type] [options]

Positional:
  agent_type    claude-code, cursor, openclaw, or all (default: all)

Options:
  --hours N     Search window in hours (default: 48)
  --profile P   Scoring profile (default: auto-detect)
  --compare F   Path to previous trace for comparison
  --apply-safe  Apply safe fixes automatically
  --report      Generate markdown remediation report
  --output DIR  Directory for generated files
  --format F    Output format: text (default) or json
```

### Machine-Readable Output (`--format json`)

For agent consumption, the loop command produces stable JSON:

```json
{
  "trace": "session_abc123.jsonl",
  "score": 30.0,
  "rating": "Critical",
  "top_issues": [
    {"id": "reliability_errors", "severity": "medium", "suggestion": "..."}
  ],
  "top_actions": [
    {"label": "Add CI quality gate", "safe_to_automate": true, "requires_approval": true}
  ],
  "safe_fixes_applied": ["Add CI quality gate", "Switch to coding_agent profile"],
  "delta": {"before_score": 72.0, "after_score": 98.9, "delta": 26.9},
  "report_path": "./reports/session_abc123_report.md"
}
```

## Advanced Usage

All `loop` sub-steps are available as standalone commands for manual control or debugging.

### Manual Commands

| Command | When to Use |
|---------|-------------|
| `trace-eval run trace.jsonl --summary` | Quick score of a specific trace |
| `trace-eval run trace.jsonl --next-steps` | Score + remediation suggestions |
| `trace-eval run trace.jsonl --format json` | Machine-readable output |
| `trace-eval remediate trace.jsonl` | Full remediation with detailed actions |
| `trace-eval compare before.jsonl after.jsonl` | Before/after comparison |
| `trace-eval locate` | Find recent agent traces manually |
| `trace-eval convert input.jsonl` | Convert non-canonical trace formats |
| `trace-eval validate trace.jsonl` | Schema validation + field coverage |
| `trace-eval ci trace.jsonl --min-score 80` | CI gate (exits non-zero below threshold) |

### Scoring Profiles

| Profile | Reliability | Efficiency | Retrieval | Tool Discipline | Context |
|---------|------------|------------|-----------|-----------------|---------|
| **default** | 35% | 20% | 20% | 15% | 10% |
| **coding_agent** | 40% | 25% | 0% | 25% | 10% |
| **rag_agent** | 30% | 15% | 30% | 15% | 10% |

```bash
trace-eval run trace.jsonl --profile coding_agent
```

### Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Reliability | 35% | Did it succeed? Errors, timeouts, partial results |
| Efficiency | 20% | Token usage, cost, tool call density |
| Retrieval | 20% | Canonical entrypoint, deprecated files, fallback search |
| Tool Discipline | 15% | Retries, redundant calls, timeouts |
| Context | 10% | Context pressure, warnings, compression events |

Weights are configurable via profiles. Unscorable dimensions redistribute proportionally.

## Supported Formats

| Format | Auto-detect | Adapter |
|--------|------------|---------|
| Claude Code | Yes | Full |
| OpenClaw | Yes | Full |
| Cursor | Yes | Full |
| Canonical JSONL | Yes (passthrough) | Full |
| Hermes SQLite | N/A (load directly) | Honest/lossy |

## Real Traces Evaluated

| Trace | Source | Events | Score | Top Issue |
|-------|--------|--------|-------|-----------|
| Bad run (synthetic) | Modeled after Hermes | 11 | 32.4 | No retrieval, 3 errors, context pressure |
| Good run (synthetic) | Modeled after Hermes | 8 | 98.9 | All clear |
| Claude Code (real) | Stillness project | 3,694 | 28.3 | 90 tool errors, high token usage |
| OpenClaw (real) | Real session | 158 | 42.6 | 11 errors, zero reliability |

See [examples/case_study.md](examples/case_study.md) for a complete walkthrough with the `loop` workflow.

## What This Is NOT

- A dashboard — CLI-first, local-first
- An LLM judge — all scoring is deterministic
- An auto-fix tool — it tells you what to fix; `--apply-safe` only applies vetted safe fixes
- A broad observability platform — focused on agent trace evaluation

## License

MIT
