# Blockers for Alpha Adoption

## No blocking issues — but 3 friction points to address

### 1. Hermes adapter doesn't extract errors from content (medium friction)

**Problem:** The Hermes adapter maps tool messages to `status: "success"` regardless of whether the tool result contains an error. The manual validation script had to parse `"error": "..."` from JSON content to detect real errors.

**Impact:** All real Hermes sessions are scored without error awareness at the adapter level. The dogfood validation worked because the extraction script added `status: "error"` manually.

**Fix scope:** Add 15 lines to `hermes.py` — parse tool result content for `"error"` field, set `status` accordingly.

**Adoption risk:** Low. Users who export their Hermes DB will get accurate scores for everything *except* error counts. The score will be slightly inflated (no error penalty).

### 2. Retrieval always 50.0 for Hermes traces (low friction)

**Problem:** The Hermes schema doesn't have retrieval fields, so the retrieval judge always scores the no-entrypoint baseline (50.0).

**Impact:** Retrieval is not a differentiator for Hermes users. The README now documents this clearly.

**Fix scope:** Not a bug — honest lossy behavior. Could be improved by adding a note in the capability report: "retrieval unscorable for this adapter."

**Adoption risk:** None. Already documented in README "Known Limitations."

### 3. No real-world non-Hermes trace example yet (low friction)

**Problem:** The only non-Hermes example (`claude_code_good.jsonl`) is synthetic. A real Claude Code, Cursor, or other agent trace hasn't been scored yet.

**Impact:** Users of other agents can't see proof that the generic JSONL adapter works on real traces.

**Fix scope:** Export one real trace from any agent framework to canonical JSONL, score it, add to examples.

**Adoption risk:** Low. The adapter interface is simple and the synthetic example validates the pipeline. Real traces will confirm it.

---

## Summary

| Blocker | Severity | Status |
|---------|----------|--------|
| Entry point works after pip install | BLOCKING | RESOLVED |
| 5 manually validated real runs | MEDIUM | COMPLETE |
| Known limitations documented | MEDIUM | COMPLETE |
| Non-Hermes trace validated | LOW | SYNTHETIC ONLY |
| Hermes error extraction | MEDIUM | DEFERRED (15-line fix) |

**Verdict:** Ready for alpha adoption. No hard blockers. The 3 friction points are documented, scoped, and non-blocking for initial users who understand this is v0.1.0.
