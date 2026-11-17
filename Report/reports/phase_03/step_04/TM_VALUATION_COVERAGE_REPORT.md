# Valuation Coverage Report (Phase 3, Step 4)

Date: 2026-11-04. Results: `target_manifest.json` in `data/phase_03/targets/target_v1__matching_v2_1/`.

These figures now describe the actual FotMob population, replacing the Step 1 estimate based on TM's own EPL players.

## 1. Coverage by season

| Season | Confirmed rows | Identity matched | Eligible valuation | `VALID` | `STALE_TARGET` | `TARGET_MISSING` | `INVALID_VALUATION` | `AMBIGUOUS_VALUATION` | Usable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 515 | 514 | 498 | 1 | 497 | 17 | 0 | 0 | 96.70% |
| 2020/21 | 524 | 524 | 515 | 500 | 15 | 9 | 0 | 0 | 98.28% |
| 2021/22 | 537 | 536 | 528 | 116 | 412 | 9 | 0 | 0 | 98.32% |
| 2022/23 | 554 | 554 | 542 | 179 | 363 | 12 | 0 | 0 | 97.83% |
| 2023/24 | 570 | 569 | 567 | 155 | 412 | 3 | 0 | 0 | 99.47% |
| 2024/25 | 562 | 562 | 545 | 220 | 325 | 17 | 0 | 0 | 96.98% |
| **Total** | **3,262** | **3,259** | **3,195** | **1,171** | **2,024** | **67** | **0** | **0** | **97.95%** |

Usable means `VALID` or `STALE_TARGET`. Unique players: 1,343, of whom 1,340 are identity matched.

## 2. Why rows differ

| Category | Rows | Status and reason |
|---|---:|---|
| No identity match | 3 | `TARGET_MISSING`, `NO_ELIGIBLE_IDENTITY_MATCH` |
| Matched, but only valuations after the cutoff | 51 | `TARGET_MISSING`, `ONLY_VALUATIONS_AFTER_CUTOFF` |
| Matched, but no valuation history | 13 | `TARGET_MISSING`, `NO_VALUATION_HISTORY` |
| Invalid valuation | 0 | `INVALID_VALUATION` |
| Same-date valuation conflict | 0 | `AMBIGUOUS_VALUATION` |
| Stale but usable valuation | 2,024 | `STALE_TARGET` |
| Valuation within 90 days | 1,171 | `VALID` |

**By season, missing:** 2019/20: 14 after cutoff, 2 no history, 1 no identity. 2020/21: 9 after cutoff. 2021/22: 7, 1, 1. 2022/23: 8, 4, 0. 2023/24: 2, 0, 1. 2024/25: 11, 6, 0.

The "only after cutoff" group plausibly means young players first valued after their debut season, but this wasn't verified. These rows are not filled from later valuations, even though one exists.

## 3. Staleness

| Season | 0–30 | 31–60 | 61–90 | 91–180 | >180 | Median days | Max days | Over 90 days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 1 | 0 | 0 | 494 | 3 | 109 | 229 | 99.80% |
| 2020/21 | 5 | 4 | 491 | 8 | 7 | 66 | 731 | 2.91% |
| 2021/22 | 17 | 95 | 4 | 398 | 14 | 150 | 586 | 78.03% |
| 2022/23 | 2 | 4 | 173 | 8 | 355 | 206 | 347 | 66.97% |
| 2023/24 | 1 | 5 | 149 | 412 | 0 | 152 | 166 | 72.66% |
| 2024/25 | 2 | 5 | 213 | 314 | 11 | 160 | 724 | 59.63% |
| **Total** | **28** | **113** | **1,030** | **1,634** | **390** | **109** | **731** | **63.35%** |

**A strict 90-day filter would remove almost all of 2019/20 and few from 2020/21,** so any later decision would change the season mix.

## 4. Most common selected dates

| Season | Date | Players on that date | Usable |
|---|---|---:|---:|
| 2019/20 | 2020-04-08 | 491 | 498 |
| 2020/21 | 2021-03-18 | 477 | 515 |
| 2021/22 | 2021-12-23 | 384 | 528 |
| 2022/23 | 2022-11-03 | 328 | 542 |
| 2023/24 | 2023-12-19 | 390 | 567 |
| 2024/25 | 2024-12-16 | 291 | 545 |

April 2020 may be a pandemic-related revaluation. That wasn't verified, but Phase 4 should test for a 2019/20 effect.

## 5. Market value distribution (usable targets, EUR)

| Season | Minimum | Median | Maximum |
|---|---:|---:|---:|
| 2019/20 | 25,000 | 9,500,000 | 128,000,000 |
| 2020/21 | 100,000 | 10,000,000 | 120,000,000 |
| 2021/22 | 200,000 | 10,000,000 | 100,000,000 |
| 2022/23 | 100,000 | 15,000,000 | 170,000,000 |
| 2023/24 | 100,000 | 13,000,000 | 180,000,000 |
| 2024/25 | 200,000 | 17,000,000 | 200,000,000 |
| **Overall** | **25,000** | **12,000,000** | **200,000,000** |

Values are in nominal EUR and aren't adjusted across seasons. No analysis of this distribution was done; that belongs to Phase 4.
