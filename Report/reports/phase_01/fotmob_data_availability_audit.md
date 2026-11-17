# FotMob data availability audit — Phase 1 final review

Reviewed at (UTC): 2026-11-02T07:10:22.769517+00:00. Scope: Premier League 2019/20–2024/25.

## 1. Executive Summary

**Overall verdict: CONDITIONAL GO for a bounded data-collection pilot; no full historical crawl yet.** [Observation] All six season identifiers were verified, and season-level goals, minutes and saves tables returned populated player rows. [Inference] The three Level 2+ components appear technically accessible, with separate limitations below. [Unresolved] There is no defensible complete player denominator, `playerMatches` returns HTTP 400, and historical profile fields require careful scoping.

## 2. Project Scope

Premier League (FotMob league ID 47), six completed seasons, FotMob performance data, and a later Transfermarkt primary dataset. This review audits availability and quality. It does not perform bulk extraction, entity matching, preprocessing, feature selection or modeling.

## 3. Data Sources and API Discovery

[Observation] The [endpoint catalog](../../reports/phase_01/fotmob_endpoint_catalog.json) and [discovery summary](../../reports/phase_01/discovery_summary.md) record working `allLeagues`, `leagues`, `leagueseasondeepstats`, `teams`, `playerData` and `matchDetails` probes. `playerStats` was also tested in Phase 1 steps 03–05. `playerMatches` failed with HTTP 400 ([error sample](../../data/audit/raw_samples/steps_03_05/player_matches_retest.json)). These are unofficial JSON interfaces and may change.

## 4. Historical Season Availability

[Observation] The season string selects `/leagues`; numeric `TournamentId` selects `leagueseasondeepstats`. The following IDs, teams, fixture counts and goal-board rows match saved season links and samples. The 2023/24 381 entries include an abandoned match and replay.

| Season | Numeric ID | Teams | Fixture entries | Goal-board rows |
|---|---:|---:|---:|---:|
| 2019/2020 | 14022 | 20 | 380 | 262 |
| 2020/2021 | 15382 | 20 | 380 | 270 |
| 2021/2022 | 16390 | 20 | 380 | 281 |
| 2022/2023 | 17664 | 20 | 380 | 271 |
| 2023/2024 | 20720 | 20 | 381 | 298 |
| 2024/2025 | 23685 | 20 | 380 | 271 |

Evidence: [season report](../../reports/phase_01/season_availability.csv) and six saved `league_*` and `goals_*` samples under `data/audit/raw_samples/steps_03_05/`.

## 5. Feature Availability Matrix

[Observation] The [matrix](../../reports/phase_01/feature_availability_matrix.csv) contains 24 candidates × six seasons: 18 direct-table `AVAILABLE`, 120 catalog/profile-sample `PARTIAL`, and 6 `UNVERIFIED`. All six saved `goals` responses contain the same 37 catalog name/title/category entries. Stable labels do not verify stable calculations.

| Classification | Count | Meaning in this audit |
|---|---:|---|
| CORE | 2 | Directly populated in all six seasons with stable catalog labels; goals and minutes only. |
| OPTIONAL | 14 | Catalog or sampled profile evidence exists, but full player values and completeness are not verified. |
| POSITION_SPECIFIC | 4 | Goalkeeper features require goalkeeper-specific validation and missingness rules. |
| UNVERIFIED | 1 | Exact candidate field was not established in the checked sources. |
| EXCLUDED_FOR_NOW | 3 | Candidate has a narrower observed field or an unverified rating definition. |

Per-feature decisions and field names: [cross-season consistency](../../reports/phase_01/cross_season_consistency.csv) and [data dictionary](../../reports/phase_01/data_dictionary.csv). `Key passes` remains unverified; `Long passes` maps only to accurate long balls; `Duels` maps only to duels won. In the checked 2019/20 saves response, the main value is per 90 and the secondary value is labeled `Total saves` ([unit evidence](../../data/audit/raw_samples/final_review/saves_2019_2020_units.json)).

## 6. Player Coverage Analysis

[Observation] Three player leaderboards per season represent all 20 league teams, but their union is a sampled numerator. The player denominator is `UNKNOWN_DENOMINATOR`; a coverage percentage would be unsupported. The prior audit reports zero duplicate player-ID rows within those boards and zero multi-team IDs across them. Its saved subsets do not allow a complete independent recount.

