# Phase 4.6 Split Strategy Assessment

Date: 2026-11-09. Evidence: `evidence/player_structure.csv`, `temporal_holdout_feasibility.csv`, `split_strategy_comparison.csv`, `feasibility_summary.json` (`random_split_leakage`). Figure: `figures/fig46_04_split_feasibility.png`. **No split was executed**; all numbers are analytic or descriptive. The final split is a Phase 5 design decision (P4-D02).

## 1. Player structure

| Seasons per player | Players | Usable rows |
|---:|---:|---:|
| 1 | 517 | 517 |
| 2 | 241 | 482 |
| 3 | 191 | 573 |
| 4 | 110 | 440 |
| 5 | 137 | 685 |

679 of 1,196 players with a target contribute 2,180 of 2,697 rows.

## 2. Random row split (prohibited, RS5-11)

Analytic expectation for an 80/20 random row split: for a player with k rows, the probability that a test row's player also has a training row is 1 - 0.2^(k-1). Averaged over usable rows: **76.2%** of test rows would have their player in training. Evaluation would measure player recognition as much as estimation.

## 3. Grouped by player (recommended primary)

- All seasons of a player in one fold; K-fold over players.
- Advantages: no identity leakage; uses all five seasons; several folds give variance estimates; supports per-position and per-season reporting.
- Limitations: each fold mixes season batches, so batch timing (ISS-21) is shared by training and test; does not test generalisation to a new season.
- Requirements: stratify or check balance by position and season; report a P4-B01 sensitivity run; fit any preprocessing inside the training folds.

## 4. Temporal by season (recommended secondary)

| Test season | Training seasons | Train / test rows | Test rows with player seen earlier | New-player test rows | Train / test median target (EUR m) | Test median valuation age | `clearances` coverage train / test |
|---|---:|---|---:|---:|---|---:|---|
| 2021/22 | 1 | 515 / 528 | 65.3% | 183 | 10 / 10 | 150 | 0% / 6.3% |
| 2022/23 | 2 | 1,043 / 542 | 65.7% | 186 | 10 / 15 | 206 | 3.2% / 0% |
| 2023/24 | 3 | 1,585 / 567 | 69.3% | 174 | 12 / 13 | 152 | 2.1% / 9.0% |
| 2024/25 | 4 | 2,152 / 545 | 74.7% | 138 | 12 / 17 | 160 | 3.9% / 81.3% |

- Meaning under objective A: training on earlier seasons and estimating end-of-season values in a later season reflects how the model would be used for a new season. It is not forecasting future value, because the test season's features and label are contemporaneous; training never uses later seasons to evaluate earlier ones.
- Advantages: tests generalisation to a new valuation batch and a new market level; realistic.
- Limitations: one test season (or small early folds in a rolling design); 65–75% of test rows belong to players with earlier seasons (their earlier rows are in training, which is legitimate here but should be reported); clear shifts in level, batch timing and RD-04 feature coverage.
- Requirements: report returning and new players separately; consider a stricter variant that removes test players from training.

## 5. Recommendation

Primary: grouped-by-player K-fold. Secondary: hold-out of 2024/25 with training on 2020/21–2023/24, reported for returning and new players. Optional: rolling origin and the strict "new player, new season" variant. Never: random row splits, or any use of later-season information to evaluate an earlier season. Owner confirmation required (P4-D02).
