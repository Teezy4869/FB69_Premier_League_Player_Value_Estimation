# Phase 5 Step 03: Error Analysis (run_v1)

Date: 2026-11-16. Input: the primary out-of-fold (OOF) predictions in `data/phase_05/results/run_v1/oof_predictions_primary.parquet`, averaged over the 5 repeats for each row. The residual is defined as prediction − actual, on the ln scale. **Exploratory**: ISS-01 is still open. The analysis was run as an ad-hoc script and is not saved in `src`.

## 1. Bias by target level: shrinkage toward the middle

Overall bias is −0.001.

| Target quintile | Rows | Median EUR | Bias | MAE |
|---|---:|---:|---:|---:|
| Q1 (lowest) | 550 | 2.0m | **+0.164** | 0.391 |
| Q2 | 507 | 8.0m | +0.005 | 0.286 |
| Q3 | 471 | 15.0m | −0.040 | 0.216 |
| Q4 | 500 | 25.0m | −0.056 | 0.198 |
| Q5 (highest) | 463 | 50.0m | **−0.105** | 0.181 |

The model overvalues cheap players and undervalues expensive ones. This is the usual pull toward the mean of a squared-loss tree model. Low-value players are also the least accurately predicted group.

## 2. Large value changes are under-predicted

These are rows with a previous value. The change is ln(target) − ln(previous value).

| Change since season start | Rows | Bias | MAE |
|---|---:|---:|---:|
| Fell more than about 40% (< −0.5) | 139 | **+0.360** | 0.362 |
| −0.5 to −0.1 | 768 | +0.087 | 0.158 |
| About stable (−0.1 to 0.1) | 725 | +0.060 | 0.190 |
| 0.1 to 0.5 | 443 | −0.086 | 0.201 |
| Rose more than about 65% (> 0.5) | 309 | **−0.403** | 0.483 |

The model mostly predicts "close to the previous value". Breakout seasons and sharp declines are where it fails. In other words, the performance features explain only part of a large value change.

## 3. Age

| Age at season end | Rows | MAE |
|---|---:|---:|
| ≤ 21 | 271 | **0.627** |
| 22–24 | 493 | 0.318 |
| 25–28 | 852 | 0.185 |
| 29–31 | 487 | 0.180 |
| ≥ 32 | 388 | 0.186 |

Young players carry the largest errors. Their values move fastest, and they often have few minutes or no previous value.

## 4. Where the total error comes from

| Group | Share of rows | Share of total absolute error |
|---|---:|---:|
| New players (107 rows) | 4.3% | **15.1%** |
| Under 900 minutes (955 rows) | 38% | **52.7%** |

New players are predicted without bias (+0.002; median prediction EUR 0.64m against a median target of 0.5m). Their errors are large in both directions.

The 10 largest errors all have a previous value missing or at most 1,315 minutes. Examples:
- A defender with **1 minute** valued at EUR 30m, predicted 0.47m. The target most likely reflects a transfer fee or reputation that the season's data cannot show.
- A forward with 255 minutes valued at EUR 0.25m, predicted 7.8m.
- 3 of the 10 rows are identity-sensitive. Their targets should be checked during ISS-01.

## 5. Feature importance

Permutation importance: the increase in MAE when a feature is shuffled. Computed on one model fitted with the most frequently tuned parameters (200 trees, 15 leaves, min_child_samples 20). It used a single 75/25 split grouped by player, with 10 permutations. It is indicative only, not cross-validated.

| Feature | ΔMAE |
|---|---:|
| `log_prev_value` | **0.783** |
| `age_at_season_end_years` | 0.155 |
| `m_minutes_played` | 0.040 |
| `m_rating` | 0.017 |
| `m_non_penalty_xg` | 0.012 |
| `m_expected_assists` | 0.011 |
| All other 13 features | ≤ 0.003 each |

The previous value dominates. Age, minutes, rating, npxG and xA add most of the remaining signal. Passing, possession and shot-rate features add almost nothing on top of these. `has_prev_value` and position show about 0, but that is expected: the previous value's null pattern and the per-position metrics already carry that information. This is not a reason to remove them.

## 6. Persistence MdAPE of exactly 20%

The median absolute percentage error of persistence falls exactly on 0.20. The neighbouring quantiles are 0.182 at the 45th percentile and 0.25 at the 55th. Transfermarkt values move in round steps, for example 10m → 12m (20%) or 8m → 10m (25%), so the error ratios cluster on a few discrete values and the median lands on one of them. Persistence is exactly right for 1.1% of rows. **This is not a bug.**

## 7. Implications (no change made)

- The main room for improvement is new and young players, low-minute players and large value changes. It is not the established regulars, whose MAE is about 0.18–0.20.
- Possible next experiments, each needing an owner decision:
  - a target or feature that captures transfers, for example the club the player moved to
  - a model of value change instead of level (excluded earlier by the owner's single-model decision)
  - a wider or more regularised grid (section 5 of the step 03 report)
- Leakage audit document: not written yet.
