# Phase 4.4 Player Group Analysis

Date: 2026-11-09. Evidence: `evidence/group_boundaries.csv`, `starts_group_profile.csv`, `usage_group_profile.csv`, `position_starts_group_profile.csv`, `position_age_band_profile.csv`, `median_target_position_x_starts.csv`, `count_position_x_starts.csv`, `starts_group_status_mix.csv`, `group_identity_sensitivity.csv`. Figures: `fig44_03`, `fig44_05`. Groups are descriptive only: derived on the fly, never written to the dataset, not features.

## 1. Group definitions and rationale

| Grouping | Variable | Boundaries | Rationale | Smallest group |
|---|---|---|---|---|
| Playing-time role | `m_starts` | 0 / 1–9 / 10–18 / 19–28 / 29–38 (+ missing: 1 row) | Quarter seasons of 38 league matches: none, occasional, rotation, regular, core. Starts rather than minutes because minutes are missing on 199 of 206 GK rows (ISS-11) | 324 rows (0 starts); per outfield position >= 68 usable targets |
| Usage pattern | `m_starts / m_appearances` | <50% / 50–89% / >=90% started | Bench vs starter independent of volume; ratio >1 on 6 rows (DQ-RS5-04) read as 100% for grouping only | 814 rows |
| Age band | `age_at_season_end_years` | <=21 / 22–24 / 25–27 / 28–30 / 31+ | Same as 4.3; three-year bands around the value peak | 320 rows (outfield bands >= 82) |
| Minutes band | `m_minutes_played` | 1–89 / 90–449 / 450–899 / 900+ / missing | Same as 4.2 (P4-B05) | 320 rows; GK nearly all "missing" |

Not used: club context (RS5-12), identity or target columns, data-driven clustering. Boundaries were not tuned to the target.

## 2. Playing-time role profile

| Role | Rows | Usable | Median target (EUR m) | Median age | Median minutes | Median null metrics | `MISSING` share of metric cells (outfield) | P4-B01 share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 starts | 324 | 282 | 2.35 | 21.2 | 14 | 46 | 73.5% | 36.7% |
| 1–9 | 755 | 747 | 8 | 26.3 | 418 | 14 | 13.0% | 22.7% |
| 10–18 | 589 | 589 | 15 | 26.9 | 1,254 | 11 | 5.9% | 16.0% |
| 19–28 | 562 | 562 | 20 | 26.9 | 2,059 | 10 | 4.6% | 13.0% |
| 29–38 | 516 | 516 | 25 | 27.4 | 2,885 | 10 | 3.9% | 14.5% |

Median value by position x role (EUR m; cells < 30 rows not interpreted): DEF 2.35 / 7 / 13 / 17.5 / 22; MID 2 / 9 / 15 / 24 / 30; FWD 2.5 / 11 / 18 / 25 / 35; GK — / 2 / — / — / 16.

## 3. Usage pattern

Mainly-substitute rows are young (median 23.9–24.3 outfield) and cheap (DEF 4.5m, MID 7m, FWD 9m); starters are valued highest (DEF 18m, MID 25m, FWD 35m). Usage pattern overlaps strongly with the starts role and adds little separation beyond it. 182 of 206 goalkeeper rows are "starter" by construction (goalkeepers are rarely substituted on).

## 4. Age x playing time

Outfield, median EUR m (rows): <19 starts — <=21 3.25 (242), 22–24 12 (326), 25–27 15 (322), 28–30 12 (316), 31+ 4 (304); >=19 starts — <=21 30 (29, not interpreted), 22–24 32 (167), 25–27 28 (322), 28–30 25 (240), 31+ 9 (223). Young regulars are the highest-valued group, young fringe players the lowest.

## 5. Reliability of groups

Fringe groups carry most nulls (P4-B07) and the highest P4-B01 share; without P4-B01 rows, 0-start medians move from EUR 2.0–2.5m to 3.0–4.25m, while medians for >= 10 starts move by at most 3%. Results about fringe players are the least robust.

## 6. Limitations

Boundaries are reasoned, not unique; RD-03 for all target values; non-independent rows (RS5-11); goalkeeper role cells small.
