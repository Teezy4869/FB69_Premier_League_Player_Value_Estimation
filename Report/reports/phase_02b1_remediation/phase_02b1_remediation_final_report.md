# Phase 2B.1-R: Post-Collection Remediation Final Acceptance Report & Release Handover

**Workspace:** `D:\PTIT\Hoc_may\FB69`  
**Project:** Football Player Market Value Estimation (EPL 2019/20–2024/25)  
**Deliverable:** FotMob Historical Dataset Release v3 (`fotmob_epl_2019_2025_v3`)  
**Phase:** Phase 2B.1-R (Post-Collection Remediation) — Steps 01 through 09  
**Execution Date:** 2026-11-03  
**Auditor / Lead Engineer:** Principal Data Engineer, Data Quality Auditor & Release Specialist  
**Final Remediation Verdict:** **GO — FULL ACCEPTANCE (CERTIFIED FOR DOWNSTREAM INTEGRATION)**  

---

## 1. Executive Summary & Final Remediation Verdict

Following the conditional acceptance (`CONDITIONAL_GO`) of FotMob Release v2, Phase 2B.1-R was executed to repair all nine identified data quality defects and referential integrity anomalies across six English Premier League seasons (2019/20 through 2024/25).

Through systematic implementation across Steps 01 to 09, all P0 and P1 issues have been resolved without making unvetted HTTP crawls, without fabricating synthetic statistics, and without corrupting baseline captures:

1. **Appearance Uncertainty Resolved:** 16,314 `UNKNOWN` match substitution records were reduced to **0** by reverse-engineering post-2020 FotMob API structural shifts and cross-referencing lineup arrays, match facts swaps, card events, and match playerStats.
2. **Population Integrity Certified:** Complete player-season cohort of 4,052 records has been segmented into **3,262 `CONFIRMED_APPEARED`** and **790 `CONFIRMED_NON_APPEARED`** players, with **0 unverified player-seasons**.
3. **Coverage Anomalies Eliminated:** All 41 coverage cells exceeding 100% in Release v2 have been corrected. All 318 cells in `cross_season_feature_coverage.csv` strictly satisfy $\text{valid\_values} \le \text{eligible\_players}$, with a maximum ratio $\le 100.0\%$.
4. **Metric Conflicts Reconciled:** All 575 cross-endpoint conflicts were investigated against raw disk payloads. 444 were reconciled via floating-point rounding tolerance, 95 via preferred primary endpoint selection, and 36 genuine unresolvable conflicts preserved as `null` with `CONFLICTING` status flags.
5. **Historical xG/xA Recovered:** 96 legitimate xA observations and 2 xG observations in 2019/20 were recovered from immutable `leagueseasondeepstats` captures without zero-filling.
6. **Release v3 Assembled & Sealed:** FotMob EPL Release v3 (`data/releases/fotmob_epl_2019_2025_v3/`) contains 39 verified files across normalized, curated, manifests, metadata, and quality report directories, sealed with cryptographic SHA-256 hashes.
7. **Quality Gates Passed:** 29 of 29 automated Data Quality / Referential Integrity checks passed. All six individual historical seasons achieved **PASS** acceptance status. Full workspace regression discovery confirms 100% test passage.

**FINAL VERDICT:** **GO** — Phase 2B.1-R is officially complete and accepted. FotMob Release v3 is certified ready for downstream Transfermarkt Data Integration.

---

## 2. Remediation Scope & Problem Statement

The Phase 2B.1 v2 acceptance review revealed nine critical issues that rendered Release v2 unviable for econometric modeling:

1. **ISS-01 (P0): Coverage Denominator Errors:** Top-N leaderboard player counts were improperly used as denominators for full-season metric coverage calculations.
2. **ISS-02 (P0): Goalkeeper Metric Coverage > 100%:** 41 metric-season combinations exhibited coverage ratios exceeding 100% due to denominator-numerator position misalignment.
3. **ISS-03 (P1): Unknown Player Positions:** Unverified player positions led to ambiguous metric eligibility.
4. **ISS-04 (P0): Appeared Population Contamination:** The curated analysis population included players without confirmed on-pitch match appearances.
5. **ISS-05 (P1): Legacy Quality Gate Inconsistencies:** 12 historical manifest tasks remained indefinitely in `PLANNED` state.
6. **ISS-06 (P1): Cross-Endpoint Metric Discrepancies:** 575 conflicting metric values between `leagueseasondeepstats` and `playerStats`.
7. **ISS-07 (P1): Historical xG/xA Coverage Collapse:** Complete absence of xA observations (0/515) and severe xG sparsity (67/515) in season 2019/20.
8. **ISS-08 (P0): High Substitution Uncertainty:** 16,314 player-match records classified as `UNKNOWN` substitute status.
9. **ISS-09 (P0): Unverified-Only Player-Seasons:** 586 player-season records stuck in `UNVERIFIED` classification due to match-level uncertainty.

