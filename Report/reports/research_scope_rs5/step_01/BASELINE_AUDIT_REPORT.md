# rs5 Step 1: Baseline Audit

Date: 2026-11-07. Scope decision: **D9**, five seasons 2020/21 to 2024/25; 2019/20 permanently excluded. Objective A (D6) unchanged.

Evidence for every count below is in `evidence/`: `artifact_season_profile.csv` (36 data artifacts profiled), `hardcoded_season_scan.csv` (352 hits in 66 files), `population_preview.json`, `historical_phase3_reproduction_py314.json`, `baseline_sha256_before_migration.json` (16,290 files).

## 1. Environment finding

The repository's `.venv` doesn't run on this machine. It points to Python 3.13 under another user and drive (`F:\...`). The owner approved a new project-local `.venv314` (Python 3.14.6). It has exactly the versions in `reports/phase_03/step_05/requirements_freeze.txt`, including duckdb 2.0.0 and pyarrow 24.0.0. `.venv` was left untouched.

**Rebuilding historical Phase 3 under `.venv314` produced byte-identical outputs at all 12 stages**, including the integrated v1 release (`historical_phase3_reproduction_py314.json`). So the new environment is a valid base for the rebuild.

## 2. Repository structure (relevant parts)

| Layer | Location | Role |
|---|---|---|
| FotMob raw | `data/phase_02b0`, `data/phase_02b1/raw`, `data/pilot/raw` | Saved API captures; referenced by `raw_path` |
| FotMob releases | `data/releases/fotmob_epl_2019_2025_v1/v2/v3/v3_1` | v3.1 is the frozen source (38 hashed files, `CONDITIONAL_GO`) |
| Transfermarkt | `data/transfermarkt/{source,staging,curated,metadata}/tm_r2_20260905` | Read-only raw snapshot (D1) plus normalized tables |
| Entity resolution | `data/phase_03/entity_resolution/matching_v{1,2,2_1}__reviews_none`, `data/phase_03/review` | `matching_v2_1` is the one in use |
| Targets | `data/phase_03/targets/target_v1__matching_v2_1` | One target per player-season |
| Step 4.1 evidence | `reports/phase_03/step_04/audit_4_1/evidence/*.parquet` | Temporal alignment and target flags, **inputs to integration** |
| Integrated | `data/releases/fb69_player_season_integrated_v1` | 3,262 rows, 180 columns |
| Code | `src/collection`, `src/audit` (Phases 1-2), `src/phase3` (Phase 3) | |
| Configs | `configs/phase_03_{seasons,matching,tm_source}.yaml` + Phase 1-2 configs | |
| Tests | `tests/{audit,collection,phase3}`, unittest | 366 tests at Phase 3 close |
| Reports | `reports/phase_01..phase_03` | Phase 3 verdict `CONDITIONAL PASS` |

There is no git (D5). Script hashes in manifests stand in for commits.

## 3. Data dependency chain (verified in code)

```
FotMob raw -> FotMob v3.1 --------------------------+--> season_targets.py --> target_v1 --+
                 |                                  |                                       |
TM raw -> normalize_tm.py -> TM curated/staging ----+--> entity_resolution.py --> crosswalk -+--> step4_1_audit.py --> flags, temporal
                                                                                            |
                                                         integrate.py <---------------------+--> integrated v1
```

Confirmed from source: `integrate.py` reads v3.1 curated and normalized tables, the `matching_v2_1` crosswalk, `target_v1`, and both Step 4.1 parquet files. `season_targets.py` reads the crosswalk, `tm_valuation_history`, `auto_match_validation_all_1299.csv`, the cutoff config and three FotMob tables. `entity_resolution.py` reads 7 FotMob tables, 3 TM curated tables, TM `stg_games`, `stg_appearances`, and the adjudication CSV. Full graph: `DEPENDENCY_INVENTORY.md`.

## 4. Season dependency findings

