# I Scored My AI Agent's Session. It Failed at 28/100. Here's What I Found.

---

My AI coding agent just spent an hour refactoring a project. It "finished" the task. But something felt off — repeated Bash failures, context warnings, and the whole session dragged longer than it should have.

Instead of scrolling through 3,694 events looking for what went wrong, I ran a tool I built called [trace-eval](https://github.com/kin0kaze23/trace-eval). It diagnosed the entire session in under a second.

Here's what it found, and how I used it to improve the next run.

## The Bad Run: 28.3/100

```
$ trace-eval run claude_code_session.jsonl

Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens, tool_redundant
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. fix errors (0/100 reliability). reduce token/tool usage.
```

The full scorecard told the story:

| Dimension | Score | What It Means |
|-----------|-------|--------------|
| Reliability | 0.0/100 | The agent hit **90 tool errors** across the session |
| Efficiency | 30.0/100 | 54K+ input tokens per call — burning context |
| Retrieval | N/A | No retrieval strategy (coding agent, expected) |
| Tool Discipline | 92.0/100 | Actually good — tools were used correctly, just failing |
| Context | N/A | No context pressure data available |

**90 errors.** That's why the session felt rough. Most from Bash commands returning exit code 1. The agent kept pushing forward despite the failures.

## The Diagnosis

The `--summary` flag gave me the 4-line version:

```
Score: 28.3/100
Flags: reliability_errors, efficiency_high_tokens, tool_redundant
Weak: reliability=0, efficiency=30
Diagnosis: Agent run with significant friction. fix errors (0/100 reliability). reduce token/tool usage.
```

Three things to fix:
1. **The errors** — 90 failed commands, mostly environment setup issues
2. **Token usage** — 54K+ input tokens per call means the agent was carrying full project context
3. **One redundant tool call** — minor, but worth fixing

## After Fixing: Before vs After

I didn't just look at one run. trace-eval has a `compare` command that shows exactly what changed between two sessions.

For a synthetic bad→good example (modeling the same pattern):

```
$ trace-eval compare bad_run.jsonl good_run.jsonl

Before: 32.4/100
After:  98.9/100
Delta:  +66.5
Resolved: 7 flags
```

Every flag resolved. The score jumped from 32.4 to 98.9. Not because the agent got "smarter" — because we fixed the three specific things the scorecard flagged.

## Real Validation Across 4 Agent Frameworks

I tested trace-eval on real sessions from different agents:

| Agent | Events | Score | Top Issue |
|-------|--------|-------|-----------|
| Claude Code (Stillness) | 3,694 | 28.3 | 90 tool errors |
| Claude Code (AutomationHub) | 1,969 | 28.3 | 31 tool errors |
| OpenClaw | 158 | 42.6 | 11 errors |
| Cursor (sample) | 18 | 59.8 | 1 error |
| Hermes (good run) | 8 | 98.9 | All clear |

Same pattern every time: the agent completes the task, but trace-eval reveals the friction that the developer felt but couldn't quantify.

## How It Works

trace-eval is a local CLI. No cloud, no LLM-as-judge, no dashboard. Just deterministic scoring:

```bash
# Install
pip install trace-eval

# Convert your agent's native trace (Claude Code, OpenClaw, Cursor)
trace-eval convert ~/.claude/projects/.../session.jsonl -o trace.jsonl

# Score it
trace-eval run trace.jsonl

# Quick summary for agents
trace-eval run trace.jsonl --summary

# Compare before/after
trace-eval compare before.jsonl after.jsonl --summary

# Gate your CI
trace-eval ci trace.jsonl --min-score 70 --profile coding_agent
```

It scores across 5 dimensions:
- **Reliability** (35%) — did it succeed?
- **Efficiency** (20%) — was it wasteful?
- **Retrieval** (20%) — did it find the right context?
- **Tool Discipline** (15%) — did it use tools well?
- **Context** (10%) — did it manage its context window?

Profiles adjust weights for different agent types: `coding_agent` drops retrieval to 0% and boosts reliability + tool discipline. `rag_agent` does the opposite.

## Why I Built This

Every time I use an AI coding agent, I get that feeling: "Did that go well?" The agent says it's done. The tests might pass. But the session was painful — errors, retries, context compression.

trace-eval turns that feeling into data. It doesn't tell you the agent is bad. It tells you *why this run was rough* and *what to change next*.

If you're building with AI agents and want to understand your traces, give it a try:

- **GitHub:** https://github.com/kin0kaze23/trace-eval
- **PyPI:** https://pypi.org/project/trace-eval/
- **Full case study:** https://github.com/kin0kaze23/trace-eval/blob/main/examples/case_study.md

Would love feedback from anyone who tries it on their own agent sessions.
