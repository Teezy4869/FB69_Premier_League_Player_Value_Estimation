# rs5 Step 1 Handoff: G1 Scope Migration Gate

Date: 2026-11-07. **G1: PASS.**

## Work completed

1. Audited repository, data layers, code dependencies and hard-coded season assumptions (`BASELINE_AUDIT_REPORT.md`).
2. Built the artifact inventory (36 data artifacts profiled; 33 inventory entries), dependency inventory and recalculation matrix.
3. Implemented the central scope: `configs/research_scope.yaml` (D9) and `src/research_scope/scope.py` (loader plus `assert_seasons`, `check_table`, `check_parquet`).
4. Protected history: SHA-256 baseline of 16,290 files before any change, and `src/research_scope/protect.py verify`.
5. Updated `CLAUDE.md` scope lines (backup in `evidence/CLAUDE.md.before_rs5_backup`) and wrote `../DATA_CONTRACT_RS5.md`.
6. Created `.venv314` (owner-approved), because `.venv` can't run on this machine.

## Files

| Created | Purpose |
|---|---|
| `configs/research_scope.yaml` | Single source of truth for seasons, exclusion, objective, cutoff policy |
| `src/research_scope/{__init__,scope,protect,audit_baseline}.py` | Scope enforcement, protection, audit evidence |
| `tests/research_scope/{__init__,test_scope}.py` | 9 scope tests |
| `reports/research_scope_rs5/step_01/*`, `reports/research_scope_rs5/DATA_CONTRACT_RS5.md` | Reports and evidence |
| `.venv314/` | Project-local environment, pinned versions |

| Modified | Change |
|---|---|
| `CLAUDE.md` | Lines 9, 23, 24: five-season scope (D9); historical six-season scope named as history |

No other file existed before and changed (`evidence/protection_check_g1.json`).

## Tests

| Run | Result |
|---|---|
| Full repository, protected runner (`step3_qa_run_full_tests.py`) | **375 of 375 passed** (366 historical + 9 new); 10 protected Phase 2 files unchanged; FotMob 38 of 38 hashes |
| Historical Phase 3 rebuild under `.venv314` | **12 of 12 stages byte-identical** |
| Historical protection check | 0 unexpected changes, 0 removed |

## G1 criteria

| Criterion | Evidence | Met |
|---|---|---|
| Repository comprehensively audited | Baseline report, 36 artifact profiles, 352 hard-code hits | Yes |
| Critical data dependencies understood | `DEPENDENCY_INVENTORY.md`, read from code | Yes |
| Historical artifacts protected | Baseline hashes, verify, historical rebuild identical | Yes |
| Five-season scope implemented centrally | `research_scope.yaml` + `scope.py`; cutoffs referenced, not copied | Yes |
| Excluded season explicitly defined | Label, FotMob id and TM year | Yes |
| Automated scope validation exists | `check_table`, `ScopeViolation`, 9 tests incl. a no-literal test | Yes |
| Recalculation plan complete | `RECALCULATION_MATRIX.md` covers all Task B items | Yes |
| No unresolved architectural uncertainty | Decisions below | Yes |

## Architectural decisions

1. **Historical `src/phase3` stays frozen.** rs5 builders live in `src/research_scope/`, read the scope config, and reuse the approved functions (`select_target`, `identity_tier`, `checked_join`, `entity_resolution.run`). Only rs5 builders may produce research data.
2. **`configs/phase_03_seasons.yaml` stays the cutoff source.** The scope selects five of its six entries; dates aren't duplicated.
3. **Target before identity ordering.** Step 2 uses the historical player-level mapping. Step 3 revalidates with in-scope evidence and rebuilds the target if any mapping changes.

## Known issues carried forward

- `.venv` is unusable here; use `.venv314`. Byte-identical reproduction was shown under it.
- 400 in-scope players' historical identity evidence includes 2019/20 games; Step 3 must re-derive it.
- Plain `unittest discover` still rewrites 10 Phase 2 files (ISS-18): always use the protected runner.

## Next actions for Prompt 02

1. Verify `protect.py verify` against `evidence/baseline_sha256_before_migration.json`.
2. Build `data/releases/fotmob_epl_2020_2025_rs5_v1` by season filter of v3.1; recompute totals, coverage, dictionary season counts; manifest with checksums.
3. Build `data/research_rs5/targets/target_rs5_v1__matching_v2_1` with `select_target` on the rs5 population; prove row equality with historical in-scope rows; produce coverage, staleness, distribution, date, position reports.
4. Reconcile against the preview: 2,747 rows, 1,228 players, 2,697 usable, 50 missing.
