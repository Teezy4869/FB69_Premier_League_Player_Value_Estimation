# Leakage Audit (Phase 3, Step 5)

Date: 2026-11-05. Research objective: **A, end-of-season estimation** (owner decision D6). Machine-readable table: `evidence/feature_leakage_table.csv`. Window evidence: `evidence/feature_window_audit.csv`.

**Conclusion:** no future valuation or post-cutoff target information reaches a candidate feature, and the target is separated from the features. No critical leakage was found under objective A. Full-season features do include matches after the valuation date, which is a **temporal alignment limitation**, not leakage under A. Under a prediction objective it would be leakage, and that is one reason the objective had to be fixed first.

## 1. Answers to the audit's focus areas

| Area | Finding | Conclusion |
|---|---|---|
| **xG and xA windows** | 2020/21 to 2024/25: season values equal the sum of EPL matches, verified. **2019/20: 4 of 380 matches** | D7 flag; values kept, unavailable for comparison |
| **Season-level aggregations** | 27 metrics and context fields checked against match data or independent totals. Multi-club values cover both clubs | Season totals are as defined |
| **Current profile attributes** | `current_position` and `current_team_id` are **excluded**. Position comes from that season's lineups | No present-day position or club in the dataset |
| **Nationality** | Present-day value from profiles collected in November 2026. Some players changed national team later | Named `nationality_profile_present_day`; **not a historical feature** |
| **Post-season or future information** | No `next_valuation`, career-high or current market value column exists. Tests fail if one appears | None found |
| **Features that may encode the target** | No `m_*` metric encodes market value. FotMob's raw `marketValues` field isn't carried. `target_audit_*` and `temporal_*` columns derive from the target, so they're marked not predictors | Separated by role |
| **Retrospective collection** | All metrics were collected in November 2026. 95 cells are marked `OBSERVED_SOURCE_REVISED` | Whether FotMob changed older values can't be determined |

## 2. Target separation

Every column has a role in `data_dictionary.csv`. Tests fail if a `target_`, `temporal_` or `identity_` column gets a feature role, or if a column has no role.

**These are derived from the target, and must not be used as predictors:** `target_*`, `target_audit_*`, `temporal_*`, `target_on_2020_04_08_batch`.

`identity_evidence_tier` and similar columns describe data quality, and correlate with player profile. They're for sensitivity checks, not prediction.

## 3. Risks that aren't leakage but affect results

| Risk | Evidence | Handling |
|---|---|---|
| Features extend past the valuation date | 41.09% of appearances; 240 player-seasons entirely after, 433 entirely before | Row-level `temporal_*` columns; don't claim that performance determines value |
| 2019/20 targets follow a birth-year cut | 491 of 498 usable | `target_on_2020_04_08_batch`; results with and without 2019/20 (D7) |
| **Age and target are linked by construction in 2019/20** | The cut is 0.8 before 1998 and 0.9 from 1998 | Noted on the age feature |
| Uneven metric coverage across seasons | `m_clearances` is almost only present in 2024/25; `m_goals_prevented` is absent in 2019/20 | Check per-season nulls before using |
| A null may mean no event | xG present in about 47% of player-games | Phase 4 must decide; not imputed |
| Club may proxy value, or reflect a later move | Club fields describe the whole season | Phase 4 review |
| Assists differ between FotMob and Transfermarkt | Up to 4 apart in some seasons | FotMob remains the feature source; don't mix |

## 4. Status of all features

| Conclusion | Meaning | Features |
|---|---|---:|
| `USABLE_WITH_ALIGNMENT_LIMIT` | Window verified or consistent; alignment limit applies | 27 |
| `USABLE_EXCEPT_2019_20_COMPARISON` | As above, but 2019/20 is unavailable for comparison | 4 |
| `PARTLY_VERIFIED_USE_WITH_CARE` | Verified only for some seasons | 5 |
| `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` | Rate from season totals; the rate itself wasn't checked | 16 |
| `WINDOW_NOT_VERIFIED` | No match-level check is possible | 1 |
| `NO_DATA` | Empty column | 1 |
| `USABLE_WITH_CARE_2019_20` | Valid, but linked to the 2019/20 cut | 1 |
| `CONTEXT_REVIEW_IN_PHASE_4` | Review before use | 1 |
| `NOT_A_HISTORICAL_FEATURE` | Present-day value | 1 |

Each `m_*` metric has a paired `s_*` status column with the same source and window.

## 5. Per-feature audit

Every row: **available by season end** is yes, unless shown otherwise. Metric rows share this concern unless stated: *season total includes matches after the selected valuation date, a temporal alignment limitation under objective A, not leakage; collected retrospectively in November 2026.*

