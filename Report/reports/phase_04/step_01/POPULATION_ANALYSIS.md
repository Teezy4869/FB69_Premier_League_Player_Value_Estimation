# Phase 4.1: Player Population Analysis

Date: 2026-11-08. Official dataset, 2,747 player-seasons and 1,228 players, five official seasons. Evidence files are in `evidence/` (`position_by_season.csv`, `appearance_profile.csv`, `minutes_profile.csv`, `low_playing_time.csv`, `gk_vs_outfield.csv`, `appearance_evidence_agreement.csv`). Figures: `figures/fig41_03_*`, `fig41_04_*`.

This is a descriptive analysis. The bins below describe the population; none of them is a filter or an exclusion rule.

## 1. Who is in the population

The population is FotMob **Confirmed** player-seasons. A player-season is included when lineup evidence shows the player started at least one league match or came on in one (`population_status = APPEARED` on every row, `confirmed_appearance_count` ≥ 1).

- **Players with no confirmed appearance are not in the dataset.** The FotMob rs5 release records **691 Unverified** player-seasons outside it: bench listings whose participation is `UNKNOWN`. It also records 20,184 `UNKNOWN` player-match records. These were never treated as zero appearances.
- `started_match_count + sub_in_match_count = confirmed_appearance_count` holds on every row.

## 2. Positions (`position_group_season`, the modal lineup position that season)

| Season | GK | DEF | MID | FWD |
|---|---:|---:|---:|---:|
| 2020/21 | 41 | 186 | 152 | 145 |
| 2021/22 | 42 | 182 | 155 | 158 |
| 2022/23 | 39 | 183 | 178 | 154 |
| 2023/24 | 40 | 191 | 180 | 159 |
| 2024/25 | 44 | 193 | 174 | 151 |

| Group | Rows | Players | Median confirmed appearances | Minutes null | Target coverage | Mean null metrics |
|---|---:|---:|---:|---:|---:|---:|
| Goalkeeper | 206 (7.5%) | 95 | 17 | 96.60% | 100.00% | 34.49 |
| Outfield | 2,541 | 1,133 | 21 | 0.00% | 98.03% | 16.11 |

Position is a whole-season modal value, so part of it comes from matches played after the valuation date (P4-B04).

## 3. Appearances and minutes

Confirmed appearances per player-season, from lineup evidence:

| Appearances | GK | DEF | MID | FWD |
|---|---:|---:|---:|---:|
| 1 | 22 | 52 | 57 | 59 |
| 2-4 | 36 | 77 | 60 | 68 |
| 5-9 | 22 | 94 | 64 | 60 |
| 10-19 | 30 | 240 | 180 | 146 |
| 20-29 | 26 | 257 | 216 | 194 |
| 30-38 | 70 | 215 | 262 | 240 |

Minutes played, as reported by FotMob. A null is shown with its source status:

| Minutes | GK | DEF | MID | FWD |
|---|---:|---:|---:|---:|
| 1-89 | 7 | 88 | 106 | 129 |
| 90-449 | 0 | 119 | 120 | 123 |
| 450-899 | 0 | 121 | 111 | 88 |
| 900-1799 | 0 | 245 | 209 | 197 |
| 1800-2699 | 0 | 221 | 182 | 164 |
| 2700-3420 | 0 | 141 | 111 | 66 |
| null (`MISSING`) | 199 | 0 | 0 | 0 |

**Goalkeeper minutes are essentially unavailable.** 199 of 206 goalkeeper rows have no minutes, all with status `MISSING`. This is a source limitation (ISS-11). It is not zero playing time.

## 4. Low playing time

| Group | Rows | Share | Goalkeepers | Target coverage | Mean null metrics (of 53) |
|---|---:|---:|---:|---:|---:|
| 1 confirmed appearance | 190 | 6.92% | 22 | 83.68% | 43.99 |
| 2-4 confirmed appearances | 241 | 8.77% | 36 | 93.36% | 34.22 |
| Reported minutes < 90 | 330 | 12.01% | 7 | 87.88% | 43.61 |
| Minutes null | 199 | 7.24% | 199 | 100.00% | 34.06 |
| All rows | 2,747 | 100% | 206 | 98.18% | 17.49 |

Fringe player-seasons are sparse, with about 44 of 53 metrics null, and they have lower target coverage. They remain in the population.

## 5. Agreement between two derivations of appearance counts

| Reported (FotMob statistics) | Lineup evidence | Compared | Equal | Reported higher | Reported null |
|---|---|---:|---:|---:|---:|
| `m_appearances` | `confirmed_appearance_count` | 2,746 | 2,746 | 0 | 1 |
| `m_starts` | `started_match_count` | 2,746 | 2,733 | 13 | 1 |

Appearances agree on every comparable row. Reported starts exceed lineup starts on 13 rows (known ISS-30), and these 13 include the 6 rows where starts exceed appearances (DQ-RS5-04). The one null row has status `MISSING`. Published values are kept.

## 6. Implications for Phase 4.2

- Analyse goalkeepers separately: their minutes are missing and their metric set differs.
- Read distributions together with playing time. Fringe rows are sparse, and their per-90 rates rest on small denominators (P4-B05).
- Within a season, rows are unique players. Across seasons they are not independent (687 multi-season players).
