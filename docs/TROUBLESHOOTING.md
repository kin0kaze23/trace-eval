# Troubleshooting Guide

## Installation Issues

### `pip install trace-eval` fails

Make sure you're using **Python 3.11 or newer**:

```bash
python3 --version   # must be >= 3.11
```

If you're on an older Python, use a virtual environment with a newer version:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install trace-eval
```

### `trace-eval: command not found` after installation

The script may not be on your PATH. Fix with:

```bash
pip install --user trace-eval
# or reinstall in your active virtual environment
pip install --force-reinstall trace-eval
```

---

## Trace Discovery Issues

### `No recent traces found`

This means `trace-eval` couldn't find any agent session files in the last 48 hours.

**Common causes:**

1. **Agent not installed** — You need at least one supported AI agent (Claude Code, Cursor, OpenClaw) installed and used recently.

2. **Traces are older than 48 hours** — Widen the search window:
   ```bash
   trace-eval loop --hours 168   # search last 7 days
   ```

3. **Agent ran a different working directory** — `trace-eval` searches standard agent directories. If your agent was configured to store traces elsewhere, use a direct file path:
   ```bash
   trace-eval run /path/to/trace.jsonl
   ```

### `trace-eval doctor` says 0 traces found for an agent I use

Check that the agent actually stores JSONL traces:

| Agent | Default trace location |
|-------|----------------------|
| Claude Code | `~/.claude/projects/` |
| OpenClaw | `~/.openclaw/sessions/` |
| Cursor | `~/.cursor/` |

If the directory exists but has no `.jsonl` files, your agent may be storing traces in a different format. Use `trace-eval convert` to check:

```bash
trace-eval convert /path/to/trace-file
```

---

## Scoring Issues

### Score seems too low / too high

Scores are deterministic — they're computed from the trace data alone. If a score seems off:

1. **Check which flags fired:**
   ```bash
   trace-eval run trace.jsonl --format json
   ```
   Look at `friction_flags` in the output.

2. **Check dimension scores:**
   ```bash
   trace-eval run trace.jsonl   # shows per-dimension breakdown
   ```

3. **Try a different profile:**
   If you're evaluating a coding agent task, the `default` profile may weight retrieval too heavily:
   ```bash
   trace-eval run trace.jsonl --profile coding_agent
   ```

### `retrieval` dimension shows N/A

This is normal for coding agents that don't perform file search during their session. The retrieval dimension weight is redistributed proportionally to the other dimensions.

If you want to see the N/A score as 0 instead, it's by design — N/A dimensions are excluded from the total score calculation.

### Score is different between runs on the same trace

This shouldn't happen — scoring is fully deterministic. If you see this:

1. Make sure you're running against the **same trace file** (check the path)
2. Make sure you're using the **same profile** (`--profile`)
3. Check for a `trace-eval` version mismatch:
   ```bash
   trace-eval doctor   # shows current version
   ```

---

## Conversion Issues

### `Could not detect trace format`

Your trace file may be in an unsupported format. Currently supported:

| Format | File extension | Detection |
|--------|---------------|-----------|
| Claude Code | `.jsonl` | Auto |
| OpenClaw | `.jsonl` | Auto |
| Cursor | `.jsonl` | Auto |
| Canonical JSONL | `.jsonl` | Auto (passthrough) |
| Hermes | `.db` or `.sqlite` | Direct load |

If your file is a JSONL but not recognized, it may be malformed. Check the first line:

```bash
head -1 /path/to/trace.jsonl | python3 -m json.tool
```

Each line must be valid JSON with at minimum: `event_index`, `actor`, `event_type`, `timestamp`, `status`.

### `Conversion failed`

This usually means the trace file is corrupted or uses a newer schema version than trace-eval supports. Check:

```bash
trace-eval validate /path/to/trace.jsonl
```

---

## Apply-Safe Issues

### `--apply-safe` didn't create any files

Safe fixes only apply when specific conditions are met:

| Condition | Fix generated |
|-----------|--------------|
| Low score (< 80) | CI gate YAML file |
| Default profile + retrieval N/A | CLI snippet to switch profile |
| Token/tool flags | Prompt scope reduction suggestions |

If none of these conditions apply, no fixes are generated. Run `trace-eval loop` without `--apply-safe` to see what actions are recommended.

### Where do `--apply-safe` files go?

By default, files are created in the current directory. Use `--output` to specify a location:

```bash
trace-eval loop --apply-safe --output ./eval-reports
```

---

## CI Integration Issues

### `trace-eval ci` exits with non-zero even though the trace looks OK

The CI gate checks the total score against a minimum threshold (default: 80). Adjust the threshold:

```bash
trace-eval ci trace.jsonl --min-score 60
```

Or use a profile that better matches your workflow:

```bash
trace-eval ci trace.jsonl --profile coding_agent --min-score 70
```

---

## Getting Help

If your issue isn't covered here:

1. Check the [GitHub Issues](https://github.com/kin0kaze23/trace-eval/issues) for similar reports
2. Run `trace-eval doctor` and include the output in your issue
3. Include the trace file (or a sanitized version) when reporting scoring bugs
