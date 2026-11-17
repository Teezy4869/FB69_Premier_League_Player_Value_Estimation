# Phase 2B.1-R Step 05: Metric Conflict Investigation & Resolution Report

**Generated UTC:** 2026-11-03T04:23:54.708129+00:00
**Total Conflicts Investigated:** 575 records across 6 seasons
**Resolved via Rounding Tolerance:** 444 (77.2%)
**Reconciled via Preferred Source Policy:** 95 (16.5%)
**Preserved as Conflicting / Null:** 36 (6.3%)

## 1. Executive Summary & Root Cause Distribution

Every single one of the 575 reported metric conflicts between `leagueseasondeepstats` and `playerStats` has been audited against raw JSON responses, capture timestamps, and mathematical precision boundaries.

### Taxonomy Distribution:
- **`ROUNDING_DIFFERENCE` (444 conflicts, 77.2%):** Arises from FotMob's leaderboard displaying numbers formatted to 1 decimal place with round-down/truncation on `.x5` boundaries (e.g. `0.45` displayed as `0.4`), whereas `playerStats` retains the exact 2-decimal or float representation. Also covers 1-minute differences in `minutes_played` over 38-match seasons.
- **`AGGREGATION_MISMATCH` (59 conflicts, 10.3%):** Arises in `rating` (58 cases) and `accurate_passes_per90` (1 case) where seasonal averaging weighting or per-match minute aggregation formulas differ slightly between the leaderboard engine and the profile summary.
- **`SOURCE_REVISION` (54 conflicts, 9.4%):** Arises where post-match event reviews, shot xG recalculations, or official lineup substitution time corrections occurred between the capture of `leagueseasondeepstats` and the later capture of `playerStats` (~10 hours later).
- **`DEFINITION_MISMATCH` (18 conflicts, 3.1%):** Specifically affects `goals_prevented` (18 cases), where the leaderboard endpoint `_goals_prevented` includes penalties differently from the playerStats profile definition.

## 2. Conflicts Breakdown by Metric

| Canonical Metric | Conflict Count | Primary Root Cause | Resolution Action | Curated Value |
| :--- | :---: | :--- | :--- | :--- |
| `rating` | 282 | ROUNDING_DIFFERENCE / AGGREGATION_MISMATCH | RESOLVED_ROUNDING_TOLERANCE / PREFERRED_SOURCE | playerStats rating |
| `expected_goals` | 117 | ROUNDING_DIFFERENCE / SOURCE_REVISION | RESOLVED_ROUNDING_TOLERANCE / PREFERRED_SOURCE | playerStats xG |
| `expected_assists` | 76 | ROUNDING_DIFFERENCE (exact diff=0.05) | RESOLVED_ROUNDING_TOLERANCE | playerStats xA (2 decimals) |
| `minutes_played` | 60 | ROUNDING_DIFFERENCE (exact diff=1 min) | RESOLVED_ROUNDING_TOLERANCE | playerStats match sum |
| `goals_prevented` | 24 | DEFINITION_MISMATCH / ROUNDING | PRESERVED_UNRESOLVED_NULL | null (retained) |
| `accurate_passes_per90` | 12 | ROUNDING_DIFFERENCE (diff<=0.07) | RESOLVED_ROUNDING_TOLERANCE | playerStats per90 |
| `interceptions_per90` | 1 | ROUNDING_DIFFERENCE | RESOLVED_ROUNDING_TOLERANCE | playerStats per90 |
| `recoveries_per90` | 1 | ROUNDING_DIFFERENCE | RESOLVED_ROUNDING_TOLERANCE | playerStats per90 |
| `shots_per90` | 1 | ROUNDING_DIFFERENCE | RESOLVED_ROUNDING_TOLERANCE | playerStats per90 |
| `tackles_per90` | 1 | ROUNDING_DIFFERENCE | RESOLVED_ROUNDING_TOLERANCE | playerStats per90 |

## 3. Seasonal Conflict Distribution

| Season Label | Total Conflicts | Rounding Difference | Aggregation Mismatch | Source Revision | Definition Mismatch |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **2019/2020** | 22 | 22 | 0 | 0 | 0 |
| **2020/2021** | 36 | 34 | 0 | 1 | 1 |
| **2021/2022** | 49 | 48 | 0 | 1 | 0 |
| **2022/2023** | 60 | 51 | 0 | 9 | 0 |
| **2023/2024** | 46 | 38 | 0 | 6 | 2 |
| **2024/2025** | 362 | 251 | 59 | 37 | 15 |
| **TOTAL** | **575** | **444** | **59** | **54** | **18** |

## 4. Evidence-Based Reconciliation Rules

1. **Display Rounding Tolerance Rule:** When `abs(board_value - player_stats_value) <= rounding_tolerance` (0.051 for rating/xG/xA; 1.01 for minutes_played), the conflict is reclassified as `RESOLVED_ROUNDING_TOLERANCE`. The higher-precision `playerStats` observation is curated as `OBSERVED`.
2. **Preferred Source Policy:** Where raw captures reflect post-match revisions (`SOURCE_REVISION`) with differences corroborated by official match events, `playerStats` is preferred as the later post-review state.
3. **Definition Conflict Preservation:** Where endpoints calculate different concepts (`_goals_prevented` vs `goals_prevented`), the conflict cannot be resolved by assumption. The value is strictly preserved as `CONFLICTING` / null in curated wide tables.
