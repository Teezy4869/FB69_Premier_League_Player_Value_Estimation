# Remediation Baseline Report — Phase 2B.1-R Step 01

**Document ID:** RBR-2B1R-01  
**Project:** FB69 — Football Player Market Value Estimation  
**Audit Stage:** Phase 2B.1-R (Post-Collection Remediation), Step 01  
**Auditor Role:** Principal Data Engineer, Data Quality Auditor & ETL Specialist  
**Execution Timestamp:** 2026-11-03T10:45:00+07:00  
**Baseline Release Audited:** `data/releases/fotmob_epl_2019_2025_v2/`  
**Verdict:** **PASS**

---

## 1. Executive Summary & Audit Mandate

Phase 2B.1 culminated in release `fotmob_epl_2019_2025_v2`, which received a **CONDITIONAL_GO** due to unresolved player-match substitute participation, cross-source metric conflicts, and anomalous metric coverage calculations.

The objective of Step 01 of Phase 2B.1-R is to conduct a strict, evidence-backed baseline audit of the actual v2 release artifact. Per the non-negotiable governance rules:
- Release v2 and all immutable raw JSON captures remain completely unmodified.
- No historical reports are overwritten.
- All historical audit findings are recomputed directly from the parquet and manifest files; no reported number is accepted on faith or hardcoded.

The audit has successfully verified all release artifacts, confirmed the exact file checksums, validated all core entity counts, reproduced all 41 coverage anomalies, isolated their mathematical root causes, and cataloged all known data-quality issues into a structured inventory.

---

## 2. Release v2 Physical & Cryptographic Verification

The release package is situated at:  
`data/releases/fotmob_epl_2019_2025_v2/`

### 2.1 Manifest Verification
- **Manifest Location:** `metadata/release_manifest.json`
- **Manifest SHA-256:** `b656af4923d22216deb690138978e2f7612434b6fce11bd7656b673cab38e067`
- **Total Release Files:** 35 files across `curated/`, `normalized/`, `metadata/`, `manifests/`, and `quality_reports/`.
- **Integrity Status:** 100% of files present; 100% of cryptographic hashes match the manifest. Complete snapshot preserved in `reports/phase_02b1_remediation/release_v2_integrity_snapshot.json`.

### 2.2 Parquet Tables Audit
Every Parquet table was inspected for schema structure, column types, row counts, and binary SHA-256 checksums:

| Table Name | Layer | Schema Version | Expected Rows | Actual Rows | Size (Bytes) | SHA-256 Digest | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| `players.parquet` | Normalized | `2b1-v1` | 1,757 | 1,757 | 110,650 | `fae45cba4e8a1aa37197db799cba2b5ee54731e936545fad0d488acbca0d3c9a` | VERIFIED |
| `teams.parquet` | Normalized | `2b1-v1` | 120 | 120 | 3,269 | `d00072ea74685f9c50cc7cb27bdc71047ea10fc5ceaaf38790f3f4190c0e5258` | VERIFIED |
| `seasons.parquet` | Normalized | `2b1-v1` | 6 | 6 | 2,117 | `0f5280d446989c625ece2974731379eddc40ab824950ba1e4065e4915a706722` | VERIFIED |
| `matches.parquet` | Normalized | `2b1-v1` | 2,281 | 2,281 | 26,675 | `b9b93392f757f4dd741d2a0a220c285686e2a01f17ee10a6aa11c9096b22caf5` | VERIFIED |
| `player_seasons.parquet` | Normalized | `2b1-v1` | 4,052 | 4,052 | 284,239 | `83ff6f0b3f09abcb62bcf5368511d1651fcb1f7629950cc0bf30fb417fe75e43` | VERIFIED |
| `player_team_seasons.parquet` | Normalized | `2b1-v1` | 4,135 | 4,135 | 270,301 | `d3f484ced06bcba10c09e8fcecadae2bdca8fbd2268006e3a1925c23b1a69437` | VERIFIED |
| `player_match_appearances.parquet` | Normalized | `2b1-v1` | 89,392 | 89,392 | 606,649 | `ae125ea8f9ec37019918834c9c636dcdc413f6b23abf82da2e4b00ba0c98e1f9` | VERIFIED |
| `historical_position_observations.parquet` | Normalized | `2b1-v1` | 151,475 | 151,475 | 352,843 | `3ffc696c3fb1d42605c30bb6746d14e33f477a18c57a67555690cb698baeaa43` | VERIFIED |
| `metric_observations.parquet` | Normalized | `2b1-v1` | 207,043 | 207,043 | 1,916,631 | `f6bce66e0040a1ba5635f1e09dd96ec5b15f3945c093460f72dd5266d96f4f8d` | VERIFIED |
| `player_season_metrics_wide.parquet` | Curated | `2b1-v1` | 4,052 | 4,052 | 502,448 | `69ec796311a76ea0b291c18a4d4c5e16112b910f4fef081f4cf15eb319ec8825` | VERIFIED |

