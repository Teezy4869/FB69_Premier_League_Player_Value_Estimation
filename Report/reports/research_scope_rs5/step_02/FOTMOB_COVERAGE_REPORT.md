# rs5 Step 2: FotMob Research Dataset and Coverage

Release: `data/releases/fotmob_epl_2020_2025_rs5_v1` (37 checksummed files). Parent: `fotmob_epl_2019_2025_v3_1`, unchanged (38 of 38 hashes). Builder: `src/research_scope/build_fotmob_rs5.py`.

## Method

Each of the 15 season-bearing tables is a row filter of v3.1 on the scope's `season_id`s. `players` keeps the 1,611 players that any in-scope table references (of 1,757). The build stops unless every table meets three conditions: its schema equals v3.1's, its rows equal the in-scope v3.1 slice in both directions (`EXCEPT ALL`), and its season values pass `scope.check_table`. **No FotMob value was recomputed.** Per-season totals were recomputed independently and match the v3.1 builder's own per-season rows.

The crawl log (`collection_manifest.sqlite`, all six seasons) is referenced by SHA-256, not copied.

## Population

| Season | Completed matches | Player-seasons | Confirmed appeared | Unverified (excluded) | UNKNOWN player-matches |
|---|---:|---:|---:|---:|---:|
| 2020/21 | 380 | 641 | 524 | 117 | 4,250 |
| 2021/22 | 380 | 679 | 537 | 142 | 4,677 |
| 2022/23 | 380 | 699 | 554 | 145 | 3,840 |
| 2023/24 | 380 (+1 abandoned) | 734 | 570 | 164 | 3,796 |
| 2024/25 | 380 | 685 | 562 | 123 | 3,621 |
| **Total** | **1,900** | **3,438** | **2,747** | **691** | **20,184** |

- **1,228 unique players** have a Confirmed row. 2,747 is a row count, not a player count.
- Player-match records: 75,358. STARTED 41,800, SUBSTITUTED_ON 13,374, UNKNOWN 20,184 (26.78%). UNKNOWN stays UNKNOWN.
- Player-team-season rows: 3,514. Matches: 1,901 (one 2023/24 match is `CANCELLED_OR_ABANDONED`, as in v3.1).

## Metric coverage (Confirmed player-seasons, `quality_reports/metric_coverage_summary_rs5.csv`)

Denominator: eligible player-seasons (2,747 for outfield-applicable metrics; 206 goalkeeper player-seasons for GK metrics).

| Coverage | Metrics |
|---|---|
| Over 90% | appearances, starts (99.96%), expected_assists (98.62%), rating (94.28%), assists, goals, minutes_played, and GK metrics clean_sheets, goals_conceded, saves, save_percentage |
| 75-90% | passing family, xG (82.05%), shots, touches, tackles, recoveries, duels, interceptions, fouls, non_penalty_xg (77.83%), aerials, chances_created, touches_opposition_box, goals_prevented (GK, 87.38%) |
| 50-75% | xGOT (68.69%), shots_on_target, blocked_shots, penalty_saves (GK), cross_accuracy, successful_crosses, big_chances_created (55.73%) |
| Under 50% | **clearances and clearances_per90: 19.33%, values in only 3 of 5 seasons** |
| No data | **key_passes: 0 values in all 5 seasons** |

**What changed with the scope:** every metric now has values in all in-scope seasons except clearances (3) and key_passes (0). The xG family covered 4 of 380 matches in 2019/20; **in every rs5 season, all 380 completed matches carry match-level xG** (2020/21 first xG match 2020-09-12 = first match). The season-level window status in the source metadata is still `UNKNOWN_COVERAGE_WINDOW`; Step 4 re-tests windows against match sums.

## Status semantics (curated Confirmed table, all 53 status columns)

| Status | Cells |
|---|---:|
| OBSERVED | 91,289 |
| MISSING | 27,361 |
| UNVERIFIED_POSITION | 17,899 |
| OBSERVED_ZERO | 5,762 |
| UNSUPPORTED | 2,747 (key_passes) |
| OBSERVED_FALLBACK_LEADERBOARD | 402 |
| OBSERVED_SOURCE_REVISED | 95 |
| CONFLICTING | 36 |

Null-count and zero-count per metric equal the v3.1 slice exactly (tested), so no null became zero.

## Metric conflicts

553 reconciliation records in scope. **All 36 open `CONFLICTING` values are in rs5 seasons** (2020/21: 1, 2023/24: 2, 2024/25: 33); 2019/20 had none. They stay null and traceable.

## Provenance finding

387 player **profiles** (player-level, present-day, collected November 2026) sit in capture folders named `2019_2020`, because the crawler filed each profile under the first season it saw the player. They aren't season data. **No season-data path** (match lineups, metric captures, fixtures, positions, substitution evidence, season stats) points to a 2019/20 folder (tested).
