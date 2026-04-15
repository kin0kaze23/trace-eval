# Dogfooding Plan

## Goal

Run trace-eval against real agent traces to build evidence that the scoring and diagnostics are useful.

## Evidence Collected (2026-04-15)

### Summary

| Source | Score | Flags | Key Finding |
|--------|-------|-------|-------------|
| Hermes DB (all 299 sessions merged) | 61.7/100 | 1 critical | Correctly flags missing retrieval entrypoint |
| Real session `...e7f11f` (75 msgs, timeout) | 50.0/100 | 1 critical, 1 medium | **Reliability 0.0** — detected 18 errors across session |
| Real session `...5be004` (10 msgs, clean) | 88.9/100 | 1 critical | Only retrieval flag — no errors, good efficiency |
| Synthetic good trace | 98.9/100 | 0 | Perfect run — all dimensions high confidence |
| Synthetic bad trace | 32.4/100 | 7 flags | 3 critical, 2 high — errors, timeout, deprecated file, context pressure |
| Before/after comparison | 67.5 → 99.3 | 4 resolved | +31.9 improvement correctly quantified |

### Key Diagnoses That Worked

1. **Error detection**: Session `20260402_194007_e7f11f` scored 50.0/100 with reliability=0.0. The session had a tool timeout and 18 error-class events. trace-eval correctly identified this as the worst-performing session in the batch.

2. **Retrieval entrypoint gap**: Across all Hermes sessions, the `retrieval_no_entrypoint` flag fires consistently. This is expected — the Hermes DB doesn't populate retrieval fields, and the adapter correctly reports `has_retrieval_fields: false`. The retrieval judge compensates with proportional weight redistribution.

3. **Score differentiation**: Small clean sessions score 88.9, medium sessions with some friction score 77.2, and sessions with errors score 50.0. The scoring differentiates meaningfully despite the lossy adapter.

4. **Before/after delta**: The synthetic comparison correctly shows 4 resolved flags and quantifies +31.9 improvement.

### Limitations Observed

- **Hermes adapter is lossy by design**: The Hermes schema doesn't have `error_type`, `retrieval_entrypoint`, `retrieval_steps`, `context_pressure_pct`, or `latency_ms` fields. This means several judges can't score at full resolution.
- **Errors embedded in content, not structured**: Tool errors appear as `"status": "timeout"` or error text in the content field. The adapter doesn't parse these — it maps all tool messages to success status. This is correct honest/lossy behavior but means some issues aren't caught.
- **All sessions share the same retrieval pattern**: Since none of them have retrieval fields, they all score 50.0 on retrieval. This makes retrieval the floor, not a differentiator, for Hermes traces.

## Next Steps

### Immediate (before PyPI)
- [ ] Extract 5 more sessions with different characteristics (errors, retries, high token usage)
- [ ] Manually verify at least 2 scores against what actually happened in the session
- [ ] Add a note to README about Hermes adapter limitations

### Short-term (after PyPI, before v0.2)
- [ ] Enrich Hermes adapter to detect errors in tool content (timeout, error patterns)
- [ ] Consider a "Hermes-specific" capability report that explains what can/can't be scored
- [ ] Collect user-submitted traces once someone else uses it

### Medium-term
- [ ] Score traces from other agent frameworks (Claude Code, OpenAI, Cursor)
- [ ] Build a corpus of "known good" and "known bad" traces for validation
- [ ] Use evidence to refine scoring weights based on real-world data

## Success Criteria

- [x] 3+ distinct score levels observed (50.0, 77.2, 88.9, 98.9)
- [x] 1+ case where trace-eval correctly identified a bad run
- [x] 1+ case where comparison showed measurable improvement
- [ ] 5+ manually validated examples
- [ ] 0 major scoring bugs or false positives confirmed
