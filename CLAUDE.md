# Project Rules: trace-eval

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
