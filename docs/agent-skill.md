# Agent Skill: Self-Evaluate with trace-eval

> After completing a meaningful task, run `trace-eval loop --format json` to self-evaluate.

## Trigger

After any meaningful agent task:
- Finished a feature or refactor
- Fixed a bug
- Completed a multi-step workflow
- Encountered errors or got stuck

Do NOT trigger after every small prompt or during casual chat.

## What to Run

```bash
trace-eval loop --format json
```

## How to Parse the Result

Parse the JSON output for these fields:

```json
{
  "score": 30.0,
  "rating": "Critical",
  "top_issues": [
    {"id": "reliability_errors", "severity": "medium", "suggestion": "Review 31 error(s)..."},
    {"id": "efficiency_high_tokens", "severity": "medium", "suggestion": "Reduce token usage..."},
    {"id": "efficiency_high_tool_calls", "severity": "low", "suggestion": "Excessive tool calls..."}
  ],
  "top_actions": [
    {"label": "Add CI quality gate", "safe_to_automate": true, "requires_approval": true},
    {"label": "Fix command errors", "safe_to_automate": false, "requires_approval": true},
    {"label": "Use appropriate scoring profile", "safe_to_automate": true, "requires_approval": false}
  ]
}
```

## Decision Flow

1. **If `score >= 70`**: Report to user: "Run scored {score}/100 [{rating}]. No issues detected."
2. **If `score < 70`**: Report top issues and proposed actions to user:
   ```
   My last run scored {score}/100 [{rating}].
   Top issues:
   - {top_issues[0].suggestion}
   - {top_issues[1].suggestion}

   I recommend:
   - {top_actions[0].label} (safe to auto-apply / requires your approval)
   ```
3. **If any action has `safe_to_automate: true` and `requires_approval: false`**: Ask user: "I can apply {label} automatically. Should I?"
   - If yes: `trace-eval loop --apply-safe`
4. **If any action has `requires_approval: true`**: Show the user what it would do. Only proceed with explicit approval.

## Compare After Fix

After applying fixes or retrying the task:

```bash
trace-eval loop --compare path/to/previous.jsonl
```

Report: "Score changed from {before} to {after} (delta: {delta:+.1f})."

## Error Handling

- If `trace-eval loop` returns no trace found: Report "No recent traces found. Try `trace-eval loop --hours 72`."
- If the JSON parse fails: Fall back to running `trace-eval loop` in text mode and summarize the output.