| Season | Unique IDs in three boards | Teams represented | Saves-board rows |
|---|---:|---:|---:|
| 2019/2020 | 515 | 20/20 | 20 |
| 2020/2021 | 524 | 20/20 | 20 |
| 2021/2022 | 537 | 20/20 | 20 |
| 2022/2023 | 554 | 20/20 | 19 |
| 2023/2024 | 570 | 20/20 | 19 |
| 2024/2025 | 562 | 20/20 | 19 |

Evidence: [coverage report](../../reports/phase_01/player_coverage_report.csv). [Unresolved] Players with few minutes, transfers, and omitted metrics may not be captured by these leaderboards.

## 7. Player Profile Availability

[Observation] Twelve sampled `playerData` profiles have IDs, names, birth dates, current primary team and position, and a season-associated `statSeasons` entry. All 12 sampled profile IDs match their selected leaderboard IDs. Current team differs from historical leaderboard team in **9/12** samples. The `playerStats` season entry is usable as a scoped request key; current primary team and position are not historical attributes.
Evidence: [profile audit](../../reports/phase_01/player_profile_audit.csv) and [2019/20 profile sample](../../data/audit/raw_samples/steps_03_05/profile_outfield_top_goals_2019_2020.json).

## 8. Match Index Availability

[Observation] Historical league responses contain 2281 fixture entries across six seasons. The prior report records dates and results for all entries; raw samples preserve three fixtures per season. The prior match-detail audit counted 36 and 40 lineup player IDs in two responses; saved subsets retain only a few lineup entries. This demonstrates representative player-to-match relationships, not complete coverage.
The 2023/24 Bournemouth–Luton pair has abandoned ID 4193691 and completed replay ID 4421797 ([anomaly sample](../../data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json)). `playerMatches` pagination remains failed. Evidence: [match-index report](../../reports/phase_01/match_index_audit.csv).

## 9. Historical Consistency

[Observation] The 37 catalog name/title/category tuples are identical in all six saved season responses. The six sampled top-scorer goals values agree between leaderboards and season profiles. [Inference] These checks support stable discovery of those fields. [Unresolved] They do not prove provider calculations, every player's values, or position-specific profile schemas are identical across seasons. Goalkeeper and outfield `topStatCard` shapes differ by position.

## 10. Data Quality Findings

The [quality ledger](../../reports/phase_01/data_quality_audit.csv) contains 16 assessments: CRITICAL 2, HIGH 4, MEDIUM 6, LOW 4. Severity reflects potential effect on later historical collection, not a measured error rate.

| Severity | Finding | Evidence |
|---|---|---|
| HIGH | Inconsistent units: The saves catalog says 'Saves per 90' and a follow-up response labels substatTitle 'Total saves'; the 2019/20 top row has statValue=4 and substatValue=81. | [source](../../data/audit/raw_samples/steps_03_05/saves_2019_2020.json) |
| HIGH | Incomplete player coverage: Sampled leaderboard unions range from 515 to 570 player IDs, but no complete historical player denominator was established. | [source](../../reports/phase_01/player_coverage_report.csv) |
| CRITICAL | Current profile used as historical: Current primary team differs from historical leaderboard team in 9/12 sampled player-seasons; current primary position is also mutable. | [source](../../reports/phase_01/player_profile_audit.csv) |
| CRITICAL | Potential future-information contamination: The 2019/20 Jamie Vardy profile sample carries current initialMatchesPage dates 2026-10-31T15:00:00.000Z, 2026-10-16T19:00:00.000Z alongside a historical statSeasons entry. | [source](../../data/audit/raw_samples/steps_03_05/profile_outfield_top_goals_2019_2020.json) |
| HIGH | Abandoned/replayed fixture: The 381-entry 2023/24 index contains 380 ordered team pairs; Bournemouth–Luton has two IDs, including abandoned match 4193691 and completed replay. | [source](../../data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json) |
| HIGH | Player match pagination: The bounded retest returned HTTP 400 with error 'Invalid or missing query parameters'. Historical player-to-match pagination remains unverified. | [source](../../data/audit/raw_samples/steps_03_05/player_matches_retest.json) |

