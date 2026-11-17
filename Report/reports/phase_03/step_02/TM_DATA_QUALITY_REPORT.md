# Transfermarkt Data Quality Report (Phase 3, Step 2)

Date: 2026-11-04. Snapshot: `tm_r2_20260905`. Results: `data/transfermarkt/metadata/tm_r2_20260905/quality_results.json`.

**Conclusion:** the valuation table is very clean: 656,300 of 656,301 rows are `VALID`. The remaining issues are about what the source does not record, not about broken rows.

## 1. Requested checks

| Check | Result |
|---|---|
| Missing player IDs | 0 in players; 0 in valuations |
| Duplicate player IDs | 0 (50,149 unique) |
| Invalid player IDs | 0; all digits |
| Duplicate valuation observations | 0 |
| Conflicting same-date valuations | 0 |
| Missing or invalid valuation dates | 0 |
| Valuations dated after the snapshot | 0 |
| Missing or unparseable values | 0 |
| Negative values | 0 |
| Zero values | **1**, flagged `INVALID_VALUE_NONPOSITIVE` |
| Unexpected currency units | None found; see limitation L1 |
| Type failures across all tables | 0 |
| Valuations with no matching player | 0 |
| Value range | 0 to 200,000,000; median 500,000 |

**The one invalid row:** `player_valuations:60096:2008-03-17`, value 0, NK Maribor. It is kept and listed in `tm_valuation_exceptions.csv`. It predates the research period by over 11 years.

## 2. Valuations relative to the research period

Period: 2019-08-09 to 2025-05-25, the first and last match dates.

| Position | Rows | Handling |
|---|---:|---|
| Before the period | 302,143 | Kept: a latest eligible valuation can predate the period |
| Within the period | 293,567 | Kept |
| After the period | 60,591 | Kept in history; Step 4's cutoff rule must exclude them |

**Rows by year (all leagues):**

| Year | Rows | Players |
|---:|---:|---:|
| 2018 | 41,097 | 20,162 |
| 2019 | 46,088 | 22,116 |
| 2020 | 48,749 | 22,807 |
| 2021 | 58,412 | 25,650 |
| 2022 | 59,564 | 26,848 |
| 2023 | 57,576 | 27,890 |
| 2024 | 45,376 | 19,628 |
| 2025 | 45,482 | 18,951 |

Earlier years are in `quality_results.json`. The drop after 2023 is across all leagues and is unexplained. Step 1 found no matching drop in EPL coverage.

## 3. Season coverage

| Season | TM games | Clubs | First and last game | Agrees with FotMob dates | Valuations in season, all leagues | EPL players | EPL appearance rows |
|---|---:|---:|---|---|---:|---:|---:|
| 2019/20 | 380 | 20 | 2019-08-09 to 2020-07-26 | Yes | 42,485 | 512 | 10,578 |
| 2020/21 | 380 | 20 | 2020-09-12 to 2021-05-23 | Yes | 33,876 | 522 | 10,356 |
| 2021/22 | 380 | 20 | 2021-08-13 to 2022-05-22 | Yes | 34,554 | 508 | 10,369 |
| 2022/23 | 380 | 20 | 2022-08-05 to 2023-05-28 | Yes | 36,614 | 554 | 11,345 |
| 2023/24 | 380 | 20 | 2023-08-11 to 2024-05-19 | Yes | 30,760 | 570 | 11,384 |
| 2024/25 | 380 | 20 | 2024-08-16 to 2025-05-25 | Yes | 26,600 | 562 | 11,567 |

TM and FotMob independently agree on the first and last game date of all six seasons, which adds evidence for the season boundaries Step 4 must verify.

## 4. Referential integrity

| Reference | Unmatched rows | Note |
|---|---:|---|
| Valuations to players | 0 | |
| Transfers to players | 0 | |
| EPL appearances to players | 0 | |
| EPL appearances to clubs | 0 | |
| Appearances to games | 0 | |
| Club-season rows to players | 0 | |
| All appearances to players | 2 | Same 2 rows have null `player_name`; non-EPL |
| All appearances to clubs | 11,062 | Non-EPL; `clubs` holds only clubs from tracked leagues |
| Games to competitions | 1,214 | None are `GB1`; competitions absent from `competitions` |
| Clubs to competitions | 20 | Clubs whose league is absent from `competitions` |