---

## 3. Recomputed Baseline Counts vs Known Findings

Each finding reported from the prior Phase 2B.1 final acceptance was independently recalculated from the v2 release tables:

| Audit Item | Prior Reported Count | Recomputed Count | Variance | Verification Status & Analysis |
| :--- | :---: | :---: | :---: | :--- |
| **Unique Players** | 1,757 | 1,757 | 0 | **CONFIRMED**. Exact match across `players` (1,757), `player_seasons` (1,757 unique IDs), and `wide` (1,757 unique IDs). |
| **Player–Season Records** | 4,052 | 4,052 | 0 | **CONFIRMED**. Strict match in `player_seasons` and `wide`. |
| **Confirmed Appeared Records** | 3,262 | 3,262 | 0 | **CONFIRMED**. Exactly 3,262 rows with `evidence_status == 'APPEARED'`. |
| **Uncertain-Only Records** | 586 | 586 | 0 | **CONFIRMED**. Exactly 586 rows with `evidence_status == 'UNKNOWN_PARTICIPATION'`. |
| **Unused-Only Records** | 204 | 204 | 0 | **CONFIRMED**. Exactly 204 rows with `evidence_status == 'UNUSED_SUBSTITUTE_ONLY'`. (3,262 + 586 + 204 = 4,052). |
| **Completed Premier League Matches** | 2,280 | 2,280 | 0 | **CONFIRMED**. Exactly 380 completed fixtures across 6 seasons. Table has 2,281 rows, including abandoned fixture 4193691 (`eligible_completed == 'False'`). |
| **Metric Observations** | 207,043 | 207,043 | 0 | **CONFIRMED**. Long table contains 207,043 rows across 53 metrics. |
| **Data Dictionary Metrics** | 53 | 53 | 0 | **CONFIRMED**. Metric dictionary v3 defines 53 canonical metrics. |
| **Metric Reconciliation Conflicts** | 575 | 575 | 0 | **CONFIRMED**. 575 comparisons between leaderboard and playerStats differ beyond display rounding tolerances. |
| **Metric-Season Coverage Anomalies** | 41 | 41 | 0 | **CONFIRMED**. Exactly 41 cells in `cross_season_feature_coverage.csv` where `valid_values > eligible_players`. |
| **Legacy Quality Gates Marked PLANNED** | 12 | 12 | 0 | **CONFIRMED**. 12 manifest tasks (6 NORMALIZATION_GATE, 6 SEASON_ACCEPTANCE_GATE) remain PLANNED in `collection_gap_report.csv`. |
| **Unresolved Substitute Records** | 16,314 | 16,314 | 0 | **CONFIRMED**. 16,314 rows in `player_match_appearances.parquet` have `participation_status == 'UNKNOWN'`. |
| **2019/20 xG / xA Valid Curated Count** | Extremely Low | xG: 67 (13.0%)<br>xA: 0 (0.0%) | 0 | **CONFIRMED**. Sparse source coverage in FotMob 2019/20 deep stats (xG collected for 67 top scorers only, xA for 0). |

---

## 4. Analysis of Population Classifications & Match Uncertainty

### 4.1 Population Classification Breakdown by Season
The 4,052 historical Player–Season records distribute across the six seasons as follows:

| Season | APPEARED | UNKNOWN_PARTICIPATION | UNUSED_SUBSTITUTE_ONLY | Total Records |
| :---: | :---: | :---: | :---: | :---: |
| **2019/2020** | 515 | 10 | 89 | 614 |
| **2020/2021** | 524 | 99 | 18 | 641 |
| **2021/2022** | 537 | 107 | 35 | 679 |
| **2022/2023** | 554 | 103 | 42 | 699 |
| **2023/2024** | 570 | 144 | 20 | 734 |
| **2024/2025** | 562 | 123 | 0 | 685 |
| **Total** | **3,262** | **586** | **204** | **4,052** |

### 4.2 Appearance Uncertainty in Match Lineups
In `player_match_appearances.parquet` (89,392 total records):
- **Lineup Role:**
  - `STARTER`: 50,160 records (100% confirmed started).
  - `SUBSTITUTE`: 39,232 records.
- **Participation Status:**
  - `STARTED`: 50,160 records (CONFIRMED).
  - `SUBSTITUTED_ON`: 15,628 records (CONFIRMED).
  - `UNUSED_SUBSTITUTE`: 7,290 records (CONFIRMED NOT APPEARED).
  - `UNKNOWN`: 16,314 records (UNRESOLVED).
- **Core Appearance Invariant:**  
  Confirmed appearances total $50,160 + 15,628 = 65,788$.  
  $65,788 \text{ confirmed} + 7,290 \text{ unused} + 16,314 \text{ unresolved} = 89,392$.  
  The 16,314 unresolved entries stem from historical FotMob matches where substitution lists were omitted or lacked explicit substitution-in event logs.

