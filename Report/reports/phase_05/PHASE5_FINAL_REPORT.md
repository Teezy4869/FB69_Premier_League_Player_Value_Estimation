# Phase 5 Final Report: Main Market-Value Model

Date: 2026-11-16. Status: **ACCEPTED by the owner on 2026-11-16.**

## 1. Question and answer

**Question:** for an EPL outfield player-season (2020/21–2024/25), how well do the player's season-start market value and whole-season FotMob performance explain the end-of-season Transfermarkt valuation?

**Answer:** one LightGBM model reaches a typical ratio error of **about 1.30×** (MAE 0.265 on the ln scale). On rows that have a season-start value, it beats persistence (0.235 vs 0.323). It is accurate for established regulars and weak for new, young and low-minute players.

**Confirmed on an untouched 2025/26 holdout** (section 12): the model beats persistence, ΔMAE 0.122 with a 95% interval of 0.092 to 0.157 (**PASS**). The ±20% secondary criterion is **INCONCLUSIVE** (64.9%, interval 59.5% to 69.9%).

Caveat (RD-03, ODR-01): 43.9% of player games fall after the target valuation date. Results therefore describe how whole-season statistics relate to an end-of-season valuation. They are not forecasts, and performance must not be read as causing an earlier valuation.

## 2. Data and population

| Item | Value |
|---|---|
| Release | `fb69_player_season_integrated_rs5_v1` (SHA-256 verified on every read) |
| Modeling population | DEF/MID/FWD with a usable target: **2,491 rows, 1,101 players** |
| Excluded | Goalkeepers (206 rows), kept in the dataset |
| Previous value | Latest valuation strictly before the season's first match (`season_start_prev_value_v1`). 107 rows have none ("new") |
| Features | 19, listed in the protocol section 5. Each redundant cluster is represented by one feature, actions are per-90, and season is not a feature |

## 3. Method

- **Target:** ln(EUR).
- **Model:** LightGBM regressor with native null handling. Nothing is imputed.
- **Primary evaluation:** Repeated StratifiedGroupKFold, 5 folds × 5 repeats, grouped by player and stratified on log-target quintiles.
- **Supplementary evaluation:** forward chaining by season.
- **Sensitivity run:** without the 454 identity-sensitive rows (ODR-08).
- **Tuning:** nested grid of 8 configurations, with inner GroupKFold.
- **Reference:** persistence (prediction = previous value).
- **Config:** `phase5_model_v1`, fixed before any result.

## 4. Results

| Run | Rows | MAE log | RMSE log | MdAPE |
|---|---:|---:|---:|---:|
| Primary | 2,491 | **0.265 ± 0.001** | 0.420 | 17.4% |
| Without identity-sensitive rows | 2,037 | 0.254 | 0.399 | 16.9% |
| Forward chaining | 2,017 | 0.283 | 0.456 | 18.3% |
| Model, rows with a previous value | 2,384 | 0.235 | 0.341 | 16.7% |
| Persistence, same rows | 2,384 | 0.323 | 0.544 | 20.0% |

MAE by group:

| Group | Rows | MAE |
|---|---:|---:|
| 900 minutes or more | 1,536 | 0.203 |
| Under 900 minutes | 955 | 0.364 |
| Age 25 or over | about 1,730 | about 0.18 |
| Age 21 or under | 271 | 0.627 |
| New (no previous value) | 107 | 0.926 |
| DEF / MID / FWD | | 0.253 / 0.267 / 0.277 |

Details: `step_03/PHASE5_STEP03_REPORT.md` and `step_03/PHASE5_ERROR_ANALYSIS.md`.

## 5. Main findings

1. **The previous value carries most of the signal.** Permutation importance is 0.78. Age, minutes, rating, npxG and xA add the rest. Passing and possession features add almost nothing.
2. **Predictions shrink toward the middle.** Cheap players are overvalued (+0.16) and expensive ones undervalued (−0.11). Large value changes are under-predicted in both directions.
3. **Error concentrates in a minority of rows.** Players under 900 minutes produce 53% of the total absolute error, and new players produce 15%.
4. **Identity is not the cause of the weaker results.** ISS-01 owner labelling found 0 wrong matches:
   - 101 sampled automatic matches, 95% upper bound 3.6%
   - all 36 adjudicated mappings
   - all three worst-error identity-sensitive players

## 6. Conditions

| Condition | Status |
|---|---|
| ISS-01 identity precision | **PASS**, accepted by the owner on 2026-11-16 |
| P4-B01 sensitivity run | Done: MAE 0.254 vs 0.265, same conclusion |
| Previous-value overlap | Resolved (season-start value) |
| RS5-11 repeated players | Handled by grouped splits, tested |
| Nulls and `s_*` (ISS-25, ISS-27, P4-D01) | Native nulls, no `s_*` features, no zero-filling |
| P4-D02 split / P4-D03 features | Decided and implemented |
| Leakage | `LEAKAGE_AUDIT.md`: no leakage. RD-03 accepted |

## 7. Limitations