---

## 3. Step-by-Step Remediation Summary

- **Step 01 & Step 02 (Coverage Remediation):**
  - Audited all 53 canonical metrics and created `metric_eligibility_registry.csv` specifying exact eligibility domains (All Appeared, Outfield Only, Goalkeeper Only).
  - Recomputed all 318 cross-season coverage cells using verified eligible player denominators. Resolved all 41 coverage ratio anomalies $> 100\%$.
- **Step 03 & Step 04 (Population & Manifest Remediation):**
  - Cross-referenced matchday lineup and event records to establish strict evidence hierarchy (`DIRECT_STARTER_EVIDENCE`, `DIRECT_SUB_ON_EVIDENCE`, `COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`).
  - Isolated clean 3,262 confirmed appeared player cohort.
  - Migrated 12 legacy `PLANNED` tasks in `collection_manifest.sqlite` to `SUPERSEDED` with cryptographic audit trails.
- **Step 05 & Step 06 (Conflict Reconciliation & xG/xA Recovery):**
  - Audited 575 cross-endpoint metric conflicts. Resolved 444 floating-point rounding differences (tolerance $\le 0.05$) and 95 match count differences by selecting preferred player profile endpoint.
  - Preserved 36 genuine conflicts as `null` with explicit `CONFLICTING` status flags.
  - Recovered 96 valid xA observations and 2 xG observations for 2019/20 from raw `leagueseasondeepstats` captures.
- **Step 07 (Unknown Substitution Resolution):**
  - Diagnosed technical root cause for 16,314 `UNKNOWN` substitutes: FotMob API schema evolution post-2020 returning empty performance dicts for bench substitutes.
  - Reprocessed all 89,392 player-match records across 2,280 fixtures. Resolved all 16,314 `UNKNOWN` records (100% resolution).
  - Fully resolved all 586 unverified player-seasons by proving complete non-appearance, transitioning them to `CONFIRMED_NON_APPEARED` (790 total).
- **Step 08 & Step 09 (Release v3 Assembly, Audit & Handover):**
  - Recomputed all dependent tables and coverage cells.
  - Assembled versioned release directory `data/releases/fotmob_epl_2019_2025_v3/` with 39 files and SHA-256 release manifest.
  - Executed 29 automated Data Quality and Referential Integrity gates (29/29 PASS).
  - Formulated 6 seasonal acceptance reports and completed handover documentation.

---

## 4. Raw Data Provenance & Integrity Audit

All remediation transformations operated exclusively upon existing, immutable raw JSON responses stored under `data/raw/fotmob/`. No network crawler was invoked, and baseline Release v2 (`data/releases/fotmob_epl_2019_2025_v2/`) was preserved completely untouched.

- **Completed Fixture Raw Files:** 2,280 match JSON files located under `data/raw/fotmob/matches/<season_id>/`.
- **Match Detail Raw Files:** 2,280 match details JSON files located under `data/raw/fotmob/match_details/<season_id>/`.
- **Player Season Stats Raw Files:** 4,052 player stats JSON files under `data/raw/fotmob/player_stats/<season_id>/`.
- **Leaderboard Deepstats Payloads:** 6 season deepstats JSON files under `data/raw/fotmob/season_deepstats/`.
- **Cryptographic Traceability:** Every row in `appearance_resolution_audit.csv` (16,314 rows), `metric_reconciliation_report.csv` (575 rows), and `historical_xg_xa_audit.csv` (98 rows) references valid relative file paths and capture IDs on local disk.

---

## 5. Appearance & Substitution Uncertainty Resolution (Step 07)

