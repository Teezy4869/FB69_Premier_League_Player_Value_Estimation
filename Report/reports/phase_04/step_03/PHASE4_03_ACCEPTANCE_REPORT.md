# Phase 4.3 Acceptance Report: Bivariate Analysis

Date: 2026-11-09. Authorization: owner prompt "PHASE 4.3 - BIVARIATE ANALYSIS". It authorizes Phase 4.3 only (recorded as P4-C03).

**G4.3 verdict: PASS.** All nine gate criteria are met. The dataset-level acceptance remains **CONDITIONAL** (Phase 4.0), and its open conditions are unchanged. **Phase 4.4 has not been started.** It requires a new owner authorization.

## 1. Pre-flight

| Item | Result |
|---|---|
| Phase 4.2 acceptance report | Read: G4.2 PASS, nine of nine criteria |
| Owner approval | The owner issued the Phase 4.3 prompt after the Phase 4.2 handoff, which had asked for that authorization. The prompt contains no separate written acceptance of G4.2 and no answer on the open owner decisions; those stay open. No condition in the register blocks 4.3 |
| Previous notebook sections | 172 cells before; all kept, ids and code unchanged. 41 cells appended (15 code, 26 Markdown): 213 in total. Six Markdown cells had status sentences updated (contents, status lists, Phase 4 table, 4.2 closing line) |
| Previous outputs after re-execution | Same values. Differences: the environment line (repository now on `D:`, Python 3.14.6) and the order of tied rows in two sorted display tables (cells `fb69-p41-011`, `fb69-p42-033`; identical values, unstable sort among ties) |
| Dataset SHA-256 | `4d94ec73…eedd` verified before reading, and again after analysis (unchanged) |
| Scope | `load_scope()` → `rs5_v1`, five seasons; `check_parquet()` on the dataset; `check_table()` on the derived position-season table; no 2019/20 |
| Condition register | All 48 conditions reviewed. None blocks 4.3. RD-04, RS5-12, ISS-01, P4-B01, RD-03, ISS-21, ISS-27, ISS-25, P4-B07, ISS-29, ISS-11, P4-B05 applied in the analysis |
| Environment | `.venv` cannot start on this machine (its Python 3.13.13 base is missing). `.venv314` runs, and its freeze is identical to the G5 freeze. Recorded as ENV-P4-03 (delegated technical decision; owner may override) |
| Baseline tests before changes | `tests/phase4` 18 and `tests/research_scope` 71: all pass under `.venv314`; protection check clean |

## 2. Gate G4.3

| Criterion | Met | Evidence |
|---|---|---|
| Numerical associations documented | Yes | 53 features: n, players, missingness, Pearson raw and log10, Spearman with player-cluster bootstrap interval, binned trends, partial Spearman (`feature_target_association.csv`, `feature_target_binned*.csv`; `FEATURE_TARGET_ASSOCIATION_SUMMARY.md`; notebook 4.3.B–E) |
| Pearson and Spearman calculated appropriately | Yes | Pairwise-complete rows on applicable positions; average ranks for ties; raw and log10 Pearson; bootstrap by player (RS5-11). Test `test_correlations_match_reference_and_use_pairwise_complete_rows` checks against pandas |
| Categorical relationships investigated | Yes | Position, season, position x season, derived age and minutes bands: quantiles with counts and epsilon-squared (`target_by_*_43.csv`, `categorical_effect_sizes.csv`; notebook 4.3.H; `fig43_06`) |
| Feature-feature redundancy assessed | Yes | Spearman and Pearson matrices with pair counts (outfield and goalkeeper), 54 + 8 strong pairs with relation labels and season stability, 4 redundancy clusters (`FEATURE_REDUNDANCY_SUMMARY.md`; `fig43_07`) |
| Sample sizes and missingness considered | Yes | n and players for every coefficient; groups below 30 left empty; null vs present target medians; missing minutes kept as a category |
| RD-03 caveat consistently applied | Yes | In the notebook introduction, every interpretation block, `bivariate_summary.json`, each report and every row of the association summary |
| No causal claims | Yes | Associations only; confounders named as hypotheses (team context), not tested or asserted |
| No unauthorized feature selection | Yes | No feature removed, merged, preferred or transformed; RD-04, ISS-29 and club context not resolved. Tests `test_only_eligible_features_analysed`, `test_redundancy_clusters_describe_without_removing` |
| Notebook updated and reproducible | Yes | Full notebook executed end to end: 96 code cells, 0 errors; 7 figures exported |