| Feature | Source | Definition | Observation period | Available by season end | Specific concern | Conclusion |
|---|---|---|---|---|---|---|
| `m_accurate_long_passes` | FotMob v3.1 season metrics (playerStats) | Accurate long balls; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_accurate_passes` | FotMob v3.1 season metrics (playerStats) | Accurate passes; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_aerials_won` | FotMob v3.1 season metrics (playerStats) | Aerials won; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_appearances` | FotMob v3.1 season metrics (playerStats) | Matches; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_assists` | FotMob v3.1 season metrics (playerStats) | Assists; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_chances_created` | FotMob v3.1 season metrics (playerStats) | Chances created; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_dribbles_succeeded` | FotMob v3.1 season metrics (playerStats) | Dribbles; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_duels_won` | FotMob v3.1 season metrics (playerStats) | Duels won; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_fouls_committed` | FotMob v3.1 season metrics (playerStats) | Fouls committed; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_fouls_won` | FotMob v3.1 season metrics (playerStats) | Fouls won; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_goals` | FotMob v3.1 season metrics (playerStats) | Goals; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_goals_conceded` | FotMob v3.1 season metrics (playerStats) | Goals conceded; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_interceptions` | FotMob v3.1 season metrics (playerStats) | Interceptions; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_minutes_played` | FotMob v3.1 season metrics (leagueseasondeepstats, playerStats) | Minutes; total aggregation; unit minutes | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_penalty_saves` | FotMob v3.1 season metrics (playerStats) | Penalty saves; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_rating` | FotMob v3.1 season metrics (playerStats) | Rating; rating aggregation; unit FotMob rating points | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_recoveries` | FotMob v3.1 season metrics (playerStats) | Recoveries; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_red_cards` | FotMob v3.1 season metrics (playerStats) | Red cards; total aggregation; unit count | Consistent with EPL season: within 1 of Transfermarkt totals on 2875 of 2877 rows; no FotMob per-match field | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_saves` | FotMob v3.1 season metrics (playerStats) | Saves; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_shots` | FotMob v3.1 season metrics (playerStats) | Shots; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_shots_on_target` | FotMob v3.1 season metrics (playerStats) | Shots on target; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_starts` | FotMob v3.1 season metrics (playerStats) | Started; total aggregation; unit count | Full EPL season: equals confirmed starts on 3241 of 3260 rows | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_successful_crosses` | FotMob v3.1 season metrics (playerStats) | Successful crosses; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_tackles` | FotMob v3.1 season metrics (playerStats) | Tackles; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_touches` | FotMob v3.1 season metrics (playerStats) | Touches; total aggregation; unit count | Full EPL season, verified against match sums in all seasons | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_yellow_cards` | FotMob v3.1 season metrics (playerStats) | Yellow cards; total aggregation; unit count | Consistent with EPL season: within 1 of Transfermarkt totals on 2759 of 2877 rows; no FotMob per-match field | Yes | Common concern only | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `position_group_season` | FotMob historical lineups | Most common known lineup position group in that season | Full EPL season | Yes | Uses the whole season, so partly after the valuation date. Historical, not the present-day profile. | `USABLE_WITH_ALIGNMENT_LIMIT` |
| `m_expected_assists` | FotMob v3.1 season metrics (playerStats) | xA; total aggregation; unit expected assists | Full EPL season verified for later seasons; **2019/20 from 4 of 380 matches** | Yes | 2019/20 values are not season measures (D7: unavailable for comparison). | `USABLE_EXCEPT_2019_20_COMPARISON` |
| `m_expected_goals` | FotMob v3.1 season metrics (playerStats) | xG; total aggregation; unit expected goals | Full EPL season verified for later seasons; **2019/20 from 4 of 380 matches** | Yes | 2019/20 values are not season measures (D7: unavailable for comparison). | `USABLE_EXCEPT_2019_20_COMPARISON` |
| `m_expected_goals_on_target` | FotMob v3.1 season metrics (playerStats) | xGOT; total aggregation; unit expected goals | Full EPL season verified for later seasons; **2019/20 from 4 of 380 matches**; 2022/2023 below verification threshold | Yes | 2019/20 values are not season measures (D7: unavailable for comparison). | `USABLE_EXCEPT_2019_20_COMPARISON` |
| `m_non_penalty_xg` | FotMob v3.1 season metrics (playerStats) | xG excl. penalty; total aggregation; unit expected goals | Full EPL season verified for later seasons; **2019/20 from 4 of 380 matches** | Yes | 2019/20 values are not season measures (D7: unavailable for comparison). | `USABLE_EXCEPT_2019_20_COMPARISON` |
| `m_big_chances_created` | FotMob v3.1 season metrics (playerStats) | Big chances created; total aggregation; unit count | Verified for 2020/2021, 2021/2022, 2022/2023, 2023/2024, 2024/2025; not verified for 2019/2020 | Yes | Common concern only | `PARTLY_VERIFIED_USE_WITH_CARE` |
| `m_blocked_shots` | FotMob v3.1 season metrics (playerStats) | Blocked scoring attempt; total aggregation; unit count | Verified for 2020/2021, 2021/2022, 2022/2023, 2023/2024, 2024/2025; not verified for 2019/2020 | Yes | Common concern only | `PARTLY_VERIFIED_USE_WITH_CARE` |
| `m_clearances` | FotMob v3.1 season metrics (playerStats) | Clearances; total aggregation; unit count | Verified for 2019/2020, 2021/2022, 2023/2024, 2024/2025; not verified for 2020/2021, 2022/2023 | Yes | Common concern only | `PARTLY_VERIFIED_USE_WITH_CARE` |
| `m_goals_prevented` | FotMob v3.1 season metrics (playerStats) | Goals prevented; total aggregation; unit goal-equivalent | Verified for 2024/2025; not verified for 2019/2020, 2020/2021, 2021/2022, 2022/2023, 2023/2024 | Yes | Common concern only | `PARTLY_VERIFIED_USE_WITH_CARE` |
| `m_touches_opposition_box` | FotMob v3.1 season metrics (playerStats) | Touches in opposition box; total aggregation; unit count | Verified for 2024/2025; not verified for 2019/2020, 2020/2021, 2021/2022, 2022/2023, 2023/2024 | Yes | Common concern only | `PARTLY_VERIFIED_USE_WITH_CARE` |
| `m_accurate_long_passes_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Accurate long balls per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_accurate_passes_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Accurate passes per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_aerials_won_percent` | FotMob v3.1 season metrics (playerStats) | Aerials won %; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_blocks_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Blocks per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_clearances_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Clearances per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_cross_accuracy` | FotMob v3.1 season metrics (playerStats) | Cross accuracy; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_duels_won_percent` | FotMob v3.1 season metrics (playerStats) | Duels won %; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_goals_conceded_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Goals conceded per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_interceptions_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Interceptions per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_long_ball_accuracy` | FotMob v3.1 season metrics (playerStats) | Long ball accuracy; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_passing_accuracy` | FotMob v3.1 season metrics (playerStats) | Pass accuracy; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_recoveries_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Recoveries per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_save_percentage` | FotMob v3.1 season metrics (playerStats) | Save percentage; percentage aggregation; unit percent | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_shots_on_target_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Shots on target per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_shots_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Shots per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_tackles_per90` | FotMob v3.1 season metrics (playerStats, leagueseasondeepstats) | Tackles per 90; per90 aggregation; unit count | Rate derived from season totals; rate itself not checked against match data | Yes | Common concern only | `RATE_WINDOW_NOT_DIRECTLY_VERIFIED` |
| `m_clean_sheets` | FotMob v3.1 season metrics (playerStats) | Clean sheets; total aggregation; unit count | Observation window could not be verified from match data | Yes | Common concern only | `WINDOW_NOT_VERIFIED` |
| `m_key_passes` | FotMob v3.1 season metrics (see release) | key_passes; unknown aggregation; unit unknown | No values in any season | No values | None; the column is empty. | `NO_DATA` |
| `age_at_season_end_years` | FotMob birth date; config cutoff | Derived: (season end minus birth date) / 365.25 | As of season end | Yes | None temporally. 4 birth dates are disputed. In 2019/20 the target cut depends on birth year, so age relates to the target by construction that season. | `USABLE_WITH_CARE_2019_20` |
| `confirmed_team_ids, confirmed_team_count, multi_club_class` | FotMob lineups | Clubs with confirmed appearances or squad rows that season | Full EPL season | Yes | Club may reflect a transfer that came after the valuation date. Club can proxy for value, which is a modeling issue, not leakage. | `CONTEXT_REVIEW_IN_PHASE_4` |
| `nationality_profile_present_day` | FotMob profile collected November 2026 | Single current nationality | Present day, not historical | **No, not established** | Post-season information. Some players changed national team after the research seasons (for example Andre Brooks, Malang Sarr). | `NOT_A_HISTORICAL_FEATURE` |

## 6. Limits of this audit

- Match-level checks prove a season value equals the sum of its EPL matches. They can't prove the provider's numbers are correct.
- 16 rates and `m_clean_sheets` weren't verified directly. Rates can be recomputed from verified totals in Phase 4 if needed.
- `m_yellow_cards` and `m_red_cards` have no FotMob per-match field, so they were compared with Transfermarkt totals. Yellow cards agree within 1 on 95.9% of rows.
- Windows use a 98% agreement threshold, chosen by judgment and recorded in `feature_window_audit.py`.
