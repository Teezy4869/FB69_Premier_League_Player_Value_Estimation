# FB69 Phase 4.0: Research Dataset Acceptance and Conditions Verification

Date: 2026-11-08. Role: data engineering lead and independent research-data auditor. Every number below was recomputed in this step from the repository (`evidence/phase4_00_verification.json`), not copied from Phase 3R handoffs. Nothing in the release, configuration, crosswalk or target method was changed.

**Verdict: CONDITIONAL PASS.** The dataset's integrity, identity and scope are verified with no discrepancy. It is conditional for two reasons. First, the accepted environment `.venv314` can't run on this machine (ENV-P4-01). Second, the Phase 3R research limitations and six owner-level decisions remain open; all are documented below.

**Phase 4.1: authorized to begin under the constraints in `PHASE4_ENTRY_CHECKLIST.md`, once the owner issues the Phase 4.1 instruction.** No Phase 4 plan file exists in the repository (P4-C01).

---

## 1. Executive summary

- The official release `player_season_integrated_rs5_v1` is intact. The dataset SHA-256 matches the accepted value. All 21 manifest files verify by hash and size. No file is unlisted or missing.
- Every reference statistic matches: 2,747 rows, 1,228 players, 175 columns, 2,697 usable / 50 missing targets (98.18%), and season counts 524 / 537 / 554 / 570 / 562.
- Scope is enforced. There are 0 rows from 2019/20. `check_parquet` passes on the dataset and on all 23 rs5 parquet files that carry a season column. The release's scope snapshot is byte-identical to `configs/research_scope.yaml`.
- 45 conditions are inventoried: 14 mandatory constraints, 20 cautions, 6 pending owner decisions and 5 later-phase requirements. None was resolved or downgraded here.
- All 175 columns are classified for eligibility. The 108 dictionary "candidate" columns split into 41 candidates, 13 conditional `m_*` metrics, 2 exclusions and 52 status columns. Club context (8 columns) is added as conditional.
- Tests: 71 of 71 rs5 scope and release tests pass. The historical protection check shows 0 unexpected changes across 16,290 baseline files.

## 2. Official dataset identity

| Item | Result |
|---|---|
| Path | `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet` (as documented) |
| SHA-256 (recomputed) | `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd` |
| Expected | `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd`: **match** |
| `release_manifest.json` | 21 files listed, **21 verified** (SHA-256 and bytes); 0 unlisted, 0 missing; dataset entry has the same hash and `rows: 2747`; scope `rs5_v1`, seasons as configured, excluded `2019/2020` |
| `integration_manifest.json` | Records the same output hash |
| Release copies of docs | `PHASE4_CONDITIONS.md`, `ISSUE_TRACKER.md`, `DATA_CONTRACT_RS5.md` and `LEAKAGE_AUDIT.md` are byte-identical to their `reports/research_scope_rs5/` sources |
| Re-hash after the test run | Unchanged |

All referenced paths exist as the prompt describes. No path discrepancy was found.

## 3. Research scope verification

| Check | Result |
|---|---|
| `configs/research_scope.yaml` | `scope_id rs5_v1`, D9; 5 official seasons with FotMob ids 15382, 16390, 17664, 20720, 23685; excluded 2019/2020 (14022); objective A; rule `latest_valid_on_or_before_season_end_v1`; `stale_label_days_is_exclusion_rule: false`. SHA-256 `a028b7d5…c4bf`, identical to the release snapshot. **Not modified** |
| `src/research_scope/scope.py` | `load_scope()` loads the config without error and cross-checks the cutoff config (all VERIFIED; season ids agree). Rejects duplicate, overlapping or excluded seasons |
| Dataset season labels and ids | Exactly the 5 official (label, id) pairs; `check_parquet(season, season_id)` passes |
| 2019/20 rows | **0** (by label and by season id) |
| `research_scope_id` / `dataset_version` | `rs5_v1` / `player_season_integrated_rs5_v1` on all 2,747 rows |
| Cutoffs | One `target_season_end_date` per season, equal to the scope: 2021-05-23, 2022-05-22, 2023-05-28, 2024-05-19, 2025-05-25 |
| Valuations after cutoff | **0** |
| Downstream rs5 artifacts | 26 rs5 parquet files scanned. 23 with a season column pass `check_parquet` (0 failures). 3 are player-level with no season column (`players.parquet`, `matching_candidates.parquet`, `player_crosswalk.parquet`) |
| Excluded-season strings in rs5 CSVs | 1 hit, in `docs/leakage_audit.csv`. It's descriptive text ("the 2019/20 age-linked revaluation is out of scope"), not data |
| Old valuation vs excluded season | The 2019-05-23 valuation belongs to an in-scope 2020/21 row (Khanya Leshabela, age 731 days). It's a player-level valuation date, not a 2019/20 season record (RD-01; `SCOPE_DECLARATION.md`) |

