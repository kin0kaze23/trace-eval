# External Alpha — trace-eval v0.5.0

## Install

```bash
pip install trace-eval
trace-eval --version  # should show 0.5.0
```

If PyPI hasn't updated yet, install from GitHub:

```bash
pip install git+https://github.com/kin0kaze23/trace-eval.git@v0.5.0
```

## Quick Test

```bash
# 1. Evaluate your latest agent trace (auto-detects Claude Code, OpenClaw, Cursor)
trace-eval loop

# 2. Machine-readable output
trace-eval loop --format json

# 3. Compare to a previous run
trace-eval loop --compare before.jsonl
```

## Troubleshooting

### "No recent traces found"
The loop command searches your filesystem for recent agent trace files.
- Increase the search window: `trace-eval loop --hours 72`
- Or score a specific file: `trace-eval run path/to/trace.jsonl --summary`

### "Score computation failed"
The trace file may be corrupted or in an unsupported format.
- Validate it first: `trace-eval validate path/to/trace.jsonl`
- Convert if needed: `trace-eval convert path/to/trace.jsonl`

### Trace from an unsupported agent
Currently supported: Claude Code, OpenClaw, Cursor, and any agent that produces JSONL traces with canonical event structure.
- Your trace file needs to be JSONL (one JSON object per line)
- Each event should have at minimum: `event_type`, `event_index`, `timestamp`

## What to Report

After trying it, send feedback on:

1. **Installation** — did `pip install trace-eval` work? Any issues?
2. **First run** — did `trace-eval loop` find and score a trace?
3. **Top 3 issues** — did they match what you'd actually look at in the trace?
4. **Top 3 actions** — did the recommended fixes make sense?
5. **Approval tags** — did [AUTO-SAFE] vs [REQUIRES APPROVAL] feel useful?
6. **Where you got stuck** — any confusing error messages or dead ends?
7. **What you expected** — anything the tool didn't do that you thought it would?
