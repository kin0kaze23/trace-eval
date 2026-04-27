# trace-eval

> Did your AI agent do a good job? Find out in 3 seconds.

A local-first CLI that scores your AI agent sessions, tells you what went wrong, and recommends what to fix. No dashboards. No API calls. No cloud. Just run a command and get a clear answer.

## 30-Second Start

```bash
pip install trace-eval
trace-eval doctor        # first run — checks your setup
trace-eval loop          # after any agent task — scores it instantly
```

That's it. One command tells you if your agent session was healthy or needs attention.

## What It Looks Like

```
$ trace-eval loop
============================================================
  TRACE-EVAL  v0.6.0  |  Score: ✗ 32/100 [Critical]
============================================================

  a40af304.jsonl (817KB)
  Claude Code | 46h 23m

  Issues found:
  ~ Review 5 error(s) at event indices [65, 204, 218, 230, 233]
  ~ Reduce token usage with more focused prompts
  . Excessive tool calls detected

  Recommended actions:
  1. [needs your OK] Add CI quality gate
  2. [needs your OK] Fix 5 command error(s)
  3. [auto-fix] Use appropriate scoring profile
```

At a glance:
- **✗ 32/100** — score icon tells you instantly (✓ = good, ~ = fair, ! = poor, ✗ = critical)
- **Issues found** — what went wrong, in plain English
- **Recommended actions** — what to do about it, with clear tags for what's auto-fixable

## When to Use It

| When | Command |
|------|---------|
| After a meaningful agent task | `trace-eval loop` |
| After a frustrating run (errors, stuck, wasted tokens) | `trace-eval loop` |
| Before merging a PR | `trace-eval ci --min-score 80` |
| To compare before/after | `trace-eval loop --compare before.jsonl` |

## What's a "Session Recording"?

A **session recording** is just a log of everything your AI agent did — every command it ran, every file it read, every error it hit, every token it used. AI agents like Claude Code, Cursor, and OpenClaw automatically save these as you work.

trace-eval reads that recording and tells you:
- **Did it succeed?** (errors, timeouts)
- **Was it efficient?** (token usage, tool calls)
- **What should you fix?** (specific, actionable recommendations)

## Integrating with Your AI Agent

trace-eval works with any AI agent that saves session traces. Here's how to connect it:

### Claude Code

Drop this file at the root of your project:

```markdown
# CLAUDE.md — Add trace-eval self-evaluation

After completing any meaningful task, run:
  trace-eval loop --format json

Read the score and top_actions. If an action has safe_to_automate: true
and requires_approval: false, run:
  trace-eval loop --apply-safe

Otherwise, show the user the issues and ask for approval.
```

Or just tell Claude Code: *"After each task, run `trace-eval loop` and fix any issues it finds."*

### OpenClaw / Cursor / Other Agents

Any agent that can run shell commands can use trace-eval the same way. Just add to your project's agent instructions:

> After completing a task, evaluate it with `trace-eval loop`. If the score is below 80, review the recommended actions and fix the top issues before reporting completion.

### CI/CD Quality Gate

Add to your GitHub Actions to block low-quality agent work:

```yaml
- name: Check agent quality
  run: trace-eval ci --min-score 80
```

## Commands You'll Actually Use

| Command | What it does |
|---------|-------------|
| `trace-eval loop` | Score your latest agent session |
| `trace-eval loop --apply-safe` | Auto-fix safe issues |
| `trace-eval ci --min-score 80` | Quality gate (exits non-zero if too low) |
| `trace-eval doctor` | Check your setup and find sessions |
| `trace-eval loop --compare before.jsonl` | See if things improved |

## Advanced Commands

<details>
<summary>Full command reference (click to expand)</summary>

| Command | Use case |
|---------|----------|
| `trace-eval run trace.jsonl` | Score a specific session file |
| `trace-eval run trace.jsonl --next-steps` | Score + remediation suggestions |
| `trace-eval run trace.jsonl --profile coding_agent` | Use coding-focused scoring |
| `trace-eval compare before.jsonl after.jsonl` | Before/after comparison |
| `trace-eval locate` | Find recent agent sessions |
| `trace-eval convert input.jsonl` | Convert session formats |
| `trace-eval validate trace.jsonl` | Check if a session file is valid |
| `trace-eval remediate trace.jsonl` | Full remediation report |
| `trace-eval loop --report --output ./reports` | Generate markdown report |

### Scoring Presets

| Preset | Best for |
|---------|----------|
| `default` | General agent evaluation |
| `coding_agent` | Coding tasks (weights tool discipline higher, retrieval at 0%) |
| `rag_agent` | RAG/search-heavy workflows |

### Daily Aliases

```bash
alias tev="trace-eval loop"
alias tevd="trace-eval doctor"
alias tevs="trace-eval loop --apply-safe"
```

</details>

## Supported Agents

| Agent | Auto-detect | Notes |
|-------|------------|-------|
| Claude Code | ✅ | Full support |
| OpenClaw | ✅ | Full support |
| Cursor | ✅ | Full support |
| Canonical JSONL | ✅ | Standard format for custom agents |
| Hermes (SQLite) | ✅ | Direct load |

Adding a new agent connector? See [CONTRIBUTING.md](CONTRIBUTING.md).

## How Scoring Works

trace-eval scores across 5 score areas:

| Score Area | What it measures |
|-----------|-----------------|
| Reliability | Did it succeed? Errors, timeouts, partial results |
| Efficiency | Token usage, cost, tool call density |
| Retrieval | Did it find the right files efficiently? |
| Tool Discipline | Retries, redundant calls, timeouts |
| Context | Context pressure, warnings, compression |

All scoring is **deterministic** — same session always gets the same score. No LLM calls, no randomness, no cloud API.

## What This Is NOT

- ❌ A dashboard — CLI-first, local-first
- ❌ An LLM judge — all scoring is rule-based and reproducible
- ❌ An auto-fix tool — it tells you what to fix; `--apply-safe` only applies vetted safe fixes
- ❌ A broad observability platform — focused on agent session evaluation

## Docs

- [Architecture](docs/ARCHITECTURE.md) — how it works under the hood
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common issues and fixes
- [CI Integration](docs/CI_INTEGRATION.md) — using trace-eval in CI/CD pipelines
- [Contributing](CONTRIBUTING.md) — how to add connectors, checkers, or features

## License

MIT
