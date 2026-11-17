# Phase 2B.1-R Step 07: Player Participation Remediation & Appearance Resolution Report

**Document:** `appearance_resolution_report.md`  
**Phase:** Phase 2B.1-R (Post-Collection Remediation) — Step 07  
**Project:** FB69 — Football Player Market Value Estimation  
**Execution Date:** 2026-11-03  
**Status:** **PASS — ALL ACCEPTANCE CRITERIA SATISFIED**

---

## 1. Executive Summary

Phase 2B.1-R Step 07 addresses the last remaining core data-quality limitation of the FotMob historical collection: the presence of **16,314 player-match participation records marked `UNKNOWN`**, which had previously prevented **586 Player–Season records** from achieving definitive participation classification.

By implementing a robust, schema-aware multi-source participation parser (`src/collection/remediation_substitutions.py`) that cross-validates lineup configurations, match event timelines (`matchFacts.events`), substitution swap entries, and per-match performance statistics (`content.playerStats`), all 16,314 unresolved bench records have been successfully audited and resolved to **`UNUSED_SUBSTITUTE`** under verifiable **`COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`**.

### Key Outcomes:
1. **Match-Level Participation Resolution:**
   - `UNKNOWN` player-match records reduced from **16,314 to 0 (100.0% reduction)**.
   - Fully resolved matches increased from **732 to 2,280 (100.0% of all 2,280 completed EPL matches)**.
   - `STARTED` (50,160) and `SUBSTITUTED_ON` (15,628) counts remain 100% stable with zero false appearances created.
   - `UNUSED_SUBSTITUTE` count updated from **7,290 to 23,604**.
2. **Player–Season Population Segmentation:**
   - **`CONFIRMED_APPEARED`:** Exactly **3,262** player-seasons (100% preserved, 0 lost, 0 falsely added).
   - **`CONFIRMED_NON_APPEARED`:** Increased from **204 to 790** ($204 + 586 = 790$).
   - **`UNVERIFIED`:** Reduced from **586 to 0**.
   - **`CONFLICTING`:** Exactly **0**.
   - **Total Population:** Exactly **4,052** player-seasons maintained in perfect referential balance.
3. **HTTP Requests Issued:** **0 live network requests** (all evidence derived from verified local raw captures).

---

## 2. Baseline Verification vs Remediated Results

### 2.1 Player–Match Appearance Table Comparison

| Metric | Baseline Release v2 | Remediated Provisional v3 | Absolute Change | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Total Player–Match Records** | 89,392 | 89,392 | 0 | Exact relational balance maintained |
| **`STARTED` Appearances** | 50,160 | 50,160 | 0 | $380 \text{ matches} \times 22 \text{ starters} \times 6 \text{ seasons}$ |
| **`SUBSTITUTED_ON` Appearances** | 15,628 | 15,628 | 0 | All confirmed via lineup subIn & matchFacts swaps |
| **`UNUSED_SUBSTITUTE` Records** | 7,290 | **23,604** | **+16,314** | Bench substitutes verified with complete event feeds |
| **`UNKNOWN` Records** | 16,314 | **0** | **-16,314** | Complete elimination of unspecified bench status |
| **`CONFLICTING` Records** | 0 | 0 | 0 | Zero contradictory records |
| **Fully Resolved Matches** | 732 / 2,280 | **2,280 / 2,280** | **+1,548** | 100% of completed fixtures fully resolved |

### 2.2 Seasonal Breakdown of Player–Match Appearances

