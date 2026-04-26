# Agent Integration Guide

> How to make any AI agent self-evaluate with trace-eval.

## The Pattern

Every AI agent that saves session traces can use trace-eval the same way:

1. Agent completes a task
2. Agent runs `trace-eval loop --format json`
3. Agent reads the score and recommended actions
4. Agent auto-fixes safe issues, asks user for the rest
5. Agent reports completion with the score

This turns trace-eval into a **quality gate** that runs automatically after every task.

---

## Claude Code

Claude Code automatically reads `CLAUDE.md` files. Drop one at your project root:

**`CLAUDE.md`**
```markdown
# Project Rules: trace-eval

After completing any meaningful task, evaluate your work:

1. Run: trace-eval loop --format json
2. Read score (80+ is good, below 60 needs attention)
3. If any action has safe_to_automate: true and requires_approval: false:
   → Run: trace-eval loop --apply-safe
4. Otherwise, show the user the issues and ask for approval
5. Report completion with the score

Skip for trivial edits (typos, formatting) or quick questions.
```

Or just tell Claude Code in conversation:
> *"After each task, run `trace-eval loop` and fix any issues it finds."*

---

## OpenClaw

OpenClaw reads `AGENTS.md` or `AGENT_PROMPT.md` in your project root.

**`AGENTS.md`**
```markdown
# Self-Evaluation

After completing a task, run:
  trace-eval loop --format json

- Score 80+: report completion
- Score 60-79: show user issues, ask if they want fixes
- Score < 60: fix top issues before reporting

Auto-fix actions with safe_to_automate: true without asking.
```

---

## Cursor

Cursor doesn't have a built-in agent instruction file, but you can:

1. Add trace-eval to your project's **Cursor Rules** (Settings → Rules)
2. Or tell Cursor in the chat:

> *"After completing tasks, run `trace-eval loop` to check quality. Fix issues if score is below 80."*

---

## Opencode

Opencode reads `.opencode/AGENT_PROMPT.md`. Use the same pattern as Claude Code:

**`.opencode/AGENT_PROMPT.md`** (excerpt)
```markdown
## Quality Check

After completing a meaningful task:
1. Run `trace-eval loop --format json`
2. If score < 80, review top_issues and fix the top 1-2
3. Run `trace-eval loop --apply-safe` for any auto-fixable issues
4. Report the final score to the user
```

---

## Custom Agents

Any agent that can:
1. Run shell commands
2. Read JSON output
3. Make decisions based on the output

Can integrate with trace-eval. Here's the generic prompt:

```
After completing a meaningful task:

1. Run: trace-eval loop --format json
2. Parse the JSON output
3. If score >= 80: task is done, report completion
4. If score < 80:
   a. Show the user the top_issues
   b. For each action in top_actions:
      - If safe_to_automate is true AND requires_approval is false:
        → Run: trace-eval loop --apply-safe
      - Otherwise: ask the user for approval
5. Re-run trace-eval loop and report the new score
```

---

## CI/CD Integration

For team workflows, add a quality gate to your CI:

**GitHub Actions:**
```yaml
- name: Check agent quality
  run: |
    pip install trace-eval
    trace-eval ci --min-score 80
```

**What this does:**
- Scores the latest agent session
- Fails the build if score is below 80
- Ensures no low-quality agent work gets merged

---

## Troubleshooting

### "No recent traces found"

The agent hasn't saved a session file yet. Run a meaningful task first, then try again.

### "trace-eval: command not found"

Install it: `pip install trace-eval`

### Score seems wrong

Run with `--details` for a full breakdown:
```bash
trace-eval loop --details
```

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for more.
