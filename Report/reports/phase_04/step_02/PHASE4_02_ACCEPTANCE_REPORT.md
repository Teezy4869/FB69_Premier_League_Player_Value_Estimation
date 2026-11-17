# Phase 4.2 Acceptance Report: Target & Univariate Analysis

Date: 2026-11-08. Authorization: owner prompt "PHASE 4.2 - TARGET & UNIVARIATE ANALYSIS". It authorizes Phase 4.2 only (recorded as P4-C02).

**G4.2 verdict: PASS.** All nine gate criteria are met. The dataset-level acceptance remains **CONDITIONAL** (Phase 4.0), and its open conditions are unchanged. **Phase 4.3 has not been started.** It requires a new owner authorization.

## 1. Pre-execution check

| Item | Result |
|---|---|
| Phase 4.1 acceptance report | Read: G4.1 PASS, ten of ten criteria |
| Owner approval and conditions | The owner issued the Phase 4.2 prompt in reply to the Phase 4.1 handoff, which had asked for that authorization. The prompt contains no separate written acceptance of G4.1 and no answer on ENV-P4-01, so the delegated ENV-P4-01 resolution stands (owner may still override). No condition in the register blocks 4.2 |
| `FB69_report.ipynb` | 129 cells before; all kept. 43 cells appended (17 code, 26 Markdown): 172 in total. Earlier cell ids, code and text outputs are identical after re-execution. Six Markdown cells had status sentences updated (contents table, status lists, Phase 4 table, and the 4.1 closing line) |
| Dataset SHA-256 | `4d94ec73…eedd` verified before reading, and again after analysis (unchanged) |
| Scope | `load_scope()` → `rs5_v1`, five seasons; `check_parquet()` on the dataset; `check_table()` on the derived season table; no 2019/20 |
| Phase 4.1 outputs vs dataset | Phase 4.1 tests (9) re-run and pass, including "recorded evidence equals recomputation" |
| Conditions and eligibility | Register and `phase4_feature_eligibility.csv` reviewed. Gap found: the eligibility CSV cites `P4-B06` for the 8 source-reported features, but the register does not define `P4-B06`. ISS-29 already states the required action, so this does not block 4.2. Not fixed here (definition is a register-owner decision) |

## 2. Gate G4.2

| Criterion | Met | Evidence |
|---|---|---|
| Target distribution documented | Yes | `TARGET_ANALYSIS_REPORT.md` §1–2; `evidence/target_summary.csv`, `target_fences.csv`, `target_extremes.csv`; notebook 4.2.B–C |
| Raw and log descriptive scales explained | Yes | Raw EUR is the source; log10 computed on the fly for description only; both summarised side by side, including the log scale's over-correction (skew 2.31 raw, −0.84 log10) |
| Season and position differences described | Yes | `target_by_season.csv`, `target_by_position.csv`, `target_median_position_season.csv`, `target_timing_by_season.csv`; notebook 4.2.D–E |
| Feature groups systematically analysed | Yes | 53 features in 9 groups, each with full statistics (`feature_summary.csv`, `feature_group_overview.csv`); `UNIVARIATE_FEATURE_ANALYSIS_REPORT.md` |
| Missingness interpreted correctly | Yes | Nulls read with `s_*` status; goalkeeper metrics on goalkeeper rows; `UNVERIFIED_POSITION` reported as not applicable; zero-recording pattern documented and **not** converted (`zero_recording.csv`, new P4-B07) |
| Outlier policy respected | Yes | No removal, cap or filter; IQR fences only count values; tail audited and shown genuine; test `test_stored_data_unchanged_and_tails_kept` |
| RD-03 caveat preserved | Yes | Stated in the notebook methodology, at every target reading, and in both reports |
| RD-04 and RS5-12 not silently resolved | Yes | RD-04 features described and flagged "pending" (test `test_rd04_flagged_not_resolved`); club context reported as counts only |
| Notebook updated and reproducible | Yes | Full notebook executed end to end: 81 code cells, 0 errors |

Unmet criteria: none.

## 3. Key results

| Measure | Value |
|---|---:|
| Usable targets | 2,697 of 2,747 |
| Target median / mean / std | EUR 13.0m / 19.26m / 20.43m |
| Target min / p99 / max | EUR 0.1m / 90m / 200m |
| Skewness / excess kurtosis (raw) | 2.31 / 8.71 |
| Skewness (log10, descriptive) | −0.84 |
| Values above the 3 IQR fence (EUR 85m) | 32 rows, 17 players, all genuine |
| Distinct target values | 84 |
| Median by season | 10 / 10 / 15 / 13 / 17m |
| Median by position (GK / DEF / MID / FWD) | 6 / 12 / 15 / 15m |
| Features analysed | 53 (40 candidate, 13 conditional) |
| Features with limited coverage | 21 |
| Count metrics never recording a zero | 18 (P4-B07) |

## 4. Tests and execution

| Run | Result |
|---|---|
| `tests/research_scope` (71) + `tests/phase4` (18: 9 for 4.1, 9 new for 4.2), under `.venv` | 89 run, 89 passed (`evidence/tests_rs5_and_phase4.log`) |
| Evidence CLI `src/phase4/univariate.py` | 24 tables and `univariate_summary.json`; dataset hash recorded after the run |
| `FB69_report.ipynb` full execution (base Python 3.13.13 with `.venv` site-packages first, as in 4.1) | 0 errors; 7 figures exported to `figures/` |
| Protection check (`evidence/protection_check_phase4_02.json`) | 16,290 historical files, 0 removed, 0 unexpected changes, 0 unexpected additions; only the documented `CLAUDE.md` edit |
| Full repository suite (437 at G5) | Not re-run. No shared code was changed in 4.2 (ENV-P4-02 remains open) |

Note: pandas `Styler` needs `jinja2`, which is not installed. The notebook therefore uses rounded tables. Nothing was installed.

## 5. Files

Created:
- `src/phase4/univariate.py`
- `tests/phase4/test_univariate_42.py`
- `reports/phase_04/step_02/`:
  - this report
  - `TARGET_ANALYSIS_REPORT.md`
  - `UNIVARIATE_FEATURE_ANALYSIS_REPORT.md`
  - `evidence/`: 27 files (24 distribution and summary tables, `univariate_summary.json`, the test log, the protection check)
  - `figures/`: 7 PNGs

Modified:
- `FB69_report.ipynb` (4.2 appended; six status sentences)
- `reports/phase_04/step_00/phase4_condition_register.yaml` and the rendered `PHASE4_CONDITION_REGISTER.md` (P4-C02 resolved, P4-B07 added; 48 conditions, 4 resolved)
- `reports/phase_04/README.md`

Not modified: the official release, the scope configuration, the crosswalk and mappings, the target method, the protection baseline, all historical data.

## 6. Open issues and owner decisions

- **New:**
  - P4-B07: count metrics record no zeros, so nulls likely include "no event". The treatment belongs to preprocessing design.
  - `P4-B06` is cited by the eligibility CSV but undefined in the register.
- **Still open from earlier phases:**
  - P4-B05: whether a minimum-minutes rule applies to analysis is an owner decision.
  - RD-04, RS5-12, RD-01, RD-02, RD-03 (default: keep D4), ISS-01 labels, ISS-04.
  - ENV-P4-01: confirm or override.
  - ENV-P4-02: the full test suite has not been re-run.
- **Authorization:** Phase 4.3 requires a new owner authorization.
