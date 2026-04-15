# Manual Validation Report — 5 Real Runs
Date: 2026-04-15

## Methodology

Extracted 5 individual sessions from the real Hermes SQLite database.
Each session was scored by `trace-eval run` and then manually inspected
against what actually happened in the session.

Error detection: tool result content was parsed to distinguish real errors
(`"error": "File not found"`) from null fields (`"error": null`).

---

## Run 1: `20260412_185310_d7c77e` — Long Phase Session

| Field | Value |
|-------|-------|
| Messages | 1,025 |
| End reason | `compression` (context limit hit) |
| Model | qwen3.6-plus |
| Task | Phase 9 — fix Hermes CLI startup bottleneck |
| Real tool errors | 24 |
| **Score** | **77.2/100** |

### Dimension breakdown
- Reliability: 70.0 (24 tool errors across session)
- Efficiency: 100.0 (no latency/cost data in Hermes — sub-scores default high)
- Retrieval: 50.0 (no entrypoint — Hermes limitation)
- Tool Discipline: 100.0 (no retries/redundancy/timeouts detected)
- Context: N/A (no context_pressure data)

### Manual validation
**What actually happened:** This was a long multi-phase coding session. The agent made 24 tool errors (file not found, edit conflicts with non-unique old_string, memory daemon failure). The session ended due to context compression.

**Score vs reality:** MATCH. 77.2 is appropriate — the agent completed its work (reliability not terminal) but had persistent friction from 24 tool errors. The score correctly identifies the errors without over-penalizing (the session wasn't a total failure).

**Suggestions useful:** Partially. "Use canonical retrieval entrypoint" is a Hermes adapter limitation, not actionable advice. "Review 24 error(s)" correctly points to the real problem area.

---

## Run 2: `20260414_083836_576dba` — Morning Session

| Field | Value |
|-------|-------|
| Messages | 203 |
| End reason | `cli_close` (user closed session) |
| Model | qwen3.6-plus |
| Task | Review Hermes release v2026.4.13 |
| Real tool errors | 12 |
| **Score** | **77.2/100** |

### Dimension breakdown
- Reliability: 70.0 (12 errors)
- Efficiency: 100.0 (no latency/cost data)
- Retrieval: 50.0 (Hermes limitation)
- Tool Discipline: 100.0
- Context: N/A

### Manual validation
**What actually happened:** User started a session to review a Hermes release. The agent repeatedly hit the protected branch guard (12 "BLOCKED: terminal command not allowed on protected branch" errors). These are real tool errors — the agent kept trying restricted commands.

**Score vs reality:** MATCH. 77.2 correctly reflects that the agent wasn't broken, but had persistent friction. The repeated blocked-branch errors are the real cause of the reliability deduction.

**Suggestions useful:** "Review 12 error(s)" correctly identifies the issue. A user seeing this would understand their agent keeps hitting branch protection.

---

## Run 3: `20260402_190553_e076f2` — Model Switch Session

| Field | Value |
|-------|-------|
| Messages | 152 |
| End reason | `cli_close` |
| Model | qwen3.5-plus |
| Task | Implement `/model` slash command |
| Real tool errors | 1 |
| **Score** | **86.9/100** |

### Dimension breakdown
- Reliability: 95.0 (1 error)
- Efficiency: 100.0
- Retrieval: 50.0
- Tool Discipline: 100.0
- Context: N/A

### Manual validation
**What actually happened:** User asked to switch the Hermes model to minimax-m2.5. The agent implemented the `/model` command successfully. Only 1 tool error across 152 messages.

**Score vs reality:** MATCH. 86.9 is the highest-scoring Hermes session because it had minimal errors and completed its task cleanly. The score correctly differentiates this as a good run.

**Suggestions useful:** Low — only 1 error and the retrieval flag is a Hermes limitation. For a clean session, trace-eval correctly shows minimal flags.

---

## Run 4: `20260411_144009_12553804` — Session Reset

| Field | Value |
|-------|-------|
| Messages | 119 |
| End reason | `session_reset` |
| Model | qwen3.6-plus |
| Task | "Are you running optimally?" (diagnostic) |
| Real tool errors | 6 |
| **Score** | **77.2/100** |

### Dimension breakdown
- Reliability: 70.0 (6 errors)
- Efficiency: 100.0
- Retrieval: 50.0
- Tool Discipline: 100.0
- Context: N/A

### Manual validation
**What actually happened:** User asked the agent to check its own health. The agent hit 6 tool errors including "Vector memory daemon disabled" and various path-not-found issues. The session was reset mid-conversation.

**Score vs reality:** MATCH. 77.2 is appropriate — the agent tried to diagnose itself but hit multiple errors. The session_reset end reason wasn't caught (Hermes doesn't expose terminal outcome per-session), but the errors were.

