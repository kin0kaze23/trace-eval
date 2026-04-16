# Sprint 5 Deliverable Report
Date: 2026-04-17

## Deliverables

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| Public case study | **DONE** | `examples/case_study.md` — synthetic bad→good + real Claude Code (3,694 events) + real OpenClaw (158 events) |
| `--summary` flag | **DONE** | `trace-eval run --summary`, `trace-eval compare --summary`, 7 new tests |
| Cursor converter | **DONE** | `convert_cursor()`, auto-detect, 6 new tests, sample file |
| README onboarding | **DONE** | 5-step quick start: install → convert → run → compare → ci |
| v0.3.0 ready | **DONE** | Version bumped, 81 tests pass (all green) |

## Test Summary

```
81 passed in 0.57s
```

New tests added this sprint:
- `test_summary_has_score`, `test_summary_has_top_flags`, `test_summary_has_diagnosis`, `test_summary_is_concise`, `test_summary_good_run` (5 tests)
- `test_run_summary`, `test_compare_summary` (2 tests)
- `test_convert_cursor_basic`, `test_convert_cursor_tool_calls`, `test_convert_cursor_tool_result_error`, `test_convert_cursor_tool_result_success`, `test_cursor_auto_detect`, `test_convert_cursor_sample_file` (6 tests)

---

## Next 3 Highest-Leverage Adoption Moves

### Move 1: Publish the case study publicly (1-2 hours)

**Why:** Proof of value is the #1 adoption driver. We have 4 agent frameworks validated and real error detection. A public-facing post showing "90 errors diagnosed in under 1 second" would be the most effective way to get people to try it.

**Content ready:** `examples/case_study.md` has three parts:
1. Synthetic bad→good walkthrough (demonstrates the full workflow)
2. Real Claude Code session (3,694 events, 90 errors)
3. Real OpenClaw session (158 events, 11 errors)

**Where to post:** README section (done), GitHub discussion, blog post, or social thread.

### Move 2: Get 3-5 external users to run `pip install trace-eval` (1-3 days)

**Why:** Watching real users hit friction is the best product feedback. Set up:
- Share the PyPI link with people who use AI coding agents
- Ask them to run `trace-eval convert` on a recent session + `trace-eval run`
- Watch where they get stuck — that tells you the next real product move

**What to watch for:**
- Does `pip install trace-eval` work on their machine?
- Can they find their trace files?
- Does auto-detect work for their agent?
- Do they understand the scorecard output?

### Move 3: Add a CI/CD integration example (1 hour)

**Why:** Teams want to gate their agent runs. A copy-pasteable `.github/workflows/trace-eval.yml` would lower the barrier to adoption.

```yaml
name: Agent Quality Gate
on: [push]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install trace-eval
      - run: trace-eval convert agent-trace.jsonl -o trace.jsonl
      - run: trace-eval ci trace.jsonl --min-score 70 --profile coding_agent
```

## What NOT to do next

- LLM-as-judge
- Dashboards
- Auto-fix
- Major framework redesign
- Many new profiles
- Broad adapter expansion ("support everything")