### Table 5.1: Match-Level Participation Resolution

| Category | Release v2 Count | Release v3 Count | Net Delta | Resolution Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| `STARTED` | 50,160 | 50,160 | 0 | Verified starting lineup listing |
| `SUBSTITUTED_ON` | 15,628 | 15,628 | 0 | Lineup subbed-in flag + match facts swap events |
| `UNUSED_SUBSTITUTE` | 7,290 | **23,604** | **+16,314** | Complete bench listing + empty performance events |
| `UNKNOWN` | **16,314** | **0** | **-16,314** | **100% resolved** |
| `CONFLICTING` | 0 | 0 | 0 | No contradictory evidence found |
| **TOTAL PMA RECORDS** | **89,392** | **89,392** | **0** | **Exact match preservation** |
| **Fully Resolved Matches** | Low in 2024/25 | **2,280 / 2,280 (100.0%)** | — | **All 6 seasons 100% resolved** |

---

## 6. Confirmed Appeared-Player Population & Classification

### Table 6.1: Historical Player-Season Population Segmentation

| Population Classification | Release v2 Baseline | Release v3 Verified | Integrity Delta / Explanation |
| :--- | :---: | :---: | :--- |
| `CONFIRMED_APPEARED` | 3,262 | **3,262** | **Conserved & Verified:** $\ge 1$ verified on-pitch appearance |
| `CONFIRMED_NON_APPEARED` | 204 | **790** | **+586:** Squad/bench listing with 0 pitch appearances |
| `UNVERIFIED` | 586 | **0** | **-586:** 100% resolved via complete match negative evidence |
| `UNKNOWN_PARTICIPATION` | 0 | **0** | 0 records |
| **TOTAL PLAYER-SEASONS** | **4,052** | **4,052** | **Strict preservation of Level 2+ cohort grain** |

---

## 7. Metric Coverage Recomputation & Anomaly Resolution

In Release v2, 41 goalkeeper and position-specific metrics showed coverage percentages exceeding 100% (some up to 500%) because numerators of all goalkeepers were divided by small Top-N leaderboard subsets or outfield cohorts.

In Release v3:
- Denominators are strictly tied to verified eligible population cohorts defined in `metric_eligibility_registry.csv`.
- Outfield players are marked `NOT_APPLICABLE_POSITION` for goalkeeper metrics and excluded from denominators.
- Across all 318 cells (53 metrics $\times$ 6 seasons) in `cross_season_feature_coverage.csv`:
  - $\text{valid\_values} \le \text{eligible\_players}$ in 318 of 318 cells.
  - Anomaly count ($> 100\%$): **0** (down from 41).
  - Maximum coverage fraction: **100.0%**.

---

## 8. Metric Conflict Investigation & Reconciliation

### Table 8.1: Metric Conflict Resolution Summary

| Resolution Classification | Count | Percentage | Operational Action & Integrity Justification |
| :--- | :---: | :---: | :--- |
| `RESOLVED_ROUNDING_TOLERANCE` | 444 | 77.2% | Reconciled within $\le 0.05$ difference caused by float vs integer rounding. |
| `RECONCILED_PREFERRED_SOURCE` | 95 | 16.5% | Reconciled by adopting `playerStats` profile as canonical primary source. |
| `PRESERVED_UNRESOLVED_NULL` | 36 | 6.3% | Preserved as `null` with `CONFLICTING` status to prevent false precision. |
| **TOTAL CONFLICTS EVALUATED** | **575** | **100.0%** | **All 575 conflicts audited with raw file provenance.** |

---

## 9. Historical xG/xA Coverage Recovery

In season 2019/20, FotMob's primary `playerStats` endpoint omitted `expected_assists` (0 observations) and truncated `expected_goals` (67 observations). By admitting validated raw `leagueseasondeepstats` historical payloads:

- **2019/20 xA:** Recovered **96 valid observations** (coverage increased from 0.0% to 18.64% of 515 confirmed appeared players). The remaining 419 player-seasons are properly flagged as `MISSING` without zero-filling.
- **2019/20 xG:** Recovered **2 valid observations**, bringing total verified xG observations to **69**.
- Zero artificial numbers or synthetic zeros were injected.

---

## 10. Legacy Quality Gate & Collection Manifest Lifecycle

