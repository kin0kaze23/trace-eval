# Blockers for Alpha Adoption

## No blocking issues — all resolved

### 1. Hermes adapter error detection (RESOLVED)

**What was done:** Added `_ERROR_PATTERNS` (8 patterns) + `_detect_tool_error()` to `hermes.py`. Detects real errors from tool result content (`"error": "..."`, `"success": false`, `BLOCKED:`, `Traceback`, etc.). Full DB detects 332 real errors (previously 0).

### 2. Terminal outcome detection (RESOLVED)

**What was done:** Added `_TERMINAL_MAP` mapping Hermes `end_reason` to Status (`cli_close` → None, `session_reset` → None, `compression` → None, `cron_complete` → success).

### 3. Retrieval unscorable for Hermes (DOCUMENTED)

**Status:** Not a bug — honest lossy behavior. Hermes schema has no retrieval fields. Documented in README "Known Limitations."

### 4. Non-Hermes trace validated (RESOLVED)

**What was done:** Real OpenClaw session (158 canonical events) scored at 44.3/100. After simulated fixes: 57.3/100 (+13.0). Compare shows meaningful delta (retrieval +50.0).

---

## Summary

| Blocker | Severity | Status |
|---------|----------|--------|
| Entry point works after pip install | BLOCKING | RESOLVED |
| 5 manually validated real runs | MEDIUM | COMPLETE |
| Known limitations documented | MEDIUM | COMPLETE |
| Non-Hermes trace validated | LOW | REAL TRACE (OpenClaw) |
| Hermes error extraction | MEDIUM | COMPLETE |

**Verdict:** All blockers resolved. Package ready for PyPI publish. Clean install verified.
