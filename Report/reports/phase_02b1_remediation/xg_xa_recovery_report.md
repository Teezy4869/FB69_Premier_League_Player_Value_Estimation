# Phase 2B.1-R Step 06: Historical xG/xA Coverage Recovery Report

**Generated UTC:** 2026-11-03T04:23:46.874321+00:00
**Target Metric Recovery:** Historical Expected Goals (`expected_goals`) & Expected Assists (`expected_assists`)

## 1. Executive Summary & Root Cause Diagnosis

During the Phase 2B.1 acceptance review, 2019/20 xA curated coverage was reported as 0 of 515 players, and xG curated coverage as only 67 of 515 players. Investigation reveals two distinct root causes:
1. **Single-Source Ingestion Filter in Normalizer:** `execution05_acceptance.py` contained an exclusive filter `if r['source_endpoint'] != 'playerStats': continue`. Because the FotMob `playerStats` endpoint did not report `expected_assists` in 2019/20 (515/515 returned null/missing in `statsSection`), zero xA values were curated.
2. **Sparse Historical Coverage at Source:** FotMob only began tracking xG/xA during the 2019/20 season (primarily post-COVID restart). Consequently, even on the league leaderboard (`leagueseasondeepstats`), only 96 players received an xA figure (34 positive, 62 zero), and 54 players received an xG figure. The values represent partial-season totals (e.g. Trent Alexander-Arnold has 0.8 xA and Mohamed Salah has 1.01 xG).

## 2. Fallback Rule & Coverage Recovery

Under the verified reconciliation policy:
- When `playerStats` is `MISSING`, validated observations from `leagueseasondeepstats` are admitted as legitimate historical fallback.
- For 2019/20 `expected_assists`: **96 player observations** are successfully recovered (coverage increases from **0.0%** to **18.64%**).
- For 2019/20 `expected_goals`: **2 additional player observations** (Albian Ajeti: 0.1, Connor Wickham: 0.9) are recovered, increasing xG coverage from **67 (13.01%)** to **69 (13.40%)**.
- In accordance with non-negotiable data engineering principles, the remaining unobserved players are **accurately preserved as MISSING**, without zero-fabrication or synthetic imputation.

## 3. Coverage Matrix Across All Seasons

| Season | Metric | Eligible Players | Pre-Remediation Count | Pre % | Recovered Fallbacks | Post-Remediation Count | Post % |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 2019/2020 | `expected_goals` | 515 | 67 | 13.01% | +2 | **69** | **13.4%** |
| 2020/2021 | `expected_goals` | 524 | 396 | 75.57% | +17 | **413** | **78.82%** |
| 2021/2022 | `expected_goals` | 537 | 403 | 75.05% | +21 | **424** | **78.96%** |
| 2022/2023 | `expected_goals` | 554 | 405 | 73.1% | +23 | **428** | **77.26%** |
| 2023/2024 | `expected_goals` | 570 | 415 | 72.81% | +27 | **442** | **77.54%** |
| 2024/2025 | `expected_goals` | 562 | 403 | 71.71% | +27 | **430** | **76.51%** |
| 2019/2020 | `expected_assists` | 515 | 0 | 0.0% | +96 | **96** | **18.64%** |
| 2020/2021 | `expected_assists` | 524 | 458 | 87.4% | +44 | **502** | **95.8%** |
| 2021/2022 | `expected_assists` | 537 | 468 | 87.15% | +47 | **515** | **95.9%** |
| 2022/2023 | `expected_assists` | 554 | 465 | 83.94% | +63 | **528** | **95.31%** |
| 2023/2024 | `expected_assists` | 570 | 473 | 82.98% | +71 | **544** | **95.44%** |
| 2024/2025 | `expected_assists` | 562 | 482 | 85.77% | +62 | **544** | **96.8%** |

## 4. Controlled Fallback Validation Samples

A total of 99 fallback candidate records were audited across 2019/20 and control seasons. All candidates have verified player IDs, matching season/competition parameters, identical units, and complete raw JSON lineage.

- Deliverable Audit CSV: `reports/phase_02b1_remediation/historical_xg_xa_audit.csv`
- Deliverable Validation CSV: `reports/phase_02b1_remediation/metric_fallback_validation.csv`
- Provisional Parquet Dataset: `data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet`
