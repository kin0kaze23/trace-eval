# Architecture Overview

> How trace-eval works under the hood. Read this if you want to write a custom judge, adapter, or integrate trace-eval into your own tooling.

## High-Level Design

trace-eval is a **deterministic-first** evaluation CLI. Every score is computed from trace data alone — no LLM calls, no randomness, no network requests in the scoring path.

```
┌─────────────┐    ┌──────────┐    ┌────────┐    ┌─────────────┐
│   Locate    │ -> │ Convert  │ -> │ Score  │ -> │  Remediate  │
│ find traces │    │ canonical│    │ judges │    │  actions    │
└─────────────┘    └──────────┘    └────────┘    └─────────────┘
```

The `loop` command chains all four steps. Each step is also available as a standalone CLI command.

## Module Map

```
trace_eval/
├── cli.py              # argparse entrypoint, all subcommands
├── loop.py             # orchestration: locate → convert → score → remediate
├── locate.py           # filesystem search across agent directories
├── convert.py          # format auto-detection + conversion
├── loader.py           # trace loading + adapter capability reports
├── scoring.py          # Scorecard computation, profile weighting
├── schema.py           # canonical types: Event, Trace, FrictionFlag, etc.
├── report.py           # output formatting: text, JSON, summary
├── remediation.py      # rule-based action recommendations
├── autofix.py          # generate safe-fix artifacts
├── doctor.py           # onboarding diagnostics
├── adapters/           # per-format trace parsers
│   ├── claude_code.py
│   ├── openclaw.py
│   ├── cursor.py
│   └── hermes.py
└── judges/             # 5 scoring dimensions
    ├── reliability.py
    ├── efficiency.py
    ├── retrieval.py
    ├── tool_discipline.py
    └── context.py
```

## Canonical Trace Schema

All adapters convert their native format into the **canonical schema** defined in `schema.py`:

```python
@dataclass
class Event:
    event_index: int          # sequential position in trace
    actor: str                # "user" | "assistant" | "tool"
    event_type: EventType     # message, llm_call, tool_call, etc.
    timestamp: str            # ISO 8601
    status: Status            # success, error, partial, timeout
    # ... 30+ optional fields for tokens, costs, context, etc.
```

The schema is **stable** — downstream consumers (including `agent-ready`) depend on it. Breaking changes require a major version bump.

## Scoring Pipeline

### 1. Judges

Each judge examines the full event list and returns a `JudgeResult`:

```python
@dataclass
class JudgeResult:
    score: float | None        # 0-100, or None if unscorable
    confidence: str            # "high" | "medium" | "low"
    friction_flags: list[FrictionFlag]
    explanation: str
    raw_metrics: dict
    scorable: bool
```

The five judges:

| Judge | Measures | Key metrics |
|-------|----------|-------------|
| `reliability` | Did it succeed? | Error count, timeouts, partial results |
| `efficiency` | Resource usage | Token count, tool call density, cost |
| `retrieval` | File access quality | Entrypoint usage, deprecated files, fallback search |
| `tool_discipline` | Tool call quality | Retries, redundant calls, timeouts |
| `context` | Context health | Pressure %, warnings, compression events |

### 2. Scorecard Computation

Judges feed into `compute_scorecard()` in `scoring.py`:

1. Filter out unscorable judges (missing required data)
2. Apply profile weights (default, coding_agent, rag_agent)
3. Redistribute weights proportionally for unscorable dimensions
4. Compute weighted average → total score (0-100)
5. Map to rating: Excellent (90+), Good (70-89), Needs Work (40-69), Critical (<40)

### 3. Profiles

| Profile | Reliability | Efficiency | Retrieval | Tool Discipline | Context |
|---------|------------|------------|-----------|-----------------|---------|
| default | 35% | 20% | 20% | 15% | 10% |
| coding_agent | 40% | 25% | 0% | 25% | 10% |
| rag_agent | 30% | 15% | 30% | 15% | 10% |

## Remediation Engine

The remediation module (`remediation.py`) uses a **rule-based system** to map friction flags and dimension scores to recommended actions:

```
Rules input: Scorecard + Events
         ↓
Rule engine: if flag X → action Y
         ↓
Enrichment: replace generic labels with specific data (tool names, counts)
         ↓
Sort: confidence (high first), then action_type alphabetically
         ↓
Output: top 5 RemediationAction objects
```

Action types:

| Action | Triggered by | Auto-safe? |
|--------|-------------|------------|
| `fix_errors` | reliability_errors flag | No (requires approval) |
| `reduce_prompt_size` | efficiency_high_tokens | No |
| `reduce_tool_calls` | efficiency_high_tool_calls | No |
| `reduce_retries` | tool_retries / tool_redundant | Yes |
| `improve_retrieval` | retrieval_* flags | No |
| `switch_profile` | retrieval N/A on default profile | Yes |
| `add_ci_gate` | total_score < 80 | Yes |
| `install_capability` | missing-tool patterns detected | No |

## Adapters

Each adapter implements two methods:

```python
def load(path: Path) -> Trace:
    """Read native trace file, return canonical Trace."""

def capability_report(trace: Trace | None = None) -> dict:
    """Report what fields/features are available in this format."""
```

Auto-detection in `_detect_format()` checks file patterns, JSON keys, and structure to identify the format before loading.

## Extension Points

### Adding a Judge

1. Create `trace_eval/judges/<name>.py`
2. Implement `def judge_<name>(events: list[Event]) -> JudgeResult`
3. Register in `JUDGES` dict in `loop.py`
4. Add weight to profiles in `scoring.py`
5. Add tests

### Adding an Adapter

1. Create `trace_eval/adapters/<name>.py`
2. Implement `load()` and `capability_report()`
3. Register in `detect_adapter()` in `loader.py`
4. Add auto-detection logic in `convert.py`
5. Add tests

## Design Decisions

### Why deterministic?

LLM-as-judge is expensive, non-reproducible, and adds latency. Deterministic rules are:
- **Free** — no API calls
- **Reproducible** — same trace = same score, always
- **Transparent** — users can see exactly why a score was given
- **Fast** — scoring takes milliseconds

### Why no randomness?

Reproducibility is critical for:
- Comparing before/after scores
- CI gating (same PR should always pass/fail)
- Debugging scoring discrepancies
- Building trust in the tool

### Why 5 dimensions?

These emerged from analyzing real agent traces across multiple sessions. They cover the full lifecycle:
1. **Did it work?** (reliability)
2. **Was it efficient?** (efficiency)
3. **Did it find the right files?** (retrieval)
4. **Did it use tools well?** (tool_discipline)
5. **Did it manage context?** (context)

More dimensions can be added, but these 5 cover 95% of real-world agent friction.
