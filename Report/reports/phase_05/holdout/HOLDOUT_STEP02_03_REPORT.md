# Holdout Steps 2–3: Final Model and Source Checks

Date: 2026-11-16. Pre-registration: `HOLDOUT_PREREGISTRATION.md` (manifest `FROZEN_OWNER_SIGNED`). **No 2025/26 player data, target value or distribution was opened.** Step 3 used counts and dates only.

## Step 2: final model

- Code: `src/phase5/final_model.py`.
  - It verifies the signed freeze manifest before running.
  - It refuses to refit if a model already exists.
- Fitted once on all 2,491 development rows (1,101 players), with the pre-registered grid and `GroupKFold(3)` by player.
- Selected configuration:
  - `n_estimators` 200
  - `num_leaves` 15
  - `min_child_samples` 50
  - `learning_rate` 0.05
  - inner-CV MAE log 0.264
- Output: `data/phase_05/final_model/final_model_v1/final_model.txt`. The model SHA-256 and the feature order are in `manifest.json`.
- `position_group_season` is categorical. LightGBM stores its category mapping in the model file. The holdout input must use the same column order and the same categories.

## Step 3: source checks

### Transfermarkt: the existing snapshot covers 2025/26, so no crawl is needed so far

Snapshot `tm_r2_20260905` (dcaribou):
- The latest valuation is dated 2026-06-12.
- 36,307 valuations fall inside the 2025/26 season window. There are large batches in Dec 2025 (16,661), Mar 2026 (3,781) and May 2026 (8,780), so end-of-season valuations exist.
- EPL (GB1) 2025/26 games run from 2025-08-15 to 2026-05-24, covering 537 players.
- Per-player coverage of the 2025/26 FotMob population cannot be measured until that population exists. If gaps appear then, the crawl rule in CLAUDE.md section 2 applies.

### Season dates: VERIFIED

Recorded in `configs/phase_05_holdout_seasons.yaml`. It is a separate file, so `phase_03_seasons.yaml` and the development scope are unchanged.

| Date | Evidence |
|---|---|
| First match 2025-08-15 (Liverpool v Bournemouth) | Premier League fixture release, https://www.premierleague.com/news/4324719 |
| Season end 2026-05-24 | Same source |

Both dates are corroborated by the Transfermarkt games span.

### FotMob: a blocker, and the main remaining work

- The frozen FotMob release (v3.1) covers seasons up to 2024/25 only.
- The collection pipeline (`src/collection`, `configs/full_collection.yaml`) has a fixed season map without 2025/26, and several validators reject seasons outside it (for example `reliability_runner.py`).
- Collecting 2025/26 means re-running the Phase 2 collection and acceptance flow for one season:
  1. fixtures
  2. match details
  3. player stats
  4. identity and position checks
  5. a frozen release
- That flow requires **live FotMob HTTP requests**, which the project gates behind explicit authorization and per-run budgets.
- The FotMob 2025/26 season id is not yet known. It needs one live probe.
- Risk: FotMob may have changed its API or metric definitions since the 2024/25 capture. The new capture must be reconciled against the v3.1 metric definitions before any feature is built.

## Next decision for the owner

Authorize live FotMob collection for 2025/26:
- a probe to get the season id and check the API is unchanged
- the full one-season collection
- a new frozen release

The rules are the same as the Phase 2 pipeline. The release must be a separate release, with v3.1 untouched.
