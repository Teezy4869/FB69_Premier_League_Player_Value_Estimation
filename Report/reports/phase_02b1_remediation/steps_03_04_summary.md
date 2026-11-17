# Phase 2B.1-R Steps 03–04: Population Segmentation & Legacy Gate Reconciliation Summary

**Phase:** Phase 2B.1-R (Post-Collection Remediation)  
**Steps:** 03 (Population Segmentation & Evidence Audit) & 04 (Legacy Quality Gate Repair & Manifest Migration)  
**Workspace:** `D:\PTIT\Hoc_may\FB69`  
**Execution Date:** 2026-11-03  
**Status:** COMPLETED — ALL ACCEPTANCE CRITERIA MET

---

## 1. Executive Summary

Phase 2B.1-R Steps 03 and 04 resolve two critical data architecture blockers identified during the Phase 2B.1 acceptance audit:
1. **Ambiguous Population Boundaries (Step 03):** Replaced monolithic/unverified population assumptions with an evidence-grounded segmentation across all **4,052 Player–Season** records. Separated players into mutually exclusive, exhaustive categories at the distinct `Player–Season` grain, audited all **16,314 unresolved substitute records**, preserved multi-club integrity for **61 confirmed multi-club player-seasons** (83 total club associations), and published versioned Parquet tables and audit CSVs.
2. **Manifest Lifecycle Inconsistencies (Step 04):** Reconciled **12 legacy Quality Gate tasks** stuck in `PLANNED` (`NORMALIZATION_GATE` and `SEASON_ACCEPTANCE_GATE` across 6 seasons). Traced their abandonment to early Phase 2A/2B.0 per-season schemas that were superseded by Phase 2B.1 Execution 04/05 multi-season architecture, executed formal state transitions to `SUPERSEDED` with full lineage linking to `execution05_acceptance.py` and season reports, validated DAG dependency integrity, and created versioned manifest `collection_manifest_v2b1r.sqlite`.

---

## 2. Step 03: Population Segmentation Results

### 2.1 Entity Definitions & Category Contracts
- **Player:** Unique FotMob Player ID (`player_id`).
- **Player–Season:** Grain `(season_id, player_id)`. Strictly unique across all datasets (0 duplicate keys).
- **Player–Team–Season:** Association during a season `(season_id, player_id, team_id)`. Multi-club players have multiple relations in `player_team_seasons` but exactly one row at the Player–Season grain.
- **Confirmed Appearance:** Actual match participation verified by lineup role `STARTER` or substitution event `SUBSTITUTED_ON` in an eligible completed Premier League fixture.
- **Unused Substitute:** Player named in matchday bench whose raw capture explicitly contains empty substitution events `substitutionEvents: []`.
- **Unobserved Bench Status:** Player named in matchday bench whose performance block is `{}` or lacks substitution events, where match event logs confirm other players completed all substitutions.

### 2.2 Population Segmentation Matrix
Across all 6 historical Premier League seasons (2019/20 through 2024/25), all **4,052 Player–Seasons** are partitioned into four mutually exclusive categories:

| Season Label | Season ID | Total Player–Seasons | Confirmed Appeared | Unverified | Confirmed Non-Appeared | Conflicting | Multi-Club (All) | Confirmed Multi-Club | Total Match Squads | Unresolved Obs | Unused Obs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2019/2020** | 14022 | 614 | 515 | 10 | 89 | 0 | 7 | 7 | 14,034 | 46 | 3,374 |
| **2020/2021** | 15382 | 641 | 524 | 99 | 18 | 0 | 11 | 11 | 14,643 | 3,449 | 801 |
| **2021/2022** | 16390 | 679 | 537 | 107 | 35 | 0 | 12 | 12 | 15,162 | 3,401 | 1,276 |
| **2022/2023** | 17664 | 699 | 554 | 103 | 42 | 0 | 24 | 21 | 15,185 | 2,561 | 1,279 |
| **2023/2024** | 20720 | 734 | 570 | 144 | 20 | 0 | 12 | 12 | 15,180 | 3,236 | 560 |
| **2024/2025** | 23685 | 685 | 562 | 123 | 0 | 0 | 17 | 17 | 15,188 | 3,621 | 0 |
| **TOTAL** | **ALL** | **4,052** | **3,262** | **586** | **204** | **0** | **83** | **80** | **89,392** | **16,314** | **7,290** |

### 2.3 Mathematical Balance & Verification
1. **Total Completeness:** $3,262 \text{ (Appeared)} + 586 \text{ (Unverified)} + 204 \text{ (Non-Appeared)} + 0 \text{ (Conflicting)} = 4,052$ Player–Seasons.
2. **Match Appearance Balance:** Exactly 89,392 match participation records across 2,280 completed fixtures:
   $$\text{Total Matchday Records} = 50,160 \text{ (Started)} + 15,628 \text{ (Sub-In)} + 16,314 \text{ (Unresolved)} + 7,290 \text{ (Unused)} = 89,392$$
