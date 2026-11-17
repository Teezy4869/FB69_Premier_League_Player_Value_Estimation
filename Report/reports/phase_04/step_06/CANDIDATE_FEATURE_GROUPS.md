# Phase 4.6 Candidate Feature Group Recommendations

Date: 2026-11-09. Evidence: `evidence/candidate_feature_groups.csv`, `eligibility_review.csv`, `status_column_role.csv`. These are groups recommended **for consideration** in Phase 5, not a selected feature set. Owner decisions RD-04, RS5-12, P4-D03 (including ISS-29 reclassification), P4-D05 and P4-B05 remain open.

## Feature groups

| Group | Features | Evidence | Recommendation for Phase 5 consideration |
|---|---|---|---|
| Playing time | m_appearances, m_starts, m_minutes_played | Strongest grouping axis (4.4) and Spearman ~0.53; the three are near-duplicates (0.92-0.995); GK minutes missing (P4-D05) | Consider; choose one primary representation; starts are complete for GK |
| Age | age_at_season_end_years | Inverted U; interacts with playing time; -0.34 to -0.59 within regulars | Consider with a non-linear form; ISS-07 for 4 birth dates |
| Position context | position_group_season | Distinct sub-populations; metric meaning differs by position; whole-season modal (P4-B04) | Consider as context or for position-specific models |
| Attacking output and xG | m_goals, m_shots, m_shots_on_target, m_expected_goals, m_non_penalty_xg, m_shots_per90, m_shots_on_target_per90 | Retained beyond playing time (partial 0.28-0.33); strong for MID/FWD regulars; high internal redundancy (cluster 2) | Consider; resolve redundancy by design (totals vs rates) |
| Chance creation and xA | m_assists, m_expected_assists, m_chances_created, m_big_chances_created | xA 0.56 pooled, 0.33 given starts; xA/chances 0.93 | Consider; big chances has 44% nulls |
| Passing quality | m_accurate_passes_per90, m_passing_accuracy, m_long_ball_accuracy, m_accurate_long_passes(_per90) | Retained for defenders (0.48-0.51); accuracy rates source-reported (ISS-29); passing accuracy drifts (P4-B09) | Consider position-specifically; ISS-29 decision needed for accuracy rates |
| Possession volume | m_touches, m_accurate_passes, m_dribbles_succeeded, m_successful_crosses | Mostly playing time (touches 0.47 -> 0.16 given starts); in playing-time cluster | Consider only with playing-time context |
| Defensive actions | m_tackles, m_interceptions, m_recoveries, m_blocked_shots, m_aerials_won, m_duels_won and rates | Positive pooled associations are playing time; negative given playing time (P4-B08); rates drift (P4-B09) | Low expected value as direct signals; possible team-context confounding (RS5-12) |
| Discipline and fouls | m_yellow_cards, m_red_cards, m_fouls_committed, m_fouls_won | Mostly playing time; fouls won retains 0.20 | Low priority |
| Overall rating | m_rating | Strongest single association (0.58; 0.41 given starts); composite source score; 17 conflicting, 58 revised cells | Consider; interpret as a composite, not independent evidence |
| Goalkeeping | m_saves, m_save_percentage, m_clean_sheets, m_goals_conceded(_per90), m_penalty_saves | 206 rows; clean sheets 0.67; saves reverse given starts; two rates internally consistent | Consider only in a goalkeeper-specific design |
| RD-04 metrics | m_clearances, m_clearances_per90, m_expected_goals_on_target, m_touches_opposition_box, m_goals_prevented | Incomplete window or season coverage (4.5) | Pending owner decision RD-04 |
| Club context | 8 RS5-12 columns | Complete but temporally ambiguous; possible strong proxy | Pending owner decision RS5-12 |
| Status columns | 52 s_* (excluding s_key_passes) | Encode why a value is null (4.5) | Not numeric features; role decided in preprocessing design (P4-D01) |

## Eligibility categories (unchanged)

| Category | Columns | Examples | Phase 4.6 reading |
|---|---:|---|---|
| CANDIDATE_PREDICTOR | 41 | age_at_season_end_years, position_group_season, m_accurate_long_passes, m_accurate_long_passes_per90 | Candidates with warnings; assessed in the matrix; no change |
| CONDITIONAL_PREDICTOR: owner decision (RD-04) | 5 | m_clearances, m_clearances_per90, m_expected_goals_on_target, m_goals_prevented | Remain pending; 4.5 evidence summarised for the owner |
| CONDITIONAL_PREDICTOR: owner decision (RS5-12) | 8 | confirmed_team_ids, confirmed_team_count, associated_team_count, associated_team_ids | Remain pending; temporally ambiguous (4.5) |
| CONDITIONAL_PREDICTOR: reliability assessment (ISS-29) | 8 | m_aerials_won_percent, m_clean_sheets, m_cross_accuracy, m_duels_won_percent | Assessed in 4.5: 2 internally consistent, 6 unverifiable; classification unchanged |
| EXCLUDED_PREDICTOR | 3 | nationality_profile_present_day, m_key_passes, s_key_passes | m_key_passes, s_key_passes, nationality_profile_present_day: remain excluded |
| IDENTITY_METADATA | 33 | canonical_player_id, season, season_id, fotmob_player_id | Never predictors (group keys and sensitivity grouping only) |
| STATUS_MISSINGNESS | 53 | missing_feature_count, s_accurate_long_passes, s_accurate_long_passes_per90, s_accurate_passes | Not numeric performance features; possible role as missingness indicators (P4-D01) |
| TARGET | 16 | target_market_value, target_currency, target_status, target_missing_reason | Never predictors |
| TEMPORAL_AUDIT | 8 | temporal_player_games_in_season, temporal_player_games_on_valuation_date, temporal_player_games_after_valuation, temporal_league_games_in_season | Never predictors (audit only; see P4-D05) |

## Status columns (`s_*`)

| Possible role | Basis | Assessment | Decision needed |
|---|---|---|---|
| Interpret nulls in EDA and audits | Distinguishes unavailable, not applicable, unsupported and conflicting nulls | Used throughout Phase 4 | none |
| Missingness indicators for preprocessing | MISSING is informative (fringe players, lower values; 4.3 and 4.5) | Possible; one indicator per metric family or per block, not per status value | P4-D01 decision |
| Applicability masks | UNVERIFIED_POSITION marks GK-only metrics on outfield rows | Possible for position-specific designs | P4-D01, P4-B10 |
| Exclusion of unusable cells | CONFLICTING (36 cells) and UNSUPPORTED (key_passes) | Keep null; never zero | none |
| Numeric performance features | Statuses are categorical source codes | Not appropriate |  |
