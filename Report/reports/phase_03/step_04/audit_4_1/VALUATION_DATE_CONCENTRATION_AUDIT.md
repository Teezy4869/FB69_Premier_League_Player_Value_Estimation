# Valuation Date Concentration Audit (Step 4.1)

Date: 2026-11-05. Results: `evidence/step_04_1_audit_results.json`, `evidence/step_04_1_followups.json`, `evidence/target_quality_flags.parquet`.

**Conclusion:** 2020-04-08 is a real date in the source and a mass update. The value changes follow a birth-year rule rather than anything specific to each player. These 491 values look like earlier valuations scaled by 0.8 or 0.9. **Nothing was replaced or changed.**

## 1. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Is it a genuine source date? | **Yes.** It's the value of the raw `datum_mw` field, passed through the source's dbt model | Records and source code |
| Is it a mass update? | **Yes.** 12,111 records across 32 competitions on one day, about 3× the next largest date | Records |
| Are there separate update and effective timestamps? | **No.** The published table has only `date`, and the model has no other date except a season taken from the file path | Records and source code |
| Does the source documentation explain it? | **No.** I found no mention in the dataset's README or model | Source documents |
| What does the date mean: when the value took effect, or when it was published? | **Unknown** | Cannot be established |
| Why did values change? | **Externally reported as a pandemic adjustment, and the data pattern fits exactly.** Not stated by the dataset, and I read press coverage rather than a primary Transfermarkt notice | External plus records |
| Are there similar concentrations in other seasons? | **Yes, but of a different kind.** See section 4 | Records |

## 2. Source lineage

From the [upstream model](https://raw.githubusercontent.com/dcaribou/transfermarkt-datasets/e44f186d6f06dd8452aaf54c7921ba66c961f637/dbt/models/base/transfermarkt_api/base_market_value_development.sql) at the pinned commit:

- `date` is parsed from `datum_mw`. `market_value_in_eur` comes from `mw`.
- Dates in the future are truncated to the build date. This doesn't affect any cutoff here.
- **Same-day duplicates are removed upstream, keeping one row.** Rows with no value (`-`) or no date are also dropped.

**Consequence not reported in Step 4:** "0 same-date conflicts" and "0 missing values" describe the published table. They can't show that no conflict or gap ever existed in Transfermarkt's data, so `AMBIGUOUS_VALUATION` can't occur with this source.

## 3. What happened on 2020-04-08

| Measure | All TM players | Selected 2019/20 targets |
|---|---:|---:|
| Records with a previous value | 12,105 | 491 |
| Values that fell | 99.88% | **491 of 491** |
| Median ratio, born before 1998 | **0.80** (n=10,076) | **0.80** (n=425) |
| Median ratio, born 1998 or later | **0.90** (n=2,023) | **0.90** (n=66) |
| Near the expected ratio for their cohort | 9,463 and 1,990 | 424 of 425 and 66 of 66 |

**The break by birth year is sharp:**

| Birth year | 1994 | 1995 | 1996 | 1997 | **1998** | 1999 | 2000 | 2001 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Median ratio | 0.8 | 0.8 | 0.8 | 0.8 | **0.9** | 0.9 | 0.9 | 0.9 |

**Compared with other large batches:** the next 11 largest dates all have a median ratio of 1.0, and 26–44% of values fell.

**External reports:** [Calcio e Finanza](https://www.calcioefinanza.it/2020/04/09/valore-rose-serie-a-mercato-transfermarkt-juve-inter-milan/), [Empire of the Kop](https://www.empireofthekop.com/2020/04/09/value-of-liverpools-playing-squad-plunges-205m-due-to-covid-19-transfer-expert-says-prices-will-drop/) and [Eurosport](https://www.eurosport.com/football/transfers/2019-2020/football-news-transfer-expert-seidel-fees-may-plummet-due-to-coronavirus_sto7713444/story.shtml) describe a Transfermarkt cut in April 2020, with search summaries giving 20% for players born before 1998 and 10% for those born in 1998 or later. I read these through search summaries, so the exact wording wasn't checked.

**What I can't say:** whether these values should be considered true market estimates at the time. Transfermarkt published them as such. Treating them as "wrong" would be my judgment, not a finding.

## 4. Other seasons

| Season | Usable | Top date | On top date | Share | Distinct dates | Second date | Top-date EPL values down / up / same | TM records that day |
|---|---:|---|---:|---:|---:|---|---|---:|
| 2019/20 | 498 | **2020-04-08** | 491 | **98.59%** | 5 | 2019-12-10 (3) | **491 / 0 / 0** | 12,111 |
| 2020/21 | 515 | 2021-03-18 | 477 | 92.62% | 13 | 2021-03-10 (10) | 225 / 97 / 143 | 567 |
| 2021/22 | 528 | 2021-12-23 | 384 | 72.73% | 23 | 2022-03-29 (91) | 166 / 34 / 180 | 600 |
| 2022/23 | 542 | 2022-11-03 | 328 | 60.52% | 24 | 2023-03-16 (163) | 113 / 69 / 136 | 598 |
| 2023/24 | 567 | 2023-12-19 | 390 | 68.78% | 18 | 2024-03-14 (134) | 137 / 88 / 156 | 1,949 |
| 2024/25 | 545 | 2024-12-16 | 291 | 53.39% | 26 | 2025-03-18 (204) | 59 / 69 / 161 | 750 |

Concentration itself is normal. Values are revised in batches, and a large share of players never change value at a batch. Only 2019/20 has a one-direction, birth-year pattern.

From 2021/22 on, a typical season has a November or December batch and a smaller March batch. In all seasons, the next valuation often arrives just after the cutoff: median 5 to 24 days in most seasons, and 79 in 2019/20. Those are excluded by the approved rule.

## 5. Effect on the 491 targets

| Measure | From the selected date | From the previous valuation |
|---|---:|---:|
| Median age at cutoff | 109 days | **229 days** |
| Share of the players' games after that date | 25.33% | **52.72%** |

Most previous valuations are from one earlier batch: 372 on 2019-12-10, and 64 on 2020-03-09.

**Interpretation:** the last player-specific judgment behind most 2019/20 targets may predate the pandemic stoppage by months. So the Step 4 age figures understate how old the information is for this season. Across all seasons, this timing view moves games-after-valuation from 41.09% to 45.48%.

The next valuation after the batch arrived a median of 188 days later, with a median ratio of 1.0.

## 6. What this means

- **2019/20 targets share an across-the-board level shift** set by birth year. Across seasons, comparing values without accounting for this may mix it up with real change. Age effects in 2019/20 may also be partly built in, because the cut depends on birth year.
- **This doesn't break the approved rule.** The rule asks for the latest valid valuation on or before the cutoff, and these are.

## 7. Handling

No date or value was changed. `evidence/target_quality_flags.parquet` has one row per player-season, with `on_2020_04_08_batch`, the previous value and date, the ratio, and age and games counted from the previous valuation. It's ready to join in Step 5.
