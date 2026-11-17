# Phase 2A controlled pilot — final technical review

## 1. Executive Summary

Phase 2A controlled pilot completed: 120/120 selected season-stat records. Structural validation passed; overall readiness **CONDITIONAL GO**. This is a pilot result, not a full-population claim.

## 2. Pilot Scope and Sampling

Premier League 2019/20–2024/25, 120 selected player-team-season rows, 109 unique players. Selection used a bounded union of 3,262 reference rows from minutes/goals/saves boards, deterministic seed 6902. The union is not an independent player population.

| Season | Selected | Stats collected | Unique sampled IDs | Player-team-season rows | Finished fixtures |
|---|---:|---:|---:|---:|---:|
| 2019/2020 | 32 | 32 | 32 | 32 | 380 |
| 2020/2021 | 8 | 8 | 8 | 8 | 380 |
| 2021/2022 | 8 | 8 | 8 | 8 | 380 |
| 2022/2023 | 32 | 32 | 32 | 32 | 380 |
| 2023/2024 | 8 | 8 | 8 | 8 | 380 |
| 2024/2025 | 32 | 32 | 32 | 32 | 380 |

| Inferred position group | Sample rows | Available cells | Missing cells | N/A cells |
|---|---:|---:|---:|---:|
| DEF | 39 | 609 | 132 | 156 |
| FWD | 31 | 470 | 119 | 124 |
| GK | 15 | 185 | 160 | 0 |
| MID | 35 | 551 | 114 | 140 |

## 3. Collection Methodology

Only six league responses, 18 reference boards, two historical team probes, 109 profiles, 120 season-stat responses and 10 selected match details were retained. Endpoint counts: leagues=6, leagueseasondeepstats=18, matchDetails=10, playerData=109, playerStats=120, teams=2. Cache keys include endpoint, parameters, season and source ID. New responses retain wire bytes; earlier Step 01–02 responses retain full canonical JSON.

## 4. Actual Collection Results

265 raw pairs; 265/265 logged attempts OK; 0 retries and 0 failed attempts in this pilot. Normalized table rows: players=109, teams=27, player_seasons=120, player_team_seasons=120, matches=2281, player_match_links=47, metric_observations=2880. Collection timestamps in raw metadata are UTC; the cached range is 2026-11-02T07:45:03.218169+00:00 to 2026-11-02T08:06:33.151254+00:00. This success rate is limited to observed requests.

## 5. Player Coverage

All 120 selected rows have season statistics, 120 historical team rows and 109 unique player profiles. Six seasons and 20 league teams per season are represented in the reference. Reference population coverage and missing historical players remain **UNKNOWN** because no independent denominator exists. Player IDs are internally traceable; Transfermarkt matching was not performed.

## 6. Feature Availability

Across 2,880 sampled metric cells: 1815 available, 525 missing, 420 position N/A, 120 unsupported. Values were never zero-filled.

| Group | Available | Missing | N/A | Unsupported |
|---|---:|---:|---:|---:|
| GENERAL | 473 | 7 | 0 | 0 |
| ATTACK | 525 | 195 | 0 | 0 |
| PASSING_CREATION | 399 | 81 | 0 | 120 |
| DEFENDING | 362 | 238 | 0 | 0 |
| GOALKEEPING | 56 | 4 | 420 | 0 |

See [per-season metric coverage](pilot_feature_coverage.csv) and [cross-season classifications](cross_season_consistency.csv). CORE: appearances and starts. OPTIONAL: available but incomplete or definition-limited metrics, including minutes_played until its cross-source discrepancy has a documented rule. POSITION_SPECIFIC: four goalkeeper metrics. UNVERIFIED: key_passes. EXCLUDED_FOR_NOW: rating because provider computation/stability is unverified. These are data-readiness labels, not predictive feature selection.

## 7. Player Profile Findings

84/120 profile current-team fields differ from the historical leaderboard team; 9 names differ literally. All 120 profile season entries were verified. Profile position/nationality/current club are current-only. Birth date is stored as a profile claim; no historical age was derived. Three retrospective career histories suggest multi-club candidates without season-scoped allocation evidence.

## 8. Match Index Findings

