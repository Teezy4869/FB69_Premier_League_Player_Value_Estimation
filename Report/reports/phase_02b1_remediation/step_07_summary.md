# Phase 2B.1-R Step 07 Summary: Unknown Substitution & Appearance Resolution

**Document:** `step_07_summary.md`  
**Phase:** Phase 2B.1-R (Post-Collection Remediation) — Step 07  
**Project:** FB69 — Football Player Market Value Estimation  
**Execution Timestamp (UTC):** 2026-11-03T04:42:23Z  
**Verdict:** **PASS**

---

## 1. Objectives Achieved

1. **Root Cause Identification:** Discovered that the 16,314 `UNKNOWN` substitute records resulted from FotMob updating its API from emitting `performance.substitutionEvents = []` in 2019/20 to returning `performance = {}` from 2020/21 onwards for bench substitutes who did not play.
2. **Schema-Aware Remediation Pipeline:** Implemented `src/collection/remediation_substitutions.py`, cross-referencing lineup arrays, match facts substitution swap events, card events, and player match statistics.
3. **Deterministic Reprocessing:** Reprocessed all 89,392 player-match records across all 2,280 completed matches in bounded local batches.
4. **Complete Elimination of Participation Uncertainty:** Reduced `UNKNOWN` records from 16,314 to 0 (100% resolution under `COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`).
5. **Population Boundary Integrity:** Preserved exactly 3,262 confirmed appeared player-seasons, while transitioning 586 unverified records to confirmed non-appeared (total 790), satisfying all population balance equations.
6. **Zero Recrawling:** Issued 0 live HTTP requests, preserving raw capture integrity.

---

## 2. Quantitative Summary

| Dimension | Baseline Count | Remediated Count | Net Change |
| :--- | :---: | :---: | :---: |
| **Total Completed Matches** | 2,280 | 2,280 | 0 |
| **Fully Resolved Matches** | 732 | **2,280** | **+1,548 (+211.5%)** |
| **Total Player–Match Records** | 89,392 | 89,392 | 0 |
| **`STARTED` Matches** | 50,160 | 50,160 | 0 |
| **`SUBSTITUTED_ON` Matches** | 15,628 | 15,628 | 0 |
| **`UNUSED_SUBSTITUTE` Matches** | 7,290 | **23,604** | **+16,314** |
| **`UNKNOWN` Matches** | 16,314 | **0** | **-16,314 (-100.0%)** |
| **`CONFLICTING` Matches** | 0 | **0** | 0 |
| **Confirmed Appeared Player–Seasons** | 3,262 | **3,262** | **0 (100% Preserved)** |
| **Unverified Player–Seasons** | 586 | **0** | **-586 (-100.0%)** |
| **Confirmed Non-Appeared Player–Seasons** | 204 | **790** | **+586 (+287.3%)** |
| **Live Network Requests** | - | **0** | 0 |

---

## 3. Key Deliverables

- `reports/phase_02b1_remediation/appearance_resolution_audit.csv`
- `reports/phase_02b1_remediation/appearance_coverage_v3.csv`
- `reports/phase_02b1_remediation/population_reconciliation_v3.csv`
- `reports/phase_02b1_remediation/substitution_schema_audit.md`
- `reports/phase_02b1_remediation/appearance_resolution_report.md`
- `reports/phase_02b1_remediation/step_07_summary.md`
- `data/phase_02b1/remediation/player_match_appearances_provisional.parquet`
- `data/phase_02b1/remediation/confirmed_appeared_player_seasons_v3.parquet`
- `data/phase_02b1/remediation/unverified_player_seasons_v3.parquet`
- `data/phase_02b1/remediation/non_appeared_player_seasons_v3.parquet`
- `data/phase_02b1/remediation/complete_player_season_classification_v3.parquet`
- `data/phase_02b1/remediation/substitution_evidence_registry.parquet`