1. **FotMob v3.1 is season-local.** 15 of 16 tables carry `season_id`. `players.parquet` is player-level. A code check of the builders (`remediation_release_v3.py`, `final_acceptance_fix.py`, `execution04_identity.py`) found every aggregation keyed by season. There are no ranks, percentiles or cross-season normalizations. **Filtering by season therefore reproduces the five-season values exactly**: no FotMob value needs recomputing, only totals and coverage.
2. **Transfermarkt values are player-level time series.** A target depends only on that player's valuation history and the season's cutoff. So target rows for in-scope seasons don't depend on 2019/20. Totals and coverage do.
3. **Entity resolution is player-level, but its evidence isn't season-free.** Game-set overlap, club-season overlap, and the club map use TM seasons 2019 to 2024 and every FotMob season. **400 in-scope players also played in 2019/20**, so their evidence includes 2019/20 games. The rebuild must recompute evidence from in-scope seasons only and compare decisions.
4. **Step 4.1 flags include 2019/20-specific columns.** `on_2020_04_08_batch` is false for every in-scope row (0 of 2,747). The derived "last non-batch" columns are then redundant.
5. **Integrated v1 has D7 columns** (`sensitivity_season_2019_20`, `xg_xa_unavailable_for_comparison`, `feature_quality_status`). D9 makes them meaningless for research data.
6. **Metric dictionary has cross-season summary columns** (`historical_seasons_with_values`, pilot sample counts). They must be recomputed or dropped, not copied.

## 5. Hard-coded season assumptions

352 hits in 66 files (`evidence/hardcoded_season_scan.csv`). Grouped by risk:

| Area | Hits | Examples | Treatment |
|---|---:|---|---|
| `src/phase3` historical pipeline | 65 | `BETWEEN 2019 AND 2024` (10), `EXPECTED_ROWS = 3262`, D7 SQL in `integrate.py`, 2020-04-08 batch logic | **Kept frozen.** It reproduces the historical release; rs5 code reuses its functions with scope inputs |
| `tests/phase3` | 17 | `== 515`, `== 67`, 2019/20 flag tests | Kept; they test historical artifacts, which don't change |
| `src/collection`, `src/audit`, `tests/collection`, `tests/audit` | 255 | Collection-time season lists | Kept; upstream collection, not rerun |
| `configs/` | 15 | `phase_03_seasons.yaml` holds six cutoffs | Reused unchanged; scope config selects five |

**Why historical code isn't edited:** historical manifests record script hashes (`code_sha256`). Editing those scripts would break the link between v1 outputs and the code that made them. With no git, that link is the only code provenance.

## 6. Population expectation (preview, not an output)

Computed in memory from historical files (`evidence/population_preview.json`):

| Item | Six seasons (historical) | Five seasons (expected) |
|---|---:|---:|
| Confirmed player-season rows | 3,262 | **2,747** |
| Unique players | 1,343 | **1,228** |
| Players only in 2019/20 | | 115 |
| Players in 2019/20 and later | | 400 |
| Usable targets | 3,195 | **2,697** |
| Missing targets | 67 | **50** |
| Rows with no identity | 3 | **2** |
| Players AUTO_EXACT / AUTO_ADJUDICATED / REVIEW_REQUIRED | 1,299 / 41 / 3 | 1,190 / 36 / 2 |

The rebuild must reproduce these as reconciliation checkpoints. Any difference must be explained, not forced.

## 7. Existing tests, manifests and checksums

- FotMob v3.1: 38 file hashes, verified by `tm_common.verify_fotmob_unchanged()`.
- TM snapshot: 7 SHA-256 pins in `configs/phase_03_tm_source.yaml`.
- Crosswalk, target and integration manifests record input, code and output hashes.
- **Test hazard (ISS-18):** plain `unittest discover` rewrites 10 Phase 2 files. Full runs must use `src/phase3/step3_qa_run_full_tests.py`, which backs them up and restores them.

## 8. Reuse decisions (summary)

| Action | Artifacts |
|---|---|
| KEEP (untouched) | All raw data; FotMob v1-v3.1; TM snapshot and normalized tables; all Phase 3 data, reports, code, configs and tests |
| FILTER | FotMob v3.1 season tables, players, eligibility registry, row-level quality reports |
| REBUILD | FotMob totals, coverage, dictionary, manifest; targets; Step 4.1 temporal evidence; crosswalk evidence; integrated dataset; all audits |
| REVALIDATE | Crosswalk decisions, adjudications, identity validation labels, referential integrity, TM coverage for the rs5 window |
| DEPRECATE (for research use) | Integrated v1, D7 flag columns, 2020-04-08 batch columns |

Per-artifact detail: `ARTIFACT_INVENTORY.csv`. Per-statistic detail: `RECALCULATION_MATRIX.md`.
