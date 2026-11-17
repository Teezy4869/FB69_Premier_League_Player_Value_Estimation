# rs5 Step 2: Target Coverage, Staleness and Valuation Dates

Source: `data/research_rs5/targets/target_rs5_v1__matching_v2_1/target_manifest.json` → `statistics`. **Every percentage below is new and replaces the six-season figure.**

## Definitions

- **Coverage** = usable targets / player-season rows.
- **Older than 90 days** = usable targets with `valuation_age_days > 90` / usable targets.
- **Appearances after valuation** = confirmed appearances (STARTED or SUBSTITUTED_ON) dated after the selected valuation date / all confirmed appearances, summed over usable-target rows.

## By season

| Season | Rows | Usable | Missing | Coverage | Median age (days) | Over 90 days | Appearances after valuation |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020/21 | 524 | 515 | 9 | 98.28% | 66 | 2.91% | 24.91% |
| 2021/22 | 537 | 528 | 9 | 98.32% | 150 | 78.03% | 48.58% |
| 2022/23 | 554 | 542 | 12 | 97.83% | 206 | 66.97% | 54.72% |
| 2023/24 | 570 | 567 | 3 | 99.47% | 152 | 72.66% | 46.84% |
| 2024/25 | 562 | 545 | 17 | 96.98% | 160 | 59.63% | 44.16% |
| **rs5 total** | **2,747** | **2,697** | **50** | **98.18%** | **150** | **56.62%** | **44.10%** |

Six-season figures, for contrast only: 63.35% over 90 days; 41.09% of appearances after valuation. Removing 2019/20 lowers the stale share (2019/20 was 99.80% stale) but raises the after-valuation share (2019/20 was 25.38%).

## Staleness bins (usable targets)

| 0-30 | 31-60 | 61-90 | 91-180 | Over 180 |
|---:|---:|---:|---:|---:|
| 27 | 113 | 1,030 | 1,140 | 387 |

## By position (modal lineup position that season)

| Position | Rows | Usable | Coverage | Median value (EUR) | Over 90 days |
|---|---:|---:|---:|---:|---:|
| GK | 206 | 206 | 100.00% | 6,000,000 | 63.59% |
| DEF | 935 | 924 | 98.82% | 12,000,000 | 58.77% |
| MID | 839 | 817 | 97.38% | 15,000,000 | 57.28% |
| FWD | 767 | 750 | 97.78% | 15,000,000 | 51.33% |

Every Confirmed player-season has a known modal position.

## By identity evidence tier

| Tier | Rows | Usable | Coverage |
|---|---:|---:|---:|
| AUTO_EXACT_VALIDATED | 2,204 | 2,182 | 99.00% |
| AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED | 459 | 435 | 94.77% |
| AUTO_ADJUDICATED_INDEPENDENT_RULE | 76 | 74 | 97.37% |
| AUTO_ADJUDICATED_EXTERNAL | 6 | 6 | 100.00% |
| UNRESOLVED | 2 | 0 | 0% |

## Valuation date concentration

Transfermarkt revalues Premier League players in league-wide batches. Each season's target dates concentrate on one or two batch days:

| Season | Main date (targets) | Second date (targets) |
|---|---|---|
| 2020/21 | 2021-03-18 (477) | 2021-03-10 (10) |
| 2021/22 | 2021-12-23 (384) | 2022-03-29 (91) |
| 2022/23 | 2022-11-03 (328) | 2023-03-16 (163) |
| 2023/24 | 2023-12-19 (390) | 2024-03-14 (134) |
| 2024/25 | 2024-12-16 (291) | 2025-03-18 (204) |

So age mostly reflects the season's batch timing, not the player. Median days from cutoff to the next (unused) valuation: 16, 24, 23, 8, 5.
