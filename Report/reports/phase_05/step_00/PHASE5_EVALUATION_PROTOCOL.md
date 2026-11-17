# Phase 5 Evaluation Protocol and Design (step 00)

Date: 2026-11-15. Status: **DRAFT, pending owner review**. No code has been written, no model has been trained, and no dependency has been installed.

This document records the Phase 5 design decisions agreed with the project owner on 2026-11-13 and 2026-11-15. It is the path referenced by ODR-08 (`PHASE4_OWNER_DECISION_REGISTER.md`).

## 1. Inputs

| Item | Value |
|---|---|
| Dataset | `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet` (SHA-256 `4d94ec73…eedd`; verify the full hash before use) |
| Rows / players / seasons | 2,747 / 1,228 / 5 (2020/21–2024/25, `configs/research_scope.yaml`) |
| Phase 4 status | ACCEPTED, with blocking conditions carried forward (section 9) |

The release dataset is read-only. Every Phase 5 change (new previous-value column, per-90 features) is derived in Phase 5 outputs and never written back.

## 2. Population

- Modeling population: rows with `position_group_season` in DEF, MID, FWD and `target_usable` true. This gives **2,491 rows and 1,101 players** (checked 2026-11-15).
- **Goalkeepers are excluded from the model**: 206 rows, 95 players. They remain in the dataset. The exclusion and its counts are reported. Conclusions apply to outfield players only.
- No other rows are removed. 49 players change position group between seasons. Each of their rows keeps its own season position.

## 3. Target and model

- Target: log of `target_market_value` (EUR). The log base and the back-transformation are fixed in step 01.
- **One main model**: LightGBM regressor, trained with native null handling. There are no auxiliary or comparison models.
- Libraries: scikit-learn (splits, nested CV, metrics) and LightGBM. Both are installed into `.venv314` and pinned in `requirements.txt` when implementation starts. PyPI has Windows wheels for Python 3.14: scikit-learn 1.9.1 (cp314) and lightgbm 4.7.0 (py3-none). Neither is installed yet.
- Untrained reference (comparison only): **persistence**, where the prediction equals the previous value. It is left empty, and reported separately, for rows without a previous value.

## 4. Previous value (open condition, blocks final results)

- Approved definition (owner decision 2026-11-15): **the latest Transfermarkt valuation strictly before the official EPL season start date**. It is derived from the Phase 3 valuation history.
- Reason: `target_audit_previous_value` usually falls mid-season. The median gap to the target is 98–198 days, depending on season. So it already reflects part of the same season that the performance features describe. This is not future leakage, but it changes the research question and makes the error look better than a true start-of-season prediction.
- Before use, the following are required:
  1. Verify each season's start date from an official source and store it in configuration, as was done for the end dates in Phase 3.
  2. Build the column in a separate audited step, with tests and a manifest.
  3. Report the coverage, and compare it with the current 71 rows that have no previous value.
  4. Run the no-overlap check: previous valuation date < season start date ≤ target cutoff.
- The flag `has_prev_value` comes from the new column.
- Until these steps pass, results that use `target_audit_previous_value` are exploratory only.

## 5. Features (baseline)

Representations were chosen manually (P4-D03) from `FEATURE_REDUNDANCY_SUMMARY.md` and `CANDIDATE_FEATURE_GROUPS.md`.

| Group | Features |
|---|---|
| Previous value | log(previous value, section 4), `has_prev_value` |
| Playing time | `m_minutes_played` (representative of cluster 1) |
| Age | `age_at_season_end_years` |
| Position | `position_group_season` (categorical) |
| Attacking | `m_goals`, `m_non_penalty_xg` (cluster 2), `m_shots_per90` (cluster 3) |
| Chance creation | `m_assists`, `m_expected_assists` (cluster 4), `m_big_chances_created` |
| Passing | `m_accurate_passes_per90`, `m_accurate_long_passes_per90`, `m_passing_accuracy`, `m_long_ball_accuracy` |
| Possession | `m_touches_per90`*, `m_dribbles_succeeded_per90`*, `m_successful_crosses_per90`* |
| Rating | `m_rating` |