## 4. Dataset statistics

| Metric | Expected | Recomputed |
|---|---:|---:|
| Player-season rows | 2,747 | **2,747** |
| Unique players (`canonical_player_id`; also `fotmob_player_id`) | 1,228 | **1,228** |
| Usable targets | 2,697 | **2,697** (`target_usable` ⇔ value non-null on every row) |
| Missing targets | 50 | **50**: 37 only later valuations, 11 no valuation history, 2 no identity |
| Target coverage | 98.18% | **98.18%** |
| Columns | 175 | **175** (dictionary has 175 rows, same order, 0 type mismatches) |
| 2019/20 records | 0 | **0** |

| Season | Expected | Recomputed | Usable targets |
|---|---:|---:|---:|
| 2020/21 | 524 | 524 | 515 |
| 2021/22 | 537 | 537 | 528 |
| 2022/23 | 554 | 554 | 542 |
| 2023/24 | 570 | 570 | 567 |
| 2024/25 | 562 | 562 | 545 |

Structure: primary key (`canonical_player_id`, `season`) has 0 duplicates and 0 nulls. (`fotmob_player_id`, `season_id`) has 0 duplicates. There are 0 duplicate full rows. Types: 96 string, 58 double, 9 int64, 6 int32, 3 bool, 3 date32. Target: EUR only; median 13.0m, mean 19.26m, min 0.1m, max 200m. Target status: VALID 1,170, STALE_TARGET 1,527, TARGET_MISSING 50.

## 5. Acceptance condition verification

The full register is in `PHASE4_CONDITION_REGISTER.md` (machine-readable: `phase4_condition_register.yaml`). It covers every item in `PHASE4_CONDITIONS.md` (1–10) and every open row in the rs5 issue tracker. Key items, with the figures recomputed in this step:

| ID | Class | Verified finding | Status |
|---|---|---|---|
| ISS-01 | B (+C, D) | `identity_human_reviewed` is False on all 2,747 rows. 0 of 514 rows in `validation_sample_for_labeling.csv` carry a human label. The random-300 lower bound is 98.73%, below the 99% SOP. **Safe:** describing mapping coverage (1,226/1,228 identities; 2,745/2,747 rows) and automated validator results. **Needs caution:** any target-based conclusion, because coverage is not precision | Open |
| RD-03 / ISS-02 | B (+C) | Median age 150 days; 56.62% of targets over 90 days (1,527/2,697); 44.10% of appearances (24,286/55,073) and 43.66% of minutes after the valuation. Construct mismatch, not leakage under A. D4/D6 unchanged | Open, escalated |
| RS5-11 | A (+D) | 687 players in 2+ seasons (2,206 rows). Random row splits prohibited; grouped-by-player and temporal-by-season splits to be assessed later | Open |
| RD-04 | C (+D) | Non-null by season. Clearances: 0 / 33 / 0 / 51 / 447. xGOT 2022/23 agreement 92.06%. Touches in the opposition box and goals prevented verified only in 2024/25. Neither included nor excluded | Open |
| RD-02 | C | El Mohamady (111930 → 66333, 1 row in 2020/21) and Wesley (656562 → 381362, rows in 2020/21 and 2021/22): AUTO_ADJUDICATED, tier AUTO_ADJUDICATED_INDEPENDENT_RULE, label INCONCLUSIVE, adjudicator automated, targets usable. Mappings unchanged. 6 further AUTO_ADJUDICATED_EXTERNAL rows (5 players) are also INCONCLUSIVE. They fall under identity sensitivity, not RD-02 | Open |
| ISS-04 | C | Chesters (2021/22) and Tauriainen (2023/24): REVIEW_REQUIRED, no target | Open |
| RD-01 | B (+C) | 12 targets over 365 days (max 731). No age cap. 18 targets predate their season's first match (ISS-21) | Open |
| ISS-27 / ISS-25 | B (+D) | Mean null metrics: 17.03 with target vs 42.10 without; GK 34.49. 33.00% of metric cells null. No null metric carries status OBSERVED | Open |
| ISS-21 / ISS-22 | B | Share of targets over 90 days by season: 2.91% / 78.03% / 66.97% / 72.66% / 59.63%. Batch timing is confounded with season | Open |
| ISS-28 | A | `m_key_passes` non-null 0; `s_key_passes` UNSUPPORTED on all rows. Excluded | Applied |
| RS5-12 | C (+D) | 73 multi-club rows; 8 club-context columns, not candidates by default | Open |
| ISS-29 | B | 8 source-reported rates aren't independently verifiable | Open |
| `s_*` statuses | D (P4-D01) | 53 string columns; values include OBSERVED_ZERO 5,762, UNVERIFIED_POSITION 17,899 and CONFLICTING 36. Not numeric performance features | Open |
| Others | B | ISS-11, RS5-13 (95 source-revised cells), DQ-RS5-04 (6 rows), ISS-23, ISS-24, ISS-09/10, ISS-07, ISS-16 (A), ISS-18 (A) and the low-impact documented items | Documented |

