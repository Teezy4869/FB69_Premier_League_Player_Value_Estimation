# Feature Redundancy Summary (Phase 4.3)

Date: 2026-11-09. Official dataset (SHA-256 verified), five official seasons. Code: `src/phase4/bivariate.py`. Evidence: `evidence/correlation_matrix_spearman_outfield.csv` (46 x 46), `correlation_matrix_pearson_outfield.csv`, `correlation_matrix_pair_counts_outfield.csv`, `correlation_matrix_spearman_goalkeeper.csv`, `strong_feature_pairs_*.csv`, `redundancy_clusters_outfield.csv`, `per90_vs_total.csv`. Figure: `figures/fig43_07_spearman_correlation_matrix_outfield.png`.

**This is a description of overlap, not feature selection.** No feature was removed, merged or preferred. Deciding which representation to keep is a feature-design decision (P4-D03), and RD-04 and ISS-29 features remain conditional.

## Method

- Spearman (primary) and Pearson on outfield rows (DEF, MID, FWD) for the 46 outfield features. Goalkeeper metrics were compared on goalkeeper rows with age, appearances, starts and rating.
- Pairwise-complete rows. Pair counts range from 381 (`big_chances_created` with `clearances`, RD-04) to about 2,500; no cell is below 30 pairs.
- Strong pair: \|Spearman\| >= 0.8. Redundancy cluster: features linked by \|Spearman\| >= 0.9 (single linkage).
- Season stability: the same pair's Spearman within each season.

## Redundancy clusters (|Spearman| >= 0.9)

| Cluster | Size | Members | Min \|rho\| within | Median \|rho\| within |
|---:|---:|---|---:|---:|
| 1 | 7 | m_appearances, m_starts, m_minutes_played, m_accurate_passes, m_touches, m_recoveries, m_duels_won | 0.723 | 0.898 |
| 2 | 5 | m_shots, m_shots_on_target, m_expected_goals, m_non_penalty_xg, m_expected_goals_on_target | 0.840 | 0.914 |
| 3 | 2 | m_shots_per90, m_shots_on_target_per90 | 0.903 | 0.903 |
| 4 | 2 | m_expected_assists, m_chances_created | 0.929 | 0.929 |

1. **Playing-time volume:** season totals of frequent actions grow with minutes, so they carry nearly the same rank information as playing time.
2. **Shots and xG:** xG is computed from shots, xG on target from shots on target, and non-penalty xG differs from xG only by penalties (0.992).
3. **Shot rates:** shots per 90 and shots on target per 90.
4. **Chance creation:** xA is built from the chances a player creates.

## Strong outfield pairs (|Spearman| >= 0.8): 54

All are positive. Relations: overlapping definition (shots, goals and xG) 15, volume metric scales with playing time 12, season totals of different actions (shared dependence on playing time) 10, same metric family (Defensive) 6, playing-time measures 3, same metric family (Passing and possession) 3, same metric family (Attacking) 3, overlapping definition (chance creation and xA) 2. The within-season Spearman of each pair varies by at most 0.07, so the overlap is structural and not season-dependent.

