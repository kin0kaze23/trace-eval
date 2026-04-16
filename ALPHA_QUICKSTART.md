# trace-eval Alpha Quickstart

> **Goal:** Score your AI agent's session in under 2 minutes.

## Install

```bash
pip install trace-eval
```

No dependencies. No cloud. No API keys. Python 3.11+.

## Step 1: Find Your Trace

trace-eval works with agent session files. Here's where to find them:

| Agent | Where to find traces |
|-------|---------------------|
| Claude Code | `~/.claude/projects/<project-id>/session.jsonl` |
| OpenClaw | `~/.openclaw/<session-id>/session.jsonl` |
| Cursor | `~/.cursor/projects/<project-id>/agent-transcripts/<id>/<id>.jsonl` |

If you have a `.db` file (Hermes), trace-eval reads it directly — no convert needed.

## Step 2: Convert (if needed)

If your trace is from Claude Code, OpenClaw, or Cursor, convert it:

```bash
# Auto-detects format — just point it at the file
trace-eval convert your-session.jsonl -o trace.jsonl
```

That's it. No format flag needed. It reads the first few lines and figures it out.

If it fails, tell it explicitly:

```bash
trace-eval convert claude-code your-session.jsonl -o trace.jsonl
trace-eval convert openclaw your-session.jsonl -o trace.jsonl
trace-eval convert cursor your-session.jsonl -o trace.jsonl
```

If you already have canonical JSONL (with `event_type` fields), skip convert — trace-eval reads it directly.

## Step 3: Score It

```bash
trace-eval run trace.jsonl
```

You'll get a scorecard like this:

```
============================================================
  TRACE-EVAL SCORECARD  Total: 28.3/100
============================================================

DIMENSION SCORES:
  reliability             0.0  (high)
  efficiency             30.0  (high)
  retrieval               N/A  (low) *
  tool_discipline        92.0  (high)
  context                 N/A  (low) *
```

### Quick Summary

For a shorter output (great for agents or quick scanning):

```bash
trace-eval run trace.jsonl --summary
```

Output:

```
Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. fix errors (0/100 reliability). reduce token/tool usage.
```

### For Your Agent Type

Different agents need different scoring weights:

```bash
# Coding agents (coding-focused, no retrieval)
trace-eval run trace.jsonl --profile coding_agent

# RAG agents (retrieval-heavy)
trace-eval run trace.jsonl --profile rag_agent
```

## Step 4: Compare Before vs After

If you've made changes and want to see if they helped:

```bash
trace-eval compare before.jsonl after.jsonl
```

Quick comparison:

```bash
trace-eval compare before.jsonl after.jsonl --summary
```

Output:

```
Before: 32.4/100
After:  98.9/100
Delta:  +66.5
Resolved: 7 flags
```

## Step 5: Gate Your CI (optional)

Add a quality threshold to your CI pipeline:

```bash
trace-eval ci trace.jsonl --min-score 70 --profile coding_agent
```

Exits with code 1 if the score is below 70. See `examples/github-actions/agent-quality.yml` for a full GitHub Actions example.

## Troubleshooting

### "could not detect trace format"

Your file isn't in a recognized format. Check:
- Is it actually a JSONL file? (one JSON object per line)
- For Claude Code: does it have `type` fields like `"user"`, `"assistant"`, `"tool_result"`?
- For OpenClaw: does the first event have `"type": "session"` with `"cwd"`?
- For Cursor: does it have `"role"` fields like `"user"`, `"assistant"`, `"toolResult"`?

If auto-detect fails, specify explicitly: `trace-eval convert claude-code file.jsonl`

### "No events in trace"

The file was read but no events were extracted. This can happen if:
- The file is empty
- The format doesn't match any known converter
- The JSONL is malformed (broken JSON on a line)

### Score is lower than expected

trace-eval scores what's in the trace, not what the agent claimed. A low score means:
- Errors happened (reliability)
- Too many tokens were used (efficiency)
- Tools were misused (tool discipline)

This is the point of trace-eval — it tells you the truth about the run, not the agent's self-assessment.

### "command not found: trace-eval"

Make sure trace-eval is installed:

```bash
pip show trace-eval
```

If it's installed but not on PATH:

```bash
python -m trace_eval.cli run trace.jsonl
```

### JSON output not parsing correctly

Use `--format json` for stable, machine-readable output. The JSON structure is guaranteed to always include: `total_score`, `dimension_scores`, `friction_flags`, `likely_causes`, `suggestions`, `scorable_dimensions`, `unscorable_dimensions`.

## Need Help?

- **Full README:** https://github.com/kin0kaze23/trace-eval/blob/main/README.md
- **Case study:** https://github.com/kin0kaze23/trace-eval/blob/main/examples/case_study.md
- **Issues:** https://github.com/kin0kaze23/trace-eval/issues

If something doesn't work or is confusing, please open an issue. This is alpha software and your feedback shapes what gets fixed next.
