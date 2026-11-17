# Transfermarkt Identity Feasibility (Phase 3, Step 1)

**Conclusion:** hybrid matching is feasible. Name plus date of birth is very discriminating on each side, and game-level club history gives independent evidence. Real match quality is unknown, because **no FotMob-to-Transfermarkt comparison was run in this step**. Every number below was computed within one source.

## 1. Field availability

| Evidence | FotMob (1,343 Confirmed identities) | TM EPL players 2019-2025 (1,328) | Usable for |
|---|---|---|---|
| Stable ID | `player_id`, 0 missing | `player_id`, unique | Keys only; **the ID spaces are unrelated** |
| Shared ID bridge | **None**: 0 of 1,343 raw profiles mention Transfermarkt | None found in inspected tables | Not available |
| Full name | `profile_name`, 0 missing; `lineup_name`, 70 missing | `name`, 0 missing | Candidate generation |
| Date of birth | `birth_date`, 0 missing | `date_of_birth`, 0 missing | Primary discriminator |
| Nationality | `nationality_name` and code, 0 missing | `country_of_citizenship`, 6 missing | Supporting |
| Position | `current_position`, present-day, mixed labels | `position`, `sub_position`, present-day | Weak support only |
| Historical club | `player_team_seasons`: club per season | `appearances.player_club_id`: club per game | Strong and historical |

## 2. Discrimination within each source

| Measure | FotMob Confirmed | TM EPL | TM all players |
|---|---:|---:|---:|
| Identities | 1,343 | 1,328 | 50,149 |
| Normalized name shared by several IDs | 1 group (2 IDs) | 0 | 982 groups (2,389 IDs) |
| Name and DOB shared by several IDs | 0 | 0 | 1 group (2 IDs) |
| DOB shared by several IDs | Not computed | 100 groups (209 IDs); maximum 3 per date | Not computed |

What this means:

- **Name alone is unsafe:** 982 name groups collide across the full TM table, so candidates must be searched with DOB and club support. This backs the rule against name-only matches.
- **DOB alone is unsafe:** 209 of 1,328 TM EPL players share a birth date with another player.
- **Name plus DOB is strong within each source,** but that does not show the two sources *agree* with each other.
- **TM duplicate to check:** the one TM name and DOB collision may be a duplicate profile or a real coincidence. Step 2 should inspect it.

## 3. Population comparison (counts only)

| Season | FotMob Confirmed | TM EPL players | Difference | FotMob appearance rows | TM appearance rows | Difference |
|---|---:|---:|---:|---:|---:|---:|
| 2019/20 | 515 | 512 | -3 | 10,614 | 10,578 | -36 |
| 2020/21 | 524 | 522 | -2 | 10,393 | 10,356 | -37 |
| 2021/22 | 537 | 508 | **-29** | 10,485 | 10,369 | **-116** |
| 2022/23 | 554 | 554 | 0 | 11,345 | 11,345 | 0 |
| 2023/24 | 570 | 570 | 0 | 11,384 | 11,384 | 0 |
| 2024/25 | 562 | 562 | 0 | 11,567 | 11,567 | 0 |
| **Total** | **3,262** | **3,228** | **-34** | 65,788 | 65,599 | -189 |

Each season has 380 TM games and 20 clubs.

- **Latest three seasons agree exactly on both counts.** That is strong independent support for both sources, though equal counts do not prove the same players are behind them.
- **Earlier seasons fall short on the TM side,** worst in 2021/22. **The cause is unknown.** Since every game exists, whole matches are not missing; individual player appearances are. A likely consequence is that some FotMob players will lack TM game-level club evidence in those seasons, and possibly a TM profile. That needs measuring in Steps 2 and 3.
- **Identities:** 1,343 vs 1,328 is a gap of 15, which bounds nothing exactly but is small.

## 4. Known risks

| Risk | Handling proposed for Step 3 |
|---|---|
| DOB disagreement between sources, including off-by-one dates from time-zone handling | Measure on a labeled sample; do not assume exact equality |
| Name forms differ (171 FotMob identities have two forms; 51 change across seasons; 229 non-ASCII) | Compare all name variants, keeping raw values |
| Nationality uses different vocabularies; dual nationals carry only one value | Map vocabularies; treat as support only |
| Present-day position and club | Never use as identity proof |
| 34 FotMob player-seasons with no equal count on the TM side | Keep as `UNMATCHED` or `REVIEW_REQUIRED`; do not force |
| Club naming across sources | A small reviewed team crosswalk: FotMob has 27 teams; TM has 20 clubs per season |

## 5. Proposed evidence hierarchy (not implemented)

1. **Deterministic:** normalized name and exact DOB, unique on both sides, and not contradicted by club evidence.
2. **Candidate:** same DOB with a similar name, or a similar name with overlapping club-season. Candidates go to scoring and review.
3. **Support only:** nationality, position.
4. **Human review:** everything ambiguous. Thresholds stay unset until a labeled sample exists and the owner approves them.

## 6. Workload estimate

Not estimated. A credible number requires comparing the sources, which is out of scope for this step.