\* Derived in Phase 5 as `total × 90 / m_minutes_played`. The result is null when minutes are null or 0, never 0.

Excluded from the baseline:

| Excluded | Reason |
|---|---|
| Defensive actions, including `m_recoveries` and `m_duels_won` | Owner decision 2026-11-15 |
| Discipline and fouls | Owner decision 2026-11-15 |
| Other members of redundancy clusters 1–4 | Manual choice of representatives |
| RD-04 features | ODR-09 |
| Club context | ODR-10 |
| `s_*` as direct predictors | ODR-13 |
| Season | Trees cannot extrapolate, and forward chaining needs unseen seasons |
| GK-only metrics | Goalkeepers are out of scope |
| Identity, target, temporal-audit columns | Never predictors |

Known feature risks, which must be reported:
- P4-B05: per-90 values are unstable at low minutes.
- ISS-29: `m_passing_accuracy` and `m_long_ball_accuracy` are reported by the source.
- P4-B09: passing accuracy drifts across seasons.
- `m_rating` is a composite source score.
- `m_big_chances_created` has about 44% nulls. The exact outfield rate has not been rechecked.

## 6. Evaluation design

- **Primary:** Repeated StratifiedGroupKFold. Groups are `canonical_player_id`, so all seasons of a player stay in one fold. Stratification uses quantile bins of log target, per row. K, the number of repeats, the number of bins and the seeds are proposed in step 01: K = 5, 5 repeats, 5 bins, fixed seeds.
- **Supplementary:** forward chaining by season, using the same model configuration. Train on seasons up to t and test on t+1. Players in the test season may also appear in training seasons. This mirrors real use and is reported as such.
- **Hyperparameters:** nested CV with a small search space. The inner loop uses GroupKFold by player on outer-training data only. The search space is fixed in step 01, before any result is seen.
- **Metrics:** MAE on log target is primary. RMSE on log and MdAPE in EUR are reported alongside. All metrics are reported as mean and spread across repeats and folds.
- **Error breakdowns** (no rows removed):
  - position group
  - season
  - returning vs new (`has_prev_value`)
  - under vs over 900 minutes

## 7. Identity sensitivity (ISS-01, P4-B01)

- The main results use all modeling rows.
- The evaluation is repeated with the 533-row identity sensitivity subset excluded (ODR-08). The number of these rows inside the outfield population is recomputed in step 01.
- Mapping coverage is never described as precision.

## 8. Leakage controls

- Every preprocessing step that is fitted, and all tuning, happens inside the training folds only.
- Status and temporal-audit columns are never used as features.
- RD-03: 44% of appearances fall after the valuation date. This is a known temporal mismatch between features and target. It is carried into `LEAKAGE_AUDIT` and is not resolved by this design.
- The previous value must satisfy section 4 before final results.

## 9. Conditions blocking final results

| Condition | Owner of next action | Status |
|---|---|---|
| Previous value redefined at season start (section 4) | Claude, then owner review | Open |
| ISS-01: owner-labelled sample of identity mappings | **Owner** | Open |
| P4-B01: sensitivity comparison run | Claude | Designed (section 7), not run |
| RS5-11: repeated players | Claude | Addressed by grouped splits, to be verified |
| ISS-25, ISS-27, P4-D01: nulls and `s_*` | Claude | Addressed by native null handling, no `s_*` features and no zero-filling, to be verified |
| P4-D02: split | Claude | Decided (section 6) |
| P4-D03: feature representations | Claude | Decided (section 5) |

## 10. Next step

Step 01 (after owner approval of this document):
1. Install and pin the dependencies.
2. Verify the season start dates.
3. Build and audit the season-start previous value.
4. Fix K, repeats, bins, seeds and the search space.
5. Only then train.
