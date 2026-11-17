# rs5 Step 3: Validation Test Report

## Integration checks (`src/research_scope/validate_rs5.py`, 27 of 27 PASS)

| Group | Checks |
|---|---|
| Scope | Five-season whitelist with all seasons present; excluded season rejected by label and id (0 rows); excluded season absent from club evidence; no 2019/20 flag columns |
| Grain and counts | Player-season uniqueness; count = rs5 Confirmed population (2,747); per-season counts reconcile |
| Identity consistency | Canonical id = `fb69p_<fotmob id>`; one TM id per player across seasons; one player per TM id; dataset identity = crosswalk; every crosswalk identity present; TM ids exist; unmapped rows carry an unresolved status |
| Target | Unique, and equal to the target table on 9 columns; null iff not usable, with a reason; nothing after cutoff; lineage on every usable target |
| Features and missingness | 106 `m_*`/`s_*` columns equal to FotMob rs5; null metric cells equal the source; `missing_feature_count` correct |
| Schema | Every column has a role; no target, temporal or identity column is a candidate predictor; dictionary covers every column with the right type |
| Provenance and club rules | Provenance columns populated; club evidence covers every row and equals the in-scope player-team-season rows |
| Historical reconciliation | 168 shared non-identity columns equal the v1 in-scope rows (0 differing rows) |

## Automated tests

| Suite | Tests | Result |
|---|---:|---|
| `tests/research_scope/test_scope.py` | 9 | PASS |
| `test_fotmob_rs5.py` | 13 | PASS |
| `test_targets_rs5.py` (both target versions) | 19 | PASS |
| `test_crosswalk_rs5.py` | 9 | PASS |
| `test_integrated_rs5.py` | 6 | PASS |
| rs5 subtotal | 56 | PASS |
| **Full repository, protected runner** | **422** | **422 passed, 0 failed, 0 skipped** |

The 366 historical tests still pass unchanged. The protected runner restored the 10 Phase 2 files that legacy tests rewrite, byte for byte. The historical protection check found 0 unexpected changes (`evidence/protection_check_g3.json`).

## Repeatability

The crosswalk, target and integration builders were each re-run. Integration and target reported "identical content".
