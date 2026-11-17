# FotMob v3.1 Input Audit (Phase 3, Step 1)

**Conclusion:** the input is complete and usable. The Confirmed population reconciles to **3,262 of 3,262** rows with no discrepancy.

Measurements: `evidence/step1_audit_results.json`, `evidence/step1_followups.json`.

## 1. Location and integrity

| Item | Value |
|---|---|
| Release | `data/releases/fotmob_epl_2019_2025_v3_1` |
| Version / parent | `fotmob_epl_2019_2025_v3_1` / `fotmob_epl_2019_2025_v3` |
| Created | 2026-11-03T08:46:50Z |
| Release's own verdict | **CONDITIONAL_GO**; all six seasons are `CONDITIONAL_PASS` |
| Manifest SHA-256 | `9aa00b227b2dbf9a6004258ff94c25e825d7c5cfd45a365cb94f5f98863fbf93` |
| Manifest check | 38 listed files recomputed: 0 hash, 0 byte, 0 row mismatches; none missing; the only unlisted file is the manifest itself |
| Main table SHA-256 | `curated/confirmed_appeared_player_seasons.parquet`: `7be1751966e8a377a1b8dedb275e903e0d76187ff11dc5503429a620d8dcd890` |

Per-file hashes for all release tables are in the evidence JSON. "Frozen" is by convention only: the files have no read-only attribute and there is no git history, so **the manifest hash check is the only tamper control**.

## 2. Population reconciliation

The status encoding differs by table, so Phase 3 must not filter on a literal `Confirmed`:

| Table.column | Confirmed value | Other value |
|---|---|---|
| `normalized/complete_player_season_classification.population_category` | `CONFIRMED_APPEARED` (3,262) | `UNVERIFIED` (790) |
| `normalized/player_seasons.evidence_status` | `APPEARED` (3,262) | `UNKNOWN_PARTICIPATION` (790) |
| `curated/player_season_metrics_wide.population_status` | `APPEARED` (3,262) | `UNKNOWN_PARTICIPATION` (790) |
| `curated/confirmed_appeared_player_seasons.population_status` | `APPEARED` (3,262) | none |

| Season | Confirmed | Unverified | Total | Completed matches |
|---|---:|---:|---:|---:|
| 2019/2020 | 515 | 99 | 614 | 380 |
| 2020/2021 | 524 | 117 | 641 | 380 |
| 2021/2022 | 537 | 142 | 679 | 380 |
| 2022/2023 | 554 | 145 | 699 | 380 |
| 2023/2024 | 570 | 164 | 734 | 380 |
| 2024/2025 | 562 | 123 | 685 | 380 |
| **Total** | **3,262** | **790** | **4,052** | 2,280 |

- **Expected vs actual:** 3,262 vs 3,262, difference 0.
- **Confirmed non-appeared:** the table exists with 0 rows, so "Confirmed" here means *confirmed appeared*.
- **Set checks, all 0:** curated vs normalized Confirmed in both directions; Confirmed vs classification; Confirmed intersecting Unverified; wide `APPEARED` minus curated; Confirmed with no `players` row; Confirmed with zero appearances.
- **Why Unverified is excluded:** all 790 have reason `SEASON_WIDE_NEGATIVE_COVERAGE_UNPROVEN`.

## 3. Grain

- **One row per player-season.** `(season_id, player_id)` has 3,262 unique keys in 3,262 rows, with 0 null keys and 0 non-numeric player IDs.
- **Unique people:** 1,343 identities behind the 3,262 rows. Players by seasons present: 1: 569, 2: 259, 3: 183, 4: 145, 5: 76, 6: 111.
- **Season labels:** the source uses `2019/2020`, not `2019/20`. Season IDs are 14022, 15382, 16390, 17664, 20720, 23685.
- **Matches:** the table has 2,281 rows because of one abandoned fixture, `4193691` on 2023-12-16 (`CANCELLED_OR_ABANDONED`); 2,280 are completed.

## 4. Multi-club records

The curated table is already one row per player-season. Club detail sits in `normalized/player_team_seasons` (4,135 rows overall, 3,342 for this population).

| `is_multi_club` | `confirmed_team_count` | `associated_team_count` | Rows |
|---|---:|---:|---:|
| false | 1 | 1 | 3,182 |
| true | 2 | 2 | 61 |
| true | 1 | 2 | **19** |

**Discrepancy to carry forward:** the two multi-club measures disagree. `is_multi_club` gives 80 rows, `confirmed_team_count >= 2` gives 61. The 19 extra rows have one confirmed club plus one association marked `UNVERIFIED`/`UNRESOLVED`. Step 5 must say which definition it reports.

## 5. Identity fields (1,343 Confirmed identities)

