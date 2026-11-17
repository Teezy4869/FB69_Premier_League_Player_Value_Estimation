# Phase 4.6 Feature Assessment Matrix

Date: 2026-11-09. Machine-readable version: `evidence/feature_assessment_matrix.csv` (all columns). Code: `src/phase4/feasibility.py`. Figures: `figures/fig46_01`, `fig46_02`.

**This is an assessment, not feature selection.** Eligibility categories are unchanged (Phase 4.0 register). Ratings use the evidence of Phases 4.2–4.5; the two judgment dimensions are labelled. RD-03 applies to every association.

## Rules

| Dimension | Rule |
|---|---|
| coverage | High: <=10% null on applicable rows and values in 5 seasons; Medium: <=30% and 5 seasons; Low: >30% or fewer than 5 seasons |
| association | \|pooled Spearman\| >= 0.5 strong, >= 0.3 moderate, >= 0.1 weak, else none (Phase 4.3) |
| beyond_playing_time | \|partial Spearman given starts\| >= 0.25 retained, 0.10-0.25 partly retained, < 0.10 mostly playing time |
| redundancy | max \|Spearman\| with another outfield feature >= 0.9 high, >= 0.8 medium, else low (outfield matrix, Phase 4.3) |
| position | GK only, or outfield within-position Spearman range >= 0.25: position-specific; else general |
| identity | \|change in Spearman without P4-B01\| >= 0.05 sensitive, else robust |
| tail | values beyond 3 IQR > 2% of observed values: heavy tail; else moderate/none |
| interpretability | judgment: {"age (years)": "high", "season count/total": "high", "per-90 rate": "medium", "percentage (source-reported)": "medium", "season total (model-based)": "medium", "average rating (0-10)": "low (composite source score)"} |
| usefulness | judgment by explicit rules in feasibility.usefulness() |

Phase 5 consideration counts: consider (core candidate) 13, low expected value; keep available, do not prioritise 12, conditional: reliability assessment (ISS-29) 6, conditional: owner decision (RD-04) 5, consider only with playing-time context 5, consider one representation of playing time 3, consider with missingness handling (P4-B07) 3, consider in a goalkeeper-specific design 3, conditional: ISS-29, internal consistency shown (owner may reclassify) 2, consider; needs a non-linear representation 1.

## Matrix (53 analysed features)