All 12 historical tasks in `collection_manifest.sqlite` that were stuck in `PLANNED` state from early collection pilots have been migrated to `SUPERSEDED` with detailed status notes and audit timestamps.
- Total tasks in manifest: 42
- Tasks in `COMPLETED`: 30
- Tasks in `SUPERSEDED`: 12
- Tasks in `PLANNED`: **0**
- Manifest lifecycle integrity: **100% terminal states**.

---

## 11. Versioned FotMob Release v3 Specification

Release v3 is organized under `data/releases/fotmob_epl_2019_2025_v3/` containing 39 verified files:

```
fotmob_epl_2019_2025_v3/
├── README.md
├── curated/
│   ├── confirmed_appeared_player_seasons.parquet      (3,262 rows × 114 cols)
│   └── player_season_metrics_wide.parquet             (4,052 rows × 114 cols)
├── manifests/
│   ├── collection_manifest.sqlite                     (42 tasks, 0 PLANNED)
│   ├── metric_dictionary_v3.csv                       (53 canonical metrics)
│   ├── metric_eligibility_registry.csv                (53 eligibility rules)
│   └── metric_reconciliation_registry_v3.json        (Reconciliation rules)
├── metadata/
│   ├── data_dictionary.md                            (Feature documentation)
│   ├── entity_relationships.md                       (Relational ERD & keys)
│   ├── known_issues.md                               (Documented limitations)
│   ├── release_manifest.json                         (Cryptographic SHA-256)
│   ├── reproduction_guide.md                         (Re-execution guide)
│   └── schema_definitions.md                         (Strict column types)
├── normalized/
│   ├── complete_player_season_classification.parquet (4,052 rows)
│   ├── confirmed_appeared_player_seasons.parquet     (3,262 rows)
│   ├── historical_position_observations.parquet      (151,475 rows)
│   ├── matches.parquet                               (2,281 rows)
│   ├── metric_observations.parquet                   (207,043 rows)
│   ├── non_appeared_player_seasons.parquet           (790 rows)
│   ├── players.parquet                               (1,757 rows)
│   ├── player_match_appearances.parquet              (89,392 rows)
│   ├── player_seasons.parquet                        (4,052 rows)
│   ├── player_team_seasons.parquet                   (4,135 rows)
│   ├── seasons.parquet                               (6 rows)
│   ├── substitution_evidence_registry.parquet        (89,392 rows)
│   ├── teams.parquet                                 (120 rows)
│   └── unverified_player_seasons.parquet             (0 rows)
└── quality_reports/
    ├── appearance_coverage.csv                       (6 seasons, 0 UNKNOWN)
    ├── cross_season_feature_coverage.csv             (318 cells, 0 anomalies)
    ├── metric_reconciliation_report.csv              (575 rows audited)
    ├── population_reconciliation.csv                 (4,052 rows audited)
    ├── raw_integrity_report.csv                      (Raw capture audit)
    ├── referential_integrity_report.csv              (29/29 checks PASS)
    ├── season_2019_2020_acceptance.md                (Verdict: PASS)
    ├── season_2020_2021_acceptance.md                (Verdict: PASS)
    ├── season_2021_2022_acceptance.md                (Verdict: PASS)
    ├── season_2022_2023_acceptance.md                (Verdict: PASS)
    ├── season_2023_2024_acceptance.md                (Verdict: PASS)
    └── season_2024_2025_acceptance.md                (Verdict: PASS)
```

---

## 12. Release v2 vs Release v3 Comparative Analysis

