# Contributing to trace-eval

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
