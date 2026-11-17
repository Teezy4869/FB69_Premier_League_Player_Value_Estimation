# 2025/26 Holdout Result (scored once, 2026-11-16T13:50:09+00:00)

Pre-registration: `HOLDOUT_PREREGISTRATION.md` with Amendment 1. Freeze, model and input SHA-256 were verified before scoring. Lock: `HOLDOUT_SCORED.lock`.

## Primary: model vs persistence (476 rows with a previous value)

| MAE model | MAE persistence | ΔMAE | 95% CI | Verdict |
|---:|---:|---:|---|---|
| 0.246 | 0.368 | 0.122 | 0.092 to 0.157 | **PASS** |

## Secondary: within ±20%, 900+ minutes (316 rows)

| Share | 95% CI | Threshold | Verdict |
|---:|---|---:|---|
| 64.9% | 59.5% to 69.9% | 60% | **INCONCLUSIVE** |

## Overall (484 rows)

MAE log 0.255, RMSE log 0.389, MdAPE 17.3%. Group results: `data/holdout_2025_26/scoring/holdout_metrics.json`.

Reported as computed. Nothing may be changed in response to these results (pre-registration section 6).

## Group results (MAE ln; persistence on rows that have a previous value)

| Group | Rows | Model | Persistence |
|---|---:|---:|---:|
| DEF | 168 | 0.233 | 0.348 |
| MID | 160 | 0.229 | 0.372 |
| FWD | 156 | 0.304 | 0.385 |
| Seen in development | 356 | 0.186 | 0.295 |
| New to the model | 128 | 0.444 | 0.582 |
| 900+ minutes | 316 | 0.189 | 0.309 |
| Under 900 minutes | 168 | 0.378 | 0.484 |
| No previous value | 8 | 0.791 | – |
| Target before season start | 2 | 0.432 | 0.000 (exact by construction) |

## Reading (written after scoring; no change was made to anything)

- **Primary: PASS.** On unseen 2025/26 data the model beats persistence clearly. ΔMAE is 0.122, with a 95% interval of 0.092 to 0.157. It beats persistence in every position group and in every reported subgroup that has a previous value.
- **Secondary: INCONCLUSIVE.** 64.9% of predictions are within ±20%, which is above the 60% threshold, but the interval is 59.5% to 69.9% and its lower bound touches the threshold.
- Holdout MAE (0.255) is in line with development (grouped CV 0.265, forward chaining 0.283), so there is no sign of overfitting to the development seasons.
- The same weak spots as in development appear again:
  - players new to the model (0.444)
  - players under 900 minutes (0.378)
  - players without a previous value (0.791, only 8 rows)
- RD-03 caveat (ODR-01): the results describe end-of-season valuation from whole-season statistics. They are not forecasts.
