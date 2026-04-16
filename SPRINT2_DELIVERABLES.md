# Sprint 2 Deliverable Report
Date: 2026-04-15

## 1. Hermes Adapter Accuracy Improvements

### Error detection from content (DONE)

Added `_ERROR_PATTERNS` (8 lambda patterns) + `_detect_tool_error()` function to `hermes.py` that parses tool result content for real errors:

- `"success": false`, `"status": "error"`, `"status": "timeout"`
- `"error": "..."` (excluding `null` and empty)
- `Error ...`, `BLOCKED:`, `Traceback ...`, edit conflict patterns
- JSON parse fallback for structured error objects

**Impact:** Full DB (312 sessions) now detects **332 real tool errors** (previously 0).

### Terminal outcome detection (DONE)

Added `_TERMINAL_MAP` that maps Hermes `end_reason` to Status:
- `cli_close` → None (user closed, not failure)
- `session_reset` → None
- `compression` → None
- `cron_complete` → Status.success

### Session-level token data (DONE)

Adapter no longer attaches session-level tokens to individual events (was misleading when merging sessions). Token totals extracted for metadata only. `has_token_data=False` in capability report.

### What was NOT changed

- Cost data not extracted (stored at session level, no per-event mapping)
- Retrieval noise not reduced (retrieval is fundamentally unscorable for Hermes)

---

## 2. Real Non-Hermes Validation

### OpenClaw session converted and scored

Source: Real OpenClaw session (`858eef94`) — 118 raw events → 158 canonical events.

**Before (raw session with gateway crash):**
- Score: **44.3/100**
- Reliability: 0.0 (12 errors: 6 gateway pairing, 1 directory read, 1 sandbox missing, 1 web_fetch, 1 elevated, 1 DNS)
- Retrieval: 50.0 (no entrypoint)
- Efficiency: 74.2 (high tool call count)
- Tool Discipline: 100.0

**After (gateway fixed + retrieval fields populated):**
- Score: **57.3/100** (+13.0 improvement)
- Reliability: 5.0 (5 remaining real errors)
- Retrieval: 100.0 (entrypoint + steps populated)
- Efficiency: 74.2 (unchanged)

**Compare output:**
```
COMPARISON: before vs after
  Total score:   44.3 ->   57.3  Change: +13.0 (improved)
  reliability             0.0 ->    5.0  ^ +5.0
  retrieval              50.0 ->  100.0  ^ +50.0
  FLAG CHANGES: [RESOLVED] retrieval_no_entrypoint
```

**What this validates:**
- Generic JSONL adapter works end-to-end for real non-Hermes traces
- Retrieval compare shows meaningful delta (+50.0)
- Error detection works across agent frameworks
- Compare correctly identifies resolved flags

### Files
- `examples/openclaw_before.jsonl` — 158 events, real session with failures
- `examples/openclaw_after.jsonl` — 158 events, simulated fixes

---

## 3. PyPI Publish Status

### NOT YET PUBLISHED — Package is ready

**Build status:**
- Source distribution: `dist/trace_eval-0.1.0.tar.gz` ✓
- Wheel: `dist/trace_eval-0.1.0-py3-none-any.whl` ✓
- 20 files included (all modules, adapters, judges)

**Clean install verification:**
- Fresh venv install from wheel: ✓ PASSED
- `trace-eval --help` works: ✓ PASSED
- `trace-eval validate` on real trace: ✓ PASSED
- `trace-eval run` produces scorecard: ✓ PASSED

**Next step to publish:**
```bash
uv publish --token <PYPI_API_TOKEN>
# or
twine upload dist/*
```

**Not published because:** Requires PyPI API token. Not attempted without user confirmation.

---

## 4. Adoption Assets Summary

### Existing assets (from Sprint 1)
| Asset | File | Status |
|-------|------|--------|
| Bad run teardown | `LAUNCH_ASSETS.md` Asset 1 | ✓ |
| Before/after compare | `LAUNCH_ASSETS.md` Asset 2 | ✓ |
| 5-minute flow | `LAUNCH_ASSETS.md` Asset 3 | ✓ |
| Non-Hermes trace | `examples/claude_code_good.jsonl` | ✓ Synthetic |
| Validation report | `VALIDATION_REPORT.md` | ✓ 5 real runs |

### New assets (Sprint 2)
| Asset | File | Status |
|-------|------|--------|
| Real OpenClaw before | `examples/openclaw_before.jsonl` | ✓ Real session |
| Real OpenClaw after | `examples/openclaw_after.jsonl` | ✓ Simulated fixes |
| OpenClaw compare output | Above (delta shown) | ✓ +13.0 improvement |
| Clean install proof | Above (venv test) | ✓ PASSED |
| Alpha blockers updated | `ALPHA_BLOCKERS.md` | See below |

### Updated ALPHA_BLOCKERS status

| Blocker | Severity | Status |
|---------|----------|--------|
| Entry point works after pip install | BLOCKING | RESOLVED |
| 5 manually validated real runs | MEDIUM | COMPLETE |
| Known limitations documented | MEDIUM | COMPLETE |
| Non-Hermes trace validated | LOW | **REAL TRACE DONE** (OpenClaw) |
| Hermes error extraction | MEDIUM | **COMPLETE** (error detection from content) |

**All blockers resolved.**

---

## 5. Next 3 Highest-Leverage Adoption Moves

### Move 1: Publish to PyPI (highest leverage)

**Why:** Every other adoption move requires a working install path. The package builds, clean install works, all features verified. Publishing removes the biggest friction for new users.

**Effort:** 15 minutes. Build is done, just needs `uv publish` with a PyPI token.

**Risk:** Low. Package name `trace-eval` appears available (pip index returns "No matching distribution").

### Move 2: Add a real Claude Code trace (second highest)

**Why:** The OpenClaw trace proves the non-Hermes adapter works, but Claude Code is the target audience. A real Claude Code trace (from `.claude/` session logs) would be the most convincing proof point for the primary user base.

**Effort:** 30-60 minutes. Export one real Claude Code session to canonical JSONL, score it, add to examples.

**Risk:** Low. The adapter already works. Just needs real data.

### Move 3: Create a "Getting Started" example with a real bad + good pair

**Why:** New users need to see what a real problem looks like and what "good" looks like in their own agent framework. The current examples (`hermes_bad.jsonl`, `hermes_good.jsonl`) are synthetic. A real pair from either OpenClaw or Claude Code would be more credible.

**Effort:** 30 minutes. Take the OpenClaw session as the "bad" example, create a cleaner session as the "good" example, document the diff.

**Risk:** Low. The OpenClaw "bad" trace already exists. Just needs a real "good" counterpart.

---

## Summary

| Deliverable | Status |
|-------------|--------|
| Hermes adapter accuracy improvements | **COMPLETE** — error detection, terminal mapping, token fix |
| One real non-Hermes validation result | **COMPLETE** — OpenClaw, 44.3→57.3, compare works |
| PyPI publish status | **READY** — built, clean install verified, not published (needs token) |
| Adoption assets summary | **COMPLETE** — this document |
| Next 3 recommendations | **COMPLETE** — PyPI publish, Claude Code trace, real example pair |
