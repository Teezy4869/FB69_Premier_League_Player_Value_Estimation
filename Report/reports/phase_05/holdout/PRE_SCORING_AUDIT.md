# Pre-Scoring Leakage Audit and Training Record (2025/26 holdout)

Date: 2026-11-16. Script: `src/holdout/pre_scoring_audit.py`. It is read-only and prints booleans, counts and dates only. **No holdout target, value or prediction was viewed.** No scoring output exists (checked).

## 1. How the model was trained

| Stage | Data | What was decided | Holdout involved? |
|---|---|---|---|
| Feature, population and metric design (owner, 2026-11-13/15) | Phase 4 EDA reports, 2020/21–2024/25 | 19 features, DEF/MID/FWD, ln target, MAE | No. 2025/26 data did not exist in the project yet |
| Development evaluation (`train_eval.py`, run_v1) | 2,491 development rows | Measured MAE (5×5 grouped CV, forward chaining, identity sensitivity). Every fold tuned on its own training rows (inner GroupKFold) | No |
| Acceptance threshold (owner, 2026-11-16) | Development results | ≥ 60% within ±20% for players with 900+ minutes | No (set after the development results, **before** any holdout data) |
| Pre-registration signed | | Config, code, rules, decision rule frozen with SHA-256 | No |
| **Final model** (`final_model.py`) | **All 2,491 development rows, 2020/21–2024/25** | One `GridSearchCV` over 8 configurations with `GroupKFold(3)` by player, then refit on all rows. Selected: 200 trees, 15 leaves, `min_child_samples` 50, learning rate 0.05 | No |
| Holdout build | 2025/26 only | Counts and nulls only | Built after the model |

Order of events, all UTC on 2026-11-16, from file timestamps and manifests:

| Event | Time |
|---|---|
| Freeze signed | 08:45:55 |
| Final model fitted | 08:48:18 |
| First 2025/26 raw response | 08:58:49 |
| Holdout input v1 | 09:34:59 |
| Holdout input v2 | 09:52:30 |

**The model was fixed before any 2025/26 data entered the project.**

## 2. Automated checks

All checks passed.

| Check | Result |
|---|---|
| Every frozen file matches its SHA-256 in the signed manifest | PASS |
| Model file matches its recorded SHA-256 | PASS |
| Training rows = 2,491, seasons 2020/21–2024/25 only | PASS |
| Model's feature names and order = config `phase5_model_v1` (19 features) | PASS |
| No target, status (`s_*`), temporal-audit, identity or season column among the features | PASS |
| Development targets after their season cutoff | 0 |
| Development previous values on or after the first match | 0 |
| Latest development target valuation date | 2025-04-29, before the 2025/26 season |
| Holdout rows sharing a player-season key with development | 0 |
| Holdout targets after the 2026-05-24 cutoff | 0 |
| Holdout previous values on or after the 2025-08-15 first match | 0 |
| Holdout features: same columns, dtypes and position categories as training | PASS |
| Value, market or target column in the ISS-01 labelling file | none |
| Any prediction, metric or lock file for the holdout | none |

## 3. Review of possible leakage routes

| Route | Assessment |
|---|---|
| Future valuation as target | Blocked by `select_target` (on or before the cutoff). Verified: 0 violations |
| Target information in features | The previous value is strictly before the first match, so it is independent of the season-end target. No `target_*` column is a feature |
| Same player in train and holdout | 356 holdout players also appear in development. Training uses their **earlier** seasons only: 0 shared player-season keys. This mirrors real use and is reported as a group ("seen in development") |
| Model or threshold tuned on the holdout | Impossible by order of events; the model, grid and threshold are frozen by SHA-256 |
| Preprocessing fitted on the holdout | None exists. Per-90 is a row-wise formula, nulls are handled natively, and the position categories come from development |
| Different data rules for the holdout | The FotMob rebuild reproduces release v3.1 2024/25 exactly (0 of 29,786 cells differ). Identity uses the same rules, and 372 of 372 returning mappings agree with development |
| ISS-01 population decisions | Made on identity evidence only, with a rule approved before labelling and with no value columns in the file |
| RD-03 (features cover the whole season, including matches after the valuation date) | Present in the holdout exactly as in development; accepted under Objective A (ODR-01). This is a construct caveat, not train/test leakage |

## 4. Exposure disclosures (not leakage into the model)

1. **Claude saw holdout target-status counts:** VALID 230, STALE 294, MISSING 13. These depend on valuation **dates**, not values, and no decision used them.
2. **The ISS-01 labelling file linked to Transfermarkt profile pages**, which display market values. The owner confirmed (2026-11-16) that the labelling was done by a different person, the labeller recorded in the file, not by the owner. So the owner, who makes the project decisions, has not seen 2025/26 values. In any case, nothing was changed after labelling.
3. A self-check flagged 11 features by substring ("s_" inside names such as `m_minutes_played`). This was a false positive of that check; the exact role check returns none.

## 5. Verdict

**No leakage found.** Every item that will be scored was frozen before the holdout existed, and every temporal rule holds on both development and holdout data.

Remaining limitations, already pre-registered:
- the RD-03 construct caveat
- about 316 rows with 900+ minutes, so the ±20% interval will be wide

The holdout is ready for one-shot scoring (step 5) when the owner authorizes it.
