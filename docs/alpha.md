# External Alpha — trace-eval v0.5.0

> For alpha testers. Takes ~5 minutes.

## What is trace-eval?

A CLI that evaluates AI agent runs. Tell it what went wrong, what to fix next, and whether it improved. No dashboards, no LLM-as-judge, no cloud dependency.

---

## Part 1: Install

```bash
pip install trace-eval
trace-eval --version    # should show 0.5.0
```

If PyPI is not updated yet, install from GitHub:

```bash
pip install git+https://github.com/kin0kaze23/trace-eval.git@v0.5.0
```

---

## Part 2: Run the Alpha Script

Run these commands in order. Copy the output of each one.

### Step 1: Diagnose your setup

```bash
trace-eval doctor
```

Expected: Shows version, which agents are detected, how many traces found, and a recommended next command.

**If you see errors here, stop and report them.** This means the install or trace detection is broken.

### Step 2: Evaluate your latest trace

```bash
trace-eval loop
```

Expected: Finds your most recent trace, scores it, shows top 3 issues and top 3 actions.

**If it says "No recent traces found":**
- Try `trace-eval loop --hours 168` (wider search)
- Or find a trace manually and run `trace-eval run path/to/trace.jsonl`

### Step 3: Get specific fix recommendations

```bash
trace-eval loop --report --output ./eval-reports
```

Expected: Generates a markdown report with detailed remediation. Check `./eval-reports/` for the file.

### Step 4: Evaluate a specific trace (optional)

```bash
trace-eval run path/to/specific-trace.jsonl --summary
```

Expected: Quick score + diagnosis in under 10 lines.

### Step 5: Compare two traces (optional)

If you have a before/after trace:

```bash
trace-eval compare before.jsonl after.jsonl --summary
```

Expected: Shows score delta and which issues were resolved or new.

---

## Part 3: Feedback Checklist

Please fill this out and send it back. Copy/paste is fine.

### Install

- [ ] `pip install trace-eval` worked: **Yes / No** (if no, what error?)
- [ ] `trace-eval --version` shows `0.5.0`: **Yes / No**

### Doctor

- [ ] `trace-eval doctor` ran successfully: **Yes / No**
- [ ] It correctly detected my agent(s): **Yes / No** (which agent?)
- [ ] It found my trace files: **Yes / No**
- [ ] The recommended next command made sense: **Yes / No / Somewhat**

### Loop (Evaluation)

- [ ] `trace-eval loop` found and scored a trace: **Yes / No**
- [ ] The score (0-100) made sense for this run: **Yes / No / Somewhat**
  - If no: what did you expect?
- [ ] The [Critical/Good/Needs Work/Excellent] rating felt accurate: **Yes / No / Somewhat**
- [ ] The "Top 3 Issues" matched what you'd actually look at: **Yes / No / Partially**
  - Which issue was wrong or missing?
- [ ] The "Top 3 Actions" were useful: **Yes / No / Partially**
  - Which action was wrong or missing?

### Remediation Specificity

- [ ] Fix recommendations referenced specific tools/failures: **Yes / No**
- [ ] They told you *what* failed, not just "fix errors": **Yes / No**
- [ ] They told you *what to change*: **Yes / No / Somewhat**

### Approval Tags

- [ ] `[AUTO-SAFE]` vs `[REQUIRES APPROVAL]` felt useful: **Yes / No / Somewhat**
- [ ] Would you trust an auto-safe fix to run without review: **Yes / No / Depends**

### First-Run Friction

- [ ] Total time from install to first score: **< 1 min / 1-5 min / > 5 min**
- [ ] Points where you got stuck or confused: **(describe each)**
- [ ] Any error messages that were unclear: **(quote them)**

### Expectations vs Reality

- [ ] Did trace-eval do anything you didn't expect? **(describe)**
- [ ] Did it NOT do something you expected? **(describe)**
- [ ] Would you use this again: **Definitely / Probably / Maybe / No**

### Agent Context

- What agent do you use: **Claude Code / Cursor / OpenClaw / Other: ___**
- What was the task you evaluated: **(briefly describe)**
- How many events in your trace: **(rough estimate)**

---

## Troubleshooting

| Problem | Try |
|---------|-----|
| "No recent traces found" | `trace-eval loop --hours 168` |
| "Could not detect trace format" | `trace-eval convert path/to/file.jsonl` |
| Doctor shows no agents installed | Install Claude Code, Cursor, or OpenClaw first |
| Score seems wrong | Run `trace-eval validate path/to/trace.jsonl` to check the trace |
| Want machine-readable output | Add `--format json` to any command |

## Questions?

Open an issue at https://github.com/kin0kaze23/trace-eval or reply to this message.
