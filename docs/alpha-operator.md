# Alpha Operator Pack — trace-eval v0.5.0

> For the person running the alpha. Contains scripts, checklists, and decision criteria.

## Target: 3–5 External Users

Recruit people who:
- Use Claude Code, Cursor, or OpenClaw regularly
- Have run AI agents on real tasks (not just toy examples)
- Willing to spend 5 minutes and give structured feedback

---

## Alpha Invitation Template

```
Hey — I built a CLI tool for evaluating AI agent runs. It's called trace-eval.

It scores your agent traces across 5 dimensions (reliability, efficiency, retrieval, tool discipline, context), tells you the top 3 issues, and recommends specific fixes. No dashboards, no LLM judge, no cloud.

I'm looking for 3-5 people to try it and tell me where it breaks. Takes ~5 minutes.

If you're interested, I'll send you the test script.
```

---

## Pre-Alpha Checklist (Run Before Inviting Users)

- [ ] `__init__.py` version matches `pyproject.toml` (both `0.5.0`)
- [ ] `pip install -e .` works in a clean venv
- [ ] `trace-eval doctor` runs and shows correct output
- [ ] `trace-eval loop` finds and scores a trace
- [ ] `trace-eval loop --format json` produces valid JSON
- [ ] `trace-eval remediate trace.jsonl` shows contextual suggestions
- [ ] `trace-eval loop --hours 0` shows improved error message with guidance
- [ ] All tests pass: `python -m pytest tests/ -q`
- [ ] README quickstart starts with `trace-eval doctor`

---

## Alpha Execution Checklist

For each user:

### Before
- [ ] Send invitation (use template above)
- [ ] Send `docs/alpha.md` test script
- [ ] Confirm which agent they use
- [ ] Confirm Python version (`python --version`)

### During (if doing live session)
- [ ] Watch them run `pip install trace-eval` — note any friction
- [ ] Watch them run `trace-eval doctor` — note any confusion
- [ ] Watch them run `trace-eval loop` — does it find their trace?
- [ ] Watch them read the output — do they understand the score?
- [ ] Watch them read remediation — do the suggestions make sense?
- [ ] Note every hesitation, question, or error

### After
- [ ] Collect completed feedback checklist
- [ ] Record friction log (each stuck point, severity, recovery)
- [ ] Note any feature requests (flag as "blocker" or "nice-to-have")
- [ ] Thank the user

---

## Feedback Aggregation Template

After all users, fill this in:

### Install Friction
| User | Install Worked? | Time | Issue |
|------|----------------|------|-------|
| 1    |                |      |       |
| 2    |                |      |       |
| 3    |                |      |       |

### Doctor Experience
| User | Detected Correct Agent? | Found Traces? | Understood Recommendation? |
|------|------------------------|---------------|---------------------------|
| 1    |                        |               |                           |
| 2    |                        |               |                           |
| 3    |                        |               |                           |

### Score Trust
| User | Score Made Sense? | Rating Accurate? | Top Issues Matched? | Top Actions Useful? |
|------|-------------------|------------------|---------------------|---------------------|
| 1    |                   |                  |                     |                     |
| 2    |                   |                  |                     |                     |
| 3    |                   |                  |                     |                     |

### Approval Tags
| User | Tags Useful? | Would Trust Auto-Safe? |
|------|-------------|------------------------|
| 1    |             |                        |
| 2    |             |                        |
| 3    |             |                        |

### Top 3 Friction Points (Ranked by Frequency)
1. **Friction:** ___ — Seen in ___/___ users
   - **User quotes:** ___
   - **Fix:** ___

2. **Friction:** ___ — Seen in ___/___ users
   - **User quotes:** ___
   - **Fix:** ___

3. **Friction:** ___ — Seen in ___/___ users
   - **User quotes:** ___
   - **Fix:** ___

---

## Decision Criteria for Next Sprint

### If ≥ 2 users hit the same friction point → **Fix it in next sprint**

### If users request a new adapter (e.g., Claude Desktop) → **Evaluate effort vs. impact**

### If users say "scores don't match my intuition" → **Investigate scoring logic**

### If users say "I'd use this daily" → **You have product-market fit signal**

### If users say "I wouldn't use this again" → **Find out why before building anything**

---

## What NOT to Do During Alpha

- Do NOT add new features during alpha
- Do NOT change scoring formulas mid-alpha
- Do NOT expand to more than 5 users until you've fixed the top friction
- Do NOT ignore negative feedback — it's the most valuable signal
- Do NOT defend the product — listen and record

---

## Success Criteria

- [ ] 3-5 users completed the full alpha script
- [ ] At least 2 users can reach `doctor → loop` without help
- [ ] Top 3 friction points identified and documented
- [ ] At least 1 user said "I'd use this again" (signal of value)
- [ ] Clear priority for next sprint based on real data, not assumptions
