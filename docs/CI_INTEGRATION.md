# CI Integration Guide

> Use trace-eval as a quality gate in your CI/CD pipeline. Prevent low-quality agent runs from being merged.

## Quick Start

Add this step to your GitHub Actions workflow:

```yaml
- name: Evaluate agent trace quality
  run: |
    pip install trace-eval
    trace-eval ci --min-score 80
```

This auto-locates the most recent agent trace, scores it, and fails the job if the score is below 80.

## How It Works

`trace-eval ci` is a dedicated CI gate command that:

1. Locates the most recent agent trace (same as `trace-eval loop`)
2. Converts it to canonical format if needed
3. Scores it across all 5 dimensions
4. Exits with code **1** if the score is below `--min-score`
5. Exits with code **0** if the score meets the threshold

## Usage

### Basic: Gate on a specific trace file

```yaml
- name: Check trace quality
  run: trace-eval ci examples/claude_code_real.jsonl --min-score 80
```

### Auto-locate: Gate on the most recent trace

```yaml
- name: Check latest agent trace
  run: trace-eval ci --min-score 70
```

### With profile

```yaml
- name: Check coding agent quality
  run: trace-eval ci --profile coding_agent --min-score 75
```

### With extended search window

```yaml
- name: Check trace (last 7 days)
  run: trace-eval ci --hours 168 --min-score 80
```

## Recommended Thresholds

| Use case | Min score | Profile |
|----------|-----------|---------|
| Strict quality gate (production deploys) | 90 | coding_agent |
| Standard PR gate | 80 | default |
| Lenient gate (early development) | 60 | default |
| RAG agent evaluation | 70 | rag_agent |

## Full Workflow Example

```yaml
name: Agent Quality Gate

on:
  pull_request:
    branches: [main]

jobs:
  agent-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install trace-eval
        run: pip install trace-eval

      - name: Run quality gate
        run: trace-eval ci --profile coding_agent --min-score 80

      - name: Show details on failure
        if: failure()
        run: trace-eval run --format json | head -50
```

## Output

On success:
```
Score: 85.3/100 [Good] ✓ PASS (threshold: 80)
```

On failure:
```
Score: 62.1/100 [Needs Work] ✗ FAIL (threshold: 80)
Top issues:
  - reliability_errors (medium) — Review 12 error(s)
  - efficiency_high_tokens (medium) — Reduce token usage
```

## JSON Output for Programmatic Use

```bash
trace-eval ci --format json
```

Returns:
```json
{
  "passed": true,
  "score": 85.3,
  "rating": "Good",
  "threshold": 80,
  "top_issues": [...]
}
```

## Combining with trace-eval loop

The CI command is a subset of `loop` — it only scores and gates. For local development, use `loop` for full diagnostics:

| Command | Purpose |
|---------|---------|
| `trace-eval loop` | Full local diagnostics (locate, score, remediate) |
| `trace-eval ci` | CI-only gate (score + pass/fail exit code) |
| `trace-eval loop --compare before.jsonl` | Measure improvement locally |

## Tips

1. **Store baseline traces** — Keep a `baseline.jsonl` of a known-good run and compare against it
2. **Use `--profile coding_agent`** for coding tasks — it weights retrieval at 0% since code agents don't typically do file search
3. **Don't set the threshold too high** — A score of 80+ is good. 90+ is excellent but may be unrealistic for complex tasks
4. **Run `trace-eval doctor` first** in your workflow to confirm traces are available before gating