**Consistency with the accepted decisions.** `PHASE4_CONDITIONS.md` is consistent with D4, D6 and D9 and with the G5 report. No conflict was found. The prompt says "two inconclusive identity adjudications", and that holds for the RULE-based adjudications (RD-02). The dataset also has 5 EXTERNAL adjudications (6 rows) labelled INCONCLUSIVE; the Phase 3R reports document those too. They are recorded under P4-B01, not reclassified.

## 6. Feature eligibility summary

From `PHASE4_FEATURE_ELIGIBILITY.md` and `phase4_feature_eligibility.csv`:

| Category | Columns |
|---|---:|
| Candidate predictors (with warnings) | 41 |
| Conditional: reliability assessment | 8 |
| Conditional: owner decision (RD-04: 5; club context: 8) | 13 |
| Excluded (`m_key_passes`, `s_key_passes`, `nationality_profile_present_day`) | 3 |
| Target | 16 |
| Identity and metadata | 33 |
| Temporal audit | 8 |
| Status and missingness (52 `s_*`, `missing_feature_count`) | 53 |

No column flagged as a dictionary candidate is a target, temporal, id, identity or club column (checked). No feature selection was performed.

## 7. Technical environment verification

| Item | Result |
|---|---|
| `.venv314` (accepted: Python 3.14.6, duckdb 2.0.0, pyarrow 24.0.0) | **Present but not executable on this machine.** `pyvenv.cfg` points to `C:\Users\THEGIOILAP\AppData\Local\Python\pythoncore-3.14-64\python.exe`, which doesn't exist here; the venv was created at `D:\PTIT\Hoc_may\FB69`. Its site-packages contain duckdb 2.0.0, pyarrow 24.0.0, pandas 3.1.0 and PyYAML 6.0.3. Not modified or replaced |
| `.venv` (project) | Runs: Python 3.13.13, duckdb 2.0.0, pyarrow 24.0.0. `pip freeze` is **identical** to the pinned `reports/phase_03/step_05/requirements_freeze.txt` (`evidence/venv_pip_freeze.txt`). This is the inverse of RS5-01, which was recorded on the other machine |
| Interpreter used for Phase 4.0 | `.venv` (3.13.13). Hashing, DuckDB queries and unit tests don't depend on the interpreter's minor version. Byte-level rebuild reproducibility, shown under `.venv314` at G5, was not re-tested (no rebuild authorized) |
| Documented commands | The rebuild commands in `reports/research_scope_rs5/README.md` (`.venv314\Scripts\python.exe …`) fail on this machine for the reason above. Not run (rebuild not authorized) |
| rs5 tests | `python -m unittest discover -s tests/research_scope -t .` under `.venv`: **71 run, 71 passed**, 0 failures, 0 errors (`evidence/rs5_tests.log`). These tests are read-only (one writes only to a temp folder) |
| Full suite (437 at G5) | Not re-run in Phase 4.0 (ENV-P4-02) |
| Historical protection | `protect.py verify` against the rs5 baseline: 16,290 historical files, **0 removed, 0 unexpected changes, 0 unexpected additions**; only the documented `CLAUDE.md` edit. Run before any Phase 4.0 file was created (`evidence/protection_check_phase4_00.json`) |