| Field | Missing | Note |
|---|---:|---|
| `player_id` | 0 | String of digits; `players` has 1,757 unique rows in total |
| `profile_name` | 0 | |
| `lineup_name` | 70 | Differs from `profile_name` for 171 identities |
| `player_name` (season table) | 0 | 51 IDs carry more than one name across seasons, so 1,394 distinct names |
| `birth_date` | 0 | All `YYYY-MM-DD`; range 1981-09-28 to 2009-07-10 |
| `nationality_code`, `nationality_name` | 0 | Single value per player |
| `current_position` | 0 | Mixed vocabulary, for example `Center Back` and `defender` |
| `current_team_id` | **1,343** | Null for everyone |

- **Encoding:** 229 names are non-ASCII, with 0 replacement characters and 0 mojibake markers.
- **Name collisions:** one normalized name is shared by 2 IDs with different birth dates; no name and birth date pair repeats.
- **No Transfermarkt bridge:** all 1,343 raw profiles were scanned and none contains the string `transfermarkt`. 400 contain an `opta` key whose content I did not analyse. No shared ID is available.

**Temporal warning:** profiles were collected on 2026-11-02 and 2026-11-03. `current_position` and nationality are therefore present-day values, not historical facts. `current_position` should not be used as a season-time predictor.

## 6. Features

`curated/confirmed_appeared_player_seasons.parquet` has 114 columns: 8 identifying columns, 53 `m_*` metrics (all `double`), and 53 `s_*` status columns.

Status cells across all rows and metrics (172,886 = 3,262 x 53):

| Status | Cells |
|---|---:|
| `OBSERVED` | 107,247 |
| `MISSING` | 33,621 |
| `UNVERIFIED_POSITION` | 21,272 |
| `OBSERVED_ZERO` | 6,853 |
| `UNSUPPORTED` | 3,262 |
| `OBSERVED_FALLBACK_LEADERBOARD` | 500 |
| `OBSERVED_SOURCE_REVISED` | 95 |
| `CONFLICTING` | 36 |

Non-null counts for the metrics most relevant to later phases:

| Metric | 19/20 | 20/21 | 21/22 | 22/23 | 23/24 | 24/25 | Null total |
|---|---:|---:|---:|---:|---:|---:|---:|
| `m_minutes_played` | 477 | 485 | 496 | 515 | 532 | 520 | 237 |
| `m_expected_goals` | **69** | 433 | 446 | 458 | 460 | 457 | 939 |
| `m_expected_assists` | **96** | 516 | 532 | 549 | 559 | 553 | 457 |
| `m_key_passes` | 0 | 0 | 0 | 0 | 0 | 0 | 3,262 |

Findings for later phases:

- **`m_key_passes` is empty:** every row is null with status `UNSUPPORTED`.
- **xG/xA windows are unknown:** every season is `UNKNOWN_COVERAGE_WINDOW` with blank verified start and end dates. 2019/20 is flagged as suspected partial coverage (xG on 69 of 515 rows).
- **Goalkeepers mostly lack minutes:** of the 237 rows with null minutes, 235 have a goalkeeper metric, and their median confirmed appearance count is 18. So the null means *not collected*, not *did not play*. There are 0 literal zeros in this column.
- **Season-level timing:** metrics are season aggregates. Individual feature windows have not been audited, which is Step 5 work.

## 7. Initial data contract

| Logical entity | Physical source | Grain | Key |
|---|---|---|---|
| `fotmob_player_season` | `curated/confirmed_appeared_player_seasons.parquet` | player-season | `(season_id, player_id)` |
| Population audit | `normalized/complete_player_season_classification.parquet` | player-season | `(season_id, player_id)` |
| Player identity | `normalized/players.parquet` | player | `player_id` |
| Club evidence | `normalized/player_team_seasons.parquet` | player-club-season | `(season_id, player_id, team_id)` |
| Season boundaries | `normalized/matches.parquet` | match | `match_id` |

Rules: IDs stay strings; nulls stay null; `s_*` columns travel with `m_*` columns; no file in the release is ever modified; the release manifest is re-verified at the start of every step.

## 8. Season boundaries from frozen fixtures

| Season | First match (UTC) | Last match (UTC) |
|---|---|---|
| 2019/2020 | 2019-08-09 19:00 | 2020-07-26 15:00 |
| 2020/2021 | 2020-09-12 11:30 | 2021-05-23 15:00 |
| 2021/2022 | 2021-08-13 19:00 | 2022-05-22 15:00 |
| 2022/2023 | 2022-08-05 19:00 | 2023-05-28 15:30 |
| 2023/2024 | 2023-08-11 19:00 | 2024-05-19 15:00 |
| 2024/2025 | 2024-08-16 19:00 | 2025-05-25 15:00 |

External corroboration is in `TM_VALUATION_COVERAGE_FEASIBILITY.md`.

## 9. Existing tests

`tests.collection.test_final_acceptance_release` and `tests.collection.test_final_acceptance_fix`: **28 tests, all passed** in the scratch venv (pyarrow 26.0.1, outside the repo pin). The rest of the repo's test suite was not run.
