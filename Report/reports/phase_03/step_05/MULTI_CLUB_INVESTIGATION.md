# Multi-Club Investigation (Phase 3, Step 5)

Date: 2026-11-05. Row-level evidence: `evidence/multi_club_investigation.csv`, `evidence/multi_club_summary.json`.

**Conclusion:** both counts are correct, and they answer different questions. Neither was chosen over the other: both original columns stay, and an explicit class column is added. It doesn't change any row, feature or target.

## 1. Actual definitions

From `src/collection/remediation_population.py`, lines 131–141:

```python
confirmed_team_count = len(teams where participation_status is STARTED or SUBSTITUTED_ON)
associated_team_count = len(teams from the player's team relations or matchday squads)
is_multi_club = (associated_team_count > 1) or (confirmed_team_count > 1)
```

| Count | Definition | Question it answers |
|---|---|---|
| **61** (`confirmed_team_count >= 2`) | Confirmed appearances for two clubs | Did he play for two clubs in the EPL that season? |
| **80** (`is_multi_club`) | Appears in the matchday squad of two clubs, whether or not he played for both | Was he listed with two clubs that season? |

## 2. The 19 difference

| Class | Rows | Clubs with appearances | Second club's evidence |
|---|---:|---:|---|
| `MULTI_CLUB_CONFIRMED_APPEARANCES` | 61 | 2 | Confirmed appearances |
| `MULTI_CLUB_SQUAD_ONLY` | 19 | 1 | Only `UNKNOWN` bench rows, with 0 confirmed appearances |
| `SINGLE_CLUB` | 3,182 | 1 | None; no row has a second club in any squad row |

**By season:**

| Season | Confirmed appearances | Squad only |
|---|---:|---:|
| 2019/20 | 7 | 0 |
| 2020/21 | 8 | 3 |
| 2021/22 | 9 | 3 |
| 2022/23 | 15 | 6 |
| 2023/24 | 10 | 2 |
| 2024/25 | 12 | 5 |
| **Total** | **61** | **19** |

**Independent check:** Transfermarkt game records, used here only as audit evidence, show **2 clubs for all 61** and **1 club for all 19**, and that one is the club where FotMob confirms appearances.

**Typical squad-only cases** are players named on the bench before a move: Diogo Jota 2020/21 (19 games for Liverpool; 1 Wolves bench row) and Neto 2024/25 (2 games for Bournemouth; 33 Arsenal bench rows). Row counts and club names are from the data; the reasons for the moves weren't researched.

**Bench participation:** these rows are `UNKNOWN` in FotMob, and the release doesn't resolve them. Transfermarkt's lack of a game supports no appearance, but this stays evidence rather than proof.

## 3. Effect on integration

| Concern | Finding |
|---|---|
| Is the source one row per player-season? | Yes: 3,262 rows, including all 80 |
| Is a player duplicated by club? | No. Club rows live in a separate table |
| Do season metrics cover both clubs? | Yes for the 61: appearances equal the confirmed total on 61 of 61, and metric sums over all clubs' matches agree (see `LEAKAGE_AUDIT.md`) |
| Is an aggregation rule needed? | **No.** FotMob's values are already season totals. I invented none |
| Does a target get selected per club? | No. One decision per player-season |
| Is club detail kept? | Yes: `player_team_season_evidence.parquet`, 3,342 rows, including unverified relations |

## 4. Columns delivered

- `is_multi_club`, `multi_club_status`, `confirmed_team_count`, `associated_team_count`: unchanged source values.
- `multi_club_class`: new, derived from these.

**Reporting guidance:** say which one is meant. Use 61 for "played for two clubs", and 80 for "listed with two clubs".
