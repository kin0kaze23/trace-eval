# Repo Hygiene Rules — trace-eval

> These rules apply to all AI agents and humans working on this repo.
> This is a public repository — everything committed is visible to the world.

## Rule 1: No internal working documents in the repo

Never create, modify, or commit these types of files:

| Pattern | Example | Where to keep it instead |
|---------|---------|-------------------------|
| Sprint notes | `SPRINT6_DELIVERABLES.md` | Local scratch, not versioned |
| Planning docs | `DOGFOOD_PLAN.md`, `LAUNCH_ASSETS.md` | Local scratch or docs/ if user-facing |
| Blocker/friction logs | `ALPHA_BLOCKERS.md`, `ALPHA_FRICTION.md` | Local scratch |
| AI assistant notes | `docs/superpowers/*`, `docs/planning/*` | Do not create these directories |
| Working drafts | `*_draft.md`, `DRAFT_*.md`, `WORKING_*.md` | Local scratch |
| Decision docs | `PYPI_RECOMMENDATION.md` | Local scratch |

**Only these `.md` files are allowed at repo root:**
- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `RELEASE_NOTES.md`

All other documentation belongs in `docs/` (user-facing) or stays local.

## Rule 2: Never commit build artifacts or caches

Never commit:
- `dist/`, `build/`, `*.whl`, `*.egg-info/`
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- `.venv/`, `venv/`, `env/`
- `.DS_Store`, `Thumbs.db`
- `uv.lock`, `poetry.lock`, `package-lock.json` (unless explicitly needed)
- `*.db`, `*.sqlite`

These are covered by `.gitignore`. If a file slips through, add it to `.gitignore`.

## Rule 3: Never commit secrets or credentials

- No API keys, tokens, passwords, or private keys in any file
- No `.env` files or secrets in example files
- Use environment variables or secret managers
- If you accidentally commit a secret, rotate it immediately — history rewrite is not enough

## Rule 4: Keep the root directory clean

The repo root should contain only:
- `README.md` — project entry point
- `CHANGELOG.md` — release history
- `CONTRIBUTING.md` — how to contribute
- `LICENSE` — license file
- `RELEASE_NOTES.md` — current release notes
- `pyproject.toml` — package config
- `.gitignore` — ignore rules
- `.github/` — CI/CD workflows
- Source directories: `trace_eval/`, `tests/`, `docs/`, `examples/`

If a file doesn't fit one of these categories, don't put it in the root.

## Rule 5: Documentation belongs in docs/

All user-facing documentation that isn't README/CHANGELOG/CONTRIBUTING/RELEASE_NOTES goes in `docs/`:
- `docs/alpha.md` — alpha test script for users
- `docs/alpha-operator.md` — operator checklist for running alpha
- `docs/agent-skill.md` — agent self-evaluation skill
- `docs/validation-report.md` — validation evidence (archive)

## Enforcement

A pre-commit hook (`.git-hooks/pre-commit`) enforces these rules automatically.
- To bypass in emergencies: `git commit --no-verify`
- To install: `cp .git-hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`

## If you made a mistake

1. Don't panic — mistakes happen
2. Unstage the file: `git reset HEAD <file>`
3. Move it to `docs/` if it's user-facing, or delete it if it's internal
4. If already pushed: the pre-commit hook will prevent it going forward
