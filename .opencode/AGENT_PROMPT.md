# OpenCode Agent Prompt — trace-eval

> Paste this into your OpenCode session when initializing an agent in this repo.

---

## Prompt (Lane B — Cross-Repo Integration)

You are an AI coding agent working on the `trace-eval` repo (v0.5.0). Your task is issue **#1 — add `install_capability` RemediationAction**.

**Read first** (in order):
1. `docs/AGENT_PICKUP.md`
2. `README.md`
3. `CHANGELOG.md`
4. `CONTRIBUTING.md`
5. `trace_eval/remediation.py` (the file you will modify)
6. `trace_eval/schema.py`
7. `../agent-ready/docs/INTEGRATION.md` § Option A — the full cross-repo context
8. Issue #1 via `gh issue view 1`

**Your deliverable:** add a new entry `install_capability` to `ACTION_TYPES` in `trace_eval/remediation.py`, plus trigger logic in `analyze_with_context()` that scans friction flags + event references for known missing-tool patterns and emits the new action.

**Work on a branch:** `feat/install-capability-action`.

**Non-negotiables:**
- The 146 existing tests must stay green. Verify with `pytest tests/ -v` before opening the PR.
- Do NOT add `agent-ready` as a dependency. The action references `agent-ready`'s capability IDs by string only.
- The capability ID mapping lives as a small static dict at the top of `remediation.py` for v1. Do NOT import from agent-ready's schemas.
- `safe_to_automate: False, requires_approval: True` — trace-eval defers to agent-ready's approval model; never auto-installs.
- Add new tests in `tests/test_remediation.py` covering: hit detection, dedup, ordering, and the action payload shape.
- Update `CHANGELOG.md` under a new section `0.6.0 (2026-04-24)`. Bump `pyproject.toml` and `trace_eval/__init__.py` to `0.6.0`.
- Conventional commit style: `feat: add install_capability action type for agent-ready integration`.
- Never `--no-verify`. Pre-commit hook must pass.

**Capability ID mapping to use for v1** (copy exactly — coordinated with agent-ready):

```python
_CAPABILITY_HINTS = {
    # pattern (case-insensitive regex) → agent-ready capability ID
    r"command not found:\s*vercel": "vercel_cli",
    r"vercel:\s*command not found": "vercel_cli",
    r"command not found:\s*gh\b": "github_cli",
    r"gh:\s*command not found": "github_cli",
    r"command not found:\s*node\b": "nodejs",
    r"node:\s*command not found": "nodejs",
    r"command not found:\s*python3?": "python",
    r"python3?:\s*command not found": "python",
    r"ModuleNotFoundError": "python",
    r"Cannot find module\s+['\"]": "nodejs",
}
```

**Scope guardrails:**
- Do NOT modify the 5-dimension scoring rubric.
- Do NOT refactor `remediation.py` beyond adding the new action type.
- Do NOT modify judges, schema, loader, or loop.
- Do NOT change the JSON output shape beyond appending the new action objects to the existing `top_actions` list.

**When done:**
1. Run `trace-eval run examples/claude_code_real.jsonl --format json` and verify the new action appears if the trace contains missing-tool patterns (it may not; test with a synthetic fixture instead).
2. Add a fixture `tests/fixtures/trace_missing_vercel.jsonl` if needed.
3. Open PR against `main` with clear before/after examples.
4. Wait for owner approval. Do not merge yourself.
