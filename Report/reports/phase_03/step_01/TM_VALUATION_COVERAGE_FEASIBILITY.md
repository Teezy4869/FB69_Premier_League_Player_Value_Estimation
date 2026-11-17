# Transfermarkt Valuation Coverage Feasibility (Phase 3, Step 1)

**Conclusion:** existence coverage is strong in all six seasons. Timeliness is the real problem: under the approved rule, most selected valuations would be more than 90 days old, and part of each season's performance happens after the valuation date.

## Scope of these numbers

**What this measures:** TM's own EPL population, meaning TM player IDs with a `GB1` appearance inside each season window. These are aggregate counts. No target table was written, and FotMob and TM players were not joined.

**What it does not measure:** coverage of the 3,262 FotMob rows. That is only known after Steps 3 and 4.

## Evidence levels

| Claim | Level |
|---|---|
| Table contents, counts, dates, staleness for TM's EPL population | **Verified from actual records** |
| Cause of paused updates; PR #378 repair | Verified from repository documentation |
| EUR as the unit | Verified from repository documentation only |
| Cause of the April 2020 batch (see below) | Inferred, not verified |
| Coverage of the FotMob population | **Unknown; requires Steps 3 and 4** |
| Whether every batch date equals the real Transfermarkt update date | Unknown |

## Season cutoffs

Dates come from the last completed match in frozen FotMob fixtures, with external sources as corroboration. **`seasons.yaml` is a Step 4 deliverable and was not created here.**

| Season | Cutoff | Corroboration | Type |
|---|---|---|---|
| 2019/20 | 2020-07-26 | [premierleague.com/news/1702418](https://www.premierleague.com/news/1702418) | Official league |
| 2020/21 | 2021-05-23 | [NBC Sports](https://nbcsports.com/soccer/news/premier-league-2020-21-season-dates-schedule-stream-how-to-watch) | Secondary |
| 2021/22 | 2022-05-22 | [Aston Villa](https://www.avfc.co.uk/news/2022/may/22/gallery--villa-complete-campaign-at-the-etihad-stadium), [Sky Sports](https://www.skysports.com/football/news/11661/12615149/man-city-win-sixth-premier-league-title-after-stunning-final-day) | Club and media |
| 2022/23 | 2023-05-28 | [Manchester United](https://www.manutd.com/en/news/detail/premier-league-announces-important-change-to-final-day-schedule-for-may-2023) | Club, relaying the league |
| 2023/24 | 2024-05-19 | [premierleague.com/en/news/3832048](https://www.premierleague.com/en/news/3832048) | Official league |
| 2024/25 | 2025-05-25 | [USA Network](https://www.usanetwork.com/usa-insider/where-to-watch-premier-league-championship-sunday-may-25-2025) | Secondary |

Only two have a direct official league source so far. All six agree with the frozen fixtures, and Step 4 should finish the evidence.

## Coverage

| Season | TM EPL players | Valuation on or before cutoff | Only after cutoff | No valuation | Coverage |
|---|---:|---:|---:|---:|---:|
| 2019/20 | 512 | 496 | 14 | 2 | 96.9% |
| 2020/21 | 522 | 513 | 9 | 0 | 98.3% |
| 2021/22 | 508 | 505 | 3 | 0 | 99.4% |
| 2022/23 | 554 | 542 | 8 | 4 | 97.8% |
| 2023/24 | 570 | 568 | 2 | 0 | 99.6% |
| 2024/25 | 562 | 545 | 11 | 6 | 97.0% |
| **Total** | **3,228** | **3,169** | **47** | **12** | **98.2%** |

There were 0 same-date conflicts on the latest eligible date in any season.

## Staleness of the latest eligible valuation

Reporting bins from `CLAUDE.md`. The 90-day line is shown for information only and is **not** an approved exclusion rule.

| Season | 0-30 | 31-60 | 61-90 | 91-180 | >180 | Median days | Max days | At or under 90 days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 1 | 0 | 0 | 492 | 3 | 109 | 229 | 0.2% |
| 2020/21 | 5 | 4 | 490 | 8 | 6 | 66 | 731 | 97.3% |
| 2021/22 | 15 | 90 | 4 | 392 | 4 | 150 | 332 | 21.6% |
| 2022/23 | 2 | 4 | 173 | 8 | 355 | 206 | 347 | 33.0% |
| 2023/24 | 1 | 5 | 150 | 412 | 0 | 152 | 166 | 27.5% |
| 2024/25 | 2 | 5 | 213 | 314 | 11 | 160 | 724 | 40.4% |
| **Total** | **26** | **108** | **1,030** | **1,626** | **379** | | | **36.7%** |

So 2,005 of 3,169 (63.3%) would be over 90 days old, and a 90-day exclusion would remove almost all of 2019/20.

## Why: valuations arrive in batches

| Season | Most common selected date | Players on that date | League games after that date (of 380) |
|---|---|---:|---:|
| 2019/20 | 2020-04-08 | 489 | 92 (24%) |
| 2020/21 | 2021-03-18 | 476 | 94 (25%) |
| 2021/22 | 2021-12-23 | 378 | 211 (56%) |
| 2022/23 | 2022-11-03 | 328 | 254 (67%) |
| 2023/24 | 2023-12-19 | 390 | 211 (56%) |
| 2024/25 | 2024-12-16 | 291 | 221 (58%) |

Across all leagues, valuation records spike in June each year (for example 19,543 in 2023-06 against 2,086 in 2023-05). Those post-season updates fall after every cutoff from 2020/21 onward, so the rule excludes them by design.

The 2020-04-08 batch sits in a month with 12,416 records, against 1,255 in March and 99 in May. It may be a pandemic-related revaluation, but I did not verify that. 2019/20 labels could therefore differ from other seasons for a non-performance reason.

## Research validity issue for the owner

The approved rule prevents *future valuation leakage*, and that remains correct. It creates a different problem that the rule does not address:

- **FotMob features cover the whole season,** but the selected valuation typically predates a large share of it. In 2022/23, 67% of league games came after the most common selected date.
- **Effect:** the model would partly "predict" a value that was set before some of the performance happened. This is not leakage of target information into features in the usual sense, and it does not violate any locked rule, but it weakens the claim that season performance explains the target.

I have **not** changed the policy and do not propose doing so silently. The owner's options are in `PHASE3_STEP1_REPORT.md`. The decision is due before Step 4, and it does not block Step 2.

## Other observations

- Yearly row counts drop after 2023 across all leagues: 57,576 rows in 2023 against 45,376 in 2024, and 27,890 against 19,628 players. The EPL population above does not show a matching coverage drop.
- A cutoff based on the last match date treats the valuation date as a plain date. No time-zone adjustment affects these dates, since all final-day matches kicked off in the afternoon UK time.