| Feature A | Feature B | Spearman | Pearson raw | n | Within-season Spearman | Relation |
|---|---|---:|---:|---:|---|---|
| `m_starts` | `m_minutes_played` | 0.995 | 0.996 | 2541 | 0.99–1.00 | playing-time measures |
| `m_expected_goals` | `m_non_penalty_xg` | 0.992 | 0.982 | 2138 | 0.98–1.00 | overlapping definition (shots, goals and xG) |
| `m_accurate_passes` | `m_touches` | 0.971 | 0.955 | 2224 | 0.97–0.97 | same metric family (Passing and possession) |
| `m_appearances` | `m_minutes_played` | 0.941 | 0.925 | 2541 | 0.93–0.96 | playing-time measures |
| `m_touches` | `m_recoveries` | 0.939 | 0.900 | 2220 | 0.94–0.95 | season totals of different actions (shared dependence on playing time) |
| `m_minutes_played` | `m_touches` | 0.932 | 0.897 | 2224 | 0.92–0.94 | volume metric scales with playing time |
| `m_expected_assists` | `m_chances_created` | 0.929 | 0.939 | 2089 | 0.92–0.93 | overlapping definition (chance creation and xA) |
| `m_shots` | `m_shots_on_target` | 0.929 | 0.952 | 1898 | 0.92–0.93 | overlapping definition (shots, goals and xG) |
| `m_shots` | `m_expected_goals` | 0.926 | 0.908 | 2139 | 0.92–0.94 | overlapping definition (shots, goals and xG) |
| `m_shots` | `m_non_penalty_xg` | 0.925 | 0.906 | 2138 | 0.92–0.93 | overlapping definition (shots, goals and xG) |
| `m_appearances` | `m_starts` | 0.925 | 0.910 | 2541 | 0.91–0.94 | playing-time measures |
| `m_starts` | `m_touches` | 0.924 | 0.888 | 2224 | 0.92–0.93 | volume metric scales with playing time |
| `m_shots_on_target` | `m_expected_goals_on_target` | 0.918 | 0.949 | 1884 | 0.91–0.93 | overlapping definition (shots, goals and xG) |
| `m_minutes_played` | `m_duels_won` | 0.915 | 0.876 | 2222 | 0.90–0.92 | volume metric scales with playing time |
| `m_expected_goals` | `m_expected_goals_on_target` | 0.910 | 0.965 | 1887 | 0.90–0.92 | overlapping definition (shots, goals and xG) |
| `m_starts` | `m_duels_won` | 0.907 | 0.869 | 2222 | 0.89–0.92 | volume metric scales with playing time |
| `m_shots_on_target` | `m_expected_goals` | 0.906 | 0.937 | 1898 | 0.90–0.91 | overlapping definition (shots, goals and xG) |
| `m_minutes_played` | `m_recoveries` | 0.904 | 0.866 | 2220 | 0.90–0.92 | volume metric scales with playing time |
| `m_shots_per90` | `m_shots_on_target_per90` | 0.903 | 0.880 | 1898 | 0.89–0.91 | same metric family (Attacking) |
| `m_shots_on_target` | `m_non_penalty_xg` | 0.901 | 0.930 | 1897 | 0.89–0.91 | overlapping definition (shots, goals and xG) |
| `m_starts` | `m_recoveries` | 0.898 | 0.861 | 2220 | 0.90–0.91 | volume metric scales with playing time |
| `m_non_penalty_xg` | `m_expected_goals_on_target` | 0.896 | 0.938 | 1886 | 0.88–0.92 | overlapping definition (shots, goals and xG) |
| `m_shots` | `m_touches_opposition_box` | 0.896 | 0.892 | 2165 | 0.88–0.91 | same metric family (Attacking) |
| `m_accurate_passes` | `m_recoveries` | 0.894 | 0.819 | 2220 | 0.88–0.91 | season totals of different actions (shared dependence on playing time) |
| `m_touches_opposition_box` | `m_non_penalty_xg` | 0.887 | 0.878 | 2118 | 0.88–0.89 | season totals of different actions (shared dependence on playing time) |
| `m_accurate_passes` | `m_accurate_long_passes` | 0.884 | 0.819 | 2132 | 0.87–0.90 | same metric family (Passing and possession) |
| `m_touches_opposition_box` | `m_expected_goals` | 0.881 | 0.865 | 2119 | 0.87–0.89 | season totals of different actions (shared dependence on playing time) |
| `m_goals` | `m_expected_goals_on_target` | 0.879 | 0.952 | 1887 | 0.86–0.90 | overlapping definition (shots, goals and xG) |
| `m_tackles` | `m_recoveries` | 0.876 | 0.825 | 2200 | 0.87–0.90 | same metric family (Defensive) |
| `m_recoveries` | `m_duels_won` | 0.864 | 0.803 | 2219 | 0.84–0.89 | same metric family (Defensive) |
| `m_touches` | `m_duels_won` | 0.864 | 0.783 | 2222 | 0.85–0.87 | season totals of different actions (shared dependence on playing time) |
| `m_accurate_long_passes` | `m_touches` | 0.856 | 0.795 | 2132 | 0.84–0.88 | same metric family (Passing and possession) |
| `m_appearances` | `m_duels_won` | 0.855 | 0.813 | 2222 | 0.83–0.88 | volume metric scales with playing time |
| `m_minutes_played` | `m_accurate_passes` | 0.852 | 0.774 | 2224 | 0.85–0.86 | volume metric scales with playing time |
| `m_goals` | `m_expected_goals` | 0.846 | 0.930 | 2246 | 0.82–0.86 | overlapping definition (shots, goals and xG) |
| `m_starts` | `m_accurate_passes` | 0.846 | 0.766 | 2224 | 0.84–0.85 | volume metric scales with playing time |
| `m_shots_on_target` | `m_touches_opposition_box` | 0.844 | 0.871 | 1891 | 0.82–0.87 | same metric family (Attacking) |
| `m_shots` | `m_expected_goals_on_target` | 0.840 | 0.881 | 1887 | 0.82–0.86 | overlapping definition (shots, goals and xG) |
| `m_interceptions` | `m_recoveries` | 0.839 | 0.802 | 2122 | 0.80–0.86 | same metric family (Defensive) |
| `m_touches` | `m_tackles` | 0.838 | 0.752 | 2203 | 0.81–0.86 | season totals of different actions (shared dependence on playing time) |
| `m_tackles` | `m_duels_won` | 0.837 | 0.791 | 2203 | 0.81–0.86 | same metric family (Defensive) |
| `m_goals` | `m_non_penalty_xg` | 0.837 | 0.909 | 2138 | 0.81–0.86 | overlapping definition (shots, goals and xG) |
| `m_blocked_shots` | `m_clearances` | 0.836 | 0.866 | 430 | 0.79–0.84 | same metric family (Defensive) |
| `m_duels_won` | `m_fouls_committed` | 0.835 | 0.800 | 2184 | 0.81–0.85 | season totals of different actions (shared dependence on playing time) |
| `m_goals` | `m_shots_on_target` | 0.828 | 0.917 | 1898 | 0.81–0.85 | overlapping definition (shots, goals and xG) |
| `m_accurate_long_passes` | `m_recoveries` | 0.819 | 0.735 | 2131 | 0.78–0.84 | season totals of different actions (shared dependence on playing time) |
| `m_appearances` | `m_touches` | 0.818 | 0.775 | 2224 | 0.80–0.84 | volume metric scales with playing time |
| `m_big_chances_created` | `m_expected_assists` | 0.815 | 0.877 | 1531 | 0.78–0.85 | overlapping definition (chance creation and xA) |
| `m_appearances` | `m_expected_assists` | 0.813 | 0.633 | 2505 | 0.80–0.82 | volume metric scales with playing time |
| `m_touches` | `m_interceptions` | 0.813 | 0.749 | 2123 | 0.80–0.83 | season totals of different actions (shared dependence on playing time) |
| `m_tackles` | `m_interceptions` | 0.811 | 0.744 | 2111 | 0.80–0.84 | same metric family (Defensive) |
| `m_appearances` | `m_recoveries` | 0.806 | 0.761 | 2220 | 0.79–0.85 | volume metric scales with playing time |
| `m_accurate_passes` | `m_interceptions` | 0.805 | 0.693 | 2123 | 0.80–0.83 | season totals of different actions (shared dependence on playing time) |
| `m_goals` | `m_shots` | 0.802 | 0.864 | 2224 | 0.79–0.81 | overlapping definition (shots, goals and xG) |

