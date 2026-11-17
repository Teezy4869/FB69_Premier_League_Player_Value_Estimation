# Coverage Correction Report — Phase 2B.1-R Step 02

**Document ID:** CCR-2B1R-02  
**Project:** FB69 — Football Player Market Value Estimation  
**Audit Stage:** Phase 2B.1-R (Post-Collection Remediation), Step 02  
**Auditor Role:** Principal Data Engineer, Data Quality Auditor & ETL Specialist  
**Execution Timestamp:** 2026-11-03T10:50:00+07:00  
**Target Release Layer:** Remediation Layer (`reports/phase_02b1_remediation/`)  
**Verdict:** **PASS**

---

## 1. Executive Summary

During Phase 2B.1 execution, 41 anomalous metric-season cells were produced in `cross_season_feature_coverage.csv` where the number of valid values exceeded the reported eligible players ($\text{valid\_values} > \text{eligible\_players}$), producing impossible coverage fractions ranging from 130% to 215.8%.

Step 02 of Phase 2B.1-R resolved these anomalies by:
1. Identifying and isolating the architectural flaw: the top-20 saves leaderboard was incorrectly utilized as the full-season goalkeeper population denominator.
2. Designing a rigorous **Verified Eligibility Model** operating strictly at the distinct **Player–Season** grain for both numerator and denominator.
3. Deriving verified goalkeeper eligibility from historical match-lineup evidence (`historical_position_observations.parquet`), identifying between 37 and 44 verified goalkeepers per season.
4. Implementing the corrected calculation in `src/collection/statistics_semantics.py` and updating `src/collection/execution05_acceptance.py`.
5. Generating `reports/phase_02b1_remediation/metric_eligibility_registry.csv` and `reports/phase_02b1_remediation/cross_season_feature_coverage_v3.csv`.
6. Authoring a 10-test regression suite (`tests/collection/test_remediation_coverage.py`), passing 10/10 tests and ensuring all 107 repository tests pass.

**Result:** Zero anomalies remain. No coverage percentage exceeds 100%. All 41 anomalies have been verified as resolved.

---

## 2. Root Cause Diagnosis

The root cause was isolated to two interacting factors:

### 2.1 The Top-N Leaderboard Truncation Flaw
In `src/collection/statistics_report.py` line 147:
```python
if spec["stat"] == "saves":
    confirmed_gk[season].update(str(row["id"]) for row in payload["statsData"])
```
The collection pipeline queried FotMob's `leagueseasondeepstats` endpoint with `stat=saves`. This endpoint returns a paginated leaderboard truncated to the top 20 goalkeepers (or 19 in seasons with rank ties). The collection script populated `confirmed_gk[season]` exclusively from this leaderboard, mistaking a top-N ranking for the complete historical population.

### 2.2 Inconsistent Population Grain and Scope
When calculating coverage in `src/collection/execution05_acceptance.py`:
- **Denominator:** Extracted from `metric_collection_coverage.csv` (`scope.get("denominator_players")`), which was 20 (or 19) from the saves board.
- **Numerator:** Calculated from all 515+ confirmed appeared players in the curated wide table (`player_season_metrics_wide.parquet`). All goalkeepers who played in the season (including backup goalkeepers who made appearances and recorded saves) were evaluated and assigned status `OBSERVED`.

As a consequence, the numerator contained all ~40 goalkeepers with observations, while the denominator was restricted to 20, causing:
- 2019/20 Saves: 37 valid values / 20 eligible players = **185.0%**
- 2021/22 Saves: 41 valid values / 20 eligible players = **205.0%**
- 2024/25 Saves: 41 valid values / 19 eligible players = **215.8%**

---

## 3. The Verified Eligibility Model

To permanently resolve this architectural defect without arbitrary denominator padding, we designed and implemented a formal **Verified Eligibility Model** governed by the following principles:

### 3.1 Mathematical Grain and Definition
Both numerator and denominator are strictly evaluated at the identical **Player–Season** grain (unique `(season_label, player_id)` tuple):

$$\text{Coverage Ratio} = \frac{\text{valid\_eligible\_count}}{\text{eligible\_verified\_count}}$$

