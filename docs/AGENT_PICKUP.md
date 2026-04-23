# Agent Pickup Guide — trace-eval

> **Read this first.** You're an AI agent being spawned into this repo to continue development. This file orients you in 5 minutes.

## TL;DR — What This Repo Is

`trace-eval` is a deterministic-first CLI for evaluating AI agent traces. No dashboards, no LLM-as-judge, no cloud dependency. Built for solo builders and small AI-native teams using coding/CLI agents.

Pairs with `agent-ready` (installs the tools/accounts the user's environment is missing). Together: `trace-eval` tells you what went wrong; `agent-ready` fixes the environment gaps.

## Current State (as of 2026-04-23)

- **v0.5.0 — alpha.** Production-quality. **146 tests pass.** CI green on `main`.
- Five deterministic judges live: `reliability`, `efficiency`, `retrieval`, `tool_discipline`, `context`.
- `trace-eval loop` chains locate → convert → score → remediate in one step.
- `--apply-safe` generates reviewable config/CI artifacts (never installs software).
- Adapters: Claude Code, OpenClaw, Cursor, Hermes, generic JSONL.

## What's Working Today

```bash
trace-eval doctor                          # first-run setup check
trace-eval loop                            # score your latest agent trace
trace-eval loop --apply-safe               # apply vetted safe fixes
trace-eval loop --compare before.jsonl     # measure improvement
trace-eval run trace.jsonl --format json   # machine output
```

See `README.md` for the full workflow and `CHANGELOG.md` for what shipped in each version.

## Do Not Break

- The 5-dimensional scoring rubric (in `trace_eval/scoring.py`) — weights are tunable, semantics are not.
- The `RemediationAction` catalog in `trace_eval/remediation.py` — extend, don't redefine.
- The canonical trace schema in `trace_eval/schema.py` — downstream consumers (including `agent-ready`) depend on stability.
- The `format_json` output shape — it's the agent-facing contract.

## Your Task (Pick One)

### Task A — New Adapter

**Deliverable:** `trace_eval/adapters/<name>.py` for a new agent surface (examples: Aider, OpenAI Assistants, LangChain, Continue, Copilot CLI).

See `CONTRIBUTING.md § Adding an Adapter`. Two methods required:
- `load(path: Path) -> Trace`
- `capability_report(trace: Trace | None = None) -> dict`

Register in `detect_adapter()` in `trace_eval/loader.py`. Add tests in `tests/test_<name>.py`.

### Task B — Cross-Repo Integration with agent-ready

**Deliverable:** Add a new `RemediationAction` type `install_capability` in `trace_eval/remediation.py`.

- Trigger: when `reliability_errors` flag's `suggestion` or the underlying events contain missing-tool error patterns (e.g. `command not found: vercel`).
- Action payload: the capability ID from `agent-ready`'s registry (e.g. `vercel_cli`) and a suggested command `agent-ready fix --capability vercel_cli`.
- `safe_to_automate: False, requires_approval: True` — installs always need user approval.

This closes the trace-eval → agent-ready loop natively, so `trace-eval loop` can recommend installs in addition to config-level fixes. See `agent-ready/docs/INTEGRATION.md § Option A` for context.

### Task C — New Judge

**Deliverable:** `trace_eval/judges/<name>.py` implementing `judge_<name>(events)`.

Must return a `JudgeResult` with deterministic scoring. See `CONTRIBUTING.md § Adding a Judge`. Add a weight to `DEFAULT_PROFILE` in `trace_eval/scoring.py`.

### Task D — Real Alpha Trace Collection

**Deliverable:** documented process for collecting anonymized traces from alpha users. Candidates: run trace-eval on a diverse set of real sessions, catalog gaps in adapter coverage, gaps in remediation action catalog, and any systematic scoring drift.

Output: a report `docs/alpha-findings.md` naming the top 3 adapter gaps and top 3 remediation gaps.

## Non-Negotiables

1. **146 tests must stay green.** If your change breaks any, diagnose before adjusting.
2. **Deterministic-only.** No LLM calls, no randomness, no network in the scoring path.
3. **No breaking changes to the JSON output shape** without bumping a major version and updating downstream consumers (`agent-ready`).
4. **Pre-commit hook enforces repo hygiene** — no internal working docs at root, no secret patterns, no build artifacts.
5. **Conventional commits only.** Follow the style in `git log --oneline`.

## Fast Orientation

```
trace-eval/
├── AGENT_PICKUP.md         ← you are here
├── README.md               ← product overview + daily usage
├── CHANGELOG.md            ← what shipped when
├── CONTRIBUTING.md         ← how to add an adapter / judge; code style
├── RELEASE_NOTES.md
├── LICENSE
├── pyproject.toml          ← v0.5.0
├── docs/                   ← agent skill, alpha plan, case study, validation
├── examples/               ← real and synthetic traces (Claude Code, Cursor, Hermes, OpenClaw)
├── trace_eval/
│   ├── cli.py              ← entrypoint: run / compare / validate / remediate / loop / ci / locate / convert / doctor
│   ├── loop.py             ← the headline command
│   ├── scoring.py          ← Scorecard + profile weighting
│   ├── schema.py           ← canonical event / judge types
│   ├── loader.py           ← trace loading + adapter detection
│   ├── convert.py          ← format auto-detection
│   ├── locate.py           ← find recent traces across agent directories
│   ├── doctor.py           ← onboarding diagnostics
│   ├── report.py           ← format_text / format_json / format_summary
│   ├── remediation.py      ← rule-based action recommendations
│   ├── autofix.py          ← generate reviewable safe-fix artifacts
│   ├── adapters/           ← per-format trace parsers
│   └── judges/             ← 5 scoring dimensions
└── tests/                  ← 146 tests
```

## Verify Your Environment Before You Start

```bash
cd ~/Developer/PersonalProjects/trace-eval
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q            # expect: 146 passed
```

If tests fail, **stop and file an issue.** Do not proceed.

## Relationship with agent-ready

- `trace-eval` diagnoses *agent behavior*: prompts, retries, token burn, tool discipline, CI gates.
- `agent-ready` diagnoses and fixes *environment gaps*: missing CLIs, unauthenticated tools, missing API keys.
- Both consume the same raw trace; each produces orthogonal remediation.
- Task B above (adding `install_capability` action) is the cleanest way to link them natively.

Full accounting: `agent-ready/docs/INTEGRATION.md`.

## Handoff Back

When you finish your task:
1. Update `CHANGELOG.md` with what shipped.
2. If behavior changed, bump `pyproject.toml` and `trace_eval/__init__.py`.
3. Commit + push + confirm CI green.
4. Update this file if the "Your Task" section now has different priorities.
