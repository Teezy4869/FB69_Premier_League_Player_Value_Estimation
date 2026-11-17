# rs5 Step 2: Data Validation

All checks ran on the generated files. Test code: `tests/research_scope/test_{scope,fotmob_rs5,targets_rs5}.py`. Build-time checks stop a build before anything is promoted.

| Check (Task D) | FotMob rs5 | Target rs5 | How |
|---|---|---|---|
| Season whitelist | PASS | PASS | `scope.check_parquet` on 15 tables, 2 target-side tables, every CSV with `season_label` |
| Excluded-season rejection | PASS | PASS | `ScopeViolation` on label, id or TM year (synthetic negative tests) |
| Schema validity | PASS | PASS | Schema equals v3.1 per table; target schema equals `season_targets.SCHEMA` |
| Primary key uniqueness | PASS | PASS | 13 keyed tables; target `canonical_player_id, season` |
| Data type validity | PASS | PASS | Same physical types as source |
| Metric integrity | PASS | n/a | Rows equal the v3.1 in-scope slice both ways |
| Missingness semantics | PASS | PASS | Null and zero counts per metric equal source; UNKNOWN count equal; every missing target has a reason |
| Source provenance | PASS | PASS | Null counts of raw paths unchanged; season-data paths never in a 2019/20 folder; target row matches history record, row number and file hash |
| Valuation date validity | n/a | PASS | 0 after cutoff; age = cutoff - date |
| Target uniqueness | n/a | PASS | 0 duplicate keys; no skipped later eligible valuation |
| Season-level record consistency | PASS | PASS | Recomputed season totals equal v3.1 per-season rows; Confirmed + Unverified = player-seasons; target population = Confirmed set |
| Referential integrity | PASS (12 of 12) | PASS | `referential_integrity_report_rs5.csv`; TM ids exist |

## Test runs

| Run | Result |
|---|---|
| rs5 tests | 31 of 31 |
| Full repository, protected runner | **397 of 397** (366 historical + 31 rs5); 10 protected Phase 2 files unchanged |
| Historical protection | 0 unexpected changes or removals (`evidence/protection_check_g2.json`) |
| Rebuild repeatability | Both builders re-run: "identical content" for every output |

No existing test was changed or weakened.