Where:
- $\text{valid\_eligible\_count} \le \text{eligible\_verified\_count}$, mathematically guaranteeing that $\text{Coverage Ratio} \le 1.0$ ($100\%$).
- $\text{eligible\_verified\_count} = 0 \implies \text{Coverage Ratio} = \text{undefined}$, assigned status `UNDEFINED`.

### 3.2 Registry Metric Attributes
The model distinguishes eight mandatory population and observation dimensions across each metric and season:
1. `population_count`: Total confirmed appeared players in that season ($N \in [515, 570]$).
2. `eligible_verified_count`: Count of players with historically verified eligibility:
   - For `applicable_positions == 'ALL'`: all confirmed appeared players ($\text{eligible} = \text{population\_count}$).
   - For `applicable_positions == 'GK_ONLY'`: appeared players with verified match-lineup evidence of `mapped_group == 'GK'`.
3. `eligibility_unknown_count`: Count of appeared players whose position group cannot be verified from lineup evidence ($0$ in the verified historical dataset; supported for future unverified inputs).
4. `observed_distinct_players`: Distinct appeared players with an observed valid value (`OBSERVED` or `OBSERVED_ZERO`).
5. `valid_eligible_count`: Distinct players who are both verified eligible AND possess a valid observed value.
6. `valid_outside_verified_eligibility_count`: Distinct players possessing a valid observed value who are NOT verified eligible (e.g. an outfield player making an emergency save). *Never silently discarded; explicitly tracked and flagged.*
7. `missing_eligible_count`: Verified eligible players with missing source data:
   $$\text{missing\_eligible\_count} = \text{eligible\_verified\_count} - \text{valid\_eligible\_count}$$
8. `coverage_status`: Deterministic status classification:
   - `FULL_COVERAGE`: $\text{valid\_eligible\_count} = \text{eligible\_verified\_count}$.
   - `VALID_PARTIAL`: $0 < \text{valid\_eligible\_count} < \text{eligible\_verified\_count}$.
   - `ZERO_OBSERVATIONS`: $\text{valid\_eligible\_count} = 0$ with $\text{eligible\_verified\_count} > 0$.
   - `SPARSE_SOURCE_COVERAGE`: Historical source absence for specific seasons (e.g., 2019/20 xG).
   - `UNSUPPORTED`: Metric unsupported across all players (e.g., `key_passes`).
   - `UNDEFINED`: $\text{eligible\_verified\_count} = 0$.
   - `ANOMALOUS_OUTSIDE_ELIGIBILITY`: $\text{valid\_outside\_verified\_eligibility\_count} > 0$.

---

## 4. Before & After Coverage Comparison

Across all 7 goalkeeper metrics and all 6 seasons (42 metric-season combinations), the table below presents the exact before/after comparison between release v2 (`cross_season_feature_coverage.csv`) and the remediated v3 matrix (`cross_season_feature_coverage_v3.csv`):

