# Target Construction Report (Phase 3, Step 4)

Date: 2026-11-04. Output: `data/phase_03/targets/target_v1__matching_v2_1/player_season_target.parquet`. Rule version: `latest_valid_on_or_before_season_end_v1`.

**G4 assessment: `PASS` on temporal validity.** Identity reliability is inherited from G3, which stays `CONDITIONAL_PASS`.

**Result:** 3,262 player-season rows, one decision each. 3,195 (97.95%) have a usable target; 67 stay missing, none imputed.

## 1. Verified season cutoffs

Config: `configs/phase_03_seasons.yaml`. Frozen FotMob fixtures and TM games agree on all six dates, independently of the official pages.

| Season | First match | Official season end | Official source | How read |
|---|---|---|---|---|
| 2019/20 | 2019-08-09 | **2020-07-26** | [Premier League](https://www.premierleague.com/news/1702418) | Search summary |
| 2020/21 | 2020-09-12 | **2021-05-23** | [Premier League](https://www.premierleague.com/en/news/1752553) | Search summary |
| 2021/22 | 2021-08-13 | **2022-05-22** | [Premier League](https://www.premierleague.com/en/news/2171434) | Search summary |
| 2022/23 | 2022-08-05 | **2023-05-28** | [Premier League](https://www.premierleague.com/en/news/2264107) | Search summary |
| 2023/24 | 2023-08-11 | **2024-05-19** | [Premier League](https://www.premierleague.com/en/news/3832048) | Fetched directly |
| 2024/25 | 2024-08-16 | **2025-05-25** | [Premier League](https://www.premierleague.com/en/news/3832048) | Fetched directly |

## 2. Method

For each Confirmed player-season:

1. Start from the frozen 3,262-row population.
2. Use the crosswalk's TM ID only for eligible statuses: `AUTO_EXACT`, `AUTO_ADJUDICATED`, `MANUAL_CONFIRMED`.
3. Keep valuations with `valuation_date <= season_end_date`.
4. Drop invalid observations, and select the latest remaining date.
5. Record value, date, age, source record, source row number and file hash.

| Case | Status | Value |
|---|---|---|
| Age up to 90 days | `VALID` | Selected |
| Age over 90 days | `STALE_TARGET` | Selected and kept |
| No eligible identity, only later valuations, or no history | `TARGET_MISSING`, with reason | Null |
| Only invalid observations by the cutoff | `INVALID_VALUATION` | Null |
| Different values on the latest eligible date | `AMBIGUOUS_VALUATION`, all record IDs kept | Null |

**The 90-day line only labels age.** It isn't an exclusion rule. `STALE_TARGET` rows are usable, and exact ages are stored. Any filtering decision belongs to Phase 4.

**Values are read only from `tm_valuation_history`,** so current and career-high profile values can't reach a target. No currency is converted.

## 3. Table

| Column | Meaning |
|---|---|
| `canonical_player_id`, `fotmob_player_id`, `season`, `season_id` | Grain and keys |
| `transfermarkt_player_id` | Null if the identity isn't eligible |
| `season_end_date`, `selected_valuation_date` | Cutoff and chosen date |
| `market_value`, `currency` | EUR as recorded by the source; null if missing |
| `valuation_age_days`, `staleness_bucket` | Exact age and reporting bin |
| `target_status`, `target_missing_reason` | Decision and reason |
| `crosswalk_status`, `crosswalk_method`, `identity_evidence_tier` | Identity basis |
| `source_record_reference`, `source_file_sha256`, `source_row_number` | Lineage to the original CSV row |
| `conflicting_record_references` | Same-date conflicts; none occurred |
| `selection_rule_version`, `matching_version` | Versions |
| `player_games_in_season`, `player_games_after_valuation` | Timing against the player's own games |
| `league_games_in_season`, `league_games_after_valuation` | Timing against all league games |

**Adaptations:** `season` uses the source label (`2019/2020`). `AUTO_ADJUDICATED` is an added crosswalk status, documented in the QA reports.

## 4. Valuation data check

From the normalized history (656,301 rows): 0 missing IDs, 0 invalid dates, 0 missing values, 0 negative values, 0 duplicates, 0 same-date conflicts, and 1 zero value from 2008, flagged and never selected. All values are recorded as EUR by the source. Details are in `step_02/TM_DATA_QUALITY_REPORT.md`.

## 5. Identity sensitivity

| Tier | Player-seasons | Usable | Over 90 days |
|---|---:|---:|---:|
| `AUTO_EXACT_VALIDATED` | 2,577 | 2,549 (98.9%) | 62.2% |
| `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 584 | 551 (94.3%) | 68.4% |
| `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 90 | 87 (96.7%) | 63.2% |
| `AUTO_ADJUDICATED_EXTERNAL` | 8 | 8 (100%) | 75.0% |
| `UNRESOLVED` | 3 | 0 | Not applicable |

## 6. Temporal alignment limitation

**This is a temporal alignment and research interpretation limitation. It is not future-data leakage:** no valuation after the cutoff is used.

FotMob features describe a player's full season, but the selected valuation was often set earlier in it. Overall, **41.09% of players' appearances happened after the selected valuation date**.

| Season | Over 90 days old | Player appearances after valuation | League games after valuation |
|---|---:|---:|---:|
| 2019/20 | 99.80% | 25.38% | 24.44% |
| 2020/21 | 2.91% | 24.91% | 26.07% |
| 2021/22 | 78.03% | 48.58% | 48.94% |
| 2022/23 | 66.97% | 54.72% | 54.71% |
| 2023/24 | 72.66% | 46.84% | 47.62% |
| 2024/25 | 59.63% | 44.16% | 45.06% |
| **Overall** | **63.35%** | **41.09%** | **41.52%** |

*Percentages use usable targets. League figures are the mean per target.*

**What this limits:**

- Full-season features partly describe performance that came after the value was set, so they can't all have informed that valuation.
- A model may still find associations, but those shouldn't be read as "season performance determined this value". Later performance may just reflect a player's existing quality, which the valuation had already captured.
- The degree differs by season, so comparisons between seasons are affected. 2020/21 is much better aligned than 2022/23.

**Valuation timing:** TM updates arrive in batches. The next valuation after the cutoff often comes soon: the median is 5 to 24 days in most seasons and 79 in 2019/20. Those later values are excluded by the approved rule and weren't used for anything except this count.

## 7. Reproducibility

Rebuilding produced a byte-identical target file. `target_manifest.json` records input, code and output hashes. There is no git commit (D5), so script hashes stand in.
