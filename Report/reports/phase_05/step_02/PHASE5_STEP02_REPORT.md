# Phase 5 Step 02: Model Input Table and Evaluation Config

Date: 2026-11-15. **No model has been trained.**

## Outputs

| Item | Path |
|---|---|
| Config (fixed before any result) | `configs/phase_05_model.yaml` (`phase5_model_v1`) |
| Code | `src/phase5/features.py` |
| Model input | `data/phase_05/features/model_input_v1/model_input.parquet` and `manifest.json` (input and output SHA-256, checks) |
| Tests | `tests/phase5/test_features.py` |

## Config choices proposed by Claude (not separately discussed)

| Choice | Value |
|---|---|
| Target scale | Natural log. exp(MAE) is the typical ratio error |
| Primary CV | StratifiedGroupKFold, 5 splits × 5 repeats (seeds 0–4), 5 quantile bins of log target |
| Forward chaining | Test seasons 2021/22–2024/25, each trained on all earlier seasons |
| Nested tuning | Inner GroupKFold with 3 splits. Grid of 8 configurations: `n_estimators` {200, 500}, `num_leaves` {15, 31}, `min_child_samples` {20, 50}, `learning_rate` 0.05 |

## Table

- **2,491 rows, 1,101 players, 19 features.**
  - 1 categorical: `position_group_season`
  - 13 numeric features from the release
  - 3 derived per-90 features
  - 2 previous-value columns: log previous value and `has_prev_value`
- Report-group columns:
  - position
  - season
  - `has_prev_value`
  - `minutes_900_plus`
  - `identity_sensitive` (454 rows)
  - `target_before_season_start` (15 rows)
- 107 rows have no previous value.
- Excluded columns are checked absent: all `s_*`, `target_audit_*`, and `season_id`. Season is kept only as a report-group key and is not in the feature list.

## Per-90 derivation

The rule is `total × 90 / minutes`, and the result is null when minutes are null or 0. Checked against the source's own per-90 columns, the maximum absolute difference is 0 over about 2,220 rows each, for `m_accurate_passes_per90`, `m_recoveries_per90` and `m_shots_per90`. So the derived features use the source convention.

## Null rates (no imputation)

| Feature | Null rate | Feature | Null rate |
|---|---:|---|---:|
| `m_big_chances_created` | 38.6% | `m_successful_crosses_per90` | 35.9% |
| `m_dribbles_succeeded_per90` | 17.3% | `m_accurate_long_passes_per90` | 14.6% |
| `m_long_ball_accuracy` | 14.6% | `m_non_penalty_xg` | 14.4% |
| `m_accurate_passes_per90` | 11.1% | `m_passing_accuracy`, `m_shots_per90`, `m_touches_per90` | 11.0% |
| `m_rating` | 4.9% | `log_prev_value` | 4.3% |
| `m_expected_assists` | 1.1% | | |

## Tests

Both Phase 5 test files were run directly with `python -I`. **13 run, 13 passed** (6 in `test_features.py`, 7 in `test_season_start_prev_value.py`).

## Not done

- No training, no CV run, no metrics.
- ISS-01 owner labelling is still open.
- The config choices above have not been reviewed by the owner.
