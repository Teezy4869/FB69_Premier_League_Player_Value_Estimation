# Step 4 Independent Audit (Step 4.1)

Date: 2026-11-05. Results: `evidence/step_04_1_audit_results.json`.

**Conclusion:** Step 4's dataset reproduces exactly, and every reported number reconciles. What it missed was interpretation: three findings change how its targets should be understood.

**Independence:** the audit code imports nothing from Step 4 and recomputes targets from the original CSV. It was written by the same agent as Step 4, so it's independent in method, not in authorship.

## 1. Reproduction

| Item | Check | Result |
|---|---|---|
| Input checksums | All files listed in `target_manifest.json` | 0 mismatches |
| Output checksums | Target and conflict files | 0 mismatches |
| Code checksum | `season_targets.py` | 0 mismatches |
| Season cutoffs | Config vs target vs last FotMob match | All 6 agree |
| Grain | 3,262 rows, 3,262 keys, 1,343 players | Correct |
| Population | Against the frozen Confirmed table | 0 missing, 0 extra |
| Crosswalk version | `matching_v2_1` on every row | Correct |
| Rule version | `latest_valid_on_or_before_season_end_v1` on every row | Correct |
| Selection after cutoff | | 0 |
| Multiple same-day records for a selected date | | 0 |

**SQL recomputation against the target table, 3,262 rows:**

| Compared field | Differences |
|---|---:|
| Selected date | 0 |
| Market value | 0 |
| Age in days | 0 |
| Source row (lineage) | 0 |
| TM ID | 0 |
| Crosswalk status | 0 |

## 2. Reported numbers, from actual files

| Reported in Step 4 | Reported | From files |
|---|---:|---:|
| Usable targets | 3,195 | 3,195 |
| Usable share | 97.95% | 97.946% |
| `VALID` | 1,171 | 1,171 |
| `STALE_TARGET` | 2,024 | 2,024 |
| `TARGET_MISSING` | 67 | 67 |
| Only after cutoff / no history / no identity | 51 / 13 / 3 | 51 / 13 / 3 |
| Over 90 days | 63.35% | 63.349% |
| Appearances after valuation | 41.09% | 41.09% (26,966 of 65,632) |
| League games after valuation | 41.52% | 41.52% |
| 2020-04-08 share of 2019/20 | 491 of 498 | 491 of 498 |
| Season status and age tables | All | All match |

**No numeric discrepancy.**

## 3. Corrections to Step 4's interpretation

| # | Step 4 said or implied | What this audit found | Impact |
|---|---|---|---|
| 1 | 0 same-date conflicts, with handling in place | The source removes same-day duplicates before publishing, so conflicts can't appear in this data | "Handled" is true, but the check can't detect upstream conflicts |
| 2 | Missing and invalid checks are clean | Upstream also drops rows with no value or no date | Gaps in Transfermarkt's history can't be seen here |
| 3 | 2019/20 "may" be a pandemic revaluation; not verified | Values follow a sharp 0.8 and 0.9 birth-year rule on that date, matching press reports | A level shift in nearly all 2019/20 targets |
| 4 | 2019/20 median age is 109 days | True for the selected date; 229 days from the last earlier valuation | Step 4 understates how old that information is |
| 5 | xG/xA windows unverified | 2020/21 on verified as full EPL season; **2019/20 is 4 of 380 matches** | 2019/20 xG and xA aren't comparable |
| 6 | Full-season features partly follow the valuation | Quantified per player: 240 with all games after, 433 all before | Supports the objective decision |

## 4. Findings in detail

- 2020-04-08: `VALUATION_DATE_CONCENTRATION_AUDIT.md`
- Features and research objective: `TEMPORAL_ALIGNMENT_AUDIT.md`
- Thresholds: `STALENESS_SENSITIVITY_REPORT.md`
- Identity: `TARGET_IDENTITY_RELIABILITY_AUDIT.md`
- Tests: `TEST_SAFETY_VERIFICATION.md`
- Decision: `STEP_04_1_FINAL_DECISION.md`

## 5. Files written by this audit

Only the new audit folder and three scripts: `step4_1_audit.py`, `step4_1_followups.py`, `step4_1_test_safety.py`. The test wrapper also gained an optional output folder, so this run wouldn't overwrite earlier evidence. The target dataset and all source data are untouched.
