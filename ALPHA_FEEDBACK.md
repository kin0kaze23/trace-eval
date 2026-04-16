# Alpha User Feedback Template

> **For:** trace-eval alpha users
> **Purpose:** Collect where users get stuck so we can fix the real onboarding friction.

---

## How to Use This Template

When a user tries trace-eval during alpha, fill in this template after their session. Use it as a GitHub issue, a shared doc, or a form response.

---

## User Context

| Field | Value |
|-------|-------|
| Date | |
| User name / handle | |
| How they heard about trace-eval | |
| What agent they use | Claude Code / Cursor / OpenClaw / Other: ___ |
| What they wanted to eval | (describe the agent task) |
| Python version | `python --version` → |
| OS | macOS / Linux / Windows / WSL |

## Install Experience

| Question | Answer |
|----------|--------|
| Did `pip install trace-eval` work? | Yes / No — error: ___ |
| Did they use pip or uv? | pip / uv |
| How long did it take? | < 1 min / 1-5 min / > 5 min |
| Any confusion about install? | Notes: ___ |

## Convert Experience

| Question | Answer |
|----------|--------|
| Did they have a trace file? | Yes / No — couldn't find one |
| Where was their trace? | Path: ___ |
| Did auto-detect work? | Yes / No — had to specify format |
| Did `convert` succeed? | Yes / No — error: ___ |
| How many events converted? | ___ |
| Any confusion about convert? | Notes: ___ |

## Run Experience

| Question | Answer |
|----------|--------|
| Did `trace-eval run` work? | Yes / No — error: ___ |
| What score did they get? | ___ /100 |
| Did they understand the scorecard? | Yes / Somewhat / No |
| Did they try `--summary`? | Yes / No |
| Did they try `--profile`? | Yes / No — which: ___ |
| Did they try `--format json`? | Yes / No |
| Any confusion about run? | Notes: ___ |

## Compare Experience (if tried)

| Question | Answer |
|----------|--------|
| Did they have a before + after trace? | Yes / No |
| Did `compare` work? | Yes / No — error: ___ |
| Did they understand the delta? | Yes / Somewhat / No |
| Did they try `compare --summary`? | Yes / No |
| Any confusion about compare? | Notes: ___ |

## CI Gate Experience (if tried)

| Question | Answer |
|----------|--------|
| Did they try the CI gate? | Yes / No |
| Did they use the GitHub Actions example? | Yes / No |
| Did it work in their CI? | Yes / No — error: ___ |
| Any confusion about CI? | Notes: ___ |

## Overall

| Question | Answer |
|----------|--------|
| Would they use trace-eval again? | Definitely / Probably / Maybe / No |
| What was the most useful output? | Scorecard / Summary / Compare / CI gate / Nothing stood out |
| What was the most confusing thing? | ___ |
| What feature would they want next? | ___ |
| What agent workflow do they want to eval? | ___ |

## Friction Log

List every point where the user hesitated, asked a question, or got stuck — in order.

| # | Step | What happened | How long stuck | How they recovered | Severity |
|---|------|---------------|----------------|-------------------|----------|
| 1 | | | | | High/Med/Low |
| 2 | | | | | High/Med/Low |
| 3 | | | | | High/Med/Low |

Severity:
- **High** — blocked, couldn't proceed without help
- **Med** — confused but found a way through
- **Low** — minor hesitation, would be clearer with better docs

## Quotes

Verbatim things the user said that are insightful:

> "..."

> "..."

## Next Action

- [ ] Fix bug: ___
- [ ] Improve docs: ___
- [ ] Add feature: ___ (only if it's onboarding friction, not a new feature)
- [ ] Nothing — worked end to end
