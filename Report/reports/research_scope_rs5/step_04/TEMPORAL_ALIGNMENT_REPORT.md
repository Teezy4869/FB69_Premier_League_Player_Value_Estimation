# rs5 Step 4: Temporal Alignment Report

Every figure was recomputed on the five-season dataset. Appearance timing was recomputed from FotMob match dates; it matches the dataset's `temporal_*` columns exactly. Evidence: `evidence/temporal_audit.json`. **No historical percentage is reused.**

## Definitions

| Indicator | Numerator | Denominator |
|---|---|---|
| Targets older than 90 days | usable targets with `target_valuation_age_days > 90` | usable targets (2,697) |
| Appearances after valuation | confirmed appearances (STARTED or SUBSTITUTED_ON) dated after `target_valuation_date` | all confirmed appearances of usable-target player-seasons (55,073) |
| Minutes after valuation | minutes in matches after the valuation date | minutes with per-match data, same rows |
| Valuation age | `target_season_end_date - target_valuation_date`, in days | |

## Headline results (rs5)

| Indicator | rs5 | Six-season figure (not reused) |
|---|---:|---:|
| **Targets older than 90 days** | **56.62%** (1,527 of 2,697) | 63.35% |
| **Appearances after valuation** | **44.10%** (24,286 of 55,073) | 41.09% |
| Minutes after valuation | 43.66% | |
| Median valuation age | 150 days | 109 |
| Targets over 365 days old | 12 | |
| Valuations after the cutoff | **0** | 0 |
| Appearances after the cutoff | **0** | |

## By season

| Season | Usable | Over 90 days | Median age | Appearances after valuation | All games after / all before |
|---|---:|---:|---:|---:|---:|
| 2020/21 | 515 | 2.91% | 66 | 24.91% (2,585 / 10,379) | 17 / 86 |
| 2021/22 | 528 | 78.03% | 150 | 48.58% (5,081 / 10,459) | 51 / 62 |
| 2022/23 | 542 | 66.97% | 206 | 54.72% (6,201 / 11,332) | 55 / 46 |
| 2023/24 | 567 | 72.66% | 152 | 46.84% (5,329 / 11,378) | 55 / 75 |
| 2024/25 | 545 | 59.63% | 160 | 44.16% (5,090 / 11,525) | 46 / 68 |

Share of each player's games after the valuation (usable rows): 0%: 337; 1-25%: 459; 26-50%: 748; 51-75%: 790; 76-99%: 139; 100%: 224.

## Valuation date distribution

Dates follow Transfermarkt's league-wide batches: March 2021, then December 2021 and March 2022, November 2022 and March 2023, December 2023 and March 2024, December 2024 and March 2025 (`step_02/TARGET_COVERAGE_REPORT.md`). Age therefore tracks the season's batch timing, not the player. 18 usable targets are dated before their own season's first match.

## Season cutoff consistency

For all five seasons, the dataset cutoff equals the scope cutoff, and **the last completed match is on the cutoff date**: 2021-05-23, 2022-05-22, 2023-05-28, 2024-05-19, 2025-05-25. First matches equal the configured first-match dates. One 2023/24 fixture is `CANCELLED_OR_ABANDONED` and isn't counted.

## Feature observation windows

Each metric-season (265 rows) was re-tested against EPL match sums using the unchanged Phase 3 logic. Results are identical to the historical rows for these seasons. Status counts: 144 full season verified, 5 rare-event consistent, 98 not verifiable from match data, 9 no values, 5 disagree with match sums, 4 partial match coverage. Per-feature conclusions: `LEAKAGE_AUDIT.md`.

The xG family is now verified for every season, except xGOT in 2022/23 (92.06% agreement, below the 98% threshold). Under six seasons, 2019/20 covered only 4 of 380 matches.

## Data availability relative to prediction time (Objective A)

Under A, the prediction time is the season end. Every feature is a season total through the last match, which is on the cutoff, so every feature is available at prediction time. But the metrics were collected retrospectively (2-3 November 2026), and 95 cells were revised by the source between collections.

## Inconsistency with Objective A (documented, not changed)

Objective A estimates value **at season end**. The approved target (D4) is the latest valuation **on or before** season end. That valuation is typically 150 days earlier, and 44.10% of the season's appearances come after it. So the label is a mid-season valuation, while the features cover the full season. That isn't leakage, since no future target information enters the features. It is a **construct mismatch**: features include performance the label couldn't reflect. This is **RD-03**, and the rule was not changed.
