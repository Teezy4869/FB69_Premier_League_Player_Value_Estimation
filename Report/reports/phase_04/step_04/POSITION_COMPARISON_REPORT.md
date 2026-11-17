# Phase 4.4 Position-Based Comparison Report

Date: 2026-11-09. Evidence: `evidence/position_profile.csv`, `position_outfield_metrics.csv`, `position_goalkeeper_metrics.csv`, `position_status_mix.csv`, `position_starts_group_profile.csv`, `position_age_band_profile.csv`, `position_correlation_{GK,DEF,MID,FWD}.csv`, `within_group_spearman.csv`. Figures: `fig44_01`, `fig44_02`, `fig44_05`, `fig44_09`. RD-03 applies to every target statement.

## 1. Profile

| | GK | DEF | MID | FWD |
|---|---:|---:|---:|---:|
| Rows / players | 206 / 95 | 935 / 418 | 839 / 401 | 767 / 367 |
| Usable targets | 206 | 924 | 817 | 750 |
| Target p25 / median / p75 (EUR m) | 2 / 6 / 17.75 | 4 / 12 / 25 | 6 / 15 / 30 | 6 / 15 / 30 |
| Target p90 / max (EUR m) | 25 / 65 | 38 / 100 | 50 / 130 | 55 / 200 |
| Median age | 30.2 | 26.8 | 26.1 | 25.5 |
| Median starts / appearances | 17 / 17 | 15 / 20 | 14 / 23 | 12 / 22 |
| Median minutes (missing %) | 14 (96.6%) | 1,370 (0%) | 1,240 (0%) | 1,118 (0%) |
| Median null metrics (of 53) | 34 | 12 | 11 | 12 |
| P4-B01 share | 24.8% | 20.0% | 18.5% | 18.3% |

Status of metric cells (all `s_*` pooled): GK 63.1% `MISSING`, 30.7% observed; outfield 63–68% observed, 13.5% `UNVERIFIED_POSITION` (goalkeeper-only metrics), 13.5–19.1% `MISSING`. The goalkeeper pattern (outfield metrics recorded as `MISSING`, not as not-applicable) is examined in Phase 4.5.

## 2. Outfield metrics (outfield rows only)

| Metric | DEF | MID | FWD |
|---|---:|---:|---:|
| Goals (median) | 0 | 1 | 2 |
| xG | 0.75 | 1.12 | 3.28 |
| xA | 0.52 | 0.95 | 1.07 |
| Shots per 90 | 0.50 | 1.13 | 2.24 |
| Accurate passes per 90 | 38.6 | 36.2 | 19.9 |
| Passing accuracy | 82.8 | 83.5 | 76.9 |
| Tackles per 90 | 1.72 | 2.07 | 1.08 |
| Interceptions per 90 | 1.14 | 0.93 | 0.39 |
| Aerials won % | 57.1 | 44.8 | 35.4 |
| Rating | 6.78 | 6.78 | 6.68 |
| Missing % of rate metrics | about 8–10 | about 12–16 | about 18–26 |

The same metric value describes different roles per position; pooled comparisons mix them.

## 3. Within-position associations (Spearman with the target)

| Feature | DEF all / >=19 starts | MID all / >=19 | FWD all / >=19 |
|---|---|---|---|
| Starts | 0.46 / 0.18 | 0.57 / 0.21 | 0.61 / 0.25 |
| Goals | 0.33 / 0.19 | 0.54 / 0.46 | 0.64 / 0.47 |
| xG | 0.39 / 0.26 | 0.55 / 0.41 | 0.59 / 0.48 |
| Shots per 90 | 0.20 / 0.17 | 0.29 / 0.38 | 0.35 / 0.52 |
| Accurate passes per 90 | 0.48 / 0.51 | 0.26 / 0.36 | 0.28 / 0.29 |
| Passing accuracy | 0.44 / 0.50 | 0.24 / 0.33 | 0.32 / 0.34 |
| Tackles | 0.33 / 0.03 | 0.44 / 0.08 | 0.33 / -0.07 |
| Rating | 0.53 / 0.51 | 0.61 / 0.56 | 0.68 / 0.66 |
| Age | -0.25 / -0.50 | -0.09 / -0.34 | 0.01 / -0.39 |

Defenders' value relates relatively more to passing; forwards' to shooting and attacking output; for all outfield positions, rating and (among regulars) age.

## 4. Goalkeepers (goalkeeper metrics only, never compared with outfield metrics)

- Bimodal roles: 75 back-up rows (1–9 starts, median EUR 2m) and 73 first-choice rows (29–38 starts, median EUR 16m); 7 rows with 0 starts and 50 in between (cells below 30 rows not interpreted).
- Associations (all GK rows): clean sheets 0.67, starts 0.64, goals conceded per 90 -0.48, age -0.41, rating 0.39, save percentage 0.35 (source-reported, ISS-29). Among first-choice goalkeepers (>= 19 starts, n = 97): clean sheets 0.45, saves -0.22, goals conceded per 90 -0.49.
- Goalkeeper metrics are complete for goalkeepers with at least one start, except `penalty_saves` (null on 65% of back-up rows) and `goals_prevented` (null on 15–29% of regular rows; RD-04). No goalkeeper metrics for the 7 zero-start rows. Nothing was filled.

## 5. Limitations

RD-03; non-independent rows; goalkeeper sample small; team context not analysed (RS5-12); source-reported metrics not verified (ISS-29).
