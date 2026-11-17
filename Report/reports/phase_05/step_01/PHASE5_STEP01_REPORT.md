# Phase 5 Step 01: Dependencies and Season-Start Previous Value

Date: 2026-11-15. Implements protocol `reports/phase_05/step_00/PHASE5_EVALUATION_PROTOCOL.md`, sections 3 and 4. **No model has been trained.**

## 1. Dependencies

- Installed into `.venv314` only: `scikit-learn==1.9.1` and `lightgbm==4.7.0`. Both are pinned in `requirements.txt`.
- pip also pulled in scipy 1.18.1, joblib 1.6.0, threadpoolctl 3.8.0, narwhals 2.28.0 and cloudpickle 3.1.2. These are not pinned.
- Import check passed: `sklearn.model_selection.StratifiedGroupKFold` imports.

## 2. Season start dates

No new lookup was needed. `configs/phase_03_seasons.yaml` already stores `first_match_date` for every season, marked VERIFIED with an official Premier League source (Phase 3). The script refuses to run if any season is unverified.

| Season | First match |
|---|---|
| 2020/21 | 2020-09-12 |
| 2021/22 | 2021-08-13 |
| 2022/23 | 2022-08-05 |
| 2023/24 | 2023-08-11 |
| 2024/25 | 2024-08-16 |

## 3. Rule and implementation

- Code: `src/phase5/season_start_prev_value.py`.
- Output: `data/phase_05/previous_value/season_start_prev_value_v1/season_start_prev_value.parquet`, plus `manifest.json` (input and output SHA-256, checks).
- Rule `latest_valid_strictly_before_first_match_v1`: the latest usable valuation with `valuation_date < first_match_date`. It reuses the Phase 3 `select_target` with cutoff = first match − 1 day, so usable statuses and same-date conflicts are handled exactly as for the target. Nothing is imputed.
- The release SHA-256 is verified before reading. The release dataset and the valuation history are read-only.

## 4. Tests

`python -I tests/phase5/test_season_start_prev_value.py`: **7 run, 7 passed.**
- 4 synthetic rule tests:
  - a valuation on the first match day is excluded
  - later-only valuations give a missing value
  - a same-date conflict is flagged
  - an invalid value is skipped
- 3 output tests:
  - 2,747 rows, one per player-season
  - invariants hold
  - every value is dated before the season start

## 5. Results on the modeling population

Population: DEF/MID/FWD with a usable target. **2,491 rows.**

| Measure | Old `target_audit_previous_value` | New season-start value |
|---|---:|---:|
| Rows without previous value | 71 | **107** |
| Lost (old present, new missing) | | 43 |
| Gained (old missing, new present) | | 7 |

The 107 missing rows all have reason `ONLY_VALUATIONS_AFTER_CUTOFF`. Their median target is EUR 0.5m, against 15m for rows that have a previous value. So "new" players remain the low-value, often first-valued, group.

Missing by position: DEF 26 / 924, MID 36 / 817, FWD 45 / 750.

| Season | Rows | Missing | Median age at first match (days) | p90 age | Median gap previous → target (days) |
|---|---:|---:|---:|---:|---:|
| 2020/21 | 474 | 27 | 157 | 157 | 344 |
| 2021/22 | 486 | 19 | 66 | 79 | 198 |
| 2022/23 | 503 | 18 | 51 | 84 | 157 |
| 2023/24 | 527 | 33 | 52 | 71 | 182 |
| 2024/25 | 501 | 10 | 81 | 84 | 206 |

## 6. Findings that need owner attention

1. **Pre-season targets: 15 rows.** On these modeling rows the selected target valuation itself predates the season start, so target and previous value are the same valuation. Persistence is exact by construction, and the target carries no in-season valuation. Across all 2,747 release rows the count is 18. The rows are flagged `target_before_season_start` and kept. No decision has been made on them.
2. **2020/21 previous values are the pandemic batch.** The median age of 157 days in 2020/21 equals the gap from the 2020-04-08 re-valuation batch (Phase 3 ISS-19) to the delayed 2020-09-12 start. Those previous values reflect the COVID-era market reset, not a normal pre-season valuation.
3. **The gap to the target is now longer** (median 157–344 days), as expected: the previous value no longer overlaps the season.
4. **Stale previous values:** 10 values are more than one year older than the season start. Exact ages are kept and nothing is excluded.

## 7. Other recounts on the modeling population

- Identity sensitivity subset (P4-B01 mask from `src/phase4/bivariate.py`): **454** of 2,491 rows. The figure 533 covers all 2,745 mapped rows.
- `m_big_chances_created` null rate: **38.6%**. The figure of about 44% covered all positions.
- Rows with null or zero `m_minutes_played`: **0**, so no per-90 feature becomes null because of zero minutes.

## 8. Still open

- Finding 1 **decided by the owner (2026-11-15): keep the 15 rows in the model and report their error separately** using the `target_before_season_start` flag. Finding 2 **accepted by the owner (2026-11-15) as a documented limitation**: 2020/21 previous values are used like other seasons, and the final report must state that they come from the COVID re-valuation batch (season error is already reported separately).
- ISS-01: owner-labelled identity sample, not started.
- K, repeats, bins, seeds and the hyperparameter search space are not yet fixed in a config file.
- Not done in this step: replacing `target_audit_previous_value` in any modeling input, feature derivation, and any training.
