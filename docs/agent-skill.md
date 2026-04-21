# Agent Self-Evaluation with trace-eval

> After completing a meaningful task, evaluate yourself. Report the result to the user.

## When to evaluate

Evaluate after:
- Finishing a feature, refactor, or bug fix
- Encountering repeated errors or getting stuck
- Completing a multi-step workflow

Do NOT evaluate after every small prompt or during casual chat.

## What to run

```bash
trace-eval --json --hours 1
```

## How to report to the user

Parse the JSON output and report in plain English:

### If score >= 70 (Good or Excellent)

> "Session quality: {score}/100. Completed cleanly."

### If score < 70 (Fair, Poor, or Critical)

> "Session quality: {score}/100 ({rating}).
>
> Issues found:
> - {top_issues[0].suggestion}
> - {top_issues[1].suggestion}
>
> I can fix this by:
> - {top_actions[0].label}
> - {top_actions[1].label}
>
> Want me to retry with these improvements?"

### If any action is safe to automate

If an action has `safe_to_automate: true` and `requires_approval: false`:

> "I can apply {label} automatically. Should I?"

### If an action requires approval

> "I recommend {label}. This requires your approval. Want me to explain?"

## After fixing

If the user asks you to retry, run the task again and then re-evaluate:

```bash
trace-eval --json --compare path/to/previous.jsonl
```

Report: "Score changed from {before} to {after} (delta: {delta})."

## Error handling

- If trace-eval returns no trace found: "No recent traces found. Try running with a wider window."
- If the JSON parse fails: Fall back to `trace-eval` (text mode) and summarize the output.
