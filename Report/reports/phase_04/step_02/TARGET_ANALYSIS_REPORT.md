# Phase 4.2: Target Analysis Report

Date: 2026-11-08. Dataset: official `player_season_integrated_rs5_v1` (SHA-256 `4d94ec73…eedd`, verified before reading), scope `rs5_v1` (2020/21–2024/25, from `load_scope()`). Code: `src/phase4/univariate.py`. Evidence: `evidence/target_*.csv`, `evidence/univariate_summary.json`. Figures: `figures/fig42_01`–`fig42_04`.

The analysis is descriptive. The target is described in raw EUR. A log10 scale is computed on the fly for description only, and the stored column is unchanged. No value is removed, capped or filtered. No age cap and no staleness filter are applied.

> **Temporal construct mismatch (RD-03).** The target is the latest Transfermarkt valuation on or before season end (D4). In practice it is a mid-season valuation: the median age is 150 days, and valuations come from league-wide batches. Features cover the whole season. Every statement below describes that valuation and inherits this limitation. Under objective A this is a known alignment limitation, not leakage.

## 1. Summary statistics (`target_summary.csv`)

| Statistic | Raw (EUR) | log10 (descriptive) |
|---|---:|---:|
| Count (usable) | 2,697 of 2,747 rows | 2,697 |
| Mean | 19.26m | 7.007 |
| Median | 13.0m | 7.114 |
| Standard deviation | 20.43m | 0.582 |
| Minimum / maximum | 0.1m / 200m | 5.00 / 8.30 |
| p01 / p05 / p10 | 0.2m / 0.8m / 1.5m | |
| p25 / p75 (IQR) | 5m / 25m (20m) | 6.70 / 7.40 (0.70) |
| p90 / p95 / p99 | 45m / 60m / 90m | |
| Skewness | **2.31** (strongly right-skewed) | **−0.84** (moderately left-skewed) |
| Excess kurtosis | **8.71** | 0.46 |
| Mean / median | 1.48 | |

- **Shape.** The target is strongly right-skewed and heavy-tailed. On the log scale it is compact (a standard deviation of 0.58 corresponds to a factor of about 3.8) but over-corrected: the longer tail moves to the low end (young fringe players at EUR 0.1–0.5m).
- **Granularity.** There are only 84 distinct values. 86.9% are whole millions, 40.7% are multiples of EUR 5m, and the most common value is EUR 10m (133 rows). Valuations are rounded, so histograms show heaping.
- **Missing targets.** There are 50 (1.82%): `ONLY_VALUATIONS_AFTER_CUTOFF` 37, `NO_VALUATION_HISTORY` 11, `NO_ELIGIBLE_IDENTITY_MATCH` 2 (the ISS-04 rows). None is imputed.

## 2. Extreme values (`target_fences.csv`, `target_extremes.csv`)

| Fence | Raw scale | log10 scale |
|---|---|---|
| 1.5 IQR | 151 above EUR 55m; 0 below | 79 below EUR 0.45m; 0 above |
| 3 IQR | 32 above EUR 85m; 0 below | 0 |

- **The 32 rows above EUR 85m are 17 players**, for example Erling Haaland (EUR 170–200m), Bukayo Saka, Phil Foden, Cole Palmer, Rodri, Harry Kane and Mohamed Salah. All 32 have a previous valuation. The ratio to it is 0.83–1.44 (median 1.00) and the median previous value is EUR 110m. Their valuation histories show no isolated spike. **These are genuine elite valuations, not errors, and they are kept (P4-A09).** `target_audit_*` columns were read for this audit check only (P4-A03).
- By position: 17 FWD, 14 MID, 1 DEF and 0 GK rows lie above the 3 IQR fence. By season there are 4–9 per season.
- **The lowest values** (EUR 0.1–0.15m) are players aged 17–23 with 1–2 confirmed appearances (the 12 lowest rows; at most 75 minutes). Where previous valuations exist they are similar (EUR 0.1–0.15m).