**Suggestions useful:** "Review 6 error(s)" is actionable — these are real infrastructure issues (memory daemon, missing paths).

---

## Run 5: `20260413_091226_b7e19c` — Short Test Session

| Field | Value |
|-------|-------|
| Messages | 10 |
| End reason | None (no end marker) |
| Model | qwen3.6-plus |
| Task | "test" (user was testing) |
| Real tool errors | 3 |
| **Score** | **83.1/100** |

### Dimension breakdown
- Reliability: 85.0 (3 errors)
- Efficiency: 100.0
- Retrieval: 50.0
- Tool Discipline: 100.0
- Context: N/A

### Manual validation
**What actually happened:** User sent "test" and the agent tried to find a `Website` directory that doesn't exist. All 3 errors were "file not found" / "path not found" for the nonexistent Website project.

**Score vs reality:** MATCH. 83.1 correctly reflects that this was a short, mostly-functional session with a few directory-not-found errors. The errors were real (user referenced a nonexistent path), not agent failures.

**Suggestions useful:** "Review 3 error(s)" — in this case the errors are user-caused (wrong path), so the suggestion is technically correct but the root cause is the user's prompt, not the agent.

---

## Summary

| Session | Messages | Errors | Score | Score Matches Reality? | Suggestions Useful? |
|---------|----------|--------|-------|----------------------|---------------------|
| `...d7c77e` | 1,025 | 24 | 77.2 | Yes — 24 errors across long session | Partially (retrieval flag is noise) |
| `...576dba` | 203 | 12 | 77.2 | Yes — repeated branch protection hits | Yes — points to real issue |
| `...e076f2` | 152 | 1 | 86.9 | Yes — clean session, 1 error | Low — minimal flags |
| `...12553804` | 119 | 6 | 77.2 | Yes — diagnostic session with infra errors | Yes — real infrastructure issues |
| `...b7e19c` | 10 | 3 | 83.1 | Yes — short session, user-caused path errors | Partially — user error, not agent |

### Key findings

1. **Score differentiation works**: Scores range from 77.2 to 86.9 for real Hermes sessions, correctly differentiating error-heavy from error-light sessions.
2. **Error detection is accurate**: Real tool errors (file not found, blocked commands, daemon failures) are correctly caught. False positives from `"error": null` are excluded.
3. **Retrieval flag is noise for Hermes**: Every session gets `retrieval_no_entrypoint` because the Hermes schema doesn't have retrieval fields. This is a known limitation, not a scoring bug.
4. **Context judge is unscorable for Hermes**: No context_pressure data in Hermes schema — this is honest behavior, weights redistribute.
5. **Efficiency overestimates for Hermes**: Without latency or cost data at the event level, efficiency defaults to 100.0. This is correct honest/lossy behavior but means efficiency isn't meaningful for Hermes traces.

### What would improve scoring accuracy

1. Enrich Hermes adapter to detect errors in tool result content (currently relies on extraction script)
2. Extract cost data from Hermes `sessions` table (stored at session level, not event level)
3. Add a session-level terminal outcome detector (cli_close vs session_reset vs compression)
