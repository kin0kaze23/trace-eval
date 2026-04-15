# PyPI Publishing Recommendation

## Recommendation: Publish v0.1.0 to PyPI now, with dogfooding as v0.1.1

### Why publish now

1. **The core product works** — 68 tests, 4 CLI commands, 2 adapters, real Hermes validation
2. **Nothing blocks installation** — `pip install trace-eval` would work today
3. **PyPI is not a commitment** — v0.1.0 signals "usable but early." It sets expectations correctly.
4. **Dogfooding is easier if people can `pip install`** — the best evidence comes from real users, not just the author
5. **v0.1.x semantics** — semantic versioning says 0.1.0 can change anything. There's no API stability promise.

### Risks of publishing now

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Someone tries it and it doesn't work for their format | High | Low | Clear README says JSONL + Hermes only. Adapters are explicitly limited |
| Scoring seems wrong for their traces | Medium | Medium | `--format json` shows exactly why. Capability report tells them what's missing |
| No one uses it | High | Low | Wasted effort, not harmful |
| Bad first impression | Low | Medium | v0.1.0 + clear "What This Is NOT" section manages expectations |

### Recommended PyPI metadata

**Name:** `trace-eval`
**Description:** `Deterministic-first CLI for evaluating AI agent traces`
**Long description:** The README (already well-structured)

**Classifiers:**
- `Development Status :: 3 - Alpha`
- `Intended Audience :: Developers`
- `License :: OSI Approved :: MIT License`
- `Programming Language :: Python :: 3.11`
- `Programming Language :: Python :: 3.12`
- `Programming Language :: Python :: 3.13`
- `Programming Language :: Python :: 3.14`
- `Topic :: Software Development :: Testing`
- `Topic :: Scientific/Engineering :: Artificial Intelligence`

**Keywords:** `ai-agent`, `evaluation`, `traces`, `llm`, `cli`, `debugging`

### Pre-publish checklist

- [x] 68 tests passing
- [x] CI workflow configured
- [x] README has install instructions and examples
- [x] `pyproject.toml` has correct metadata
- [ ] Add `readme = "README.md"` and `dynamic = ["version"]` to pyproject if not present
- [ ] Test `pip install trace-eval` from a clean environment
- [ ] Verify `trace-eval` entry point works after pip install

### Post-publish plan

1. **v0.1.0**: Ship as-is. Focus on getting 3-5 external users.
2. **v0.1.1**: Fix any issues found during dogfooding. Enrich Hermes adapter if needed.
3. **v0.2.0**: Add first new adapter (based on what users actually request).

### Alternative: Wait for more dogfooding

If you prefer to wait:
- Extract 10 more real sessions
- Manually validate 5 scores
- Enrich the Hermes adapter to catch embedded errors
- Then publish v0.1.0

**But**: The marginal value of 10 more sessions is low. You've already confirmed the scoring differentiates (50.0, 77.2, 88.9, 98.9) and the diagnostics are correct. More dogfooding will refine, not fundamentally change, the product.

### Verdict

**Ship v0.1.0 to PyPI now.** The product works, the README is honest about limitations, and the v0.1.x version signal tells people exactly where it is. Dogfooding should happen in parallel with a public release, not as a gate before it.