- RD-03 construct mismatch (section 1).
- 2020/21 previous values come from the COVID re-valuation batch.
- 15 rows have a target dated before the season start. They are reported separately.
- Conclusions apply to outfield players only.
- The tuned hyperparameters sit at the smallest values in the grid, so the grid may not have explored the best region.
- Permutation importance came from a single split.
- FotMob post-season revisions (P4-B03) were not rechecked.

## 8. Possible next work (each needs an owner decision)

- Transfer or club-move information for new and low-minute players.
- A wider or more regularised hyperparameter grid, under a new config version.
- A goalkeeper-specific model.

## 9. Reproducibility

Run in order with `.venv314` (scikit-learn 1.9.1 and lightgbm 4.7.0, pinned in `requirements.txt`):

1. `src/phase5/season_start_prev_value.py`
2. `src/phase5/features.py`
3. `src/phase5/train_eval.py`

Each output folder has a manifest with input and output SHA-256 values. Tests: `tests/phase5/` (3 files, 19 tests; all passed when last run).

## 10. Acceptance threshold (owner, 2026-11-16)

Owner target: **at least 60% of predictions within ±20% of the actual value, for players with 900 or more minutes.** "Within ±20%" means a predicted/actual ratio between 0.8 and 1.2.

The threshold was set **after** the development results had been seen, so the checks below do not test it. A valid test needs a holdout that no one has looked at.

| Check on existing predictions | 900+ minute rows | Share within ±20% | Against 60% |
|---|---:|---:|---|
| Primary out-of-fold (5×5), mean over repeats | 1,536 | **62.1%** (per repeat 61.3–63.1%) | Above |
| Same, player-cluster bootstrap 95% interval (2,000 draws, 693 players) | | 59.7%–64.3% | **Interval includes 60%** |
| Forward chaining, all test seasons | 1,231 | 58.2% | Below |
| Forward chaining by season | | 2021/22: 60.4, 2022/23: 51.3, 2023/24: 57.4, 2024/25: 64.1 | 2 of 4 seasons below |

Reading: the threshold is met on the grouped cross-validation point estimate, but narrowly. It is not established, because the interval spans 60% and forward chaining falls below it.

Not yet done: no untouched holdout exists. The proposed test is the 2025/26 season after it ends, with the previous value built by the same season-start rule.

## 11. Deviation from ODR-14 (recorded 2026-11-16)

ODR-14 (Phase 4) set a secondary temporal hold-out: develop on 2020/21–2023/24 and hold out 2024/25. Phase 5 did not keep it. 2024/25 was used in the grouped CV, in forward chaining and in the error analysis, and its results were seen before the acceptance threshold was set. **2024/25 is therefore development data**, and none of its numbers are holdout evidence.

Owner decision **D10** (2026-11-16): 2025/26 becomes the single untouched holdout season. See `configs/research_scope.yaml` (`holdout_seasons`) and CLAUDE.md section 2.

## 12. 2025/26 holdout result (D10, scored once on 2026-11-16 at 13:50 UTC)

**Process:**
- The rules were pre-registered, signed, and amended once (Amendment 1), all before any prediction. Everything scored was frozen with SHA-256.
- The final model was fitted once on all 2,491 development rows (2020/21–2024/25) before any 2025/26 data entered the project.
- The 2025/26 data was built blind:
  - FotMob was collected with owner authorization.
  - The rebuild code reproduces release v3.1 2024/25 exactly.
  - The Transfermarkt snapshot already covered the season, so no crawl was needed.
  - Identities were labelled by a person who is not the owner.
- A pre-scoring leakage audit found nothing.
- Records:
  - `holdout/HOLDOUT_PREREGISTRATION.md`
  - `holdout/PRE_SCORING_AUDIT.md`
  - `holdout/HOLDOUT_STEP04_REPORT.md`
  - `holdout/HOLDOUT_RESULT.md`
  - `holdout/HOLDOUT_SCORED.lock`

| Criterion | Rows | Result | 95% interval | Verdict |
|---|---:|---|---|---|
| **Primary:** ΔMAE = persistence − model (ln) | 476 | model 0.246 vs persistence 0.368, Δ 0.122 | 0.092 to 0.157 | **PASS** |
| Secondary: share within ±20%, 900+ minutes, threshold 60% | 316 | 64.9% | 59.5% to 69.9% | **INCONCLUSIVE** |

**Holdout vs development (MAE ln):**

| Evaluation | MAE |
|---|---:|
| Holdout, all 484 rows | 0.255 |
| Development, grouped CV | 0.265 |
| Development, forward chaining | 0.283 |

No sign of overfitting to the development seasons.

**Groups:**

| Group | MAE |
|---|---:|
| Seen in development | 0.186 |
| 900+ minutes | 0.189 |
| New players | 0.444 |
| Under 900 minutes | 0.378 |
| No previous value (8 rows) | 0.791 |

The weak spots found in development are confirmed.

**Consequences:**
- 2025/26 is no longer an untouched holdout.
- Any further model change needs a new holdout season, for example 2026/27, and a new pre-registration.
- The RD-03 caveat (section 1) still applies.
