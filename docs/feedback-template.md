# External Alpha Feedback Collection

## Template (send this to each alpha user)

---

**trace-eval Alpha Feedback**

1. **What agent(s) do you use?** (Claude Code, Cursor, OpenClaw, other)

2. **Did `pip install trace-eval` work cleanly?**

3. **Did `trace-eval loop` find and score a trace?**
   - If yes: what score did it give? Did that feel right?
   - If no: what error did you see?

4. **Look at the "TOP 3 ISSUES" output. Did they match what you'd actually look at in the trace?**
   - Yes / Mostly / No
   - What issue did it miss that you care about?

5. **Look at the "NEXT ACTIONS" output. Did the recommended fixes make sense?**
   - Yes / Mostly / No
   - Which action felt wrong or unhelpful?

6. **Did the [AUTO-SAFE] vs [REQUIRES APPROVAL] tags feel useful?**
   - Yes / Kind of / No
   - Would you use `--apply-safe` on a real trace?

7. **Where did you get stuck or confused?**

8. **Anything the tool didn't do that you expected it would?**

9. **Would you use this again on your next agent run?**
   - Yes / Maybe / No
   - Why or why not?

---

## How to collect feedback

1. Identify 3-5 people who regularly use AI coding agents
2. Send them the alpha doc (in `docs/alpha.md`)
3. Give them 15 minutes to install + run loop on a real trace
4. Collect responses to the template above
5. Categorize into:
   - **Onboarding friction** — install, first-run, locate issues
   - **Accuracy** — false positives, missed issues, wrong scores
   - **Confusion** — unclear output, missing context
   - **Converter bugs** — format detection failures, missing fields
   - **Feature requests** — hold for later, fix adoption friction first

## Top 3 issues to track from early usage

After the first 3-5 users report back, fill in:

| # | Issue | Users Affected | Severity | Fix Plan |
|---|-------|---------------|----------|----------|
| 1 | TBD | | | |
| 2 | TBD | | | |
| 3 | TBD | | | |