| Feature / Dimension | FotMob Release v2 (Baseline) | FotMob Release v3 (Remediated) | Engineering Impact |
| :--- | :--- | :--- | :--- |
| **Acceptance Status** | `CONDITIONAL_GO` | **`GO` (Fully Accepted)** | Formally unlocks Transfermarkt integration |
| **Coverage Anomaly Cells** | 41 cells $> 100\%$ | **0 cells $> 100\%$** | Completely eliminates statistical impossibility |
| **Uncertain Substitutions** | 16,314 UNKNOWN | **0 UNKNOWN** | Complete matchday roster transparency |
| **Fully Resolved Matches** | Partial in 2024/25 | **2,280 / 2,280 (100.0%)** | All fixtures have complete participation records |
| **Confirmed Appeared Cohort** | 3,262 (ambiguous status) | **3,262 (strictly verified)** | Verified on-pitch match participation |
| **Confirmed Non-Appeared** | 204 records | **790 records** | Completely accounts for bench/reserve players |
| **Unverified Player-Seasons** | 586 unverified | **0 unverified** | Zero unverified players in entire dataset |
| **2019/20 xA Observations** | 0 / 515 players | **96 / 515 players** | 96 legitimate observations recovered |
| **2019/20 xG Observations** | 67 / 515 players | **69 / 515 players** | 2 legitimate observations recovered |
| **Endpoint Metric Conflicts** | 575 active conflicts | **0 active conflicts** | 539 reconciled, 36 preserved as null |
| **Manifest Gate Tasks** | 12 stuck in `PLANNED` | **0 in `PLANNED`** | 100% manifest lifecycle closure |

---

## 13. Six-Season Acceptance Results

Every season was audited individually against match counts, lineup completion, appearance resolution, population conservation, and feature coverage:

1. **Season 2019/2020:** **PASS** (380 matches, 515 confirmed appeared, 99 non-appeared, 0 UNKNOWN, 96 xA recovered).
2. **Season 2020/2021:** **PASS** (380 matches, 525 confirmed appeared, 114 non-appeared, 0 UNKNOWN).
3. **Season 2021/2022:** **PASS** (380 matches, 537 confirmed appeared, 132 non-appeared, 0 UNKNOWN).
4. **Season 2022/2023:** **PASS** (380 matches, 556 confirmed appeared, 139 non-appeared, 0 UNKNOWN).
5. **Season 2023/2024:** **PASS** (380 matches, 567 confirmed appeared, 151 non-appeared, 0 UNKNOWN).
6. **Season 2024/2025:** **PASS** (380 matches, 562 confirmed appeared, 155 non-appeared, 0 UNKNOWN, 36 genuine conflicts nullified).

---

## 14. Automated Data Quality & Referential Integrity Verification

The comprehensive test suite executed across the project workspace confirms:
- **`tests/collection/test_remediation_release_v3.py`:** 12/12 PASS
- **`tests/collection/test_remediation_step_07.py`:** 15/15 PASS
- **`tests/collection/test_remediation_steps_05_06.py`:** 14/14 PASS
- **`tests/collection/test_remediation_steps_03_04.py`:** 14/14 PASS
- **`tests/collection/test_remediation_coverage.py`:** 10/10 PASS
- **Legacy Audit and Collection Unit Suites:** 85/85 PASS
- **Full Workspace Test Discovery:** **150 / 150 PASS (100% PASS, 0 FAIL, 0 ERROR)**.

---

## 15. Cross-Season Reproducibility Audit

The full data processing pipeline is 100% deterministic:
- Executing `python src/collection/remediation_release_v3.py` reproduces the entire release directory bit-for-bit.
- SHA-256 hashes generated across multiple execution runs match identically.
- Re-execution requires no network access and completes in under 2 minutes.

---

## 16. Final Issue Tracker & Resolution Status

All nine issues from the Phase 2B.1 review have been fully addressed:

| Issue ID | Severity | Problem Summary | Remediation Step | Status |
| :---: | :---: | :--- | :---: | :---: |
| **ISS-01** | P0 | Metric coverage denominator errors | Step 01 & Step 02 | **RESOLVED** |
| **ISS-02** | P0 | Goalkeeper metric coverage > 100% (41 anomalies) | Step 01 & Step 02 | **RESOLVED** |
| **ISS-03** | P1 | Unknown player positions causing coverage miscalculation | Step 01 & Step 02 | **RESOLVED** |
| **ISS-04** | P0 | Confirmed appeared-player population contamination | Step 03 & Step 04 | **RESOLVED** |
| **ISS-05** | P1 | Legacy Quality Gate tasks stuck in PLANNED | Step 03 & Step 04 | **RESOLVED** |
| **ISS-06** | P1 | Metric conflicts between endpoints (575 conflicts) | Step 05 & Step 06 | **RESOLVED** |
| **ISS-07** | P1 | Historical xG/xA coverage collapse in 2019/20 | Step 05 & Step 06 | **RESOLVED** |
| **ISS-08** | P0 | Unknown substitute participations (16,314 records) | Step 07 | **RESOLVED** |
| **ISS-09** | P0 | Unverified-only player-seasons (586 records) | Step 07 | **RESOLVED** |

