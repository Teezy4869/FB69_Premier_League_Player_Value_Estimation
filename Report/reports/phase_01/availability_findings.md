# Phase 1 steps 03–05: availability findings

Collected at (UTC): 2026-11-02T06:58:20.762256+00:00
Seasons: 6; HTTP attempts in this run: 50/64.

## Statistics

The matrix checks 24 candidate features in each of six seasons. `AVAILABLE` means a nonempty direct leaderboard probe; `PARTIAL` means the season catalog lists the field or a sampled player profile returns it; `UNVERIFIED` means the checked sources did not establish the field. `MISSING` in `catalog_status` means missing from that season's `statsList` only.

- General: AVAILABLE 6, PARTIAL 18, EMPTY 0, FAILED 0, UNVERIFIED 0 season-feature checks.
- Attacking: AVAILABLE 6, PARTIAL 30, EMPTY 0, FAILED 0, UNVERIFIED 0 season-feature checks.
- Passing & Creation: AVAILABLE 0, PARTIAL 24, EMPTY 0, FAILED 0, UNVERIFIED 6 season-feature checks.
- Defending: AVAILABLE 0, PARTIAL 30, EMPTY 0, FAILED 0, UNVERIFIED 0 season-feature checks.
- Goalkeeping: AVAILABLE 6, PARTIAL 18, EMPTY 0, FAILED 0, UNVERIFIED 0 season-feature checks.

The three directly fetched tables are `goals`, `mins_played`, and `saves`. Other listed fields have not had all their values downloaded. Per-player `playerStats` samples supply additional fields such as appearances, starts, shots and pass accuracy, but do not establish league-wide completeness. Catalog title stability does not prove unchanged provider definitions.

## Player coverage

The union of three leaderboards is only a sampled player numerator. The league team index does not supply a complete player roster, so the player denominator and coverage percentage remain `UNKNOWN_DENOMINATOR`. Duplicate and multi-team counts refer only to the sampled boards. Numeric position codes are reported as observed; goalkeeper identity is checked against sampled profile positions.

- 2019/2020: 515 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.
- 2020/2021: 524 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.
- 2021/2022: 537 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.
- 2022/2023: 554 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.
- 2023/2024: 570 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.
- 2024/2025: 562 unique sampled IDs across three boards; 20/20 league teams represented; 0 duplicate rows within boards; 0 IDs with multiple team IDs across boards; goalkeeper profile confirmed: True.

## Profiles and match indexes

`playerData` includes player ID, name, birth date, primary position, current primary team and a season-specific `statSeasons` entry. The current team and primary position are mutable and must not be assigned to a past season. Historical team IDs in these reports come from that season's leaderboard.
Historical `leagues?season=` responses supply match IDs, dates, team IDs and results. Two `matchDetails` samples check league identity and lineup player IDs; this supports representative player-to-match links, not a complete relationship table. The `playerMatches` retest status is recorded separately and remains a pagination blocker if it fails.

## Remaining checks before a final audit report

- Establish a defensible full player roster denominator, including transfers and short appearances.
- Check all metric definitions, row missingness, and goalkeeper feature coverage beyond the sampled boards.
- Resolve `playerMatches` historical pagination or document an alternative; inspect the 381-entry 2023/2024 fixture index.
- Verify historical team and position joins without using mutable current profile fields.

## Evidence

Season-level CSV rows link to request URLs, timestamps and representative JSON samples where data was returned. The data dictionary links to sample files across seasons. Request attempts are in `logs/fotmob_steps_03_05_requests.jsonl`. The samples are source subsets and include only a few leaderboard players or fixtures, so they are not a training dataset.
