# Phase 5 Leakage Audit

Date: 2026-11-16. Scope: the main model run `run_v1` (config `phase5_model_v1`, input `model_input_v1`). Covers every feature, the target, the evaluation design and the tuning procedure.

## 1. Verdict

| Check | Result |
|---|---|
| Future valuation used as target or feature | **None** |
| Target information in features | **None** |
| Train/test contamination in evaluation | **None found** (checked by tests) |
| Season-level temporal construct mismatch (RD-03) | **Present; known and accepted (ODR-01).** Results are association with an end-of-season valuation, not prediction made before the valuation. |

## 2. Target

- The target is the latest valid Transfermarkt valuation on or before the official season end (D4, Phase 3 `select_target`). Valuations after the cutoff are never selectable.
- Current-profile and career-high values are never read.
- `target_*` and `target_audit_*` columns are absent from the model input. This is asserted in `src/phase5/features.py` `check()`.

## 3. Feature-by-feature

| Feature | Source | Time window | Risk | Status |
|---|---|---|---|---|
| `log_prev_value`, `has_prev_value` | Transfermarkt valuation history | Strictly before the season's first match | None: dated before the season and before the target. Asserted in `season_start_prev_value.check()` and tested | OK |
| `age_at_season_end_years` | FotMob birth date | Fixed at season end | None | OK |
| `position_group_season` | FotMob, whole season | Whole season (P4-B04) | RD-03 only | Accepted (ODR-01) |
| `m_minutes_played`, `m_goals`, `m_assists`, `m_non_penalty_xg`, `m_expected_assists`, `m_big_chances_created`, `m_rating` | FotMob season totals | Whole season | RD-03 | Accepted (ODR-01) |
| Per-90 and accuracy rates (`m_shots_per90`, `m_accurate_passes_per90`, `m_accurate_long_passes_per90`, `m_passing_accuracy`, `m_long_ball_accuracy`) | FotMob | Whole season | RD-03. ISS-29: accuracy rates are reported by the source | Accepted |
| Derived `m_touches_per90`, `m_dribbles_succeeded_per90`, `m_successful_crosses_per90` | Computed in Phase 5 from season totals and minutes | Whole season | RD-03. The formula matches the source's own per-90 values exactly | Accepted |

Excluded from the model:

| Excluded | Reason |
|---|---|
| RD-04 features | Incomplete window evidence (ODR-09) |
| Club context | Temporally ambiguous (ODR-10) |
| `s_*` status columns | ODR-13 |
| `temporal_*` audit columns | P4-A03 |
| Present-day nationality | Excluded predictor |
| Season | Design choice |

## 4. RD-03: temporal construct mismatch

On the 2,491 modeling rows:
- **43.9%** of player games happen after the target valuation date.
- **87.8%** of rows have at least one game after it.
- The median valuation age at season end is **150 days**.

So the season features partly describe matches played after the valuation they are compared with. The model therefore learns how end-of-season valuations relate to whole-season statistics. It does not learn a forecast made at the valuation date.

The owner kept D4 and accepted reporting this mismatch (ODR-01). Every Phase 5 result must carry this caveat. Performance must never be read as causing an earlier valuation.

## 5. Previous value

- The original `target_audit_previous_value` was usually dated mid-season, so it overlapped the feature window. The owner had it replaced (decision 2026-11-15) by the season-start value. That value is strictly before the first match and therefore never overlaps the season.
- **15 rows** have a target valuation dated before the season start, so their target equals their previous value. These rows are kept and reported separately (owner decision). They make persistence look perfect on those rows; they are not leakage into the model.
- **2020/21** previous values are the COVID re-valuation batch. This is an accepted limitation.

## 6. Evaluation and tuning

- **Grouped CV:** each repeat splits by `canonical_player_id`. Tests assert that no player appears in two folds of the same repeat, and that each row is predicted exactly once per repeat.
- **Stratification** uses quantile bins of log target only to assign folds. The bins are not a feature.
- **Nested tuning:** GridSearchCV runs on the training rows of each outer fold, with inner GroupKFold by player. Test rows never inform hyperparameters.
- **No fitted preprocessing outside the folds:** there is no scaler and no imputer (LightGBM handles nulls natively), and the per-90 features are row-wise formulas.
- **Forward chaining** trains on seasons strictly before the test season. Players may recur across seasons, which mirrors real use and is documented.
- **Fixed in advance:** the config was fixed before any result. After results were seen, no feature, grid or population was changed.
- **Quantile bin edges** are computed on the full modeling set. They only balance folds, so the information effect is negligible. Noted for completeness.

## 7. Not covered

- No separate check that the FotMob statistics were not revised after the season (P4-B03 revisions; noted in Phase 4).
- The error analysis permutation importance used a single holdout split. It is diagnostic only and is not a reported result.
