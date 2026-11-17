# Phase 4.4 Acceptance Report: Multivariate & Group Analysis

Date: 2026-11-09. Authorization: owner prompt "PHASE 4.4 - MULTIVARIATE & GROUP ANALYSIS" and the owner's instruction (2026-11-09) to execute Phases 4.4 to 4.7 without approval between phases (recorded as P4-C04).

**G4.4 verdict: PASS.** All nine gate criteria are met. The dataset-level acceptance remains **CONDITIONAL** (Phase 4.0). Under the owner's instruction, Phase 4.5 follows without a separate approval.

## 1. Pre-flight

| Item | Result |
|---|---|
| Phase 4.3 acceptance report | Read: G4.3 PASS |
| Owner approval | Owner instruction to proceed through 4.4–4.7 without approvals between phases (P4-C04). It is not a written acceptance of G4.3 and answers no open owner decision |
| Previous notebook sections | 213 cells before; all kept, ids and code unchanged. 30 cells appended (14 code, 16 Markdown): 243 in total. Status sentences updated in six cells (contents, status lists, Phase 4 table, 4.3 closing line) |
| Dataset SHA-256 | Verified before reading and after analysis (unchanged) |
| Scope | `load_scope()` → `rs5_v1`; `check_parquet()` on the dataset; `check_table()` on the derived season table |
| Condition register | Read in full (51 entries before this phase). None blocks 4.4 |
| Baseline | `tests/phase4` (27) pass under `.venv314`; protection check clean before changes |

## 2. Gate G4.4

| Criterion | Met | Evidence |
|---|---|---|
| Position-specific analysis completed | Yes | Population, target, age, playing time, metrics, missingness and correlations per position (`POSITION_COMPARISON_REPORT.md`; notebook 4.4.B, 4.4.E; `fig44_01`, `fig44_02`, `fig44_09`) |
| Season comparison completed | Yes | Population, composition, target and timing, playing time, metric coverage and drift, stratified medians, returning players (`SEASON_COMPARISON_REPORT.md`; 4.4.D; `fig44_06`–`fig44_08`) |
| Player groups documented | Yes | Four groupings with rationale and counts (`PLAYER_GROUP_ANALYSIS.md`; `group_boundaries.csv`) |
| Multivariate relationships explored | Yes | Grouped heatmap, faceted age x role x position, pair plot, position-specific and within-group Spearman (`fig44_02`–`fig44_05`) |
| Sample sizes and missingness considered | Yes | Counts on every table and chart; cells below 30 left empty; null metrics, status mix and minutes missingness per group |
| GK metrics interpreted separately | Yes | GK metrics only on GK rows; separate GK section; test `test_goalkeeper_metrics_described_on_goalkeeper_rows_only` |
| Temporal caveats preserved | Yes | RD-03 and ISS-21/ISS-22 in the notebook introduction, every target interpretation, `multivariate_summary.json` and all reports; no staleness filter |
| No unauthorized preprocessing or modeling | Yes | Groups derived on the fly and never written back; no imputation, filtering, PCA, clustering or model; tests `test_groups_cover_every_row_without_filling`, `test_dataset_unchanged_after_analysis` |
| Notebook updated and reproducible | Yes | Full notebook executed end to end: 110 code cells, 0 errors; 9 figures exported |

## 3. Key results

| Measure | Value |
|---|---|
| Median value by role (0 → 29–38 starts) | EUR 2.35m → 25m (all positions) |
| Strongest grouping | Playing-time role, then age, then position |
| Age x playing time | Outfield regulars peak at 22–27 (EUR 25–45m); fringe players <=21 about EUR 3–3.5m |
| Within regulars (>= 19 starts) | Starts 0.18–0.25; rating 0.51–0.66; age -0.34 to -0.59; defensive volumes about 0 |
| Season level within strata (2024/25 vs 2020/21) | x1.20–1.75 |
| Returning players' own value (median ratio) | 0.89 / 0.93 / 1.00 / 1.00 |
| Metric drift (regular outfield) | Recoveries per 90 -23%, interceptions per 90 -29% (P4-B09) |
| Identity sensitivity of group medians (>= 10 starts) | at most 3% |

## 4. Tests and execution

| Run | Result |
|---|---|
| `tests/research_scope` (71) + `tests/phase4` (34: 27 earlier, 7 new for 4.4), `.venv314` | 105 run, 105 passed (`evidence/tests_rs5_and_phase4.log`) |
| Evidence CLI `src/phase4/multivariate.py` | 27 tables and `multivariate_summary.json` |
| Notebook full execution (base Python 3.14.6, `.venv314` site-packages first; ENV-P4-03) | 110 code cells, 0 errors; 9 figures |
| Protection check (`evidence/protection_check_phase4_04.json`) | 0 removed, 0 unexpected changes, 0 unexpected additions |

## 5. Files

Created: `src/phase4/multivariate.py`; `tests/phase4/test_multivariate_44.py`; `reports/phase_04/step_04/` (this report, `MULTIVARIATE_ANALYSIS_REPORT.md`, `POSITION_COMPARISON_REPORT.md`, `SEASON_COMPARISON_REPORT.md`, `PLAYER_GROUP_ANALYSIS.md`, `evidence/` 30 files, `figures/` 9 PNGs).
Modified: `FB69_report.ipynb`; condition register YAML and rendered Markdown (P4-C04 resolved, P4-B09 added; 53 entries); `reports/phase_04/README.md` (updated at the end of Phase 4.7).
Not modified: release, scope, mappings, target method, historical data, earlier Phase 4 code and evidence.

## 6. Open issues

New: P4-B09 (rate-metric drift across seasons). Unchanged: RD-04, RS5-12, RD-01, RD-02, RD-03, ISS-01, ISS-04, P4-B05, P4-B07/ISS-25, P4-B06 undefined, ENV-P4-02, ENV-P4-03.
