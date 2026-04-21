# v0.5.0 — External Alpha Release

**Deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency.**

## Quick Start

```bash
pip install trace-eval
trace-eval doctor    # verify setup, find traces
trace-eval loop      # evaluate latest trace
trace-eval remediate trace.jsonl  # get specific fix recommendations
```

## What's in this release

### Core Workflow
- `trace-eval doctor` — diagnose installation, detect agents, find traces, recommend next steps
- `trace-eval loop` — locate → convert → score → remediate in one command
- `trace-eval run` — score a specific trace with 5 deterministic dimensions
- `trace-eval remediate` — specific, contextual fix recommendations (which tool failed, how often, what pattern)
- `trace-eval compare` — delta between two traces
- `trace-eval ci` — CI quality gate
- `trace-eval convert` — format auto-detection for Claude Code, OpenClaw, Cursor
- `trace-eval validate` — schema validation + field coverage

### Scoring Profiles
- `default` — balanced profile (reliability 35%, efficiency 20%, retrieval 20%, tool discipline 15%, context 10%)
- `coding_agent` — coding-focused (reliability 40%, efficiency 25%, tool discipline 25%, context 10%)
- `rag_agent` — retrieval-focused (reliability 30%, efficiency 15%, retrieval 30%, tool discipline 15%, context 10%)

### Agent Integration
- Stable JSON output with `score`, `rating`, `top_issues`, `top_actions`, `safe_to_automate`, `requires_approval`
- Both human-readable text and machine-readable JSON on every command
- Agent self-check pattern documented in `docs/agent-skill.md`

### What works today
- Auto-detect and evaluate traces from Claude Code, OpenClaw, Cursor
- Score with 5 deterministic dimensions (reliability, efficiency, retrieval, tool discipline, context)
- Get specific remediation: "Bash failed 36 times with exit_code_1" not just "fix errors"
- Compare before/after to measure improvement
- Gate CI pipelines on agent run quality
- Agent self-evaluation via `--format json`

### What is explicitly NOT in this release
- No dashboards — CLI-first by design
- No LLM-as-judge — all scoring is deterministic
- No auto-fix — tells you what to fix; `--apply-safe` only generates vetted config artifacts
- No broad observability — focused on agent trace evaluation only
- No plugin system
- No watch/follow mode

### Known limitations
- Hermes SQLite adapter is lossy by design (no span IDs, no latency, no retrieval fields)
- Context judge is unscorable when no context_pressure data exists
- Efficiency scoring requires token/cost fields in the trace

### Test suite
- 146 tests passing