## Goalkeeper pairs (|Spearman| >= 0.8, goalkeeper rows): 8

| Feature A | Feature B | Spearman | Pearson raw | n | Relation |
|---|---|---:|---:|---:|---|
| `m_appearances` | `m_starts` | 0.996 | 0.999 | 205 | playing-time measures |
| `m_saves` | `m_goals_conceded` | 0.951 | 0.939 | 198 | same metric family (Goalkeeping) |
| `m_appearances` | `m_saves` | 0.945 | 0.936 | 198 | volume metric scales with playing time |
| `m_starts` | `m_saves` | 0.944 | 0.935 | 198 | volume metric scales with playing time |
| `m_appearances` | `m_goals_conceded` | 0.911 | 0.898 | 198 | volume metric scales with playing time |
| `m_starts` | `m_goals_conceded` | 0.910 | 0.897 | 198 | volume metric scales with playing time |
| `m_starts` | `m_clean_sheets` | 0.883 | 0.845 | 198 | volume metric scales with playing time |
| `m_appearances` | `m_clean_sheets` | 0.882 | 0.844 | 198 | volume metric scales with playing time |

All goalkeeper volume metrics (saves, goals conceded, clean sheets) follow how often the goalkeeper plays. Goalkeeper minutes are mostly missing (ISS-11), so starts and appearances stand in for playing time.

## Totals vs per-90 rates (outfield rows)

| Total | Rate | n | Spearman total-rate | Spearman total-minutes | Spearman rate-minutes |
|---|---|---:|---:|---:|---:|
| `m_shots` | `m_shots_per90` | 2224 | 0.709 | 0.667 | 0.026 |
| `m_shots_on_target` | `m_shots_on_target_per90` | 1898 | 0.719 | 0.484 | -0.181 |
| `m_accurate_passes` | `m_accurate_passes_per90` | 2223 | 0.569 | 0.852 | 0.113 |
| `m_accurate_long_passes` | `m_accurate_long_passes_per90` | 2132 | 0.749 | 0.729 | 0.163 |
| `m_tackles` | `m_tackles_per90` | 2203 | 0.446 | 0.792 | -0.112 |
| `m_interceptions` | `m_interceptions_per90` | 2123 | 0.621 | 0.721 | -0.005 |
| `m_recoveries` | `m_recoveries_per90` | 2220 | 0.397 | 0.904 | 0.032 |
| `m_blocked_shots` | `m_blocks_per90` | 1794 | 0.718 | 0.519 | -0.133 |
| `m_clearances` | `m_clearances_per90` | 531 | 0.712 | 0.656 | 0.016 |

Totals correlate with minutes at 0.48–0.90; their per-90 rates at -0.18 to 0.16. Rates remove most of the playing-time component and are therefore far less redundant with the volume block, but they are unstable on small minute totals (P4-B05).

## Observations for later phases (no action taken here)

- Near-duplicates: `starts`/`minutes_played` (0.995), `expected_goals`/`non_penalty_xg` (0.992), `accurate_passes`/`touches` (0.971).
- Raw Pearson is higher than Spearman for goal-xG pairs (for example goals vs xG on target: Pearson 0.952, Spearman 0.879): both totals are extreme for the same elite forwards.
- Models sensitive to collinearity will see heavily overlapping inputs; models that use both totals and rates will see playing time twice. These are inputs to feature design (P4-D03), not decisions.
- Several overlapping features are conditional: `touches_opposition_box` and `expected_goals_on_target` (RD-04) sit in the attacking and shot-xG blocks; `clearances` (RD-04) pairs strongly with `blocked_shots` on only 430 rows.