| Season | Completed Matches | Total PMA Records | Started | Substituted On | Unused Substitute | Unknown (Baseline) | Unknown (Remediated) | Resolved Ratio (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2019/20** | 380 | 14,034 | 8,360 | 2,254 | 3,420 | 46 | **0** | **100.0%** |
| **2020/21** | 380 | 14,643 | 8,360 | 2,033 | 4,250 | 3,449 | **0** | **100.0%** |
| **2021/22** | 380 | 15,162 | 8,360 | 2,125 | 4,677 | 3,401 | **0** | **100.0%** |
| **2022/23** | 380 | 15,185 | 8,360 | 2,985 | 3,840 | 2,561 | **0** | **100.0%** |
| **2023/24** | 380 | 15,180 | 8,360 | 3,024 | 3,796 | 3,236 | **0** | **100.0%** |
| **2024/25** | 380 | 15,188 | 8,360 | 3,207 | 3,621 | 3,621 | **0** | **100.0%** |
| **TOTAL** | **2,280** | **89,392** | **50,160** | **15,628** | **23,604** | **16,314** | **0** | **100.0%** |

---

## 3. Player–Season Population Reconstruction

### 3.1 Population Reconciliation Table

| Season Label | Season ID | Baseline Appeared | Remediated Appeared | Baseline Unverified | Remediated Unverified | Baseline Non-Appeared | Remediated Non-Appeared | Total Player–Seasons |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2019/2020** | 14022 | 515 | 515 | 10 | **0** | 89 | **99** | 614 |
| **2020/2021** | 15382 | 524 | 524 | 99 | **0** | 18 | **117** | 641 |
| **2021/2022** | 16390 | 537 | 537 | 107 | **0** | 35 | **142** | 679 |
| **2022/2023** | 17664 | 554 | 554 | 103 | **0** | 42 | **145** | 699 |
| **2023/2024** | 20720 | 570 | 570 | 144 | **0** | 20 | **164** | 734 |
| **2024/2025** | 23685 | 562 | 562 | 123 | **0** | 0 | **123** | 685 |
| **TOTAL** | **ALL** | **3,262** | **3,262** | **586** | **0** | **204** | **790** | **4,052** |

### 3.2 Population Invariants Satisfied:
1. **Conservation of Appeared Population:** Exactly 3,262 player-seasons have $\ge 1$ confirmed on-pitch appearance (`started_match_count + sub_in_match_count > 0`). Zero non-appeared players were promoted to appeared.
2. **Transition of Unverified Population:** All 586 unverified player-seasons transitioned to `CONFIRMED_NON_APPEARED` because their matchday squad selections were conclusively verified as unused substitutes with zero minutes played across the full 380-match campaign.
3. **Multi-Club Identity Preservation:** All 61 confirmed multi-club appeared player-seasons retain distinct appearances summed across clubs while maintaining single Player–Season rows (zero duplicate keys).

---

## 4. Evidence Classification Rules & Implementation Details

The implementation in `src/collection/remediation_substitutions.py` strictly follows the mandated 5-class evidence taxonomy:

1. **`DIRECT_STARTER_EVIDENCE`:**
   - Criteria: Matchday starting lineup verified in `lineup.[home/away]Team.starters` (length 11).
   - Transition: `STARTED` with `validation_status = 'CONFIRMED'`.
2. **`DIRECT_SUBSTITUTION_ON_EVIDENCE`:**
   - Criteria: Bench listing with `performance.substitutionEvents` containing `subIn` OR listed as `swap[0]` in `matchFacts.events`.
   - Transition: `SUBSTITUTED_ON` with `validation_status = 'CONFIRMED'`.
3. **`COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`:**
   - Criteria:
     - Match lineup is standard with 11 starters for both teams.
     - `matchFacts.events` timeline is present and non-empty.
     - All substitution events have complete swaps with valid player IDs.
     - Player is not present in any `subIn` swap.
     - Player has 0 match statistics in `content.playerStats`.
   - Transition: `UNUSED_SUBSTITUTE` with `validation_status = 'NOT_APPEARED'`.
4. **`INSUFFICIENT_EVIDENCE`:**
   - Criteria: Missing match events, truncated feed, or non-standard lineup.
   - Status: Retained as `UNKNOWN` (applied to 0 matches in this audit).
5. **`CONFLICTING_EVIDENCE`:**
   - Criteria: Incompatible lineup listings or stats present without substitution.
   - Status: Retained as `CONFLICTING` (applied to 0 matches in this audit).

---

## 5. Artifacts and Datasets Generated

The execution generated all required versioned provisional datasets and reports:

- **Audit Trail:** [reports/phase_02b1_remediation/appearance_resolution_audit.csv](file:///D:/PTIT/Hoc_may/FB69/reports/phase_02b1_remediation/appearance_resolution_audit.csv) (16,314 rows).
- **Appearance Coverage Matrix:** [reports/phase_02b1_remediation/appearance_coverage_v3.csv](file:///D:/PTIT/Hoc_may/FB69/reports/phase_02b1_remediation/appearance_coverage_v3.csv) (6 seasons).
- **Population Reconciliation Report:** [reports/phase_02b1_remediation/population_reconciliation_v3.csv](file:///D:/PTIT/Hoc_may/FB69/reports/phase_02b1_remediation/population_reconciliation_v3.csv) (6 seasons + total).
- **Schema Audit Technical Document:** [reports/phase_02b1_remediation/substitution_schema_audit.md](file:///D:/PTIT/Hoc_may/FB69/reports/phase_02b1_remediation/substitution_schema_audit.md).
- **Provisional Parquet Datasets:** `data/phase_02b1/remediation/`
  - `player_match_appearances_provisional.parquet` (89,392 rows $\times$ 21 columns).
  - `confirmed_appeared_player_seasons_v3.parquet` (3,262 rows $\times$ 20 columns).
  - `unverified_player_seasons_v3.parquet` (0 rows $\times$ 20 columns).
  - `non_appeared_player_seasons_v3.parquet` (790 rows $\times$ 20 columns).
  - `complete_player_season_classification_v3.parquet` (4,052 rows $\times$ 20 columns).
  - `substitution_evidence_registry.parquet` (89,392 rows $\times$ 11 columns).

---

## 6. Downstream Impact Notice

> [!IMPORTANT]
> **Mandatory Action for Step 08 / Release v3 Packaging:**
> The feature coverage ratios originally computed in Step 02 (`cross_season_feature_coverage_v3.csv`) used the Step 03 confirmed appeared population (3,262). Because Step 07 strictly maintained the exact 3,262 confirmed appeared player-season population, the overall coverage denominators remain fundamentally sound. However, the final Release v3 metadata generation in Step 08 must verify and freeze all coverage metrics against these final provisional tables.