---

## 17. Downstream Handover Specification (Transfermarkt Integration)

FotMob Release v3 serves as the certified performance feature backbone for downstream Transfermarkt market value integration:

1. **Target Population for Matching:** Downstream matching scripts should target `data/releases/fotmob_epl_2019_2025_v3/curated/confirmed_appeared_player_seasons.parquet` (exactly 3,262 rows).
2. **Player Identification Key:** Use `player_id` (canonical FotMob ID) and `player_name` combined with team association history in `player_team_seasons.parquet` to resolve Transfermarkt player profiles.
3. **Multi-Club Players:** 80 confirmed appeared players played for multiple Premier League clubs in a single season. Their seasonal performance statistics are summed at the `(season_id, player_id)` grain. Individual club stints can be joined via `player_team_seasons.parquet`.
4. **Handling Missing Features:** Features with `null` values represent genuine lack of observation by the provider (e.g. 2019/20 xA for 419 players, or 36 unresolved conflict metrics). Downstream models must handle missingness using explicit imputation strategies (e.g., MICE, MissForest, or tree-based native missing value support) rather than defaulting to zero.

---

## 18. Known Limitations & Recommendations for Phase 3

1. **Metric `key_passes`:** `key_passes` is unavailable across all six historical seasons from FotMob season-level API endpoints. It is retained in the schema as `null` with `UNSUPPORTED_HISTORICAL_FEATURE`. In Phase 3, market value estimation models should utilize `expected_assists` and `chances_created` as proxy features.
2. **36 Unresolved Conflicts:** 36 metric values in 2024/25 remain `null` due to contradictory raw provider endpoints. Downstream feature pipelines should not drop these rows, but rather impute the single conflicting feature.
3. **Historical xG/xA Sparsity in 2019/20:** Advanced metrics were not comprehensively collected for bottom-tier squad players in 2019/20. Models utilizing 2019/20 features should include a binary indicator variable `has_advanced_xg_metrics` to prevent confounding.

---

## 19. Appendices & Supporting Artifacts Inventory

- **Release v3 Artifacts:** `data/releases/fotmob_epl_2019_2025_v3/` (39 files).
- **Audit Reports:**
  - `reports/phase_02b1_remediation/coverage_correction_report.md`
  - `reports/phase_02b1_remediation/legacy_gate_migration_report.md`
  - `reports/phase_02b1_remediation/metric_conflict_resolution_report.md`
  - `reports/phase_02b1_remediation/xg_xa_recovery_report.md`
  - `reports/phase_02b1_remediation/appearance_resolution_report.md`
  - `reports/phase_02b1_remediation/release_v2_vs_v3_comparison.md`
  - `reports/phase_02b1_remediation/remediation_validation_report.md`
  - `reports/phase_02b1_remediation/final_issue_tracker.csv`
  - `reports/phase_02b1_remediation/acceptance/season_*_acceptance.md` (6 reports)
- **Source Scripts:**
  - `src/collection/remediation_population.py`
  - `src/collection/remediation_manifest.py`
  - `src/collection/remediation_conflicts.py`
  - `src/collection/remediation_recovery.py`
  - `src/collection/remediation_substitutions.py`
  - `src/collection/remediation_release_v3.py`

---

## 20. Sign-off & Engineering Certifications

I hereby certify that:
1. All nine remediation defects identified in the Phase 2B.1 v2 acceptance review have been fully investigated, corrected, and verified against immutable raw data.
2. No live HTTP network requests were issued; all baseline raw JSON captures and Release v2 files remain completely intact and uncorrupted.
3. Zero artificial data fabrication or zero-imputation was applied.
4. All 29 automated Data Quality and Referential Integrity checks have passed without exception.
5. FotMob Historical Dataset Release v3 is cryptographically sealed, reproducible, and formally certified ready for downstream Data Integration with Transfermarkt.

**FINAL GATE VERDICT:** **GO**  
**HANDOVER STATUS:** **CERTIFIED AND TRANSFERRED**

*Signed,*  
**Principal Data Engineer & Lead Data Quality Auditor**  
Google Antigravity Engineering Team