The non-zero references are all outside the EPL scope, are left as-is, and don't affect Phase 3 tables.

## 5. Other tables

- **Players:** 49 missing birth dates and 269 missing nationalities overall; all are kept and flagged.
- **8,621 players have no valuation history.** They are kept, and any that get matched will need a missing-target status in Step 4.
- **Possible duplicate player:** IDs `398057` and `461923` are both João Ricciulli, born 1999-10-10, with different positions. Both are kept and flagged `is_name_dob_collision`. This is the only such case in 50,149 players. It may be one person with two profiles, but this was not determined.
- **Transfers:** 488 rows are dated after the snapshot, up to 2030-06-30. They look like scheduled moves or data errors. They are flagged `is_after_snapshot` and must not be treated as completed moves. 1,144 rows have an `Unknown` club. There are no duplicate rows on player, date and both clubs.
- **Appearances:** 3 non-EPL rows have over 130 minutes; no EPL rows do. No negative minutes.

## 6. TM appearance shortfall (R3 from Step 1)

Compared by season, date and final score, using counts only. No player was compared. All groups aligned between the sources, and FotMob rows use participation statuses `STARTED` and `SUBSTITUTED_ON`.

| Season | FotMob rows | TM rows | Difference | Date-score groups | Groups where TM is short | Largest group shortfall | Groups where TM is higher |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 10,614 | 10,578 | -36 | 337 | 32 | 2 | 0 |
| 2020/21 | 10,393 | 10,356 | -37 | 357 | 37 | 1 | 0 |
| 2021/22 | 10,485 | 10,369 | -116 | 346 | 102 | 3 | 0 |
| 2022/23 | 11,345 | 11,345 | 0 | 331 | 0 | 0 | 0 |
| 2023/24 | 11,384 | 11,384 | 0 | 347 | 0 | 0 | 0 |
| 2024/25 | 11,567 | 11,567 | 0 | 333 | 0 | 0 | 0 |

**Verified:**
- TM never exceeds FotMob in any group.
- Shortfalls are thin and scattered, so no whole game is missing.
- No TM EPL game has under 22 rows (minimum 23).

**Inferred, not verified:** with at least 22 rows in every game, the missing rows may be a few individual players, possibly substitutes.

**Still unknown:** the actual cause, and whether the affected players also lack a TM profile. Step 3 can measure this once identities are matched.

**Consequence:** some FotMob player-seasons in 2019/20 to 2021/22 may have no TM club-season row. Step 3 must not read a missing club row as evidence against a match. The FotMob and TM appearance tables can't be treated as equal in these seasons.

## 7. Limitations

| ID | Limitation | Impact | Handling |
|---|---|---|---|
| L1 | EUR rests on the source's column name and documentation, with no currency column and no independent check | Low | `currency_basis` records this; no conversion |
| L2 | Valuation record IDs are derived, not source-native | Low | Uniqueness tested; row number and file hash retained |
| L3 | `source_current_club_*` can fall back to a present-day club | Medium if misused | Named and documented; use `tm_player_club_seasons` for history |
| L4 | `position_profile`, `nationality` and other profile fields are present-day, single values | Medium | Support only in Step 3 |
| L5 | `tm_player_club_seasons` is EPL only and incomplete for 2019/20 to 2021/22 | Medium | Section 6 |
| L6 | Valuations arrive in batches, so age at cutoff is often over 90 days (Step 1) | High, for interpretation | Owner decision D4, Option A: report in Step 4 as a temporal alignment limitation, not as leakage |
| L7 | R2 URLs can change, and the snapshot is only reproducible from local files or if R2 stays unchanged | Low | Hash pins; a mismatch stops acquisition |
| L8 | Upstream Transfermarkt rights not independently verified | Per D2 | Internal academic use only; no raw redistribution |
| L9 | Read-only file attributes can be removed, and there is no version control (D5) | Low | Hash re-checks at each step |