3. **Multi-Club Players:** Exactly 61 player-seasons have confirmed appearances for $>1$ club (e.g., Minamino in 2020/21: 9 apps for Liverpool, 10 for Southampton; Lingard in 2020/21: 16 apps for West Ham; Ings in 2022/23: 18 apps for Aston Villa, 8 for West Ham). Exactly 83 player-seasons had $>1$ club association in squad records. All retain a single deduplicated Player–Season record with summed appearances.
4. **Non-Appeared Player Justification:** All 204 players in `CONFIRMED_NON_APPEARED` (e.g. Michel Vorm, David Button, Heurelho Gomes) were named only as unused substitutes with verified `substitutionEvents: []` across their listed matches, and in all 380 completed fixtures of the target season have 0 starts and 0 sub-ins. Because all 380 fixtures have complete verified lineups, non-appearance is mathematically proven.
5. **Audit of 16,314 Unresolved Substitute Records:**
   - 100% of 16,314 records across 1,548 matches were classified as `UNOBSERVED_BENCH_STATUS`.
   - In all 1,548 matches, match event logs (`matchFacts.events`) were present and complete; all official substitutions were verified for other players.
   - 0 records were `MISSING_MATCH_EVENT_LOG`.
   - 0 records were `UNPARSED_SUBSTITUTION_EVENT`.
   - FotMob changed its API response format after 2019/20: unused substitutes no longer received an explicit empty array `[]`, but an empty performance dictionary `{}`. Because affirmative proof of non-entry is absent, these records cannot be converted to `FALSE` and are transparently preserved as `UNVERIFIED`.

---

## 3. Step 04: Legacy Quality Gate Repair Results

### 3.1 Legacy Gate Inventory & Root Cause
In Phase 2B.1 Execution 01, 12 tasks were seeded in `collection_manifest.sqlite`:
- 6 tasks of `resource_type == 'NORMALIZATION_GATE'` (Stage F)
- 6 tasks of `resource_type == 'SEASON_ACCEPTANCE_GATE'` (Stage G)

**Root Cause of Abandonment:**
The original runner (`full_orchestrator.py` invoking `validate_full_season()`) required 7 per-season Parquet tables in `data/phase_02b1/normalized/{season}/` and strictly failed if `unknown_match_links > 0`. When Phase 2B.1 modernized to a 10-table multi-season architecture with documented `UNKNOWN` substitute tracking, `execution05_acceptance.py` was introduced as the replacement audit engine. The 12 legacy tasks were left in `PLANNED` state without a formal lifecycle transition.

### 3.2 State Transition & DAG Integrity
- **Transition:** Every one of the 12 tasks was migrated from `PLANNED` to `SUPERSEDED`.
- **Predecessor Verification:** All 4 Stage A–D predecessors (`MATCH_INDEX_GATE`, `POPULATION_GATE`, `HISTORICAL_MEMBERSHIP_GATE`, `SEASON_STATS_GATE`) were verified in `VALIDATED` state across all 6 seasons.
- **Successor Impact:** `NORMALIZATION_GATE` was depended on only by `SEASON_ACCEPTANCE_GATE`. `SEASON_ACCEPTANCE_GATE` has 0 downstream dependents. No published tables or downstream tasks are blocked.
- **Metadata & Lineage:** Updated `context_json` with migration rationale, replacement mechanism (`src/collection/execution05_acceptance.py`), checkpoint pointer (`reports/phase_02b1/execution05_checkpoint.json`), season acceptance reports, and UTC timestamps.
- **Task Event Audit:** 12 events inserted into `task_events` recording old state `PLANNED`, new state `SUPERSEDED`, and audit note.
- **Idempotency:** Re-running `remediation_manifest.py` verifies 0 remaining `PLANNED` tasks and maintains consistent state.

---

## 4. Deliverables Manifest

### Data Files (Step 03)
1. `data/phase_02b1/remediation/complete_player_season_classification.parquet` (4,052 rows, 327,640 bytes)
2. `data/phase_02b1/remediation/confirmed_appeared_player_seasons.parquet` (3,262 rows, 293,626 bytes)
3. `data/phase_02b1/remediation/unverified_player_seasons.parquet` (586 rows, 57,197 bytes)
4. `data/phase_02b1/remediation/non_appeared_player_seasons.parquet` (204 rows, 25,714 bytes)

### Report Files (Steps 03 & 04)
1. `reports/phase_02b1_remediation/population_segmentation_report.csv` (840 bytes)
2. `reports/phase_02b1_remediation/population_evidence_audit.csv` (16,314 rows, 5,392,859 bytes)
3. `reports/phase_02b1_remediation/legacy_gate_migration_report.md` (4,673 bytes)
4. `reports/phase_02b1_remediation/quality_gate_evidence_registry.csv` (6,131 bytes)
5. `reports/phase_02b1_remediation/steps_03_04_summary.md` (This document)

### Versioned Manifests (Step 04)
1. `data/phase_02b1/manifests/collection_manifest_v2b1r.sqlite` (19,689,472 bytes, 0 PLANNED tasks, 12 SUPERSEDED)
2. `data/phase_02b1/collection_manifest_v2b1r.sqlite` (19,689,472 bytes)
3. `data/phase_02b1/collection_manifest.sqlite` (19,689,472 bytes, remediated working manifest)
*(Baseline release v2 manifest `data/releases/fotmob_epl_2019_2025_v2/manifests/collection_manifest.sqlite` remains 100% unaltered)*

