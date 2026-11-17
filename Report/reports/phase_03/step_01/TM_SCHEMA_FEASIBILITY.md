# Transfermarkt Schema Feasibility (Phase 3, Step 1)

**Conclusion:** the required schema exists. Historical valuations are a real observation table, with caveats on traceability and on club columns.

Headers, row counts and null counts come directly from the downloaded CSVs (`evidence/step1_audit_results.json`). Derivation notes come from the repository's dbt SQL and `models.yml`. CSVs carry no types, so "observed format" describes the text. DuckDB column types are **unverified**.

## 1. Tables inspected

| Table | Rows | Columns | Basis |
|---|---:|---:|---|
| `player_valuations` | 656,301 | 6 | Records |
| `players` | 50,149 | 26 | Records |
| `transfers` | 175,165 | 10 | Records |
| `clubs` | 796 | 17 | Records |
| `competitions` | 65 | 11 | Records |
| `appearances` | 1,894,350 | 13 | Records |
| `games`, `club_games`, `game_events`, `game_lineups`, `countries`, `national_teams` | README only | Unknown | **Not inspected** |

## 2. Logical requirements mapped to physical fields

| FB69 requirement | Physical field | Status |
|---|---|---|
| Transfermarkt player ID | `player_valuations.player_id`, `players.player_id` | Verified; unique in `players`; 0 orphan valuations |
| Valuation date | `player_valuations.date` | Verified; `YYYY-MM-DD`; 0 unparseable |
| Market value | `player_valuations.market_value_in_eur` | Verified; 0 null |
| Currency/unit | **No column.** EUR is implied by the column name and the `models.yml` description | Documented, not independently verified |
| Source record ID | **None.** | Use `(player_id, date)` plus file SHA-256; that key had 0 duplicates in 656,301 rows |
| Player name | `players.name`, `first_name` (3,164 null), `last_name` | Verified |
| Date of birth | `players.date_of_birth`; format `1978-06-09 00:00:00` | Verified; 49 null, 0 unparseable |
| Nationality | `players.country_of_citizenship`, single value | Verified; 269 null |
| Position | `players.position`, `sub_position` | Verified; `Missing` = 586. Present-day profile value |
| Club | `clubs.club_id`, `name`, `domestic_competition_id` | Verified |
| Competition | `competitions.competition_id`; EPL = `GB1` (`premier-league`) | Verified |
| Historical player-club relation | `appearances.player_club_id` per game; `transfers.from_club_id`, `to_club_id` | Verified |

The `players.url` value contains `/spieler/<player_id>` for all 50,149 rows, which supports ID traceability back to the Transfermarkt profile.

## 3. Valuation table quality

| Check | Result |
|---|---|
| Date range | 2000-01-20 to 2026-06-12 |
| Players | 41,528 (8,621 players have no valuation) |
| Duplicate or conflicting `(player_id, date)` | 0 and 0 |
| Null or unparseable values | 0 |
| Non-integer values | 0 |
| Zero values | 1 row (player `60096`, 2008-03-17), outside the research window |
| Negative values | 0 |
| Value range | 0 to 200,000,000; median 500,000 |

The upstream dbt model tests `(player_id || date)` uniqueness, which agrees with the measured result.

## 4. Fields that must not be used as historical facts

| Field | Why |
|---|---|
| `players.market_value_in_eur` | The dbt SQL takes the **latest** valuation per player: a current value. Forbidden by `CLAUDE.md`. |
| `players.highest_market_value_in_eur` | Career maximum across all dates, which leaks the future. Forbidden. |
| `transfers.market_value_in_eur` | Value at transfer time, not a valuation observation; 68,160 null. Not part of the target rule. |
| `player_valuations.current_club_id` | **Not a pure historical fact.** The SQL uses the latest transfer on or before the valuation date, then **falls back to the player's present-day club**. |
| `player_valuations.player_club_domestic_competition_id` | Derived from the club above; 92,973 null. |
| `player_valuations.current_club_name` | 3,199 rows say `Unknown`. |
| `players.current_club_id`, `current_club_name`, `last_season` | Present-day profile. |
| `appearances.player_current_club_id` | Present-day club, despite being in a game-level table. Use `player_club_id`. |

**Measured:** comparing `player_valuations.current_club_id` with the club in that player's latest EPL game in the prior 30 days gave 5,642 agreements and 131 disagreements out of 5,773 (2.3% disagree). Treat it as supporting evidence only, and use `appearances.player_club_id` as the historical club signal.

## 5. Other data quality notes

- `clubs.total_market_value` is 100% null (796 of 796).
- `transfers` has 488 rows dated after 2026-09-05, up to 2030-06-30, so it needs date filtering before any use.
- `clubs.domestic_competition_id = 'GB1'` returns 37 clubs. That reflects each club's latest known league, so it is not a season membership record. `appearances` gives exactly 20 clubs in each research season.

## 6. Conclusion for Step 2

Normalize `player_valuations`, `players`, `clubs`, `competitions`, `appearances` (EPL scope for evidence) and `transfers`. Add a synthetic lineage key built from `(player_id, date)`, and record that it is derived rather than source-native.
