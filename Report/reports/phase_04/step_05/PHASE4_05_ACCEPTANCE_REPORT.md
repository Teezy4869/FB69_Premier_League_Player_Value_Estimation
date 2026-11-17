# Phase 4.5 Acceptance Report: Missingness, Temporal & Data Reliability Analysis

Date: 2026-11-09. Authorization: owner prompt "PHASE 4.5 - MISSINGNESS, TEMPORAL & DATA RELIABILITY ANALYSIS" under the owner's instruction to execute 4.4–4.7 without approval between phases (P4-C04).

**G4.5 verdict: PASS.** All ten gate criteria are met. The dataset-level acceptance remains **CONDITIONAL**. Phase 4.6 follows under the owner's instruction.

## 1. Pre-flight

| Item | Result |
|---|---|
| Phase 4.4 acceptance report | Read: G4.4 PASS |
| Owner approval | P4-C04 (instruction to proceed through 4.4–4.7) |
| Previous notebook sections | 243 cells before; all kept, ids and code unchanged. 40 cells appended (16 code, 24 Markdown): 283 in total. Status sentences updated in six cells |
| Dataset SHA-256 / scope | Verified before and after; `load_scope()` → `rs5_v1`; `check_parquet()`; `check_table()` on the derived season table |
| Condition register and eligibility documentation | Read in full (53 entries before this phase; `PHASE4_FEATURE_ELIGIBILITY.md`, `phase4_feature_eligibility.csv`) |

## 2. Gate G4.5

| Criterion | Met | Evidence |
|---|---|---|
| Missingness analysed by feature and population | Yes | Feature level by family, season, position, target availability; population by target, position, playing-time role, minutes, season (`MISSINGNESS_ANALYSIS_REPORT.md`; 4.5.B–C; `fig45_01`–`fig45_03`) |
| Status semantics preserved | Yes | Eight statuses kept separate; value-status agreement on all 145,591 cells; observed zero vs unavailable vs not applicable vs unverified vs conflicting explained (4.5.A; test `test_status_semantics_preserved`) |
| GK analysis separated | Yes | 4.5.D, `gk_*.csv`, `fig45_04`; GK minutes, coverage, applicability, consistency checks |
| Temporal mismatch quantified | Yes | All seven RD-03 reference values reproduced exactly; per-season batches, after-valuation appearances and minutes, alignment classes, before/after associations (`TEMPORAL_RELIABILITY_REPORT.md`; `fig45_05`, `fig45_06`) |
| Identity sensitivity completed | Yes | Main vs subset vs main without subset; target, relationships, groups, representation; coverage vs precision (`IDENTITY_SENSITIVITY_REPORT.md`; `fig45_07`) |
| RD-04 metrics assessed | Yes | Coverage, window, missingness, position relevance, evidence quality per season; not approved or excluded (`rd04_assessment.csv`; `fig45_08`) |
| Club context documented | Yes | Availability and temporal interpretation of all eight columns (`club_context_*.csv`) |
| Source reliability limitations documented | Yes | All eight ISS-29 metrics, with two internal consistency checks; other known conditions (`METRIC_RELIABILITY_REPORT.md`) |
| No unauthorized exclusions or imputation | Yes | No row excluded, no value imputed or filtered; P4-B01 rows kept; tests `test_identity_subset_kept_and_compared`, `test_dataset_unchanged_after_analysis` |
| Notebook updated and reproducible | Yes | Full notebook executed end to end: 126 code cells, 0 errors; 9 figures |

## 3. Key results

| Finding | Value |
|---|---|
| Metric cells with a value / null | 66.9% / 33.0% (18.8% MISSING, 12.3% not applicable, 1.9% unsupported, 36 conflicting) |
| `MISSING` share by outfield role (0 → 29–38 starts) | 72.1% → 3.8% |
| GK metric coverage on GK rows | 93–100% (penalty saves 62–77%; goals prevented 59% in 2024/25) |
| GK minutes | metric 7/206; lineup evidence 206/206 (P4-D05) |
| Source-reported GK rates | save % and goals conceded per 90 internally consistent |
| RD-03 references | all reproduced (150 days, 56.62%, 44.10%, 43.66%, 12) |
| Appearances after valuation by season | 24.9% (2020/21) to 54.7% (2022/23) |
| Target vs minutes before / after valuation | Spearman 0.52 / 0.38 |
| P4-B01 subset median vs rest | EUR 8m vs 15m; relationship changes median 0.016 |
| Reliability classes | 25 / 15 / 2 / 6 / 5 (see metric report) |

## 4. Tests and execution

| Run | Result |
|---|---|
| `tests/research_scope` (71) + `tests/phase4` (41: 34 earlier, 7 new), `.venv314` | 112 run, 112 passed (`evidence/tests_rs5_and_phase4.log`) |
| Evidence CLI `src/phase4/reliability.py` | 32 tables and `reliability_summary.json` |
| Notebook full execution | 126 code cells, 0 errors |
| Protection check (`evidence/protection_check_phase4_05.json`) | 0 removed, 0 unexpected changes, 0 unexpected additions |

## 5. Files

Created: `src/phase4/reliability.py`; `tests/phase4/test_reliability_45.py`; `reports/phase_04/step_05/` (this report, `MISSINGNESS_ANALYSIS_REPORT.md`, `TEMPORAL_RELIABILITY_REPORT.md`, `IDENTITY_SENSITIVITY_REPORT.md`, `METRIC_RELIABILITY_REPORT.md`, `evidence/` 35 files, `figures/` 9 PNGs).
Modified: `FB69_report.ipynb`; condition register (the Phase 4 issue tracker; P4-B10 and P4-D05 added, 55 entries).

## 6. Open issues and owner attention

New: P4-B10 (status coding asymmetry on GK rows; conflicts concentrated in 2024/25); P4-D05 (GK minutes from lineup evidence: owner decision). Unchanged: RD-04, RS5-12, RD-01, RD-02, RD-03, ISS-01, ISS-04, P4-B05, P4-B07/ISS-25, P4-B09, P4-B06 undefined, ENV-P4-02, ENV-P4-03.
