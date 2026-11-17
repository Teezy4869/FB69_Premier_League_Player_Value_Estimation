# 2025/26 Holdout Pre-Registration (D10)

Date: 2026-11-16. Status: **DRAFT, pending owner sign-off.** Once signed, the files listed in `holdout_freeze_manifest.json` are frozen. Any later change to them makes 2025/26 development data, and that must be reported.

No 2025/26 data has been collected, opened or inspected at the time of writing.

## 1. What is frozen

Exact SHA-256 values are in `holdout_freeze_manifest.json`:
- Config `configs/phase_05_model.yaml` (`phase5_model_v1`).
- Code:
  - `src/phase5/season_start_prev_value.py`
  - `src/phase5/features.py`
  - `src/phase5/train_eval.py`
  - `src/phase3/season_targets.py` (`select_target`)
- Development model input: `data/phase_05/features/model_input_v1/model_input.parquet`.
- This document.

## 2. Final model

- Training data: all 2,491 development rows (2020/21–2024/25, DEF/MID/FWD, usable target).
- Hyperparameters: the same 8-configuration grid and `GridSearchCV` with `GroupKFold(3)` by player, run **once** on all development rows. The best configuration is refit on all development rows.
- The fitted model is saved with its SHA-256 **before** any 2025/26 row is built into a model input.

## 3. Holdout population and features

- Built with the frozen rules:
  - Confirmed FotMob player-seasons for 2025/26.
  - DEF/MID/FWD by `position_group_season`.
  - Usable target from `select_target`, with cutoff at the verified 2025/26 season end.
  - Previous value: the latest valid valuation strictly before the verified 2025/26 first match.
  - The same 19 features, same per-90 formula, no imputation.
- Identity: the same matching rules as `matching_v2_1`. The owner labels a sample of the new mappings **without seeing any value or target column**. Mappings labelled WRONG are excluded from scoring and counted. All other rows are scored.

## 4. Metrics, all reported regardless of outcome

- **Primary:** MAE on ln target.
- **Secondary:** RMSE on ln target, MdAPE in EUR.
- **Acceptance metric:** share of predictions within ±20% (predicted/actual ratio in [0.8, 1.2]) for rows with 900 or more minutes, with a 95% player-cluster bootstrap interval (2,000 draws, seed 0).
- **Reference:** persistence (prediction = previous value) on rows that have one.
- **Report groups:**
  - position
  - `has_prev_value` (returning / new)
  - seen in development (player appears in 2020/21–2024/25: yes / no)
  - under / over 900 minutes
  - `target_before_season_start`

## 5. Decision rule for the ±20% threshold (60%)

| Result | Condition |
|---|---|
| **PASS** | Lower bound of the 95% interval ≥ 60% |
| **FAIL** | Upper bound < 60% |
| **INCONCLUSIVE** | Interval contains 60% |

The point estimate alone never decides the result.

## 6. One-shot scoring

- The scoring script verifies every SHA in the freeze manifest before running.
- It writes a lock file on completion, and refuses to run if the lock exists.
- After scoring, the result is reported as computed. No feature, parameter, population rule or threshold is changed in response to it.

## 7. Amendment 1 (owner decision 2026-11-16, before any holdout prediction)

**Why:** the ±20% ≥ 60% threshold had been set after the development results were seen. With about 316 rows of 900+ minutes it would most likely end INCONCLUSIVE, and it does not answer the project's main question. The owner chose option C.

**New primary criterion: model vs persistence.**
- Rows: holdout rows with `has_prev_value` true. The 2 `target_before_season_start` rows are included, as pre-registered. The 8 rows without a previous value are excluded from this comparison and reported separately.
- Statistic: ΔMAE = MAE(persistence) − MAE(model), on the ln scale. A positive value means the model is better.
- Interval: paired player-cluster bootstrap, 2,000 draws, seed 0. Model and persistence errors are always resampled together on the same players.

| Result | Condition |
|---|---|
| **PASS** | Lower bound of the 95% interval of ΔMAE > 0 |
| **FAIL** | Upper bound < 0 (the model is worse than persistence) |
| **INCONCLUSIVE** | Interval contains 0 |

**Secondary criterion:** the ±20% ≥ 60% rule for rows with 900+ minutes stays exactly as in section 5, with the same three-level rule. It is reported but no longer decides the primary verdict.

Everything else in sections 1–6 is unchanged. The original signed manifest is kept as `holdout_freeze_manifest_v1_signed.json`.