## 8. Unresolved issues

Nothing below was resolved in this step.

- **Owner decisions (Category C):** RD-04 features; RS5-12 club context; RD-02 El Mohamady and Wesley; RD-01 age cap; ISS-04 two unresolved identities; ISS-01 human labels; RD-03 position (default: keep D4 and report); ISS-22 any staleness filter; P4-C01 Phase 4.1 instruction; ENV-P4-01 interpreter on this machine.
- **Research limitations (Category B):** RD-03 construct mismatch; identity not human-validated; non-random missingness; batch-timed valuations; source-reported rates; retrospective collection.
- **Later-phase requirements (Category D):** split strategy; missingness plan; `s_*` role; final feature inclusion; protection-checker roots for Phase 4 outputs (P4-D04); full-suite re-run.
- The dataset is **not** claimed to be leakage-free in the broad sense.

## 9. Phase 4.0 verdict: CONDITIONAL PASS

| Gate requirement | Met | Evidence |
|---|---|---|
| Official dataset exists | Yes | Path verified |
| SHA-256 matches | Yes | Recomputed |
| Manifest valid | Yes | 21/21 |
| Structure matches the accepted release | Yes | All reference statistics equal |
| Five-season scope verified | Yes | `check_parquet`, config snapshot |
| No excluded-season records | Yes | 0 rows; 23/23 rs5 tables pass |
| Conditions fully inventoried | Yes | 45 conditions; all tracker items and `PHASE4_CONDITIONS.md` 1–10 |
| Feature eligibility documented | Yes | 175/175 columns |
| Environment verification succeeds | **Partly** | Accepted `.venv314` not executable here; `.venv` has identical packages, but its interpreter is 3.13.13 |
| No critical integrity discrepancy | Yes | None found |

**Why not PASS:** the accepted environment can't be run on this machine, so verification used `.venv` with a different interpreter. Byte-level rebuild reproducibility wasn't re-tested. Also, research limitations and owner decisions remain open. **Why not FAIL:** the hash, manifest, structure and scope all verify; no excluded-season record exists; every required check was completed; and the conditions document agrees with D4, D6 and D9.

## 10. Phase 4.1 authorization

- **Authorized:** Phase 4.1 (EDA) may begin on the official dataset, under `PHASE4_ENTRY_CHECKLIST.md`, **once the owner issues the Phase 4.1 instruction** (no approved Phase 4 plan file exists in the repository).
- **Not authorized:** feature selection, feature engineering, preprocessing, model training or evaluation, any change to the release, scope, mappings or target rule, and any decision in Category C.
- Nothing from Phase 4.1 was started in this step.

## Files

| File | Content |
|---|---|
| `PHASE4_00_ACCEPTANCE_REPORT.md` | This report |
| `PHASE4_CONDITION_REGISTER.md` | Full condition register (rendered from the YAML) |
| `phase4_condition_register.yaml` | Machine-readable condition register (source) |
| `PHASE4_ENTRY_CHECKLIST.md` | Must and must-not checklist for Phase 4 work |
| `PHASE4_FEATURE_ELIGIBILITY.md` | Feature eligibility register |
| `phase4_feature_eligibility.csv` | Column-level eligibility (175 rows) |
| `evidence/phase4_00_verification.json` | All recomputed figures |
| `evidence/rs5_tests.log` | rs5 test output |
| `evidence/protection_check_phase4_00.json` | Historical protection check |
| `evidence/venv_pip_freeze.txt` | `.venv` package freeze |
| `evidence/scripts/` | `p40_verify.py`, `p40_eligibility.py`, `render_condition_register.py` (read-only on the release) |

Reproduce from the repository root: `.venv\Scripts\python.exe -I -X utf8 reports\phase_04\step_00\evidence\scripts\p40_verify.py . <out_dir>`.
