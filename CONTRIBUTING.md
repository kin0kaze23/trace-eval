# Contributing to trace-eval

## Pull Request Process

### Merge Gate Checklist

Before merging any PR, verify:

1. **PR remains draft** until independent review completes
2. **Review targets current head SHA** — not an outdated commit
3. **Material changes after review require re-review** — do not merge unreviewed updates
4. **CI passes on the reviewed head** — lint, tests, and build must succeed
5. **Only then may the PR be marked ready and merged**

### Why This Matters

The PR #10 correction pass merged before independent re-review completed. This process violation was recorded to prevent recurrence. The merge gate ensures:

- Every change receives independent verification
- Review confidence remains high
- CI validates the exact code that was reviewed
- No unreviewed material changes sneak through

### PR Lifecycle

1. **Draft** — Open PR with clear description
2. **Review** — Independent reviewer examines current head SHA
3. **Fixes** — If material changes needed, push updates and request re-review
4. **CI** — Wait for all checks to pass on reviewed head
5. **Merge** — Squash-merge with conventional commit message

## Adding an Adapter

1. Create `trace_eval/adapters/<name>.py`
2. Implement two methods:
   - `load(path: Path) -> Trace` — read the trace file and return canonical events
   - `capability_report(trace: Trace | None = None) -> dict` — report what fields are available
3. Register it in `detect_adapter()` in `trace_eval/loader.py`
4. Add tests in `tests/test_<name>.py`
5. Update the README adapter table

## Adding a Judge

1. Create `trace_eval/judges/<name>.py`
2. Implement `def judge_<name>(events: list[Event]) -> JudgeResult`
3. Register it in the `JUDGES` dict in `trace_eval/cli.py`
4. Add it to `DEFAULT_PROFILE` in `trace_eval/scoring.py` with a weight (default: 0.15)
5. Add tests in `tests/test_<name>.py`

## Running Tests

```bash
uv sync --all-extras
uv run pytest tests/ -v
```

## Code Style

- Type hints on all functions
- Dataclasses for data, not dicts where types matter
- Deterministic-only logic (no LLM calls, no randomness)