Six league responses contain 2281 fixture records: 2,280 finished (380 per season) and abandoned/cancelled match `4193691`; replay `4421797` is a separate finished fixture. All retained dates and results parse/present. Ten matchDetails responses yield 47 verified selected-player lineup links, spanning 28 players and 32/120 selected player-season keys. The `playerMatches` route was not used after a prior HTTP 400 with unverified parameters; fixture membership is not player participation.

## 9. Historical Data Integrity

Historical club is taken from season-scoped leaderboard rows, never current profile club. Season IDs are checked against the six configured mappings. Every player-match link has matching season and fixture team. Current-only profile fields remain separate, and retrospective transfer suggestions create no new team rows. The normalized match table retains both canceled and replay IDs. Historical position is only an inferred numeric code-band; no verified role taxonomy exists.

## 10. Data Quality Findings

No duplicate primary keys, invalid UTC match dates, invalid percentages, negative count values, nonfinite available values, wide/long metric mismatch or missing raw checksum found. One `source_id` collision affects two team-probe metadata records, though endpoint+parameter pairs are unique. Cross-source conflict: 2024/2025 player 831489 team 8650: leaderboard 2607 vs playerStats 2606 minutes (`mins_played_2024_2025`, `stats_2024_2025_831489`). The 2024/25 `player_seasons` value uses 2606 from playerStats; sample manifest preserves leaderboard 2607. Quality findings and severities are in [pilot_data_quality_report.csv](pilot_data_quality_report.csv).

## 11. Cross-Season Consistency

All six seasons have selected rows and 380 finished fixtures. 20/24 metrics have at least one available cell in every season; source units and Parquet column types are stable in this pilot. This does not prove provider definitions were stable or that unobserved player groups have the same schema. Original FotMob field names, null status, units and source formats are retained in metric_observations. Minutes, goals and saves have 183 cross-source comparisons, with one disagreement. Saves compares the `Total saves` secondary leaderboard value, not the per-90 main value.

## 12. Pipeline Reliability

265/265 observed HTTP attempts succeeded. 265 raw pairs pass JSON and SHA-256 validation; 0 exact endpoint+parameter repeats. All 7 Parquet tables parse and match declared key/type schemas. Cached reruns issue zero HTTP requests. The source ID collision must be corrected before scaling.

## 13. Automated Test Results

31/31 passing (python -m unittest discover -s tests -v). Commands: `python -m unittest discover -s tests -v`; `python -m src.collection.final_validation --check`; `python -m src.collection.pilot_runner discover --dry-run`; `python -m src.collection.phase_02a_03_06 profiles --max-requests 0`; `python -m src.collection.phase_02a_03_06 stats --max-requests 0`; `python -m src.collection.phase_02a_03_06 matches --max-requests 0`. These commands do not perform Phase 2B.

## 14. Technical Limitations

Reference boards do not establish full player population. Position groups are inferred. Retrospective multi-club club spells and team-level stat allocation are unverified. Player-match participation is sparse. Provider definitions for rating, xG/xA, goals prevented and percentage denominators are not independently verified. Prior 26 raw responses are full canonical JSON rather than wire-byte originals. Zero pilot failures do not estimate full-crawl failure rate.

## 15. Phase 2B Readiness Verdict

**CONDITIONAL GO for engineering feasibility; full historical collection remains gated.** HTTP/cache/raw/normalization mechanics passed this bounded pilot, but population coverage, source ID uniqueness, historical multi-club attribution, player-match association and validation thresholds require the actions below. See [readiness plan](phase_02b_readiness_plan.md).

## 16. Required Actions Before Full Collection

1. Establish a season-scoped independent historical player denominator and verify roster completeness.
2. Make every raw source ID unique across seasons and validate collisions.
3. Define multi-club historical team attribution and minute/stat split policy using season-scoped evidence.
4. Validate a bounded, supported player-match association path or explicitly limit Phase 2B to fixture index.
5. Resolve the one-minute cross-source conflict policy and document source priority.
6. Version metric definitions and set season/position-aware null, uniqueness, integrity and resume checkpoints.

Do not execute Phase 2B without a separate instruction.
