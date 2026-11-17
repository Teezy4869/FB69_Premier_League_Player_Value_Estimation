# Phase 5 Step 03: Nested-CV Training and Evaluation (run_v1)

Date: 2026-11-16. Config `phase5_model_v1`, input `model_input_v1`. Code `src/phase5/train_eval.py`. Outputs are in `data/phase_05/results/run_v1/`:
- `metrics.json`
- `oof_predictions_primary.parquet`
- `predictions_forward.parquet`
- `best_params.csv`
- `manifest.json`

**Status: exploratory.** Final results remain blocked by ISS-01 (owner identity labelling).

## Overall results (ln scale; MdAPE on EUR)

| Run | Rows | MAE log | RMSE log | MdAPE % |
|---|---:|---:|---:|---:|
| Primary: StratifiedGroupKFold 5×5, mean ± sd across repeats | 2,491 | **0.265 ± 0.001** | 0.420 ± 0.004 | 17.4 ± 0.3 |
| Sensitivity without the 454 identity-sensitive rows | 2,037 | 0.254 | 0.399 | 16.9 |
| Forward chaining (test seasons 2021/22–2024/25) | 2,017 | 0.283 | 0.456 | 18.3 |

An MAE of 0.265 on the ln scale means a typical ratio error of about exp(0.265) ≈ 1.30×.

## Model vs persistence, on rows that have a previous value

| Run | Rows | Model MAE | Persistence MAE | Model MdAPE | Persistence MdAPE |
|---|---:|---:|---:|---:|---:|
| Primary | 2,384 | **0.235** | 0.323 | 16.7 | 20.0 |
| Forward | 1,937 | 0.253 | 0.316 | 17.7 | 20.0 |

The model beats the untrained persistence reference on every reported group except the 15 pre-season-target rows (section "Error by group").

Persistence MdAPE is exactly 20.0% in all three runs. This is plausible, because Transfermarkt values move in round steps. It has not been investigated.

## Error by group (primary run, MAE log; persistence in brackets)

| Group | Rows | Model MAE | Persistence MAE |
|---|---:|---:|---:|
| DEF | 924 | 0.253 | 0.299 |
| MID | 817 | 0.267 | 0.331 |
| FWD | 750 | 0.277 | 0.345 |
| 2020/21 | 474 | 0.270 | 0.353 |
| 2021/22 | 486 | 0.237 | 0.242 |
| 2022/23 | 503 | 0.276 | 0.380 |
| 2023/24 | 527 | 0.281 | 0.318 |
| 2024/25 | 501 | 0.257 | 0.322 |
| Returning (previous value present) | 2,384 | 0.235 | 0.323 |
| **New (no previous value)** | **107** | **0.926** | – |
| Under 900 minutes | 955 | 0.364 | 0.397 |
| 900 minutes or more | 1,536 | 0.203 | 0.281 |
| Identity-sensitive | 454 | 0.343 | 0.356 |
| Not identity-sensitive | 2,037 | 0.247 | 0.316 |
| Target before season start | 15 | 0.502 | 0.000 (exact by construction) |

Forward chaining, MAE by test season:

| Test season | MAE |
|---|---:|
| 2021/22 | 0.256 |
| 2022/23 | 0.312 |
| 2023/24 | 0.293 |
| 2024/25 | 0.272 |

## Findings

1. **New players are the weak spot.** MAE 0.926 means a typical error of about 2.5×. These are only 107 rows, but they are a quarter of the problem. Without a previous value, the performance features carry far less signal.
2. **The identity-sensitive rows are harder.** Their MAE is 0.343, against 0.247 for the other rows. Removing them lowers the overall MAE from 0.265 to 0.254, but the conclusion is unchanged. This difference is consistent with possible wrong-identity targets, but it is not proof. It is a further reason to do the ISS-01 labelling.
3. **Low-minute players are much harder** (0.364 vs 0.203). This is consistent with the per-90 instability noted in P4-B05.
4. **Forward chaining is worse than the grouped CV** (0.283 vs 0.265), as expected for unseen seasons. 2022/23 is the hardest season in both designs.
5. **The tuned settings sit on the grid edge.** 51 of 54 tuning runs picked `num_leaves=15`, and all 54 picked `n_estimators=200`. These are the smallest values in the grid. A smaller or more regularised model might do slightly better. Any change to the grid needs owner approval and a new `config_version`, and must not be chosen from these test results.

## Tests

`tests/phase5/test_train_eval.py`: **6 run, 6 passed.**
- metric definitions, checked on synthetic values
- each row is predicted once per repeat
- no player appears in two folds of the same repeat
- forward chaining predicts test seasons only
- the sensitivity population has 2,037 rows

## Not done

- No feature importance or residual analysis.
- No leakage audit document yet.
- ISS-01 owner labelling is still open.