| Feature | Group | Eligibility | Coverage (null %) | Informative nulls | Reliability | Temporal | Position | Tail | Redundancy (max \|rho\|, partner) | Interpretability (judgment) | Association (pooled / given starts / regulars) | Identity | Usefulness (judgment) | Phase 5 consideration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `age_at_season_end_years` | Player context and age | CANDIDATE_PREDICTOR | high (0.0) | no | reliable with caveat | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                                  age_at_season_end_years
analysis_group                                            Player context and age
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                             ISS-07
null_applicable_pct                                                          0.0
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                    False
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                             position-specific
outfield_position_rho_range                                             0.264019
shape                                                    approximately symmetric
skew                                                                    0.193496
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.265466
most_correlated_with                                            m_minutes_played
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         -0.16694
association                                                                 weak
partial_given_starts                                                   -0.337445
beyond_playing_time                                                     retained
max_abs_rho_within_regulars                                             0.502552
identity_change                                                        -0.069928
identity_sensitivity                                                   sensitive
usefulness_judgment            promising (non-monotonic; interacts with playi...
phase5_recommendation                consider; needs a non-linear representation
Name: 0, dtype: object> | low (0.27, m_minutes_played) | high | weak (-0.17 / -0.34 / 0.50) | sensitive (-0.07) | promising (non-monotonic; interacts with playing time) | consider; needs a non-linear representation |
| `m_appearances` | Playing time and participation | CANDIDATE_PREDICTOR | high (0.0) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                            m_appearances
analysis_group                                    Playing time and participation
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                     0.036403
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                              0.10392
shape                                                    approximately symmetric
skew                                                                   -0.179567
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.941396
most_correlated_with                                            m_minutes_played
redundancy                                                                  high
redundancy_cluster                                                           1.0
interpretability_judgment                                                   high
pooled_spearman                                                         0.532814
association                                                               strong
partial_given_starts                                                    0.138358
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.172282
identity_change                                                        -0.049064
identity_sensitivity                                                      robust
usefulness_judgment            promising as the playing-time axis; highly red...
phase5_recommendation                consider one representation of playing time
Name: 1, dtype: object> | high (0.94, m_minutes_played) | high | strong (0.53 / 0.14 / 0.17) | robust (-0.05) | promising as the playing-time axis; highly redundant within the group | consider one representation of playing time |
| `m_starts` | Playing time and participation | CANDIDATE_PREDICTOR | high (0.0) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                                 m_starts
analysis_group                                    Playing time and participation
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                     0.036403
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.149413
shape                                                    approximately symmetric
skew                                                                    0.303628
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                                0.99451
most_correlated_with                                            m_minutes_played
redundancy                                                                  high
redundancy_cluster                                                           1.0
interpretability_judgment                                                   high
pooled_spearman                                                         0.527535
association                                                               strong
partial_given_starts                                                         NaN
beyond_playing_time                                         n/a (is the control)
max_abs_rho_within_regulars                                             0.246984
identity_change                                                         -0.04222
identity_sensitivity                                                      robust
usefulness_judgment            promising as the playing-time axis; highly red...
phase5_recommendation                consider one representation of playing time
Name: 2, dtype: object> | high (0.99, m_minutes_played) | high | strong (0.53 /  / 0.25) | robust (-0.04) | promising as the playing-time axis; highly redundant within the group | consider one representation of playing time |
| `m_minutes_played` | Playing time and participation | CANDIDATE_PREDICTOR | high (7.2) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                         m_minutes_played
analysis_group                                    Playing time and participation
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      7.24427
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.153075
shape                                                    approximately symmetric
skew                                                                    0.291325
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                                0.99451
most_correlated_with                                                    m_starts
redundancy                                                                  high
redundancy_cluster                                                           1.0
interpretability_judgment                                                   high
pooled_spearman                                                         0.536821
association                                                               strong
partial_given_starts                                                    0.052627
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.269689
identity_change                                                        -0.038726
identity_sensitivity                                                      robust
usefulness_judgment            promising as the playing-time axis; highly red...
phase5_recommendation                consider one representation of playing time
Name: 3, dtype: object> | high (0.99, m_starts) | high | strong (0.54 / 0.05 / 0.27) | robust (-0.04) | promising as the playing-time axis; highly redundant within the group | consider one representation of playing time |
| `m_goals` | Attacking | CANDIDATE_PREDICTOR | high (7.2) | yes | reliable with caveat | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                           m_goals
analysis_group                                  Attacking
eligibility_category                  CANDIDATE_PREDICTOR
condition_ids                                       RD-03
null_applicable_pct                               7.24427
seasons_with_values                                     5
coverage                                             high
missingness_informative                              True
reliability_class                    reliable with caveat
temporal                                       RD-03 only
position_relevance                      position-specific
outfield_position_rho_range                      0.307171
shape                               strongly right-skewed
skew                                              3.07122
beyond_3iqr_pct                                   6.20094
tail                                                heavy
max_abs_rho_other_feature                        0.879388
most_correlated_with           m_expected_goals_on_target
redundancy                                         medium
redundancy_cluster                                    NaN
interpretability_judgment                            high
pooled_spearman                                  0.500254
association                                        strong
partial_given_starts                             0.280779
beyond_playing_time                              retained
max_abs_rho_within_regulars                      0.466071
identity_change                                 -0.017726
identity_sensitivity                               robust
usefulness_judgment                             promising
phase5_recommendation           consider (core candidate)
Name: 4, dtype: object> | medium (0.88, m_expected_goals_on_target) | high | strong (0.50 / 0.28 / 0.47) | robust (-0.02) | promising | consider (core candidate) |
| `m_assists` | Attacking | CANDIDATE_PREDICTOR | high (6.7) | yes | reliable with caveat | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                        m_assists
analysis_group                                 Attacking
eligibility_category                 CANDIDATE_PREDICTOR
condition_ids                                      RD-03
null_applicable_pct                              6.66181
seasons_with_values                                    5
coverage                                            high
missingness_informative                             True
reliability_class                   reliable with caveat
temporal                                      RD-03 only
position_relevance                     position-specific
outfield_position_rho_range                     0.291833
shape                              strongly right-skewed
skew                                             2.24305
beyond_3iqr_pct                                  2.06708
tail                                               heavy
max_abs_rho_other_feature                        0.78724
most_correlated_with                  m_expected_assists
redundancy                                           low
redundancy_cluster                                   NaN
interpretability_judgment                           high
pooled_spearman                                 0.461871
association                                     moderate
partial_given_starts                            0.218043
beyond_playing_time                      partly retained
max_abs_rho_within_regulars                     0.402555
identity_change                                 -0.02509
identity_sensitivity                              robust
usefulness_judgment                            promising
phase5_recommendation          consider (core candidate)
Name: 5, dtype: object> | low (0.79, m_expected_assists) | high | moderate (0.46 / 0.22 / 0.40) | robust (-0.03) | promising | consider (core candidate) |
| `m_shots` | Attacking | CANDIDATE_PREDICTOR | medium (19.0) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                          m_shots
analysis_group                                 Attacking
eligibility_category                 CANDIDATE_PREDICTOR
condition_ids                                      RD-03
null_applicable_pct                               19.039
seasons_with_values                                    5
coverage                                          medium
missingness_informative                             True
reliability_class                   reliable with caveat
temporal                                      RD-03 only
position_relevance                               general
outfield_position_rho_range                     0.148056
shape                              strongly right-skewed
skew                                              1.7751
beyond_3iqr_pct                                  1.03417
tail                                       moderate/none
max_abs_rho_other_feature                       0.928779
most_correlated_with                   m_shots_on_target
redundancy                                          high
redundancy_cluster                                   2.0
interpretability_judgment                           high
pooled_spearman                                 0.514651
association                                       strong
partial_given_starts                            0.330142
beyond_playing_time                             retained
max_abs_rho_within_regulars                     0.529565
identity_change                                -0.016167
identity_sensitivity                              robust
usefulness_judgment                            promising
phase5_recommendation          consider (core candidate)
Name: 6, dtype: object> | high (0.93, m_shots_on_target) | high | strong (0.51 / 0.33 / 0.53) | robust (-0.02) | promising | consider (core candidate) |
| `m_shots_on_target` | Attacking | CANDIDATE_PREDICTOR | low (30.9) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                  m_shots_on_target
analysis_group                                                   Attacking
eligibility_category                                   CANDIDATE_PREDICTOR
condition_ids                                                        RD-03
null_applicable_pct                                                30.9064
seasons_with_values                                                      5
coverage                                                               low
missingness_informative                                               True
reliability_class                        reliable values, limited coverage
temporal                                                        RD-03 only
position_relevance                                                 general
outfield_position_rho_range                                       0.218916
shape                                                strongly right-skewed
skew                                                               2.07599
beyond_3iqr_pct                                                    1.47524
tail                                                         moderate/none
max_abs_rho_other_feature                                         0.928779
most_correlated_with                                               m_shots
redundancy                                                            high
redundancy_cluster                                                     2.0
interpretability_judgment                                             high
pooled_spearman                                                   0.435558
association                                                       moderate
partial_given_starts                                               0.31039
beyond_playing_time                                               retained
max_abs_rho_within_regulars                                       0.487104
identity_change                                                  -0.005499
identity_sensitivity                                                robust
usefulness_judgment                               promising but incomplete
phase5_recommendation          consider with missingness handling (P4-B07)
Name: 7, dtype: object> | high (0.93, m_shots) | high | moderate (0.44 / 0.31 / 0.49) | robust (-0.01) | promising but incomplete | consider with missingness handling (P4-B07) |
| `m_shots_per90` | Attacking | CANDIDATE_PREDICTOR | medium (19.0) | yes | reliable with caveat | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                              m_shots_per90
analysis_group                                           Attacking
eligibility_category                           CANDIDATE_PREDICTOR
condition_ids                                                RD-03
null_applicable_pct                                         19.039
seasons_with_values                                              5
coverage                                                    medium
missingness_informative                                       True
reliability_class                             reliable with caveat
temporal                       RD-03 + small denominators (P4-B05)
position_relevance                                         general
outfield_position_rho_range                               0.147401
shape                                        strongly right-skewed
skew                                                       1.05341
beyond_3iqr_pct                                           0.089928
tail                                                 moderate/none
max_abs_rho_other_feature                                 0.902646
most_correlated_with                       m_shots_on_target_per90
redundancy                                                    high
redundancy_cluster                                             3.0
interpretability_judgment                                   medium
pooled_spearman                                           0.294874
association                                                   weak
partial_given_starts                                      0.322692
beyond_playing_time                                       retained
max_abs_rho_within_regulars                               0.521521
identity_change                                           0.004693
identity_sensitivity                                        robust
usefulness_judgment                                      promising
phase5_recommendation                    consider (core candidate)
Name: 8, dtype: object> | high (0.90, m_shots_on_target_per90) | medium | weak (0.29 / 0.32 / 0.52) | robust (0.00) | promising | consider (core candidate) |
| `m_shots_on_target_per90` | Attacking | CANDIDATE_PREDICTOR | low (30.9) | yes | reliable values, limited coverage | RD-03 + small denominators (P4-B05) | position-specific | <bound method NDFrame.tail of feature                                            m_shots_on_target_per90
analysis_group                                                   Attacking
eligibility_category                                   CANDIDATE_PREDICTOR
condition_ids                                                        RD-03
null_applicable_pct                                                30.9064
seasons_with_values                                                      5
coverage                                                               low
missingness_informative                                               True
reliability_class                        reliable values, limited coverage
temporal                               RD-03 + small denominators (P4-B05)
position_relevance                                       position-specific
outfield_position_rho_range                                        0.25229
shape                                                strongly right-skewed
skew                                                               2.83231
beyond_3iqr_pct                                                   0.210748
tail                                                         moderate/none
max_abs_rho_other_feature                                         0.902646
most_correlated_with                                         m_shots_per90
redundancy                                                            high
redundancy_cluster                                                     3.0
interpretability_judgment                                           medium
pooled_spearman                                                   0.208072
association                                                           weak
partial_given_starts                                              0.305212
beyond_playing_time                                               retained
max_abs_rho_within_regulars                                       0.473661
identity_change                                                   0.014071
identity_sensitivity                                                robust
usefulness_judgment                               promising but incomplete
phase5_recommendation          consider with missingness handling (P4-B07)
Name: 9, dtype: object> | high (0.90, m_shots_per90) | medium | weak (0.21 / 0.31 / 0.47) | robust (0.01) | promising but incomplete | consider with missingness handling (P4-B07) |
| `m_big_chances_created` | Attacking | CANDIDATE_PREDICTOR | low (44.3) | yes | reliable values, limited coverage | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                              m_big_chances_created
analysis_group                                                   Attacking
eligibility_category                                   CANDIDATE_PREDICTOR
condition_ids                                                        RD-03
null_applicable_pct                                                44.2665
seasons_with_values                                                      5
coverage                                                               low
missingness_informative                                               True
reliability_class                        reliable values, limited coverage
temporal                                                        RD-03 only
position_relevance                                       position-specific
outfield_position_rho_range                                       0.310026
shape                                                strongly right-skewed
skew                                                               2.39548
beyond_3iqr_pct                                                    1.04507
tail                                                         moderate/none
max_abs_rho_other_feature                                         0.815166
most_correlated_with                                    m_expected_assists
redundancy                                                          medium
redundancy_cluster                                                     NaN
interpretability_judgment                                             high
pooled_spearman                                                   0.399165
association                                                       moderate
partial_given_starts                                              0.272765
beyond_playing_time                                               retained
max_abs_rho_within_regulars                                       0.468431
identity_change                                                   0.009467
identity_sensitivity                                                robust
usefulness_judgment                               promising but incomplete
phase5_recommendation          consider with missingness handling (P4-B07)
Name: 10, dtype: object> | medium (0.82, m_expected_assists) | high | moderate (0.40 / 0.27 / 0.47) | robust (0.01) | promising but incomplete | consider with missingness handling (P4-B07) |
| `m_dribbles_succeeded` | Attacking | CANDIDATE_PREDICTOR | medium (24.8) | yes | reliable values, limited coverage | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                     m_dribbles_succeeded
analysis_group                                         Attacking
eligibility_category                         CANDIDATE_PREDICTOR
condition_ids                                              RD-03
null_applicable_pct                                      24.7907
seasons_with_values                                            5
coverage                                                  medium
missingness_informative                                     True
reliability_class              reliable values, limited coverage
temporal                                              RD-03 only
position_relevance                             position-specific
outfield_position_rho_range                             0.254832
shape                                      strongly right-skewed
skew                                                     2.15018
beyond_3iqr_pct                                         0.726041
tail                                               moderate/none
max_abs_rho_other_feature                               0.745061
most_correlated_with                           m_chances_created
redundancy                                                   low
redundancy_cluster                                           NaN
interpretability_judgment                                   high
pooled_spearman                                         0.427761
association                                             moderate
partial_given_starts                                    0.263255
beyond_playing_time                                     retained
max_abs_rho_within_regulars                             0.346908
identity_change                                        -0.010243
identity_sensitivity                                      robust
usefulness_judgment                                    promising
phase5_recommendation                  consider (core candidate)
Name: 11, dtype: object> | low (0.75, m_chances_created) | high | moderate (0.43 / 0.26 / 0.35) | robust (-0.01) | promising | consider (core candidate) |
| `m_touches_opposition_box` | Attacking | CONDITIONAL_PREDICTOR | medium (21.2) | yes | pending owner decision (RD-04) | RD-03 + incomplete window (RD-04) | general | <bound method NDFrame.tail of feature                                   m_touches_opposition_box
analysis_group                                           Attacking
eligibility_category                         CONDITIONAL_PREDICTOR
condition_ids                                                RD-04
null_applicable_pct                                        21.1867
seasons_with_values                                              5
coverage                                                    medium
missingness_informative                                       True
reliability_class                   pending owner decision (RD-04)
temporal                         RD-03 + incomplete window (RD-04)
position_relevance                                         general
outfield_position_rho_range                               0.213023
shape                                        strongly right-skewed
skew                                                       2.11267
beyond_3iqr_pct                                            1.38568
tail                                                 moderate/none
max_abs_rho_other_feature                                  0.89565
most_correlated_with                                       m_shots
redundancy                                                  medium
redundancy_cluster                                             NaN
interpretability_judgment                                     high
pooled_spearman                                           0.495026
association                                               moderate
partial_given_starts                                      0.327108
beyond_playing_time                                       retained
max_abs_rho_within_regulars                                0.67489
identity_change                                          -0.012103
identity_sensitivity                                        robust
usefulness_judgment                 unknown until RD-04 is decided
phase5_recommendation          conditional: owner decision (RD-04)
Name: 12, dtype: object> | medium (0.90, m_shots) | high | moderate (0.50 / 0.33 / 0.67) | robust (-0.01) | unknown until RD-04 is decided | conditional: owner decision (RD-04) |
| `m_expected_goals` | Expected (model-based) metrics | CANDIDATE_PREDICTOR | medium (17.9) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                      m_expected_goals
analysis_group                 Expected (model-based) metrics
eligibility_category                      CANDIDATE_PREDICTOR
condition_ids                                           RD-03
null_applicable_pct                                   17.9469
seasons_with_values                                         5
coverage                                               medium
missingness_informative                                  True
reliability_class                        reliable with caveat
temporal                                           RD-03 only
position_relevance                                    general
outfield_position_rho_range                          0.205481
shape                                   strongly right-skewed
skew                                                  2.87198
beyond_3iqr_pct                                       3.46051
tail                                                    heavy
max_abs_rho_other_feature                            0.991967
most_correlated_with                         m_non_penalty_xg
redundancy                                               high
redundancy_cluster                                        2.0
interpretability_judgment                              medium
pooled_spearman                                      0.490656
association                                          moderate
partial_given_starts                                 0.316174
beyond_playing_time                                  retained
max_abs_rho_within_regulars                          0.477339
identity_change                                     -0.015326
identity_sensitivity                                   robust
usefulness_judgment                                 promising
phase5_recommendation               consider (core candidate)
Name: 13, dtype: object> | high (0.99, m_non_penalty_xg) | medium | moderate (0.49 / 0.32 / 0.48) | robust (-0.02) | promising | consider (core candidate) |
| `m_non_penalty_xg` | Expected (model-based) metrics | CANDIDATE_PREDICTOR | medium (22.2) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                         m_non_penalty_xg
analysis_group                    Expected (model-based) metrics
eligibility_category                         CANDIDATE_PREDICTOR
condition_ids                                              RD-03
null_applicable_pct                                      22.1696
seasons_with_values                                            5
coverage                                                  medium
missingness_informative                                     True
reliability_class              reliable values, limited coverage
temporal                                              RD-03 only
position_relevance                                       general
outfield_position_rho_range                             0.152348
shape                                      strongly right-skewed
skew                                                     2.53117
beyond_3iqr_pct                                          2.75959
tail                                                       heavy
max_abs_rho_other_feature                               0.991967
most_correlated_with                            m_expected_goals
redundancy                                                  high
redundancy_cluster                                           2.0
interpretability_judgment                                 medium
pooled_spearman                                         0.471277
association                                             moderate
partial_given_starts                                    0.320346
beyond_playing_time                                     retained
max_abs_rho_within_regulars                             0.488422
identity_change                                        -0.009474
identity_sensitivity                                      robust
usefulness_judgment                                    promising
phase5_recommendation                  consider (core candidate)
Name: 14, dtype: object> | high (0.99, m_expected_goals) | medium | moderate (0.47 / 0.32 / 0.49) | robust (-0.01) | promising | consider (core candidate) |
| `m_expected_assists` | Expected (model-based) metrics | CANDIDATE_PREDICTOR | high (1.4) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                    m_expected_assists
analysis_group                 Expected (model-based) metrics
eligibility_category                      CANDIDATE_PREDICTOR
condition_ids                                           RD-03
null_applicable_pct                                   1.38333
seasons_with_values                                         5
coverage                                                 high
missingness_informative                                  True
reliability_class                        reliable with caveat
temporal                                           RD-03 only
position_relevance                                    general
outfield_position_rho_range                          0.226791
shape                                   strongly right-skewed
skew                                                  2.31733
beyond_3iqr_pct                                       1.69804
tail                                            moderate/none
max_abs_rho_other_feature                            0.929408
most_correlated_with                        m_chances_created
redundancy                                               high
redundancy_cluster                                        4.0
interpretability_judgment                              medium
pooled_spearman                                      0.556969
association                                            strong
partial_given_starts                                 0.327911
beyond_playing_time                                  retained
max_abs_rho_within_regulars                          0.497351
identity_change                                     -0.028935
identity_sensitivity                                   robust
usefulness_judgment                                 promising
phase5_recommendation               consider (core candidate)
Name: 15, dtype: object> | high (0.93, m_chances_created) | medium | strong (0.56 / 0.33 / 0.50) | robust (-0.03) | promising | consider (core candidate) |
| `m_expected_goals_on_target` | Expected (model-based) metrics | CONDITIONAL_PREDICTOR | low (31.3) | yes | pending owner decision (RD-04) | RD-03 + incomplete window (RD-04) | general | <bound method NDFrame.tail of feature                                 m_expected_goals_on_target
analysis_group                      Expected (model-based) metrics
eligibility_category                         CONDITIONAL_PREDICTOR
condition_ids                                                RD-04
null_applicable_pct                                        31.3069
seasons_with_values                                              5
coverage                                                       low
missingness_informative                                       True
reliability_class                   pending owner decision (RD-04)
temporal                         RD-03 + incomplete window (RD-04)
position_relevance                                         general
outfield_position_rho_range                               0.248615
shape                                        strongly right-skewed
skew                                                       2.63323
beyond_3iqr_pct                                             2.7027
tail                                                         heavy
max_abs_rho_other_feature                                 0.917793
most_correlated_with                             m_shots_on_target
redundancy                                                    high
redundancy_cluster                                             2.0
interpretability_judgment                                   medium
pooled_spearman                                           0.405271
association                                               moderate
partial_given_starts                                      0.296143
beyond_playing_time                                       retained
max_abs_rho_within_regulars                                0.48817
identity_change                                          -0.000931
identity_sensitivity                                        robust
usefulness_judgment                 unknown until RD-04 is decided
phase5_recommendation          conditional: owner decision (RD-04)
Name: 16, dtype: object> | high (0.92, m_shots_on_target) | medium | moderate (0.41 / 0.30 / 0.49) | robust (-0.00) | unknown until RD-04 is decided | conditional: owner decision (RD-04) |
| `m_accurate_passes` | Passing and possession | CANDIDATE_PREDICTOR | medium (11.8) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                m_accurate_passes
analysis_group                    Passing and possession
eligibility_category                 CANDIDATE_PREDICTOR
condition_ids                                      RD-03
null_applicable_pct                              11.8311
seasons_with_values                                    5
coverage                                          medium
missingness_informative                             True
reliability_class                   reliable with caveat
temporal                                      RD-03 only
position_relevance                               general
outfield_position_rho_range                     0.021038
shape                              strongly right-skewed
skew                                             1.33658
beyond_3iqr_pct                                 0.123865
tail                                       moderate/none
max_abs_rho_other_feature                       0.971237
most_correlated_with                           m_touches
redundancy                                          high
redundancy_cluster                                   1.0
interpretability_judgment                           high
pooled_spearman                                 0.482764
association                                     moderate
partial_given_starts                            0.219329
beyond_playing_time                      partly retained
max_abs_rho_within_regulars                     0.498058
identity_change                                -0.028752
identity_sensitivity                              robust
usefulness_judgment                            promising
phase5_recommendation          consider (core candidate)
Name: 17, dtype: object> | high (0.97, m_touches) | high | moderate (0.48 / 0.22 / 0.50) | robust (-0.03) | promising | consider (core candidate) |
| `m_accurate_passes_per90` | Passing and possession | CANDIDATE_PREDICTOR | medium (11.9) | yes | reliable with caveat | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                    m_accurate_passes_per90
analysis_group                              Passing and possession
eligibility_category                           CANDIDATE_PREDICTOR
condition_ids                                                RD-03
null_applicable_pct                                        11.8675
seasons_with_values                                              5
coverage                                                    medium
missingness_informative                                       True
reliability_class                             reliable with caveat
temporal                       RD-03 + small denominators (P4-B05)
position_relevance                                         general
outfield_position_rho_range                               0.218512
shape                                      moderately right-skewed
skew                                                      0.880861
beyond_3iqr_pct                                                0.0
tail                                                 moderate/none
max_abs_rho_other_feature                                 0.794658
most_correlated_with                            m_passing_accuracy
redundancy                                                     low
redundancy_cluster                                             NaN
interpretability_judgment                                   medium
pooled_spearman                                           0.232947
association                                                   weak
partial_given_starts                                      0.217334
beyond_playing_time                                partly retained
max_abs_rho_within_regulars                               0.506911
identity_change                                          -0.014282
identity_sensitivity                                        robust
usefulness_judgment                                      promising
phase5_recommendation                    consider (core candidate)
Name: 18, dtype: object> | low (0.79, m_passing_accuracy) | medium | weak (0.23 / 0.22 / 0.51) | robust (-0.01) | promising | consider (core candidate) |
| `m_accurate_long_passes` | Passing and possession | CANDIDATE_PREDICTOR | medium (15.2) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                   m_accurate_long_passes
analysis_group                                            Passing and possession
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      15.2166
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                              0.08331
shape                                                      strongly right-skewed
skew                                                                     2.69995
beyond_3iqr_pct                                                           2.7909
tail                                                                       heavy
max_abs_rho_other_feature                                               0.884437
most_correlated_with                                           m_accurate_passes
redundancy                                                                medium
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                          0.22143
association                                                                 weak
partial_given_starts                                                   -0.142137
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                              0.21868
identity_change                                                        -0.025023
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 19, dtype: object> | medium (0.88, m_accurate_passes) | high | weak (0.22 / -0.14 / 0.22) | robust (-0.03) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_accurate_long_passes_per90` | Passing and possession | CANDIDATE_PREDICTOR | medium (15.2) | yes | reliable with caveat | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                             m_accurate_long_passes_per90
analysis_group                                            Passing and possession
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      15.2166
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       general
outfield_position_rho_range                                             0.108822
shape                                                      strongly right-skewed
skew                                                                     1.94588
beyond_3iqr_pct                                                           1.1593
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.748573
most_correlated_with                                      m_accurate_long_passes
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.083456
association                                                                 none
partial_given_starts                                                   -0.167076
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.186237
identity_change                                                         0.005698
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 20, dtype: object> | low (0.75, m_accurate_long_passes) | medium | none (-0.08 / -0.17 / 0.19) | robust (0.01) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_chances_created` | Passing and possession | CANDIDATE_PREDICTOR | medium (21.6) | yes | reliable values, limited coverage | RD-03 only | position-specific | <bound method NDFrame.tail of feature                                        m_chances_created
analysis_group                            Passing and possession
eligibility_category                         CANDIDATE_PREDICTOR
condition_ids                                              RD-03
null_applicable_pct                                      21.5872
seasons_with_values                                            5
coverage                                                  medium
missingness_informative                                     True
reliability_class              reliable values, limited coverage
temporal                                              RD-03 only
position_relevance                             position-specific
outfield_position_rho_range                             0.279767
shape                                      strongly right-skewed
skew                                                     1.82905
beyond_3iqr_pct                                         0.742804
tail                                               moderate/none
max_abs_rho_other_feature                               0.929408
most_correlated_with                          m_expected_assists
redundancy                                                  high
redundancy_cluster                                           4.0
interpretability_judgment                                   high
pooled_spearman                                           0.4189
association                                             moderate
partial_given_starts                                    0.259174
beyond_playing_time                                     retained
max_abs_rho_within_regulars                             0.451495
identity_change                                        -0.008759
identity_sensitivity                                      robust
usefulness_judgment                                    promising
phase5_recommendation                  consider (core candidate)
Name: 21, dtype: object> | high (0.93, m_expected_assists) | high | moderate (0.42 / 0.26 / 0.45) | robust (-0.01) | promising | consider (core candidate) |
| `m_successful_crosses` | Passing and possession | CANDIDATE_PREDICTOR | low (41.8) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                     m_successful_crosses
analysis_group                                            Passing and possession
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      41.7546
seasons_with_values                                                            5
coverage                                                                     low
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.058874
shape                                                      strongly right-skewed
skew                                                                     2.86166
beyond_3iqr_pct                                                           2.9375
tail                                                                       heavy
max_abs_rho_other_feature                                               0.692171
most_correlated_with                                          m_expected_assists
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         0.178935
association                                                                 weak
partial_given_starts                                                    0.019706
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.058115
identity_change                                                         -0.01846
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 22, dtype: object> | low (0.69, m_expected_assists) | high | weak (0.18 / 0.02 / 0.06) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_passing_accuracy` | Passing and possession | CONDITIONAL_PREDICTOR | medium (11.8) | yes | uncertain: source-reported | RD-03 only | general | <bound method NDFrame.tail of feature                                                  m_passing_accuracy
analysis_group                                       Passing and possession
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                                 ISS-29;P4-B06
null_applicable_pct                                                 11.8311
seasons_with_values                                                       5
coverage                                                             medium
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  general
outfield_position_rho_range                                        0.201749
shape                                                  strongly left-skewed
skew                                                               -1.18487
beyond_3iqr_pct                                                         0.0
tail                                                          moderate/none
max_abs_rho_other_feature                                          0.794658
most_correlated_with                                m_accurate_passes_per90
redundancy                                                              low
redundancy_cluster                                                      NaN
interpretability_judgment                                            medium
pooled_spearman                                                    0.302017
association                                                        moderate
partial_given_starts                                               0.323005
beyond_playing_time                                                retained
max_abs_rho_within_regulars                                        0.499505
identity_change                                                    -0.01282
identity_sensitivity                                                 robust
usefulness_judgment                                               promising
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 23, dtype: object> | low (0.79, m_accurate_passes_per90) | medium | moderate (0.30 / 0.32 / 0.50) | robust (-0.01) | promising | conditional: reliability assessment (ISS-29) |
| `m_long_ball_accuracy` | Passing and possession | CONDITIONAL_PREDICTOR | medium (15.2) | yes | uncertain: source-reported | RD-03 only | general | <bound method NDFrame.tail of feature                                                m_long_ball_accuracy
analysis_group                                       Passing and possession
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                                 ISS-29;P4-B06
null_applicable_pct                                                 15.2166
seasons_with_values                                                       5
coverage                                                             medium
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  general
outfield_position_rho_range                                        0.071217
shape                                               moderately right-skewed
skew                                                               0.540706
beyond_3iqr_pct                                                         0.0
tail                                                          moderate/none
max_abs_rho_other_feature                                          0.393734
most_correlated_with                                     m_clearances_per90
redundancy                                                              low
redundancy_cluster                                                      NaN
interpretability_judgment                                            medium
pooled_spearman                                                    0.352754
association                                                        moderate
partial_given_starts                                               0.365453
beyond_playing_time                                                retained
max_abs_rho_within_regulars                                        0.470365
identity_change                                                    0.003947
identity_sensitivity                                                 robust
usefulness_judgment                                               promising
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 24, dtype: object> | low (0.39, m_clearances_per90) | medium | moderate (0.35 / 0.37 / 0.47) | robust (0.00) | promising | conditional: reliability assessment (ISS-29) |
| `m_cross_accuracy` | Passing and possession | CONDITIONAL_PREDICTOR | low (41.8) | yes | uncertain: source-reported | RD-03 only | general | <bound method NDFrame.tail of feature                                                    m_cross_accuracy
analysis_group                                       Passing and possession
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                                 ISS-29;P4-B06
null_applicable_pct                                                 41.7546
seasons_with_values                                                       5
coverage                                                                low
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  general
outfield_position_rho_range                                        0.195569
shape                                                 strongly right-skewed
skew                                                                2.58276
beyond_3iqr_pct                                                       2.375
tail                                                                  heavy
max_abs_rho_other_feature                                          0.215304
most_correlated_with                                   m_dribbles_succeeded
redundancy                                                              low
redundancy_cluster                                                      NaN
interpretability_judgment                                            medium
pooled_spearman                                                   -0.070224
association                                                            none
partial_given_starts                                              -0.052454
beyond_playing_time                                     mostly playing time
max_abs_rho_within_regulars                                           0.124
identity_change                                                    0.012602
identity_sensitivity                                                 robust
usefulness_judgment                                                 limited
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 25, dtype: object> | low (0.22, m_dribbles_succeeded) | medium | none (-0.07 / -0.05 / 0.12) | robust (0.01) | limited | conditional: reliability assessment (ISS-29) |
| `m_touches` | Passing and possession | CANDIDATE_PREDICTOR | medium (19.0) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                        m_touches
analysis_group                    Passing and possession
eligibility_category                 CANDIDATE_PREDICTOR
condition_ids                                      RD-03
null_applicable_pct                               19.039
seasons_with_values                                    5
coverage                                          medium
missingness_informative                             True
reliability_class                   reliable with caveat
temporal                                      RD-03 only
position_relevance                               general
outfield_position_rho_range                     0.035833
shape                            moderately right-skewed
skew                                            0.749623
beyond_3iqr_pct                                      0.0
tail                                       moderate/none
max_abs_rho_other_feature                       0.971237
most_correlated_with                   m_accurate_passes
redundancy                                          high
redundancy_cluster                                   1.0
interpretability_judgment                           high
pooled_spearman                                 0.465421
association                                     moderate
partial_given_starts                            0.159907
beyond_playing_time                      partly retained
max_abs_rho_within_regulars                     0.424986
identity_change                                -0.017846
identity_sensitivity                              robust
usefulness_judgment                            promising
phase5_recommendation          consider (core candidate)
Name: 26, dtype: object> | high (0.97, m_accurate_passes) | high | moderate (0.47 / 0.16 / 0.42) | robust (-0.02) | promising | consider (core candidate) |
| `m_tackles` | Defensive | CANDIDATE_PREDICTOR | medium (19.8) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                      m_tackles
analysis_group                                               Defensive
eligibility_category                               CANDIDATE_PREDICTOR
condition_ids                                                    RD-03
null_applicable_pct                                            19.8034
seasons_with_values                                                  5
coverage                                                        medium
missingness_informative                                           True
reliability_class                                 reliable with caveat
temporal                                                    RD-03 only
position_relevance                                             general
outfield_position_rho_range                                    0.11039
shape                                            strongly right-skewed
skew                                                           1.17504
beyond_3iqr_pct                                               0.136178
tail                                                     moderate/none
max_abs_rho_other_feature                                     0.875907
most_correlated_with                                      m_recoveries
redundancy                                                      medium
redundancy_cluster                                                 NaN
interpretability_judgment                                         high
pooled_spearman                                               0.314824
association                                                   moderate
partial_given_starts                                         -0.052337
beyond_playing_time                                mostly playing time
max_abs_rho_within_regulars                                    0.07885
identity_change                                              -0.025313
identity_sensitivity                                            robust
usefulness_judgment                        mostly a playing-time proxy
phase5_recommendation          consider only with playing-time context
Name: 27, dtype: object> | medium (0.88, m_recoveries) | high | moderate (0.31 / -0.05 / 0.08) | robust (-0.03) | mostly a playing-time proxy | consider only with playing-time context |
| `m_tackles_per90` | Defensive | CANDIDATE_PREDICTOR | medium (19.8) | yes | reliable with caveat | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                                          m_tackles_per90
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      19.8034
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       general
outfield_position_rho_range                                             0.116617
shape                                                      strongly right-skewed
skew                                                                     25.0058
beyond_3iqr_pct                                                         0.317749
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.489515
most_correlated_with                                          m_recoveries_per90
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.103289
association                                                                 weak
partial_given_starts                                                   -0.063509
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.142341
identity_change                                                        -0.000908
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 28, dtype: object> | low (0.49, m_recoveries_per90) | medium | weak (-0.10 / -0.06 / 0.14) | robust (-0.00) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_interceptions` | Defensive | CANDIDATE_PREDICTOR | medium (22.7) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                          m_interceptions
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      22.7157
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.081579
shape                                                      strongly right-skewed
skew                                                                      1.2645
beyond_3iqr_pct                                                         0.141309
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.839139
most_correlated_with                                                m_recoveries
redundancy                                                                medium
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         0.188606
association                                                                 weak
partial_given_starts                                                   -0.184363
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.090067
identity_change                                                         -0.01806
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 29, dtype: object> | medium (0.84, m_recoveries) | high | weak (0.19 / -0.18 / 0.09) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_interceptions_per90` | Defensive | CANDIDATE_PREDICTOR | medium (22.7) | yes | reliable values, limited coverage | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                                    m_interceptions_per90
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      22.7157
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       general
outfield_position_rho_range                                             0.116947
shape                                                      strongly right-skewed
skew                                                                     1.00888
beyond_3iqr_pct                                                         0.282619
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.621291
most_correlated_with                                             m_interceptions
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.177567
association                                                                 weak
partial_given_starts                                                   -0.194843
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                              0.21165
identity_change                                                         0.005077
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 30, dtype: object> | low (0.62, m_interceptions) | medium | weak (-0.18 / -0.19 / 0.21) | robust (0.01) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_recoveries` | Defensive | CANDIDATE_PREDICTOR | medium (19.2) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                   m_recoveries
analysis_group                                               Defensive
eligibility_category                               CANDIDATE_PREDICTOR
condition_ids                                                    RD-03
null_applicable_pct                                            19.1846
seasons_with_values                                                  5
coverage                                                        medium
missingness_informative                                           True
reliability_class                                 reliable with caveat
temporal                                                    RD-03 only
position_relevance                                             general
outfield_position_rho_range                                   0.026264
shape                                          moderately right-skewed
skew                                                           0.79971
beyond_3iqr_pct                                                    0.0
tail                                                     moderate/none
max_abs_rho_other_feature                                     0.938591
most_correlated_with                                         m_touches
redundancy                                                        high
redundancy_cluster                                                 1.0
interpretability_judgment                                         high
pooled_spearman                                               0.377742
association                                                   moderate
partial_given_starts                                          -0.04788
beyond_playing_time                                mostly playing time
max_abs_rho_within_regulars                                   0.153983
identity_change                                              -0.024569
identity_sensitivity                                            robust
usefulness_judgment                        mostly a playing-time proxy
phase5_recommendation          consider only with playing-time context
Name: 31, dtype: object> | high (0.94, m_touches) | high | moderate (0.38 / -0.05 / 0.15) | robust (-0.02) | mostly a playing-time proxy | consider only with playing-time context |
| `m_recoveries_per90` | Defensive | CANDIDATE_PREDICTOR | medium (19.2) | yes | reliable with caveat | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                                       m_recoveries_per90
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      19.1846
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       general
outfield_position_rho_range                                              0.14446
shape                                                    moderately right-skewed
skew                                                                    0.509307
beyond_3iqr_pct                                                          0.09009
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.491685
most_correlated_with                                       m_interceptions_per90
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.036137
association                                                                 none
partial_given_starts                                                   -0.058169
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.132585
identity_change                                                        -0.009185
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 32, dtype: object> | low (0.49, m_interceptions_per90) | medium | none (-0.04 / -0.06 / 0.13) | robust (-0.01) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_blocked_shots` | Defensive | CANDIDATE_PREDICTOR | low (34.7) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                          m_blocked_shots
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      34.6924
seasons_with_values                                                            5
coverage                                                                     low
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.192379
shape                                                      strongly right-skewed
skew                                                                      2.4079
beyond_3iqr_pct                                                          1.67224
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.836301
most_correlated_with                                                m_clearances
redundancy                                                                medium
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         0.048169
association                                                                 none
partial_given_starts                                                   -0.215991
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.190006
identity_change                                                        -0.024274
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 33, dtype: object> | medium (0.84, m_clearances) | high | none (0.05 / -0.22 / 0.19) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_blocks_per90` | Defensive | CANDIDATE_PREDICTOR | low (34.7) | yes | reliable values, limited coverage | RD-03 + small denominators (P4-B05) | general | <bound method NDFrame.tail of feature                                                           m_blocks_per90
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      34.6924
seasons_with_values                                                            5
coverage                                                                     low
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       general
outfield_position_rho_range                                             0.225181
shape                                                      strongly right-skewed
skew                                                                     1.46404
beyond_3iqr_pct                                                         0.501672
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.717849
most_correlated_with                                             m_blocked_shots
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.263581
association                                                                 weak
partial_given_starts                                                   -0.229227
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.259122
identity_change                                                         0.004846
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 34, dtype: object> | low (0.72, m_blocked_shots) | medium | weak (-0.26 / -0.23 / 0.26) | robust (0.00) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_clearances` | Defensive | CONDITIONAL_PREDICTOR | low (80.7) | no | pending owner decision (RD-04) | RD-03 + incomplete window (RD-04) | general | <bound method NDFrame.tail of feature                                               m_clearances
analysis_group                                           Defensive
eligibility_category                         CONDITIONAL_PREDICTOR
condition_ids                                         RD-04;ISS-28
null_applicable_pct                                        80.6698
seasons_with_values                                              3
coverage                                                       low
missingness_informative                                      False
reliability_class                   pending owner decision (RD-04)
temporal                         RD-03 + incomplete window (RD-04)
position_relevance                                         general
outfield_position_rho_range                                0.17255
shape                                        strongly right-skewed
skew                                                       2.07526
beyond_3iqr_pct                                            2.82486
tail                                                         heavy
max_abs_rho_other_feature                                 0.836301
most_correlated_with                               m_blocked_shots
redundancy                                                  medium
redundancy_cluster                                             NaN
interpretability_judgment                                     high
pooled_spearman                                           0.123275
association                                                   weak
partial_given_starts                                     -0.232161
beyond_playing_time                                partly retained
max_abs_rho_within_regulars                               0.225911
identity_change                                          -0.012536
identity_sensitivity                                        robust
usefulness_judgment                 unknown until RD-04 is decided
phase5_recommendation          conditional: owner decision (RD-04)
Name: 35, dtype: object> | medium (0.84, m_blocked_shots) | high | weak (0.12 / -0.23 / 0.23) | robust (-0.01) | unknown until RD-04 is decided | conditional: owner decision (RD-04) |
| `m_clearances_per90` | Defensive | CONDITIONAL_PREDICTOR | low (80.7) | no | pending owner decision (RD-04) | RD-03 + incomplete window (RD-04) | position-specific | <bound method NDFrame.tail of feature                                         m_clearances_per90
analysis_group                                           Defensive
eligibility_category                         CONDITIONAL_PREDICTOR
condition_ids                                         RD-04;ISS-28
null_applicable_pct                                        80.6698
seasons_with_values                                              3
coverage                                                       low
missingness_informative                                      False
reliability_class                   pending owner decision (RD-04)
temporal                         RD-03 + incomplete window (RD-04)
position_relevance                               position-specific
outfield_position_rho_range                               0.252208
shape                                        strongly right-skewed
skew                                                       1.12964
beyond_3iqr_pct                                                0.0
tail                                                 moderate/none
max_abs_rho_other_feature                                 0.717765
most_correlated_with                                m_blocks_per90
redundancy                                                     low
redundancy_cluster                                             NaN
interpretability_judgment                                   medium
pooled_spearman                                          -0.208588
association                                                   weak
partial_given_starts                                     -0.240156
beyond_playing_time                                partly retained
max_abs_rho_within_regulars                               0.316045
identity_change                                           0.002273
identity_sensitivity                                        robust
usefulness_judgment                 unknown until RD-04 is decided
phase5_recommendation          conditional: owner decision (RD-04)
Name: 36, dtype: object> | low (0.72, m_blocks_per90) | medium | weak (-0.21 / -0.24 / 0.32) | robust (0.00) | unknown until RD-04 is decided | conditional: owner decision (RD-04) |
| `m_aerials_won` | Defensive | CANDIDATE_PREDICTOR | medium (21.7) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                            m_aerials_won
analysis_group                                                         Defensive
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      21.7328
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                              reliable values, limited coverage
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.188449
shape                                                      strongly right-skewed
skew                                                                     2.21528
beyond_3iqr_pct                                                           1.2093
tail                                                               moderate/none
max_abs_rho_other_feature                                                 0.7221
most_correlated_with                                                m_clearances
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                          0.17602
association                                                                 weak
partial_given_starts                                                   -0.147388
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.118736
identity_change                                                         -0.01719
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 37, dtype: object> | low (0.72, m_clearances) | high | weak (0.18 / -0.15 / 0.12) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_aerials_won_percent` | Defensive | CONDITIONAL_PREDICTOR | medium (21.7) | yes | uncertain: source-reported | RD-03 only | general | <bound method NDFrame.tail of feature                                               m_aerials_won_percent
analysis_group                                                    Defensive
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                                 ISS-29;P4-B06
null_applicable_pct                                                 21.7328
seasons_with_values                                                       5
coverage                                                             medium
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  general
outfield_position_rho_range                                        0.090139
shape                                               approximately symmetric
skew                                                               0.208309
beyond_3iqr_pct                                                         0.0
tail                                                          moderate/none
max_abs_rho_other_feature                                          0.717217
most_correlated_with                                    m_duels_won_percent
redundancy                                                              low
redundancy_cluster                                                      NaN
interpretability_judgment                                            medium
pooled_spearman                                                   -0.067801
association                                                            none
partial_given_starts                                              -0.109392
beyond_playing_time                                         partly retained
max_abs_rho_within_regulars                                        0.054226
identity_change                                                    0.000916
identity_sensitivity                                                 robust
usefulness_judgment                                                 limited
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 38, dtype: object> | low (0.72, m_duels_won_percent) | medium | none (-0.07 / -0.11 / 0.05) | robust (0.00) | limited | conditional: reliability assessment (ISS-29) |
| `m_duels_won` | Defensive | CANDIDATE_PREDICTOR | medium (19.1) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                    m_duels_won
analysis_group                                               Defensive
eligibility_category                               CANDIDATE_PREDICTOR
condition_ids                                                    RD-03
null_applicable_pct                                            19.1118
seasons_with_values                                                  5
coverage                                                        medium
missingness_informative                                           True
reliability_class                                 reliable with caveat
temporal                                                    RD-03 only
position_relevance                                             general
outfield_position_rho_range                                   0.138601
shape                                          moderately right-skewed
skew                                                          0.688818
beyond_3iqr_pct                                                    0.0
tail                                                     moderate/none
max_abs_rho_other_feature                                     0.914538
most_correlated_with                                  m_minutes_played
redundancy                                                        high
redundancy_cluster                                                 1.0
interpretability_judgment                                         high
pooled_spearman                                               0.437341
association                                                   moderate
partial_given_starts                                          0.094402
beyond_playing_time                                mostly playing time
max_abs_rho_within_regulars                                   0.242583
identity_change                                              -0.019034
identity_sensitivity                                            robust
usefulness_judgment                        mostly a playing-time proxy
phase5_recommendation          consider only with playing-time context
Name: 39, dtype: object> | high (0.91, m_minutes_played) | high | moderate (0.44 / 0.09 / 0.24) | robust (-0.02) | mostly a playing-time proxy | consider only with playing-time context |
| `m_duels_won_percent` | Defensive | CONDITIONAL_PREDICTOR | medium (19.1) | yes | uncertain: source-reported | RD-03 only | general | <bound method NDFrame.tail of feature                                                 m_duels_won_percent
analysis_group                                                    Defensive
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                                 ISS-29;P4-B06
null_applicable_pct                                                 19.1118
seasons_with_values                                                       5
coverage                                                             medium
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  general
outfield_position_rho_range                                        0.027109
shape                                               approximately symmetric
skew                                                               0.181428
beyond_3iqr_pct                                                    0.135014
tail                                                          moderate/none
max_abs_rho_other_feature                                          0.717217
most_correlated_with                                  m_aerials_won_percent
redundancy                                                              low
redundancy_cluster                                                      NaN
interpretability_judgment                                            medium
pooled_spearman                                                   -0.011521
association                                                            none
partial_given_starts                                              -0.091449
beyond_playing_time                                     mostly playing time
max_abs_rho_within_regulars                                        0.067811
identity_change                                                   -0.014246
identity_sensitivity                                                 robust
usefulness_judgment                                                 limited
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 40, dtype: object> | low (0.72, m_aerials_won_percent) | medium | none (-0.01 / -0.09 / 0.07) | robust (-0.01) | limited | conditional: reliability assessment (ISS-29) |
| `m_yellow_cards` | Discipline and fouls | CANDIDATE_PREDICTOR | medium (11.8) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                           m_yellow_cards
analysis_group                                              Discipline and fouls
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      11.8311
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.134867
shape                                                      strongly right-skewed
skew                                                                     1.07362
beyond_3iqr_pct                                                         0.041288
tail                                                               moderate/none
max_abs_rho_other_feature                                               0.710989
most_correlated_with                                           m_fouls_committed
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         0.295644
association                                                                 weak
partial_given_starts                                                    0.033063
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.061554
identity_change                                                         -0.02213
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 41, dtype: object> | low (0.71, m_fouls_committed) | high | weak (0.30 / 0.03 / 0.06) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_red_cards` | Discipline and fouls | CANDIDATE_PREDICTOR | medium (11.8) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                                              m_red_cards
analysis_group                                              Discipline and fouls
eligibility_category                                         CANDIDATE_PREDICTOR
condition_ids                                                              RD-03
null_applicable_pct                                                      11.8311
seasons_with_values                                                            5
coverage                                                                  medium
missingness_informative                                                     True
reliability_class                                           reliable with caveat
temporal                                                              RD-03 only
position_relevance                                                       general
outfield_position_rho_range                                             0.080907
shape                                                      strongly right-skewed
skew                                                                     3.19582
beyond_3iqr_pct                                                          9.04211
tail                                                                       heavy
max_abs_rho_other_feature                                                0.16082
most_correlated_with                                                m_clearances
redundancy                                                                   low
redundancy_cluster                                                           NaN
interpretability_judgment                                                   high
pooled_spearman                                                         0.064727
association                                                                 none
partial_given_starts                                                    0.001824
beyond_playing_time                                          mostly playing time
max_abs_rho_within_regulars                                             0.069698
identity_change                                                         -0.01569
identity_sensitivity                                                      robust
usefulness_judgment                              limited descriptive association
phase5_recommendation          low expected value; keep available, do not pri...
Name: 42, dtype: object> | low (0.16, m_clearances) | high | none (0.06 / 0.00 / 0.07) | robust (-0.02) | limited descriptive association | low expected value; keep available, do not prioritise |
| `m_fouls_committed` | Discipline and fouls | CANDIDATE_PREDICTOR | medium (20.4) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                              m_fouls_committed
analysis_group                                    Discipline and fouls
eligibility_category                               CANDIDATE_PREDICTOR
condition_ids                                                    RD-03
null_applicable_pct                                            20.4223
seasons_with_values                                                  5
coverage                                                        medium
missingness_informative                                           True
reliability_class                    reliable values, limited coverage
temporal                                                    RD-03 only
position_relevance                                             general
outfield_position_rho_range                                   0.124619
shape                                          moderately right-skewed
skew                                                            0.9625
beyond_3iqr_pct                                                    0.0
tail                                                     moderate/none
max_abs_rho_other_feature                                     0.835388
most_correlated_with                                       m_duels_won
redundancy                                                      medium
redundancy_cluster                                                 NaN
interpretability_judgment                                         high
pooled_spearman                                               0.364001
association                                                   moderate
partial_given_starts                                          0.034629
beyond_playing_time                                mostly playing time
max_abs_rho_within_regulars                                   0.059168
identity_change                                              -0.021271
identity_sensitivity                                            robust
usefulness_judgment                        mostly a playing-time proxy
phase5_recommendation          consider only with playing-time context
Name: 43, dtype: object> | medium (0.84, m_duels_won) | high | moderate (0.36 / 0.03 / 0.06) | robust (-0.02) | mostly a playing-time proxy | consider only with playing-time context |
| `m_fouls_won` | Discipline and fouls | CANDIDATE_PREDICTOR | medium (21.5) | yes | reliable values, limited coverage | RD-03 only | general | <bound method NDFrame.tail of feature                                                    m_fouls_won
analysis_group                                    Discipline and fouls
eligibility_category                               CANDIDATE_PREDICTOR
condition_ids                                                    RD-03
null_applicable_pct                                            21.5144
seasons_with_values                                                  5
coverage                                                        medium
missingness_informative                                           True
reliability_class                    reliable values, limited coverage
temporal                                                    RD-03 only
position_relevance                                             general
outfield_position_rho_range                                   0.149355
shape                                            strongly right-skewed
skew                                                           1.60678
beyond_3iqr_pct                                                0.41744
tail                                                     moderate/none
max_abs_rho_other_feature                                     0.794454
most_correlated_with                                       m_duels_won
redundancy                                                         low
redundancy_cluster                                                 NaN
interpretability_judgment                                         high
pooled_spearman                                               0.421656
association                                                   moderate
partial_given_starts                                            0.1995
beyond_playing_time                                    partly retained
max_abs_rho_within_regulars                                    0.26653
identity_change                                              -0.008815
identity_sensitivity                                            robust
usefulness_judgment                        mostly a playing-time proxy
phase5_recommendation          consider only with playing-time context
Name: 44, dtype: object> | low (0.79, m_duels_won) | high | moderate (0.42 / 0.20 / 0.27) | robust (-0.01) | mostly a playing-time proxy | consider only with playing-time context |
| `m_saves` | Goalkeeping | CANDIDATE_PREDICTOR | high (3.9) | yes | reliable with caveat | RD-03 only | GK only | <bound method NDFrame.tail of feature                                                         m_saves
analysis_group                                              Goalkeeping
eligibility_category                                CANDIDATE_PREDICTOR
condition_ids                                                     RD-03
null_applicable_pct                                              3.8835
seasons_with_values                                                   5
coverage                                                           high
missingness_informative                                            True
reliability_class                                  reliable with caveat
temporal                                                     RD-03 only
position_relevance                                              GK only
outfield_position_rho_range                                         NaN
shape                                           approximately symmetric
skew                                                           0.360937
beyond_3iqr_pct                                                     0.0
tail                                                      moderate/none
max_abs_rho_other_feature                                           NaN
most_correlated_with                                                NaN
redundancy                                              n/a (GK matrix)
redundancy_cluster                                                  NaN
interpretability_judgment                                          high
pooled_spearman                                                0.527454
association                                                      strong
partial_given_starts                                          -0.217201
beyond_playing_time                                     partly retained
max_abs_rho_within_regulars                                    0.221473
identity_change                                                -0.05566
identity_sensitivity                                          sensitive
usefulness_judgment                           promising for goalkeepers
phase5_recommendation          consider in a goalkeeper-specific design
Name: 45, dtype: object> | n/a (GK matrix) () | high | strong (0.53 / -0.22 / 0.22) | sensitive (-0.06) | promising for goalkeepers | consider in a goalkeeper-specific design |
| `m_save_percentage` | Goalkeeping | CONDITIONAL_PREDICTOR | high (4.4) | yes | source-reported, internally consistent | RD-03 only | GK only | <bound method NDFrame.tail of feature                                                        m_save_percentage
analysis_group                                                       Goalkeeping
eligibility_category                                       CONDITIONAL_PREDICTOR
condition_ids                                               ISS-29;P4-B06;ISS-11
null_applicable_pct                                                      4.36893
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                     True
reliability_class                         source-reported, internally consistent
temporal                                                              RD-03 only
position_relevance                                                       GK only
outfield_position_rho_range                                                  NaN
shape                                                     moderately left-skewed
skew                                                                   -0.556779
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                                    NaN
most_correlated_with                                                         NaN
redundancy                                                       n/a (GK matrix)
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                         0.346938
association                                                             moderate
partial_given_starts                                                    0.188873
beyond_playing_time                                              partly retained
max_abs_rho_within_regulars                                             0.133038
identity_change                                                        -0.092438
identity_sensitivity                                                   sensitive
usefulness_judgment                                                    promising
phase5_recommendation          conditional: ISS-29, internal consistency show...
Name: 46, dtype: object> | n/a (GK matrix) () | medium | moderate (0.35 / 0.19 / 0.13) | sensitive (-0.09) | promising | conditional: ISS-29, internal consistency shown (owner may reclassify) |
| `m_clean_sheets` | Goalkeeping | CONDITIONAL_PREDICTOR | high (3.9) | yes | uncertain: source-reported | RD-03 only | GK only | <bound method NDFrame.tail of feature                                                      m_clean_sheets
analysis_group                                                  Goalkeeping
eligibility_category                                  CONDITIONAL_PREDICTOR
condition_ids                                          ISS-29;P4-B06;ISS-11
null_applicable_pct                                                  3.8835
seasons_with_values                                                       5
coverage                                                               high
missingness_informative                                                True
reliability_class                                uncertain: source-reported
temporal                                                         RD-03 only
position_relevance                                                  GK only
outfield_position_rho_range                                             NaN
shape                                               moderately right-skewed
skew                                                               0.895311
beyond_3iqr_pct                                                         0.0
tail                                                          moderate/none
max_abs_rho_other_feature                                               NaN
most_correlated_with                                                    NaN
redundancy                                                  n/a (GK matrix)
redundancy_cluster                                                      NaN
interpretability_judgment                                              high
pooled_spearman                                                    0.671015
association                                                          strong
partial_given_starts                                               0.339688
beyond_playing_time                                                retained
max_abs_rho_within_regulars                                        0.446711
identity_change                                                   -0.040486
identity_sensitivity                                                 robust
usefulness_judgment                                               promising
phase5_recommendation          conditional: reliability assessment (ISS-29)
Name: 47, dtype: object> | n/a (GK matrix) () | high | strong (0.67 / 0.34 / 0.45) | robust (-0.04) | promising | conditional: reliability assessment (ISS-29) |
| `m_goals_conceded` | Goalkeeping | CANDIDATE_PREDICTOR | high (3.9) | yes | reliable with caveat | RD-03 only | GK only | <bound method NDFrame.tail of feature                                                m_goals_conceded
analysis_group                                              Goalkeeping
eligibility_category                                CANDIDATE_PREDICTOR
condition_ids                                                     RD-03
null_applicable_pct                                              3.8835
seasons_with_values                                                   5
coverage                                                           high
missingness_informative                                            True
reliability_class                                  reliable with caveat
temporal                                                     RD-03 only
position_relevance                                              GK only
outfield_position_rho_range                                         NaN
shape                                           approximately symmetric
skew                                                           0.401801
beyond_3iqr_pct                                                     0.0
tail                                                      moderate/none
max_abs_rho_other_feature                                           NaN
most_correlated_with                                                NaN
redundancy                                              n/a (GK matrix)
redundancy_cluster                                                  NaN
interpretability_judgment                                          high
pooled_spearman                                                0.465915
association                                                    moderate
partial_given_starts                                          -0.294824
beyond_playing_time                                            retained
max_abs_rho_within_regulars                                    0.314253
identity_change                                               -0.024846
identity_sensitivity                                             robust
usefulness_judgment                           promising for goalkeepers
phase5_recommendation          consider in a goalkeeper-specific design
Name: 48, dtype: object> | n/a (GK matrix) () | high | moderate (0.47 / -0.29 / 0.31) | robust (-0.02) | promising for goalkeepers | consider in a goalkeeper-specific design |
| `m_goals_conceded_per90` | Goalkeeping | CONDITIONAL_PREDICTOR | high (3.9) | yes | source-reported, internally consistent | RD-03 + small denominators (P4-B05) | GK only | <bound method NDFrame.tail of feature                                                   m_goals_conceded_per90
analysis_group                                                       Goalkeeping
eligibility_category                                       CONDITIONAL_PREDICTOR
condition_ids                                               ISS-29;P4-B06;ISS-11
null_applicable_pct                                                       3.8835
seasons_with_values                                                            5
coverage                                                                    high
missingness_informative                                                     True
reliability_class                         source-reported, internally consistent
temporal                                     RD-03 + small denominators (P4-B05)
position_relevance                                                       GK only
outfield_position_rho_range                                                  NaN
shape                                                    moderately right-skewed
skew                                                                    0.887352
beyond_3iqr_pct                                                              0.0
tail                                                               moderate/none
max_abs_rho_other_feature                                                    NaN
most_correlated_with                                                         NaN
redundancy                                                       n/a (GK matrix)
redundancy_cluster                                                           NaN
interpretability_judgment                                                 medium
pooled_spearman                                                        -0.476557
association                                                             moderate
partial_given_starts                                                   -0.399559
beyond_playing_time                                                     retained
max_abs_rho_within_regulars                                             0.491169
identity_change                                                         0.062167
identity_sensitivity                                                   sensitive
usefulness_judgment                                                    promising
phase5_recommendation          conditional: ISS-29, internal consistency show...
Name: 49, dtype: object> | n/a (GK matrix) () | medium | moderate (-0.48 / -0.40 / 0.49) | sensitive (0.06) | promising | conditional: ISS-29, internal consistency shown (owner may reclassify) |
| `m_penalty_saves` | Goalkeeping | CANDIDATE_PREDICTOR | low (31.6) | yes | reliable values, limited coverage | RD-03 only | GK only | <bound method NDFrame.tail of feature                                                 m_penalty_saves
analysis_group                                              Goalkeeping
eligibility_category                                CANDIDATE_PREDICTOR
condition_ids                                                     RD-03
null_applicable_pct                                             31.5534
seasons_with_values                                                   5
coverage                                                            low
missingness_informative                                            True
reliability_class                     reliable values, limited coverage
temporal                                                     RD-03 only
position_relevance                                              GK only
outfield_position_rho_range                                         NaN
shape                                             strongly right-skewed
skew                                                            1.28722
beyond_3iqr_pct                                                     0.0
tail                                                      moderate/none
max_abs_rho_other_feature                                           NaN
most_correlated_with                                                NaN
redundancy                                              n/a (GK matrix)
redundancy_cluster                                                  NaN
interpretability_judgment                                          high
pooled_spearman                                                0.077304
association                                                        none
partial_given_starts                                          -0.026484
beyond_playing_time                                 mostly playing time
max_abs_rho_within_regulars                                    0.066531
identity_change                                               -0.029345
identity_sensitivity                                             robust
usefulness_judgment                                             limited
phase5_recommendation          consider in a goalkeeper-specific design
Name: 50, dtype: object> | n/a (GK matrix) () | high | none (0.08 / -0.03 / 0.07) | robust (-0.03) | limited | consider in a goalkeeper-specific design |
| `m_goals_prevented` | Goalkeeping | CONDITIONAL_PREDICTOR | medium (12.6) | no | pending owner decision (RD-04) | RD-03 + incomplete window (RD-04) | GK only | <bound method NDFrame.tail of feature                                          m_goals_prevented
analysis_group                                         Goalkeeping
eligibility_category                         CONDITIONAL_PREDICTOR
condition_ids                                                RD-04
null_applicable_pct                                        12.6214
seasons_with_values                                              5
coverage                                                    medium
missingness_informative                                      False
reliability_class                   pending owner decision (RD-04)
temporal                         RD-03 + incomplete window (RD-04)
position_relevance                                         GK only
outfield_position_rho_range                                    NaN
shape                                       moderately left-skewed
skew                                                     -0.946154
beyond_3iqr_pct                                                0.0
tail                                                 moderate/none
max_abs_rho_other_feature                                      NaN
most_correlated_with                                           NaN
redundancy                                         n/a (GK matrix)
redundancy_cluster                                             NaN
interpretability_judgment                                   medium
pooled_spearman                                            0.14489
association                                                   weak
partial_given_starts                                      0.262675
beyond_playing_time                                       retained
max_abs_rho_within_regulars                               0.303216
identity_change                                          -0.067813
identity_sensitivity                                     sensitive
usefulness_judgment                 unknown until RD-04 is decided
phase5_recommendation          conditional: owner decision (RD-04)
Name: 51, dtype: object> | n/a (GK matrix) () | medium | weak (0.14 / 0.26 / 0.30) | sensitive (-0.07) | unknown until RD-04 is decided | conditional: owner decision (RD-04) |
| `m_rating` | Overall match rating | CANDIDATE_PREDICTOR | high (5.7) | yes | reliable with caveat | RD-03 only | general | <bound method NDFrame.tail of feature                                            m_rating
analysis_group                         Overall match rating
eligibility_category                    CANDIDATE_PREDICTOR
condition_ids                                         RD-03
null_applicable_pct                                 5.71533
seasons_with_values                                       5
coverage                                               high
missingness_informative                                True
reliability_class                      reliable with caveat
temporal                                         RD-03 only
position_relevance                                  general
outfield_position_rho_range                        0.149551
shape                               approximately symmetric
skew                                              -0.322284
beyond_3iqr_pct                                         0.0
tail                                          moderate/none
max_abs_rho_other_feature                          0.670363
most_correlated_with                     m_expected_assists
redundancy                                              low
redundancy_cluster                                      NaN
interpretability_judgment      low (composite source score)
pooled_spearman                                     0.58138
association                                          strong
partial_given_starts                               0.406024
beyond_playing_time                                retained
max_abs_rho_within_regulars                        0.664146
identity_change                                   -0.007649
identity_sensitivity                                 robust
usefulness_judgment                               promising
phase5_recommendation             consider (core candidate)
Name: 52, dtype: object> | low (0.67, m_expected_assists) | low (composite source score) | strong (0.58 / 0.41 / 0.66) | robust (-0.01) | promising | consider (core candidate) |

Columns not in the matrix: `position_group_season` (candidate context, see `CANDIDATE_FEATURE_GROUPS.md`), 8 club-context columns (RS5-12 pending), 3 excluded columns, and target, identity, temporal-audit and status columns (never predictors).