| Season | Metric Name | Old Eligible | Old Valid | Old Ratio | New Eligible | New Valid | New Ratio | New Status | Resolution Verdict |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2019/20** | `clean_sheets` | 20 | 37 | **185.0%** | 37 | 37 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2019/20** | `goals_conceded` | 20 | 37 | **185.0%** | 37 | 37 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2019/20** | `goals_conceded_per90` | 20 | 37 | **185.0%** | 37 | 37 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2019/20** | `goals_prevented` | 20 | 0 | 0.0% | 37 | 0 | **0.0%** | `ZERO_OBSERVATIONS` | **VALIDATED** |
| **2019/20** | `penalty_saves` | 20 | 28 | **140.0%** | 37 | 28 | **75.68%** | `VALID_PARTIAL` | **REPAIRED** |
| **2019/20** | `save_percentage` | 20 | 36 | **180.0%** | 37 | 36 | **97.30%** | `VALID_PARTIAL` | **REPAIRED** |
| **2019/20** | `saves` | 20 | 37 | **185.0%** | 37 | 37 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2020/21** | `clean_sheets` | 20 | 39 | **195.0%** | 41 | 39 | **95.12%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `goals_conceded` | 20 | 39 | **195.0%** | 41 | 39 | **95.12%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `goals_conceded_per90` | 20 | 39 | **195.0%** | 41 | 39 | **95.12%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `goals_prevented` | 20 | 37 | **185.0%** | 41 | 37 | **90.24%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `penalty_saves` | 20 | 27 | **135.0%** | 41 | 27 | **65.85%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `save_percentage` | 20 | 38 | **190.0%** | 41 | 38 | **92.68%** | `VALID_PARTIAL` | **REPAIRED** |
| **2020/21** | `saves` | 20 | 39 | **195.0%** | 41 | 39 | **95.12%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `clean_sheets` | 20 | 41 | **205.0%** | 42 | 41 | **97.62%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `goals_conceded` | 20 | 41 | **205.0%** | 42 | 41 | **97.62%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `goals_conceded_per90` | 20 | 41 | **205.0%** | 42 | 41 | **97.62%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `goals_prevented` | 20 | 38 | **190.0%** | 42 | 38 | **90.48%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `penalty_saves` | 20 | 26 | **130.0%** | 42 | 26 | **61.90%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `save_percentage` | 20 | 41 | **205.0%** | 42 | 41 | **97.62%** | `VALID_PARTIAL` | **REPAIRED** |
| **2021/22** | `saves` | 20 | 41 | **205.0%** | 42 | 41 | **97.62%** | `VALID_PARTIAL` | **REPAIRED** |
| **2022/23** | `clean_sheets` | 19 | 39 | **205.3%** | 39 | 39 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2022/23** | `goals_conceded` | 19 | 39 | **205.3%** | 39 | 39 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2022/23** | `goals_conceded_per90` | 19 | 39 | **205.3%** | 39 | 39 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2022/23** | `goals_prevented` | 19 | 38 | **200.0%** | 39 | 38 | **97.44%** | `VALID_PARTIAL` | **REPAIRED** |
| **2022/23** | `penalty_saves` | 19 | 30 | **157.9%** | 39 | 30 | **76.92%** | `VALID_PARTIAL` | **REPAIRED** |
| **2022/23** | `save_percentage` | 19 | 39 | **205.3%** | 39 | 39 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2022/23** | `saves` | 19 | 39 | **205.3%** | 39 | 39 | **100.0%** | `FULL_COVERAGE` | **REPAIRED** |
| **2023/24** | `clean_sheets` | 19 | 38 | **200.0%** | 40 | 38 | **95.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `goals_conceded` | 19 | 38 | **200.0%** | 40 | 38 | **95.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `goals_conceded_per90` | 19 | 38 | **200.0%** | 40 | 38 | **95.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `goals_prevented` | 19 | 35 | **184.2%** | 40 | 35 | **87.50%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `penalty_saves` | 19 | 30 | **157.9%** | 40 | 30 | **75.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `save_percentage` | 19 | 38 | **200.0%** | 40 | 38 | **95.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2023/24** | `saves` | 19 | 38 | **200.0%** | 40 | 38 | **95.00%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `clean_sheets` | 19 | 41 | **215.8%** | 44 | 41 | **93.18%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `goals_conceded` | 19 | 41 | **215.8%** | 44 | 41 | **93.18%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `goals_conceded_per90` | 19 | 41 | **215.8%** | 44 | 41 | **93.18%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `goals_prevented` | 19 | 26 | **136.8%** | 44 | 26 | **59.09%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `penalty_saves` | 19 | 28 | **147.4%** | 44 | 28 | **63.64%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `save_percentage` | 19 | 41 | **215.8%** | 44 | 41 | **93.18%** | `VALID_PARTIAL` | **REPAIRED** |
| **2024/25** | `saves` | 19 | 41 | **215.8%** | 44 | 41 | **93.18%** | `VALID_PARTIAL` | **REPAIRED** |

---

## 5. Implementation Changes & Backward Compatibility

### 5.1 Updates to `src/collection/statistics_semantics.py`
- Appended `verified_goalkeepers_from_positions(positions, season_label_map)` to extract exact goalkeepers from match lineup observations.
- Appended `compute_metric_eligibility_registry(wide, metrics, rules, positions, seasons)` to calculate the complete registry and corrected coverage matrix.
- Preserved existing `metric_denominator()` unmodified to maintain 100% backward compatibility with legacy tests.