Unmet criteria: none.

## 3. Key results

| Measure | Value |
|---|---:|
| Features analysed | 53 (on 2,697 usable targets) |
| Strongest Spearman (outfield) | rating 0.58 [0.55, 0.61], xA 0.56, minutes 0.54 |
| Strongest Spearman (goalkeepers, n 198) | clean sheets 0.67 [0.54, 0.77] |
| Readings | 9 strong positive, 20 moderate positive, 10 weak positive, 1 moderate negative, 8 weak negative, 5 no clear association |
| Appearances given starts / GK saves given starts | 0.53 → 0.14 / 0.53 → -0.22 |
| Age | Spearman -0.17; inverted U (peak 25–26); age-band epsilon-squared 0.20 |
| Position / season / position x season epsilon-squared | 0.026 / 0.015 / 0.043 |
| Strong outfield pairs (\|rho\| >= 0.8) / redundancy clusters (>= 0.9) | 54 / 4 |
| Identity sensitivity | median change 0.016, max 0.092, 0 sign changes |

## 4. Tests and execution

| Run | Result |
|---|---|
| `tests/research_scope` (71) + `tests/phase4` (27: 9 for 4.1, 9 for 4.2, 9 new for 4.3), under `.venv314` | 98 run, 98 passed (`evidence/tests_rs5_and_phase4.log`) |
| Evidence CLI `src/phase4/bivariate.py` | 28 tables and `bivariate_summary.json` (about 35 s, bootstrap included); dataset hash recorded after the run |
| `FB69_report.ipynb` full execution (base Python 3.14.6 with `.venv314` site-packages first) | 96 code cells, 0 errors; 7 figures exported to `figures/` |
| Protection check (`evidence/protection_check_phase4_03.json`) | 16,290 historical files, 0 removed, 0 unexpected changes, 0 unexpected additions; only the documented `CLAUDE.md` edit |
| Full repository suite (437 at G5) | Not re-run. No shared code was changed in 4.3 (ENV-P4-02 remains open) |

Nothing was installed. `tabulate` and `jinja2` are not available, so tables use plain DataFrame display.

## 5. Files

Created:
- `src/phase4/bivariate.py`
- `tests/phase4/test_bivariate_43.py`
- `reports/phase_04/step_03/`:
  - this report
  - `BIVARIATE_ANALYSIS_REPORT.md`
  - `FEATURE_TARGET_ASSOCIATION_SUMMARY.md`
  - `FEATURE_REDUNDANCY_SUMMARY.md`
  - `evidence/`: 32 files (28 tables including the correlation matrices, `bivariate_summary.json`, the test log, the `.venv314` freeze, the protection check)
  - `figures/`: 7 PNGs

Modified:
- `FB69_report.ipynb` (4.3 appended; status sentences in six cells; re-executed)
- `reports/phase_04/step_00/phase4_condition_register.yaml` and the rendered `PHASE4_CONDITION_REGISTER.md` (P4-C03 and ENV-P4-03 resolved, P4-B08 added; 51 conditions, 6 resolved)
- `reports/phase_04/README.md`

Not modified: the official release, the scope configuration, the crosswalk and mappings, the target method, the protection baseline, all historical data, Phase 4.1 and 4.2 code and evidence.

## 6. Open issues and owner decisions

- **New:** P4-B08 (playing time drives most volume associations; defensive and goalkeeper volumes reverse given playing time; team-context hypothesis untestable while RS5-12 is open). ENV-P4-03 (interpreter on this machine; owner may override).
- **Still open:** RD-04, RS5-12, RD-01, RD-02, RD-03 (default: keep D4), ISS-01 labels, ISS-04, P4-B05 (minimum-minutes rule), P4-B07 and ISS-25 (null treatment), `P4-B06` undefined in the register, ENV-P4-02 (full suite not re-run).
- **Authorization:** Phase 4.4 requires a new owner authorization.