## 3. Target by season (`target_by_season.csv`, `target_timing_by_season.csv`)

| Season | Usable | Coverage | Median | Mean | p90 | Max | Skew (raw) | Median valuation age | Share on modal date |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020/21 | 515 | 98.28% | 10.0m | 16.88m | 40.0m | 120m | 2.15 | 66 d (2021-03-18) | 92.6% |
| 2021/22 | 528 | 98.32% | 10.0m | 17.21m | 40.0m | 100m | 1.88 | 150 d (2021-12-23) | 72.7% |
| 2022/23 | 542 | 97.83% | 15.0m | 19.61m | 45.0m | 170m | 2.29 | 206 d (2022-11-03) | 60.5% |
| 2023/24 | 567 | 99.47% | 13.0m | 20.13m | 48.8m | 180m | 2.24 | 152 d (2023-12-19) | 68.8% |
| 2024/25 | 545 | 96.98% | 17.0m | 22.24m | 50.0m | 200m | 2.66 | 160 d (2024-12-16) | 53.4% |

- The median rises from EUR 10m to 17m and the maximum from EUR 120m to 200m. Skew is strong in every season.
- **Season and valuation timing are confounded (ISS-21).** 53–93% of each season's targets come from one league-wide valuation date, and that date's distance to season end ranges from 66 to 206 days. A season difference mixes market movement, the season's population and the batch date. This analysis does not separate them and does not claim a trend.
- No staleness filter is applied (P4-A08). A 90-day filter would remove 2.9% of 2020/21 but 78.0% of 2021/22 targets (ISS-22).

## 4. Target by position, and by position and season

Position is `position_group_season`, the whole-season modal lineup position. It is partly determined after the valuation date (P4-B04, RD-03).

| Position | Rows | Usable | Median | Mean | p90 | Max | Skew (raw) | Mean/median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GK | 206 | 206 | 6.0m | 11.22m | 25.0m | 65m | 1.67 | 1.87 |
| DEF | 935 | 924 | 12.0m | 16.65m | 38.0m | 100m | 1.58 | 1.39 |
| MID | 839 | 817 | 15.0m | 20.95m | 50.0m | 130m | 1.87 | 1.40 |
| FWD | 767 | 750 | 15.0m | 22.84m | 55.0m | 200m | 2.42 | 1.52 |

Median (EUR m) by position and season (`target_median_position_season.csv`; cells hold 39–191 targets, `target_count_position_season.csv`):

| Position | 2020/21 | 2021/22 | 2022/23 | 2023/24 | 2024/25 |
|---|---:|---:|---:|---:|---:|
| GK | 6.0 | 4.5 | 6.0 | 9.5 | 8.5 |
| DEF | 7.25 | 10.0 | 15.0 | 12.0 | 16.0 |
| MID | 12.0 | 12.0 | 15.0 | 15.0 | 18.0 |
| FWD | 12.0 | 12.0 | 15.0 | 15.0 | 19.0 |

- Goalkeepers are valued lowest and have no extreme tail. Forwards have the longest tail.
- Outfield medians move together across seasons. Defenders rise most. Goalkeeper medians rest on about 40 rows per season and are imprecise.
- These are descriptive differences. No causal reading is made (D6).

## 5. Policy compliance

| Rule | Status |
|---|---|
| Raw target as the source; stored column unchanged | Yes (test `test_stored_data_unchanged_and_tails_kept`; dataset hash unchanged) |
| Log scale for description only | Yes (computed on the fly) |
| Elite tails kept; no extreme value treated as an error without evidence | Yes (§2) |
| No age cap, no staleness filter (RD-01, ISS-22, P4-A08) | Yes |
| RD-03 caveat stated with target interpretation | Yes |
| Old targets (RD-01: 12 rows over 365 days) included | Yes (unchanged; RD-01 still open) |