[Observation] No missing IDs/team IDs/positions/stat values or duplicate IDs were reported in the three sampled leaderboard tables. Only the first five raw rows of each board were retained, so the full aggregate checks are not independently replayable from raw JSON.

## 11. Technical Limitations

`playerMatches` rejected the checked query; complete historical player-to-match pagination is unresolved. Leaderboards cannot be treated as the player population. Raw samples are intentionally partial. Catalog titles can describe per-90 or percentage values, but the checked responses do not publish full metric definitions. Current `playerData.initialMatchesPage` can contain later matches and must not be used as a historical season index.

## 12. Level 2+ Feasibility Assessment

| Component | Verdict | Evidence and limitation |
|---|---|---|
| Season-level player statistics | CONDITIONAL_PASS | Populated goals, minutes and saves tables for all six seasons; optional metric completeness and definitions remain unchecked. |
| Player profiles | CONDITIONAL_PASS | Twelve IDs and season entries verified; current team/position are not historical, and full player coverage is unknown. |
| Match index | CONDITIONAL_PASS | All six fixture indexes accessible and two lineups sampled; `playerMatches` failed and an abandoned/replayed pair requires status-aware handling. |

## 13. Recommended Data Collection Architecture

[Inference] Use direct HTTP JSON as the primary acquisition method. First retrieve season metadata and numeric IDs; then bounded season-stat tables; then supplemental player profiles and season-scoped `playerStats` only for IDs in a verified reference population; then season fixture indexes. Use selective `matchDetails` where player-to-match links or missing fields require it. If `playerMatches` remains unavailable, selective match-detail requests are the fallback for those links. No Selenium need was demonstrated.

| Acquisition approach | Role | Observed constraint |
|---|---|---|
| HTTP JSON season tables | Primary player-stat source | One metric table per request; denominator and optional metric definitions unresolved. |
| Player/team supplemental requests | Identity and season-scoped detail | Current profile fields must not be backdated; historical team stints need validation. |
| Historical league match index | Season fixture IDs, dates, teams and results | Abandoned/replayed entries require status-aware handling. |
| Selective match-detail fallback | Sampled lineups and player-to-match evidence | Response is larger; use only for specific missing links or fields. |

Expected JSON shapes observed: `leagues.details`, `stats.seasonStatLinks` and `fixtures.allMatches`; `leagueseasondeepstats.statsList` plus `statsData[]` entries with player/team IDs, position code, `statValue` and `substatValue`; `playerData.statSeasons` and current `primaryTeam`; `playerStats.topStatCard`/`statsSection`; `matchDetails.general`/`header`/`content.lineup`. Treat optional keys and position-specific sections as nullable until further checks.

Store raw responses (or complete bounded response archives), request URL/time/status, content hash, season string and numeric ID, field title/format/unit, and schema version. Keep normalized season-stat, profile, player-team-season, fixture and match-link tables separate. Cache completed seasons with a documented refresh policy. Reuse the existing configurable timeout, 0.7-second minimum request interval, 64-attempt audit budget and bounded transient retries as a cautious pilot baseline; tune only after observing service behavior. Log errors and resume by idempotent keys. Deduplicate by season, stat, player and team, while preserving multiple team stints and both raw IDs for abandoned/replayed matches. Validate nulls, types, units, domains, date windows and profile-to-season joins before expanding volume.

## 14. Outstanding Risks

- No complete season-specific player roster denominator; coverage and omission bias cannot be measured.
- `playerMatches` parameters or alternative historical pagination remain unresolved.
- Current profile attributes and current match page data can contaminate historical records.
- Optional metrics, especially ratings and position-specific fields, need value and definition checks beyond catalog presence.
- Saved raw subsets limit independent replay of aggregate counts; a later pilot must retain complete bounded evidence.

## 15. Go / Conditional Go / No-Go Recommendation

**Conditional Go for a small, instrumented historical collection pilot. No-Go for an unrestricted full historical crawl at this point.** The pilot should establish a full player denominator, verify a stratified set of optional metrics and historical joins, resolve player-match pagination or a selective lineup fallback, and confirm status-aware fixture handling. Reassess the full crawl only after those checks pass. Transfermarkt matching and any modeling work remain outside this phase.
