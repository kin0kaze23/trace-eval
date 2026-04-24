# Changelog

## 0.6.0 (2026-04-24)

### Added
- `install_capability` RemediationAction type for agent-ready integration
- Detection of missing-tool patterns (e.g. `command not found: vercel`) in trace events and friction flags
- Static capability ID mapping (`_CAPABILITY_HINTS`) mapping error patterns to agent-ready capability IDs
- One `install_capability` action emitted per distinct capability_id; deduped across multiple matching patterns
- Synthetic fixture `tests/fixtures/trace_missing_vercel.jsonl` for deterministic testing
- Actions include `context` with `capability_id` and `suggested_command` (e.g. `agent-ready fix --capability vercel_cli`)
- `confidence: "high"`, `safe_to_automate: False`, `requires_approval: True` — installs always need user approval

## 0.5.0 (2026-04-19)

### Added
- `trace-eval loop` command: locate → convert → score → remediate in one step
- `--apply-safe` flag: apply vetted safe fixes automatically
- `--compare` flag on loop: delta against a previous trace
- `--report` flag: generate markdown remediation reports
- `format_next_steps()`: compact inline guidance for `run --next-steps`
- Lean JSON fields: `rating`, `top_issues` (top 3 by severity), `top_actions` (deterministic ordering)
- Remediation top-3 format: "TOP 3 ACTIONS:" header with approval tags at front
- `--output` directory flag for loop: saves canonical trace + report files
- Graceful fallbacks: missing trace, convert failure, compare file missing, apply-safe failure
- `format_loop_text()`: human-readable output under 15 lines
- `format_loop_json()`: agent-friendly JSON with trace, score, rating, issues, actions, delta

### Changed
- `run --next-steps` uses compact format (no remediate footer) — distinct from `remediate` full view
- `format_remediation()` shows top 3 actions first with descriptions, then additional actions, then footer links
- `top_actions` ordering: AUTO-SAFE first, then by confidence (high/medium/low), then by action_type alphabetically
- JSON output now includes `rating`, `top_issues`, `top_actions` on all scorecard outputs
- Agent integration section updated to reflect loop-first JSON output contract

### Fixed
- Loop score computation: judges called with `trace.events` (not `trace` object)
- `--next-steps` wired to use `format_next_steps()` instead of `format_remediation()`
- Loop output reduced from 16 to 14 lines (under 15-line target)
- Warnings from compare/apply-safe/report now surface in text output

## 0.4.0 (2026-04-17)

### Added
- `trace-eval remediate` command with rule-based action recommendations
- `RemediationAction` dataclass with `safe_to_automate` and `requires_approval` fields
- Remediation analysis: fix errors, reduce retries, reduce prompts, switch profiles, CI gate
- Autofix module: `apply_safe_fixes()` for automated safe fixes
- Remediation report generation: `generate_remediation_report()` produces markdown
- Remediation text formatting: `format_remediation()` with full actionable output

### Changed
- `trace-eval locate` command added for filesystem search across agent directories
- `trace-eval convert` command with auto-detection for Claude Code, OpenClaw, Cursor formats

## 0.3.0 (2026-04-16)

### Added
- `format_summary()`: concise output under 10 lines for humans + agents
- `--summary` flag on `run`: score, top flags, diagnosis, weak dimensions
- `--next-steps` flag on `run`: show remediation after scorecard
- Diagnosis builder: automatic 1-2 sentence diagnosis from scorecard signals
- ScoreRating enum: Excellent (90+), Good (70-89), Needs Work (40-69), Critical (<40)
- Rating field on Scorecard output

## 0.2.0 (2026-04-16)

### Added
- `trace-eval convert` command with format auto-detection
- Generic JSONL adapter with observed capability reporting
- Claude Code trace adapter (auto-detect)
- OpenClaw trace adapter (auto-detect)
- Cursor trace adapter (auto-detect)
- Field coverage analysis with visual bar chart

### Changed
- Adapter capability reporting: honest/lossy for Hermes, full for JSONL adapters
- Unscorable dimension handling: weight redistribution to scorable dimensions

## 0.1.0 (2026-04-15)

### Added
- Initial MVP release
- 4 CLI commands: validate, run, compare, ci
- 5 deterministic judges: Reliability, Efficiency, Retrieval, Tool Discipline, Context
- Generic JSONL adapter with observed capability reporting
- Hermes SQLite adapter (honest/lossy)
- Weighted scoring with proportional redistribution for unscorable dimensions
- Structured friction flags sorted by severity
- Root cause surfacing in text output
- Machine-readable JSON output for agent consumption
- Before/after comparison with delta indicators
