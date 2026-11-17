# Phase 4.4 Season Comparison Report

Date: 2026-11-09. Evidence: `evidence/season_population.csv`, `season_profile.csv`, `season_timing.csv`, `season_stratified_medians*.csv`, `returning_player_change.csv`, `season_rate_metric_*_regular_outfield.csv`. Figures: `fig44_06`–`fig44_08`. Season coverage of every feature: Phase 4.2 `feature_coverage_by_season.csv` and `fig42_07`.

> **ISS-21/ISS-22 and RD-03.** Each season's targets come mainly from one league-wide valuation batch, at a different distance from season end, and staleness differs strongly by season. No seasonal change is interpreted without target timing and data availability. Season is a grouping key, not a predictor (P4-A05).

## 1. Population and composition

| Season | Rows | Returning from previous season | Usable / missing targets | GK / DEF / MID / FWD % | 0-start % | Median starts | Median minutes | Multi-club rows | P4-B01 rows |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| 2020/21 | 524 | n/a | 515 / 9 | 7.8 / 35.5 / 29.0 / 27.7 | 9.9 | 15 | 1,355 | 11 | 110 |
| 2021/22 | 537 | 349 (65.0%) | 528 / 9 | 7.8 / 33.9 / 28.9 / 29.4 | 9.7 | 15 | 1,349 | 12 | 116 |
| 2022/23 | 554 | 337 (60.8%) | 542 / 12 | 7.0 / 33.0 / 32.1 / 27.8 | 12.3 | 13 | 1,212 | 21 | 94 |
| 2023/24 | 570 | 350 (61.4%) | 567 / 3 | 7.0 / 33.5 / 31.6 / 27.9 | 14.4 | 13.5 | 1,161 | 12 | 102 |
| 2024/25 | 562 | 352 (62.6%) | 545 / 17 | 7.8 / 34.3 / 31.0 / 26.9 | 12.5 | 13 | 1,149 | 17 | 111 |

Composition is stable. Slightly more rows and fringe players from 2022/23 lower the median playing time.

## 2. Target level and timing

| Season | Median target (EUR m) | Median valuation age (days) | Modal date (share) | > 90 days | > 180 days |
|---|---:|---:|---|---:|---:|
| 2020/21 | 10 | 66 | 2021-03-18 (92.6%) | 2.9% | 1.4% |
| 2021/22 | 10 | 150 | 2021-12-23 (72.7%) | 78.0% | 2.7% |
| 2022/23 | 15 | 206 | 2022-11-03 (60.5%) | 67.0% | 65.5% |
| 2023/24 | 13 | 152 | 2023-12-19 (68.8%) | 72.7% | 0.0% |
| 2024/25 | 17 | 160 | 2024-12-16 (53.4%) | 59.6% | 2.0% |

A 90-day staleness filter would remove 3% of 2020/21 but 78% of 2021/22 (ISS-22); no filter is applied.

## 3. Is the level shift composition?

Season medians within position x role (two roles; every outfield cell >= 48 rows) still rise from 2020/21 to 2024/25 by a factor of 1.20–1.75 (DEF >= 19 starts EUR 16.5m → 28m; MID < 19 starts 7m → 12m). Composition does not explain the shift.

Returning players' own values between consecutive seasons: median ratio 0.89, 0.93, 1.00, 1.00; decreases outnumber increases in every pair (44.6–56.8% vs 26.1–43.5%). The level shift therefore does not affect every player; it is compatible with population turnover (entrants with higher values), batch timing and market movement, which this analysis cannot separate.

## 4. Metric distributions and coverage

Regular outfield players (>= 19 starts), median by season (2020/21 → 2024/25): recoveries per 90 5.19 → 3.98 (index 77), interceptions per 90 1.07 → 0.76 (71), shots per 90 0.84 → 1.05 (peak 1.24 in 2023/24), tackles per 90 1.44 → 1.55 (peak 1.69), passing accuracy 81.7 → 84.3, rating 6.89 → 7.02. Coverage of these metrics is 99.5–100% except rating in 2024/25 (94.6%). The drift is not missingness; its cause (style, or source definition and collection, RS5-13) is not identifiable here and is recorded as P4-B09. Feature-level season coverage limits (for example `clearances` in three seasons, RD-04) are documented in Phase 4.2.

## 5. Conclusion

Seasons differ mainly in target timing and target level; population and composition are stable. Season-level target differences must never be read as performance effects, and season-aware evaluation will be required later (RS5-11, P4-D02).