### 5.2 Updates to `src/collection/execution05_acceptance.py`
- Enhanced `coverage_matrix()` signature to accept optional `positions` and `seasons`. When provided, verified eligibility is automatically utilized.
- Implemented `run_remediation(output_dir)` and wired the `--remediation` command line flag.
- Executing:
  ```powershell
  python -m src.collection.execution05_acceptance --remediation
  ```
  deterministically rebuilds both remediation files without modifying release v2 or previous reports.

---

## 6. Regression Testing & Execution Evidence

A dedicated test suite was implemented in `tests/collection/test_remediation_coverage.py`:

| Test Method | Requirement Addressed | Scenario & Validation Details | Exit Result |
| :--- | :--- | :--- | :---: |
| `test_01_top_n_leaderboard_denominator_errors_prevented` | 1. Top-N leaderboard denominator errors | Simulates 20-player leaderboard vs 37 appeared GKs; asserts ratio 37/37 = 1.0 (valid <= 1.0) and rejects 37/20. | **OK** |
| `test_02_goalkeeper_only_metrics_coverage_valid_across_all_seasons` | 2. Goalkeeper-only metrics | Asserts `valid_eligible_count <= eligible_verified_count` across all 42 GK metric-season cells in real v2 release data. | **OK** |
| `test_03_unknown_positions_tracked_not_imputed` | 3. Unknown positions | Injects players with unknown position; confirms they are tracked in `eligibility_unknown_count` without false position mapping. | **OK** |
| `test_04_duplicate_source_observations_do_not_inflate_numerator` | 4. Duplicate source observations | Asserts distinct player counting at Player-Season grain prevents numerator inflation from redundant observations. | **OK** |
| `test_05_multi_club_players_grain_consistency` | 5. Multi-club players | Validates that multi-club players (61 confirmed relations) are evaluated strictly at 1 Player-Season grain. | **OK** |
| `test_06_missing_values_tracked_not_zero_filled` | 6. Missing values | Asserts missing source data for eligible players increases `missing_eligible_count` without zero fabrication. | **OK** |
| `test_07_not_applicable_values_excluded_from_denominator` | 7. Not-applicable values | Asserts outfield players (e.g. 478 in 2019/20) are marked `not_applicable` and excluded from GK denominators. | **OK** |
| `test_08_eligible_population_zero_returns_undefined` | 8. Eligible population equal to zero | Asserts denominator = 0 produces `coverage_status == 'UNDEFINED'` without division-by-zero or false 0% / 100%. | **OK** |
| `test_09_valid_observations_outside_verified_eligibility_tracked` | 9. Valid observations outside verified eligibility | Simulates outfield player with emergency save; asserts observation is preserved, tracked, and flagged as anomalous. | **OK** |
| `test_10_numerator_denominator_grain_consistency_across_full_dataset` | 10. Numerator/denominator grain consistency | Asserts `valid_eligible_count <= eligible_verified_count` holds strictly for all 318 cells in release v2. | **OK** |

### Execution Command & Results:
```powershell
python -m unittest tests/collection/test_remediation_coverage.py -v
```
**Output:** Ran 10 tests in 3.348s — **OK**

Full regression test discovery across the entire repository:
```powershell
python -m unittest discover -s tests -v
```
**Output:** Ran 107 tests in 32.618s — **OK** (97 legacy tests + 10 remediation tests, 0 failures, 0 errors).

---

## 7. Step 02 Acceptance Gate Verdict

- Root cause diagnosed and documented: **CONFIRMED**
- Release v2 preserved unmodified: **CONFIRMED**
- Prior reports preserved unmodified: **CONFIRMED**
- Every reproduced coverage anomaly resolved: **100% RESOLVED (0 remaining)**
- No invalid coverage percentage reported: **CONFIRMED (Max ratio = 1.0)**
- Verified eligibility registry created: **`metric_eligibility_registry.csv` (318 rows)**
- Remediated coverage matrix created: **`cross_season_feature_coverage_v3.csv` (318 rows)**
- All 10 regression tests implemented and passing: **PASS (10/10)**
- Full repository test suite passing: **PASS (107/107)**

**Final Step 02 Verdict: PASS**

