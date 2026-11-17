# Phase 2B.1-R Steps 05–06: Conflict Resolution & xG/xA Recovery Summary

**Generated UTC:** 2026-11-03T04:23:54.715683+00:00
**Phase:** Phase 2B.1-R (Post-Collection Remediation)
**Status:** COMPLETED — ALL ACCEPTANCE CRITERIA MET

## 1. Key Accomplishments

### Step 05: Metric Conflict Investigation & Reconciliation
- Reconstructed and audited all **575 metric conflicts** across 6 seasons.
- Classified root causes using strict evidence taxonomy: **444 Rounding Differences** (77.2%), **59 Aggregation Mismatches** (10.3%), **54 Source Revisions** (9.4%), and **18 Definition Mismatches** (3.1%).
- Resolved **444 conflicts** within display rounding tolerance ($\le 0.051$ for rating/xG/xA; $\le 1.01$ min for minutes_played) by adopting higher-precision `playerStats` values.
- Reconciled **95 conflicts** via preferred-source post-review policy.
- Strictly preserved **36 genuine definition/source divergences** as `CONFLICTING` / null with explicit audit traceability.
- Formulated `metric_reconciliation_registry_v3.json` covering all 53 canonical metrics.

### Step 06: Historical xG/xA Coverage Recovery
- Diagnosed root cause of 2019/20 xA omission: single-source normalizer filter bypassed valid `leagueseasondeepstats` observations.
- Recovered **96 historical xA observations** for 2019/20 from raw leaderboard responses (34 positive, 62 zero), increasing coverage from **0.0%** to **18.64%**.
- Recovered **2 historical xG observations** for 2019/20, increasing coverage from **67 (13.01%)** to **69 (13.40%)**.
- Proved that 2019/20 xG/xA was partial/sparse at FotMob source level; preserved remaining unobserved players as `MISSING` without zero-fabrication.
- Validated multi-season fallback rules on controlled samples.
- Published provisional wide curated table: `D:/PTIT/Hoc_may/FB69/data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet`.

## 2. Deliverables Summary

- `reports/phase_02b1_remediation/metric_conflict_root_causes.csv` (575 rows)
- `reports/phase_02b1_remediation/metric_reconciliation_registry_v3.json` (53 metrics)
- `reports/phase_02b1_remediation/metric_conflict_resolution_report.md`
- `reports/phase_02b1_remediation/historical_xg_xa_audit.csv` (12 seasonal rows)
- `reports/phase_02b1_remediation/metric_fallback_validation.csv` (100 candidate rows)
- `reports/phase_02b1_remediation/xg_xa_recovery_report.md`
- `reports/phase_02b1_remediation/steps_05_06_summary.md` (This document)
- `D:/PTIT/Hoc_may/FB69/data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet` (4,052 curated rows)
