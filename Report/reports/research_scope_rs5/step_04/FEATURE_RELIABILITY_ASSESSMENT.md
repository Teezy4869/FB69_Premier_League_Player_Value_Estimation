# rs5 Step 4: Feature Reliability Assessment

This is an assessment only: no feature engineering, selection or modeling. Full table (55 candidate features × 15 attributes: type, family, missingness overall and among applicable positions, seasons with values, observed-status share, unverified-position and conflicting cells, reliability, temporal availability, leakage class, Spearman with log target, extreme values, recommended treatment): **`evidence/feature_reliability.csv`**. The 53 `s_*` status columns pair with their metric and share its assessment.

## Reliability status

| Status | Count | Features | Recommended downstream treatment |
|---|---:|---|---|
| RELIABLE | 1 | `age_at_season_end_years` | Candidate (4 birth dates historically disputed) |
| RELIABLE_WITH_ALIGNMENT_LIMIT | 40 | 28 match-verified metrics, 8 per90 rates, starts, yellow and red cards, `position_group_season` | Candidate; read with its `s_*` status; null is not zero |
| SOURCE_REPORTED_NOT_VERIFIED | 8 | `aerials_won_percent`, `cross_accuracy`, `duels_won_percent`, `long_ball_accuracy`, `passing_accuracy`, `save_percentage`, `clean_sheets`, `goals_conceded_per90` | Candidate; source value accepted without an independent window check |
| WINDOW_NOT_FULLY_VERIFIED | 3 | `expected_goals_on_target`, `touches_opposition_box`, `goals_prevented` | Decide first (RD-04): exclude, or use with a per-season verified flag |
| PARTIAL_SEASON_COVERAGE | 2 | `clearances`, `clearances_per90` | Exclude, or season-aware handling only; never impute absent seasons (RD-04) |
| NO_DATA | 1 | `key_passes` | Exclude |

## Missingness among applicable rows (selected)

| Feature | Applies to | Null % |
|---|---|---:|
| appearances, starts | All | 0.04 |
| expected_assists | All | 1.38 |
| rating | All | 5.72 |
| goals, minutes_played | All | 7.24 |
| expected_goals | All | 17.95 |
| big_chances_created | All | 44.27 |
| cross_accuracy, successful_crosses | All | 41.75 |
| clearances | All | 80.67 |
| clean_sheets, saves, goals_conceded | GK | 3.88 |
| goals_prevented | GK | 12.62 |
| penalty_saves | GK | 31.55 |

## Outlier concerns

Count metrics have heavy right tails. The most values beyond 3 IQR are in goals (158), xG (78), accurate long passes (65), npxG (59), assists (53) and xGOT (51). These are genuine elite-player tails. Don't remove them; use robust or transformed handling if Phase 4 needs it. 6 rows have `m_starts` > `m_appearances` (DQ-RS5-04).

## Relationship with the target (Spearman with log target, usable rows; descriptive only)

Highest: `m_clean_sheets` 0.671 (GK), `m_rating` 0.581, `m_expected_assists` 0.557, `m_minutes_played` 0.537, `m_appearances` 0.533, `m_starts` and `m_saves` 0.528, `m_shots` 0.515, `m_goals` 0.500. None is at or above 0.8, so no feature looks like an encoding of the target. These figures are for leakage screening, not feature selection.
