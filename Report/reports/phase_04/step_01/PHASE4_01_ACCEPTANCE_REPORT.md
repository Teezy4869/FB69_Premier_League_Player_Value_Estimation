# Phase 4.1 Acceptance Report: Dataset Profiling & Structural EDA

Date: 2026-11-08. Authorization: owner prompt "PHASE 4.1 - DATASET PROFILING & STRUCTURAL EDA". It authorizes Phase 4.1 only (P4-C01).

**G4.1 verdict: PASS.** All ten gate criteria are met. The dataset-level acceptance remains **CONDITIONAL** (Phase 4.0), and its open conditions are unchanged. **Phase 4.2 has not been started.** It requires a new owner authorization.

## 1. Pre-flight

| Item | Result |
|---|---|
| Documents read | Phase 4.0 acceptance report, condition register, entry checklist, feature eligibility; G5 final acceptance report; `configs/research_scope.yaml`; `src/research_scope/scope.py` |
| `FB69_report.ipynb` | Existing notebook (95 cells) kept. The Phase 4 section was appended (34 cells; 129 in total). All 95 earlier cell ids, code sources and text outputs are identical after re-execution. Five status sentences in four Markdown cells were updated so they no longer say Phase 4.1 has not started |
| ENV-P4-01 | `.venv314` still cannot start (its base interpreter `C:\Users\THEGIOILAP\...\pythoncore-3.14-64` is missing). `.venv` runs Python 3.13.13, with duckdb 2.0.0, pyarrow 24.0.0, pandas 3.1.0 and numpy 2.5.4 (the pinned freeze). **Resolved as a delegated technical decision**: evidence and tests ran under `.venv`. The notebook needs matplotlib and a Jupyter kernel, which `.venv` lacks, so it ran on the same base interpreter (Python 3.13.13) with `.venv` site-packages first on `PYTHONPATH`. That way the pinned data libraries were used. Nothing was installed or replaced. The owner may override this choice |
| P4-C01 | Recorded as resolved for 4.1 in `../step_00/phase4_condition_register.yaml` |
| P4-D04 | `PHASE4_OUTPUT_ROOTS` (`reports/phase_04/`, `src/phase4/`, `tests/phase4/`, `FB69_report.ipynb`) added to `src/research_scope/protect.py`. Historical baseline not modified. The protection check passes with 0 unexpected additions |

## 2. Gate G4.1

| Criterion | Met | Evidence |
|---|---|---|
| Dataset hash verified | Yes | `load_verified()` checks SHA-256 before reading; `evidence/profiling_summary.json`; test `test_hash_mismatch_stops_before_loading` |
| Official scope enforced | Yes | `load_scope()`, `check_parquet()` on the dataset, `check_table()` on the derived season table; 0 rows outside scope |
| Dataset structure fully described | Yes | `DATASET_PROFILING_REPORT.md`, notebook 4.1.B–C |
| Primary key integrity verified | Yes | 0 duplicate keys, 0 null keys, 0 duplicate rows |
| Column profiling completed | Yes | `evidence/schema_profile.csv`: 175 of 175 columns, categories from the Phase 4.0 register |
| Population distribution understood | Yes | `POPULATION_ANALYSIS.md`, notebook 4.1.E |
| Missingness overview documented | Yes | `DATASET_PROFILING_REPORT.md` §4, `evidence/missingness_*.csv`, `status_by_*.csv` |
| Structural anomalies explained | Yes | `STRUCTURAL_DATA_QUALITY_REPORT.md`: 6 starts>appearances rows kept; 40 low-minute per-90 rows documented (P4-B05) |
| Notebook updated and executable | Yes | Full notebook executed end to end: 64 code cells (18 new), 0 errors |
| No historical source data modified | Yes | `evidence/protection_check_phase4_01.json`: 16,290 historical files, 0 removed, 0 unexpected changes (only the documented `CLAUDE.md` edit); dataset and scope hashes unchanged |

Unmet criteria: none.

## 3. Key statistics

| Measure | Value |
|---|---:|
| Rows / columns / players / seasons | 2,747 / 175 / 1,228 / 5 |
| Usable / missing targets (coverage) | 2,697 / 50 (98.18%) |
| Rows per season | 524 / 537 / 554 / 570 / 562 (19.1–20.8%) |
| Goalkeeper rows (players) | 206 (95) |
| Null metric cells | 33.00% (all cells 12.43%) |
| Constant columns | 14 |
| Type mismatches / invalid values / unexpected categories / value-status disagreements | 0 / 0 / 0 / 0 |

## 4. Findings to carry into Phase 4.2

1. Repeated players: 687 have several seasons, and about 63–65% of each season's players return the following season (RS5-11).
2. Goalkeepers: minutes are null on 199 of 206 rows (`MISSING`), and 65% of their metric cells are null (ISS-11).
3. Low playing time: 190 single-appearance rows and 330 rows with under 90 minutes. These rows are sparse (about 44 null metrics) and have lower target coverage.
4. Per-90 rates from under 90 minutes on 40 rows (new **P4-B05**).
5. Missingness is coded. `UNVERIFIED_POSITION` on outfield rows means a goalkeeper-only metric is not applicable (17,787 cells). `MISSING` means a source gap (27,361 cells). `OBSERVED_ZERO` marks true zeros (5,762).
6. Preserved anomalies: 6 rows with starts greater than appearances; 13 rows where reported starts exceed lineup starts.

## 5. Tests and execution

| Run | Result |
|---|---|
| `tests/research_scope` + `tests/phase4` (`.venv`) | 80 run, 80 passed (`evidence/tests_rs5_and_phase4.log`) |
| `FB69_report.ipynb` full execution | 0 errors; Phase 4.1 figures exported to `figures/` from the executed outputs |
| Full repository suite (437 at G5) | Not re-run. The only changed shared code is `protect.py`, which no test uses (ENV-P4-02 remains open) |

## 6. Files

Created: `src/phase4/__init__.py`, `src/phase4/profiling.py`, `tests/phase4/__init__.py`, `tests/phase4/test_profiling_41.py`, and everything in `reports/phase_04/step_01/` (this report, `DATASET_PROFILING_REPORT.md`, `POPULATION_ANALYSIS.md`, `STRUCTURAL_DATA_QUALITY_REPORT.md`, `evidence/` with 25 files (22 tables, the profiling summary, the protection check and the test log), `figures/` with 7 PNGs), plus `reports/phase_04/README.md`.
Modified: `FB69_report.ipynb` (Phase 4.1 appended), `src/research_scope/protect.py` (Phase 4 roots), `reports/phase_04/step_00/phase4_condition_register.yaml` and its rendered `PHASE4_CONDITION_REGISTER.md` (statuses, P4-B05), `reports/phase_04/step_00/evidence/scripts/render_condition_register.py` (status column).
Not modified: the official release, the scope configuration, rs5 and historical data, mappings, target method, protection baseline.

## 7. Owner decisions

- Confirm or override the ENV-P4-01 resolution (`.venv` / Python 3.13.13 for Phase 4 on this machine).
- Authorize Phase 4.2, if desired.
- Still open from Phase 4.0: RD-04, RS5-12, RD-02, RD-01, RD-03 (default: keep D4), ISS-01 labels, ISS-04.
