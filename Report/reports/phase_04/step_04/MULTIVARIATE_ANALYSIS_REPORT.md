# Phase 4.4 Multivariate Analysis Report

Date: 2026-11-09. Official dataset `player_season_integrated_rs5_v1` (SHA-256 `4d94ec73…eedd`, verified before reading and unchanged after), scope `rs5_v1` (2020/21–2024/25 from `load_scope()`; `check_parquet()` on the dataset, `check_table()` on the derived season table). Code: `src/phase4/multivariate.py`. Notebook: section 4.4 of `FB69_report.ipynb`. Evidence: `evidence/` (27 tables, `multivariate_summary.json`). Figures: `figures/fig44_01`–`fig44_09`. Companion reports: `POSITION_COMPARISON_REPORT.md`, `SEASON_COMPARISON_REPORT.md`, `PLAYER_GROUP_ANALYSIS.md`.

> **RD-03** applies to every target statement: the target is the latest valuation on or before season end (mostly mid-season), while metrics cover the whole season. All results are descriptive associations, not causal effects. **ISS-21/ISS-22** apply to every season comparison: each season's targets come mainly from one league-wide batch at a different distance from season end.

## 1. Research questions and answers

| Question | Answer |
|---|---|
| How do positions differ? | They are distinct sub-populations: GK median EUR 6m, oldest, minutes missing on 96.6% of rows; DEF/MID/FWD EUR 12/15/15m with similar ages and missingness; metric meanings differ by position (median xG 0.75 for defenders vs 3.28 for forwards) |
| How do seasons differ? | Stable population and composition; strongly different target timing (median age 66–206 days); level rise 1.2–1.75x within position x role strata; returning players' own values flat or falling; drift in some rate metrics |
| Which groups separate the population? | Playing-time role (starts) most strongly, then age, then position; usage pattern adds little beyond starts |
| Do associations hold inside groups? | Among players with >= 19 starts, playing-time and defensive-volume associations largely disappear; attacking output, shot rates, passing quality (DEF) and rating remain; age becomes clearly negative |
| Which interactions are visible? | Age x playing time (young regulars most valuable, young fringe players cheapest); position x metric family; goalkeeper role x clean sheets |

## 2. Methods

- Groups derived on the fly (no write-back): playing-time role from starts (0 / 1–9 / 10–18 / 19–28 / 29–38, quarter seasons of 38 matches), usage pattern (share of appearances started: <50% / 50–89% / >=90%), age bands (as 4.3), minutes bands (as 4.2). Missing grouping values form their own group. Rationale and counts: `PLAYER_GROUP_ANALYSIS.md`, `evidence/group_boundaries.csv`.
- Group profiles: rows, players, target quantiles, age, playing time, null metrics, P4-B01 share, valuation age.
- Grouped heatmaps (position x role; position x role x season), faceted line charts (age x role x position), pair plot (age, starts, rating, xA, log10 target; outfield, coloured by position), position-specific Spearman matrices, within-group feature-target Spearman (all rows vs >= 19 starts).
- Season comparisons: population and turnover, composition, target timing and staleness buckets, stratified medians, returning players' own value change, rate-metric medians and coverage for regular outfield players.
- Minimum interpretable group: 30 usable targets. No intervals for group medians (RS5-11 non-independence noted). No PCA, clustering or model: the variables are few and interpretable, and the questions are about known groupings.

## 3. Main findings

1. **Playing time is the dominant axis.** Median value rises in every position from 0 starts (EUR 2–2.5m) to 29–38 starts (EUR 16m GK, 22m DEF, 30m MID, 35m FWD) (`fig44_03`).
2. **Age x playing time interaction.** Outfield players with >= 19 starts peak at 22–27 years (EUR 25–45m by position); players with fewer starts are cheapest when young (<=21: about EUR 3–3.5m). The pooled age correlation (-0.17) hides opposite patterns.
3. **Within regular players (>= 19 starts)** (`fig44_05`): starts' association drops from 0.46–0.61 to 0.18–0.25; tackles, interceptions, recoveries, clearances and aerials fall to about zero or below; goals (0.46–0.47 MID/FWD), xG (0.41–0.48), shots per 90 (FWD 0.52), touches in the box (FWD 0.67, RD-04 pending) and rating (0.51–0.66) remain; age turns clearly negative (-0.34 to -0.59).
4. **Positions** (`fig44_01`, `fig44_02`): different levels, ages, metric meanings and missingness patterns. Goalkeepers are separate (see `POSITION_COMPARISON_REPORT.md`).
5. **Seasons** (`fig44_06`–`fig44_08`): level and timing differences not explained by composition; individual values do not rise on average; recoveries per 90 and interceptions per 90 drift down by 23–29% among regular outfield players with full coverage (new condition P4-B09).
6. **Identity sensitivity:** group medians for >= 10 starts change by at most 3% without the P4-B01 rows; fringe-group medians are less robust (0-start medians rise from EUR 2.0–2.5m to 3.0–4.25m without them).

## 4. Limitations

RD-03, ISS-21/ISS-22; row counts are not independent players (RS5-11); boundaries chosen by domain reasoning and checked for size, not optimised; goalkeeper cells mostly below 30 rows by role x season; confounders (team strength, club context RS5-12) not analysed; metric drift described, not explained; groups are descriptive and are not features.

## 5. Conclusion

Population heterogeneity runs along position, playing-time role and age, with clear interactions. Inside regular players, a smaller set of associations remains (attacking output, shot rates, passing quality, rating, age). Goalkeepers and fringe players need separate treatment and caution. Season differences are dominated by target timing and level, not by population composition.
