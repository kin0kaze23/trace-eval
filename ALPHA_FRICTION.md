# Alpha Onboarding: Top 3 Friction Points to Watch

> These are the most likely places a first-time user will get stuck with trace-eval.
> Watch for these during alpha outreach. Fix them before adding new features.

---

## Friction Point 1: Finding the Trace File

**Why it's likely:** Users don't know where their agent stores session files. The paths are deep and vary by agent:

- Claude Code: `~/.claude/projects/<long-uuid>/<long-uuid>/session.jsonl`
- OpenClaw: `~/.openclaw/<session-id>/session.jsonl`
- Cursor: `~/.cursor/projects/<project-id>/agent-transcripts/<id>/<id>.jsonl`

**What it looks like:** "I have Claude Code but I don't know where my trace file is."

**How to watch for it:** Count how many users can't find their trace file without looking it up. If > 1 out of 3, add a `trace-eval locate` helper command or better docs.

**Fix priority:** HIGH — if users can't find their trace, nothing else matters.

---

## Friction Point 2: Auto-Detect Failing on Real Files

**Why it's likely:** Auto-detect reads the first 5 lines looking for type signatures. But:

- Claude Code files sometimes start with `file-history-snapshot` events (we fixed this in Sprint 4, but edge cases may exist)
- Users may have truncated files, mixed-format files, or files with non-JSON lines
- Cursor sessions with only text messages (no tool calls) might not look like a "real" trace

**What it looks like:** `Error: could not detect trace format for your-file.jsonl`

**How to watch for it:** Every time a user reports format detection failure, log the file's first 10 lines. Build a corpus of missed formats.

**Fix priority:** HIGH — auto-detect is the promise that makes "just run it on my trace" work. If it breaks, users assume the tool doesn't support their agent at all.

---

## Friction Point 3: Understanding What the Score Means

**Why it's likely:** A score of 28.3/100 is not inherently meaningful without context. Users will ask:

- "Is 28 good or bad?" (bad, but they need to know the scale)
- "What should my score be?" (depends on the task, but we need a baseline answer)
- "Why is reliability 0 but the agent finished?" (because it had errors even though it completed)
- "What does N/A mean?" (dimension not applicable, weight redistributed — but that's jargon)

**What it looks like:** Users get the scorecard but don't know what action to take next.

**How to watch for it:** Count how many users ask "what should I do with this?" after seeing their first scorecard. If > 1 out of 3, the `--summary` diagnosis text needs improvement.

**Fix priority:** MEDIUM — the scorecard is useful even without perfect interpretability, but if users can't act on it, they won't come back.

---

## Lower Priority Friction Points (watch but don't pre-fix)

| Friction | Likelihood | Why lower priority |
|----------|-----------|-------------------|
| `pip install` fails on old Python | Low — we check >= 3.11 | Error message is clear |
| JSONL file is corrupted | Low — rare in practice | `convert` will fail cleanly |
| User wants to eval a format we don't support | Medium — LangChain, OpenAI traces | "Not yet" is an acceptable answer for alpha |
| CI gate threshold confusion | Medium — what threshold to set? | Users will experiment; `--min-score 70` is a reasonable default |

---

## What NOT to Fix Yet

These are common instincts but would be premature optimization:

- **Adding more converters** — we have 3 + canonical. That's enough for alpha.
- **Making scores absolute** ("this is a good score") — we don't have baseline data yet.
- **Adding a web UI** — the CLI is the right interface for this stage.
- **LLM-as-judge** — defeats the deterministic-first promise and adds complexity.

Fix the 3 friction points above first. Then repeat based on what users actually tell us.
