# Project Rules: trace-eval

## Strategic Context (read first)

This repo is one of three products in the AI Workstation Suite (Pulse · trace-eval · agent-ready). Before any non-trivial work, read the suite-level strategy at:

`/Users/jonathannugroho/Developer/PersonalProjects/AI_WORKSTATION_SUITE.md`

Your product's specific role: **§5.2 — trace-eval: every session, scored, plain-English.** Deterministic scoring · MCP server · passive file-watcher · plain-English issues. Read-only by design (no destructive operations).

When the strategy and this file conflict, the strategy doc wins for vision and direction; this file wins for repo-local execution rules.

---

After completing any meaningful task, always evaluate your work with trace-eval before reporting completion.

## How to use

1. **Score your session:**
   ```bash
   trace-eval loop --format json
   ```

2. **Read the output:**
   - `score` — overall quality (0-100). 80+ is good, below 60 needs attention.
   - `rating` — "Excellent", "Good", "Needs Work", or "Critical".
   - `top_issues` — what went wrong.
   - `top_actions` — what to fix.

3. **Auto-fix safe issues:**
   If any action has `"safe_to_automate": true` and `"requires_approval": false`, run:
   ```bash
   trace-eval loop --apply-safe
   ```

4. **For issues that need approval:**
   Show the user the recommended actions and ask before applying them.

5. **Compare improvement (optional):**
   If the user has a baseline trace:
   ```bash
   trace-eval loop --compare before.jsonl
   ```

## Quick reference

| Command | Use |
|---------|-----|
| `trace-eval loop` | Score latest session |
| `trace-eval loop --apply-safe` | Auto-fix safe issues |
| `trace-eval ci --min-score 80` | Quality gate |
| `trace-eval doctor` | Check setup |

## When to skip

- Trivial edits (typos, formatting)
- Quick questions (non-task interactions)
- Mid-task (only evaluate when a task is complete)
