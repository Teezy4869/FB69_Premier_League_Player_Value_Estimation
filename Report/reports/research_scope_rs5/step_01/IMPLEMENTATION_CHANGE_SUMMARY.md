# rs5 Step 1 Implementation Change Summary

| Change | Why | Risk control |
|---|---|---|
| New `configs/research_scope.yaml` | One place declares the five seasons, the exclusion, objective A and the cutoff policy | Loader rejects overlap, duplicates, unverified cutoffs, rule mismatch and objective changes |
| New `src/research_scope/scope.py` | Every rs5 builder and test calls it instead of keeping a season list | `ScopeViolation` stops a build; label/id pairs must agree |
| New `src/research_scope/protect.py` | Proves no historical file changed (no git, D5) | Only listed rs5 roots may gain files; `CLAUDE.md` is the one documented edit |
| New `src/research_scope/audit_baseline.py` | Reproducible audit evidence | Read-only |
| New `tests/research_scope/test_scope.py` | Automated scope validation (synthetic fixtures only) | Includes a test that rs5 code has no season literals |
| `CLAUDE.md` lines 9, 23, 24 | Future sessions must see D9, not the six-season scope | Byte backup in `evidence/` |
| New `.venv314` | `.venv` points to a missing interpreter | Same pinned versions; historical rebuild byte-identical |

**Not changed, on purpose:** `src/phase3/*`, `configs/phase_03_*.yaml`, `tests/phase3/*`, and every historical data file and report. They define and test the historical six-season release, which stays valid as history.
