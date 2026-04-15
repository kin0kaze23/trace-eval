# v0.1.0 — Initial Release

**Deterministic-first CLI for evaluating AI agent traces.**

## What's in this release

### 5-Dimension Scorecard
- **Reliability** (35%) — errors, timeouts, terminal outcome, partial results
- **Efficiency** (20%) — token usage, cost estimation, tool call density
- **Retrieval** (20%) — canonical entrypoint usage, deprecated file access, fallback search
- **Tool Discipline** (15%) — retries, redundant calls, timeouts
- **Context** (10%) — context pressure, compression events, warnings
- Proportional weight redistribution when a dimension is unscorable

### CLI Commands
- `trace-eval validate trace.jsonl` — schema validation + field coverage bars + adapter report
- `trace-eval run trace.jsonl` — scorecard with root causes and friction flags
- `trace-eval compare before.jsonl after.jsonl` — delta view with resolved/new flag tracking
- `trace-eval ci trace.jsonl --min-score 80` — CI gate (exit 0=pass, 1=fail)
- All commands support `--format json` for agent consumption

### Adapters
- **Generic JSONL** — full capability, inspects actual field presence (not hardcoded)
- **Hermes SQLite** — honest/lossy adapter for the real Hermes DB schema (sessions + messages tables). Tested against 12,455 events across 299 sessions.

### Agent Integration
- Stable JSON output with `likely_causes`, `suggestions`, `friction_flags`, `judge_coverage`, `adapter_capability_report`
- Designed for direct use in agent remediation loops

### Test Suite
- 68 tests passing
- CI workflow configured (`.github/workflows/ci.yml`)

## What works today
- Score any JSONL trace file with the canonical format
- Score real Hermes SQLite databases
- Compare two traces to see what improved/regressed
- Gate CI pipelines with minimum score thresholds
- Agent remediation via `--format json` output

## What is explicitly deferred
- **No dashboards** — CLI-first by design
- **No LLM-as-judge** — all scoring is deterministic
- **No auto-fix** — tells you what to fix, not how
- **No broad observability** — focused on agent trace evaluation only
- **No more adapters yet** — no OpenAI, LangSmith, or LangGraph adapters until real usage data demands them
- **No score profiles** — balanced profile only for now
- **No baseline comparison** — not yet comparing cost vs similar tasks
- **No parallelization analysis** — Tool Discipline measures retries/redundancy/timeouts but not parallel tool calls

## Known limitations
- Hermes adapter is lossy by design: no span IDs, no latency data, no retrieval fields (these come from the Hermes schema itself)
- Context judge returns unscorable when no context_pressure data exists
- Cost estimation depends on tokens + cost_estimate fields being present in the trace

## Dogfood evidence
- Real Hermes DB (12,455 events): scored 61.7/100 — correctly identified missing retrieval entrypoint as sole critical issue
- Synthetic good trace: 98.9/100 — all dimensions high confidence
- Synthetic bad trace: 32.4/100 — 7 friction flags across 3 dimensions, 3 critical, 2 high
- Before/after comparison: correctly shows +31.9 improvement with 4 resolved flags