---

## 5. Denominator Incompatibility & Coverage Anomaly Reproduction

### 5.1 Confirmation of the 41 Anomalies
In `data/releases/fotmob_epl_2019_2025_v2/quality_reports/cross_season_feature_coverage.csv`, exactly 41 rows exhibit:
$$\text{valid\_values} > \text{eligible\_players}$$

All 41 anomalies reside strictly within the 7 metrics having `applicable_positions == 'GK_ONLY'`:

1. `clean_sheets` (6 seasons: 2019/20 to 2024/25)
2. `goals_conceded` (6 seasons: 2019/20 to 2024/25)
3. `goals_conceded_per90` (6 seasons: 2019/20 to 2024/25)
4. `penalty_saves` (6 seasons: 2019/20 to 2024/25)
5. `save_percentage` (6 seasons: 2019/20 to 2024/25)
6. `saves` (6 seasons: 2019/20 to 2024/25)
7. `goals_prevented` (5 seasons: 2020/21 to 2024/25; in 2019/20 valid_values = 0 <= 20)

Total anomaly count: $6 \times 6 + 5 = 41$.

### 5.2 Root Cause Analysis
The bug originated in `src/collection/statistics_report.py` line 147:
```python
if spec["stat"] == "saves":
    confirmed_gk[season].update(str(row["id"]) for row in payload["statsData"])
```
1. **Top-N Leaderboard Truncation:** FotMob's `leagueseasondeepstats` endpoint for stat `saves` returns only the top 20 goalkeepers (or 19 in 2022/23+ due to tie-breakers/rank cutoffs). The script mistakenly treated this leaderboard subset as the entire confirmed goalkeeper population for the season (`confirmed_gk[season]`).
2. **Inconsistent Population Scopes:** In `execution05_acceptance.py`, `eligible_players` was populated from `denominator_players` ($N=20$ or $19$) from `metric_collection_coverage.csv`. Meanwhile, `valid_values` was counted across all 515+ appeared players in the curated wide table.
3. **Backup Goalkeepers:** In reality, between 37 and 44 goalkeepers played in each Premier League season (starters + backup goalkeepers who recorded appearances). Because all appeared goalkeepers with valid `playerStats` records received `OBSERVED` status, the numerator counted all ~40 goalkeepers, while the denominator was capped at 20.

---

## 6. Legacy Quality Gates Audit

In `reports/phase_02b1/collection_gap_report.csv`, exactly 12 manifest tasks remain marked as `PLANNED` with classification `LOCAL_GATE_PENDING`:
- 6 tasks: `NORMALIZATION_GATE` (1 per season)
- 6 tasks: `SEASON_ACCEPTANCE_GATE` (1 per season)

**Root Cause:** The earlier Phase 2A/2B.0 pipeline required an absolute participation contract (all substitute listings had to be strictly binary TRUE/FALSE). When the Phase 2B.1 contract introduced `UNKNOWN` participation to truthfully represent missing substitution events, the older local gates were left `PLANNED` to avoid failing an outdated assertion. They were superseded by the independent Execution 05 acceptance audit.

---

## 7. Structured Issue Inventory Summary

The structured issue inventory has been saved to:  
`reports/phase_02b1_remediation/remediation_issue_tracker.csv`

Nine canonical issues have been classified:
- `ISS-COV-01` (HIGH): 41 metric-season coverage anomalies (Addressed in Step 02).
- `ISS-PART-01` (MEDIUM): 16,314 unresolved substitute participation records (Scope of Steps 03–04).
- `ISS-CONF-01` (MEDIUM): 575 cross-source metric conflicts (Scope of Steps 05–06).
- `ISS-MET-01` (MEDIUM): `key_passes` unsupported in source (Preserved as UNSUPPORTED).
- `ISS-XG-01` (MEDIUM): Sparse source 2019/20 xG/xA coverage (Documented).
- `ISS-GATE-01` (LOW): 12 legacy quality gates marked PLANNED (Documented).
- `ISS-POS-01` (LOW): Current profile position is CURRENT_ONLY (Enforced).
- `ISS-RAW-01` (LOW): 14 prior null playerStats raw attempts (Retained in raw, excluded from accepted lineage).
- `ISS-PAGE-01` (LOW): `playerMatches` HTTP 400 unverified pagination (Fallback to matchDetails verified).

---

## 8. Step 01 Acceptance Gate Verdict

- Baseline release integrity: **CONFIRMED**
- Cryptographic checksums: **100% MATCH**
- All 13 historical audit findings: **RECOMPUTED & CONFIRMED**
- 41 coverage anomalies: **REPRODUCED & ROOT CAUSE ISOLATED**
- Deliverables generated:
  - `reports/phase_02b1_remediation/release_v2_integrity_snapshot.json`
  - `reports/phase_02b1_remediation/remediation_issue_tracker.csv`

**Final Step 01 Verdict: PASS**

