# Feature-Target Association Summary (Phase 4.3)

Date: 2026-11-09. Official dataset `player_season_integrated_rs5_v1` (SHA-256 `4d94ec73…eedd`, verified before reading), scope `rs5_v1` (2020/21–2024/25, from `load_scope()`). Code: `src/phase4/bivariate.py`. Source table: `evidence/feature_target_association.csv` (all columns), with `feature_target_binned_shape.csv`, `feature_target_pooled_vs_within.csv` and `identity_sensitivity_spearman.csv`.

> **RD-03 applies to every row.** The target is the latest valuation on or before season end, in practice mostly a mid-season valuation, while the features cover the whole season. These are descriptive associations. They do not show that performance caused or determined the valuation. Analysing a conditional feature (RD-04, ISS-29) does not approve it.

## How to read the table

- **n / Players:** pairwise-complete rows (usable target, non-null feature, applicable position) and the distinct players behind them. Goalkeeper metrics use goalkeeper rows only.
- **Missing %:** share of applicable rows with a target where the feature is null. Nulls are not filled.
- **Spearman [95% CI]:** rank correlation; interval from a player-cluster bootstrap (500 replicates, seed 43).
- **Partial given starts:** Spearman after removing the dependence that feature and target share with starts. Results given minutes are in the CSV and are nearly identical for outfield features.
- **Within-position / within-season range:** smallest and largest Spearman inside a position or a season (groups with at least 30 pairs; number of seasons reported in brackets).
- **Without P4-B01:** Spearman without the 533 identity-sensitivity rows (comparison only).
- **Reading:** strength of Spearman (<0.3 weak, 0.3–0.5 moderate, >=0.5 strong), or "no clear monotonic association" when the interval contains 0.

Reading counts: moderate positive 20, weak positive 10, strong positive 9, weak negative 8, no clear monotonic association 5, moderate negative 1.

| Feature | Group | n | Players | Missing % | Pearson raw | Pearson log10 | Spearman [95% CI] | Partial given starts | Within-position range | Within-season range | Without P4-B01 | Binned trend | Reading | Flags |
|---|---|---:|---:|---:|---:|---:|---|---:|---|---|---:|---|---|---|
| `m_clean_sheets` | Goalkeeping | 198 | 87 | 3.9 | 0.68 | 0.63 | 0.67 [0.54, 0.77] | 0.34 | 0.67 (GK only) | 0.63 to 0.78 (5) | 0.63 | monotonic | strong positive | ISS-29 source-reported; GK rows only (ISS-11) |
| `m_rating` | Overall match rating | 2567 | 1127 | 4.8 | 0.56 | 0.57 | 0.58 [0.55, 0.61] | 0.41 | 0.39 to 0.68 | 0.54 to 0.62 (5) | 0.57 | monotonic | strong positive |  |
| `m_expected_assists` | Expected (model-based) metrics | 2668 | 1177 | 1.1 | 0.56 | 0.46 | 0.56 [0.52, 0.60] | 0.33 | 0.43 to 0.66 | 0.53 to 0.58 (5) | 0.53 | monotonic | strong positive |  |
| `m_minutes_played` | Playing time and participation | 2498 | 1108 | 7.4 | 0.47 | 0.52 | 0.54 [0.50, 0.58] | 0.05 | 0.46 to 0.61 | 0.52 to 0.57 (5) | 0.50 | monotonic | strong positive |  |
| `m_appearances` | Playing time and participation | 2696 | 1195 | 0.0 | 0.45 | 0.55 | 0.53 [0.50, 0.57] | 0.14 | 0.46 to 0.64 | 0.52 to 0.56 (5) | 0.48 | monotonic | strong positive |  |
| `m_starts` | Playing time and participation | 2696 | 1195 | 0.0 | 0.45 | 0.51 | 0.53 [0.49, 0.57] |  | 0.46 to 0.64 | 0.52 to 0.56 (5) | 0.49 | monotonic | strong positive |  |
| `m_saves` | Goalkeeping | 198 | 87 | 3.9 | 0.40 | 0.50 | 0.53 [0.39, 0.64] | -0.22 | 0.53 (GK only) | 0.32 to 0.61 (5) | 0.47 | mostly monotonic (minor reversals) | strong positive | GK rows only (ISS-11) |
| `m_shots` | Attacking | 2216 | 954 | 17.8 | 0.57 | 0.48 | 0.51 [0.47, 0.56] | 0.33 | 0.43 to 0.58 | 0.50 to 0.54 (5) | 0.50 | monotonic | strong positive |  |
| `m_goals` | Attacking | 2498 | 1108 | 7.4 | 0.55 | 0.41 | 0.50 [0.46, 0.54] | 0.28 | 0.33 to 0.64 | 0.46 to 0.54 (5) | 0.48 | monotonic | strong positive |  |
| `m_touches_opposition_box` | Attacking | 2158 | 929 | 20.0 | 0.56 | 0.46 | 0.50 [0.44, 0.54] | 0.33 | 0.42 to 0.64 | 0.46 to 0.55 (5) | 0.48 | monotonic | moderate positive | RD-04 pending |
| `m_expected_goals` | Expected (model-based) metrics | 2242 | 981 | 16.9 | 0.53 | 0.41 | 0.49 [0.44, 0.53] | 0.32 | 0.39 to 0.59 | 0.45 to 0.53 (5) | 0.48 | monotonic | moderate positive |  |
| `m_accurate_passes` | Passing and possession | 2414 | 1041 | 10.5 | 0.42 | 0.43 | 0.48 [0.44, 0.52] | 0.22 | 0.53 to 0.69 | 0.46 to 0.54 (5) | 0.45 | mostly monotonic (minor reversals) | moderate positive |  |
| `m_non_penalty_xg` | Expected (model-based) metrics | 2132 | 923 | 20.9 | 0.52 | 0.41 | 0.47 [0.42, 0.52] | 0.32 | 0.39 to 0.54 | 0.44 to 0.50 (5) | 0.46 | monotonic | moderate positive |  |
| `m_goals_conceded` | Goalkeeping | 198 | 87 | 3.9 | 0.33 | 0.43 | 0.47 [0.34, 0.58] | -0.29 | 0.47 (GK only) | 0.21 to 0.56 (5) | 0.44 | irregular | moderate positive | GK rows only (ISS-11) |
| `m_touches` | Passing and possession | 2216 | 954 | 17.8 | 0.42 | 0.44 | 0.47 [0.42, 0.51] | 0.16 | 0.51 to 0.54 | 0.47 to 0.50 (5) | 0.45 | monotonic | moderate positive |  |
| `m_assists` | Attacking | 2514 | 1118 | 6.8 | 0.52 | 0.42 | 0.46 [0.42, 0.50] | 0.22 | 0.28 to 0.57 | 0.45 to 0.49 (5) | 0.44 | mostly monotonic (minor reversals) | moderate positive |  |
| `m_duels_won` | Defensive | 2214 | 953 | 17.9 | 0.37 | 0.41 | 0.44 [0.40, 0.48] | 0.09 | 0.38 to 0.52 | 0.41 to 0.48 (5) | 0.42 | monotonic | moderate positive |  |
| `m_shots_on_target` | Attacking | 1894 | 835 | 29.8 | 0.53 | 0.42 | 0.44 [0.38, 0.49] | 0.31 | 0.32 to 0.54 | 0.43 to 0.45 (5) | 0.43 | mostly monotonic (minor reversals) | moderate positive |  |
| `m_dribbles_succeeded` | Attacking | 2060 | 895 | 23.6 | 0.40 | 0.38 | 0.43 [0.38, 0.48] | 0.26 | 0.25 to 0.50 | 0.41 to 0.49 (5) | 0.42 | monotonic | moderate positive |  |
| `m_fouls_won` | Discipline and fouls | 2150 | 919 | 20.3 | 0.39 | 0.38 | 0.42 [0.37, 0.47] | 0.20 | 0.31 to 0.46 | 0.40 to 0.46 (5) | 0.41 | monotonic | moderate positive |  |
| `m_chances_created` | Passing and possession | 2149 | 935 | 20.3 | 0.49 | 0.41 | 0.42 [0.37, 0.47] | 0.26 | 0.11 to 0.53 | 0.41 to 0.44 (5) | 0.41 | monotonic | moderate positive |  |
| `m_expected_goals_on_target` | Expected (model-based) metrics | 1883 | 832 | 30.2 | 0.50 | 0.38 | 0.41 [0.35, 0.46] | 0.30 | 0.27 to 0.52 | 0.38 to 0.43 (5) | 0.40 | monotonic | moderate positive | RD-04 pending |
| `m_big_chances_created` | Attacking | 1529 | 722 | 43.3 | 0.48 | 0.40 | 0.40 [0.34, 0.45] | 0.27 | 0.17 to 0.48 | 0.35 to 0.44 (5) | 0.41 | mostly monotonic (minor reversals) | moderate positive |  |
| `m_recoveries` | Defensive | 2212 | 951 | 18.0 | 0.30 | 0.35 | 0.38 [0.33, 0.42] | -0.05 | 0.41 to 0.43 | 0.37 to 0.45 (5) | 0.35 | monotonic | moderate positive |  |
| `m_fouls_committed` | Discipline and fouls | 2180 | 939 | 19.2 | 0.30 | 0.35 | 0.36 [0.32, 0.41] | 0.03 | 0.31 to 0.43 | 0.34 to 0.40 (5) | 0.34 | monotonic | moderate positive |  |
| `m_long_ball_accuracy` | Passing and possession | 2324 | 999 | 13.8 | 0.32 | 0.30 | 0.35 [0.30, 0.40] | 0.37 | 0.02 to 0.33 | 0.30 to 0.41 (5) | 0.36 | mostly monotonic (minor reversals) | moderate positive | ISS-29 source-reported |
| `m_save_percentage` | Goalkeeping | 197 | 87 | 4.4 | 0.24 | 0.33 | 0.35 [0.21, 0.48] | 0.19 | 0.35 (GK only) | 0.13 to 0.60 (5) | 0.25 | inverted U (peak in bin 4) | moderate positive | ISS-29 source-reported; GK rows only (ISS-11) |
| `m_tackles` | Defensive | 2195 | 945 | 18.6 | 0.22 | 0.29 | 0.31 [0.27, 0.36] | -0.05 | 0.33 to 0.44 | 0.27 to 0.35 (5) | 0.29 | mostly monotonic (minor reversals) | moderate positive |  |
| `m_passing_accuracy` | Passing and possession | 2414 | 1041 | 10.5 | 0.25 | 0.30 | 0.30 [0.24, 0.35] | 0.32 | 0.24 to 0.44 | 0.19 to 0.35 (5) | 0.29 | monotonic | moderate positive | ISS-29 source-reported |
| `m_yellow_cards` | Discipline and fouls | 2414 | 1041 | 10.5 | 0.23 | 0.28 | 0.30 [0.25, 0.34] | 0.03 | 0.23 to 0.48 | 0.23 to 0.33 (5) | 0.27 | mostly monotonic (minor reversals) | weak positive |  |
| `m_shots_per90` | Attacking | 2216 | 954 | 17.8 | 0.31 | 0.28 | 0.29 [0.24, 0.35] | 0.32 | 0.20 to 0.35 | 0.26 to 0.36 (5) | 0.30 | mostly monotonic (minor reversals) | weak positive | per-90 on small denominators (P4-B05) |
| `m_accurate_passes_per90` | Passing and possession | 2413 | 1041 | 10.5 | 0.21 | 0.23 | 0.23 [0.17, 0.29] | 0.22 | 0.26 to 0.48 | 0.11 to 0.30 (5) | 0.22 | mostly monotonic (minor reversals) | weak positive | per-90 on small denominators (P4-B05) |
| `m_accurate_long_passes` | Passing and possession | 2324 | 999 | 13.8 | 0.13 | 0.14 | 0.22 [0.17, 0.27] | -0.14 | 0.33 to 0.49 | 0.19 to 0.29 (5) | 0.20 | mostly monotonic (minor reversals) | weak positive |  |
| `m_shots_on_target_per90` | Attacking | 1894 | 835 | 29.8 | 0.24 | 0.18 | 0.21 [0.14, 0.27] | 0.31 | 0.09 to 0.34 | 0.16 to 0.28 (5) | 0.22 | irregular | weak positive | per-90 on small denominators (P4-B05) |
| `m_interceptions` | Defensive | 2117 | 912 | 21.5 | 0.10 | 0.17 | 0.19 [0.14, 0.24] | -0.18 | 0.24 to 0.32 | 0.19 to 0.24 (5) | 0.17 | irregular | weak positive |  |
| `m_successful_crosses` | Passing and possession | 1598 | 763 | 40.7 | 0.21 | 0.18 | 0.18 [0.12, 0.25] | 0.02 | 0.14 to 0.20 | 0.15 to 0.22 (5) | 0.16 | irregular | weak positive |  |
| `m_aerials_won` | Defensive | 2144 | 922 | 20.5 | 0.09 | 0.14 | 0.18 [0.12, 0.23] | -0.15 | 0.10 to 0.29 | 0.12 to 0.24 (5) | 0.16 | irregular | weak positive |  |
| `m_goals_prevented` | Goalkeeping | 180 | 86 | 12.6 | 0.14 | 0.09 | 0.14 [-0.03, 0.27] | 0.26 | 0.14 (GK only) | 0.03 to 0.31 (4) | 0.08 | irregular | no clear monotonic association | RD-04 pending; GK rows only (ISS-11) |
| `m_clearances` | Defensive | 527 | 477 | 80.5 | 0.03 | 0.11 | 0.12 [0.03, 0.21] | -0.23 | 0.14 to 0.31 | 0.07 to 0.15 (3) | 0.11 | irregular | weak positive | RD-04 pending |
| `m_penalty_saves` | Goalkeeping | 141 | 64 | 31.6 | 0.05 | 0.04 | 0.08 [-0.06, 0.24] | -0.03 | 0.08 (GK only) | -0.18 to 0.24 (2) | 0.05 | mostly monotonic (minor reversals) | no clear monotonic association | GK rows only (ISS-11) |
| `m_red_cards` | Discipline and fouls | 2414 | 1041 | 10.5 | 0.04 | 0.06 | 0.06 [0.03, 0.10] | 0.00 | 0.02 to 0.14 | 0.04 to 0.11 (5) | 0.05 | irregular | weak positive |  |
| `m_blocked_shots` | Defensive | 1791 | 806 | 33.6 | -0.00 | 0.05 | 0.05 [-0.01, 0.12] | -0.22 | -0.00 to 0.19 | 0.01 to 0.09 (5) | 0.02 | irregular | no clear monotonic association |  |
| `m_duels_won_percent` | Defensive | 2214 | 953 | 17.9 | -0.02 | -0.01 | -0.01 [-0.07, 0.05] | -0.09 | 0.09 to 0.12 | -0.05 to 0.03 (5) | -0.03 | irregular | no clear monotonic association | ISS-29 source-reported |
| `m_recoveries_per90` | Defensive | 2212 | 951 | 18.0 | -0.06 | -0.03 | -0.04 [-0.09, 0.02] | -0.06 | -0.06 to 0.09 | -0.07 to 0.06 (5) | -0.05 | irregular | no clear monotonic association | per-90 on small denominators (P4-B05) |
| `m_aerials_won_percent` | Defensive | 2144 | 922 | 20.5 | -0.08 | -0.08 | -0.07 [-0.13, -0.01] | -0.11 | -0.04 to 0.05 | -0.12 to -0.01 (5) | -0.07 | irregular | weak negative | ISS-29 source-reported |
| `m_cross_accuracy` | Passing and possession | 1598 | 763 | 40.7 | -0.07 | -0.09 | -0.07 [-0.12, -0.01] | -0.05 | -0.13 to 0.07 | -0.15 to -0.04 (5) | -0.06 | mostly monotonic (minor reversals) | weak negative | ISS-29 source-reported |
| `m_accurate_long_passes_per90` | Passing and possession | 2324 | 999 | 13.8 | -0.07 | -0.15 | -0.08 [-0.15, -0.02] | -0.17 | -0.19 to 0.15 | -0.18 to -0.02 (5) | -0.08 | irregular | weak negative | per-90 on small denominators (P4-B05) |
| `m_tackles_per90` | Defensive | 2195 | 945 | 18.6 | -0.10 | -0.11 | -0.10 [-0.16, -0.05] | -0.06 | -0.12 to -0.01 | -0.16 to -0.08 (5) | -0.10 | mostly monotonic (minor reversals) | weak negative | per-90 on small denominators (P4-B05) |
| `age_at_season_end_years` | Player context and age | 2697 | 1196 | 0.0 | -0.15 | -0.13 | -0.17 [-0.22, -0.11] | -0.34 | -0.41 to 0.01 | -0.23 to -0.07 (5) | -0.24 | inverted U (peak in bin 5) | weak negative |  |
| `m_interceptions_per90` | Defensive | 2117 | 912 | 21.5 | -0.20 | -0.17 | -0.18 [-0.24, -0.12] | -0.19 | -0.16 to -0.04 | -0.21 to -0.11 (5) | -0.17 | irregular | weak negative | per-90 on small denominators (P4-B05) |
| `m_clearances_per90` | Defensive | 527 | 477 | 80.5 | -0.20 | -0.17 | -0.21 [-0.29, -0.11] | -0.24 | -0.35 to -0.10 | -0.24 to -0.05 (3) | -0.21 | irregular | weak negative | RD-04 pending; per-90 on small denominators (P4-B05) |
| `m_blocks_per90` | Defensive | 1791 | 806 | 33.6 | -0.24 | -0.26 | -0.26 [-0.32, -0.20] | -0.23 | -0.38 to -0.15 | -0.29 to -0.27 (5) | -0.26 | monotonic | weak negative | per-90 on small denominators (P4-B05) |
| `m_goals_conceded_per90` | Goalkeeping | 198 | 87 | 3.9 | -0.41 | -0.46 | -0.48 [-0.59, -0.33] | -0.40 | -0.48 (GK only) | -0.67 to -0.30 (5) | -0.41 | inverted U (peak in bin 2) | moderate negative | ISS-29 source-reported; GK rows only (ISS-11); per-90 on small denominators (P4-B05) |

## Main points

1. **Strongest associations:** rating, expected assists, the three playing-time measures, shots and goals (Spearman 0.50–0.58). Among goalkeepers: clean sheets (0.67) and saves (0.53), on 198 rows from 87 goalkeepers.
2. **Playing time explains most volume associations:** given starts, appearances, recoveries, tackles, duels won, fouls and cards fall to about 0.1 or below. Rating, shots, xG, xA, touches in the box, passing and long-ball accuracy keep 0.28–0.41 (P4-B08).
3. **Sign changes under playing-time control:** goalkeeper saves (+0.53 to -0.22) and goals conceded (+0.47 to -0.29), and defensive totals (interceptions, blocked shots, clearances, aerials won) turn negative. A team-context explanation is plausible but cannot be examined while RS5-12 is pending.
4. **Age:** weak negative Spearman (-0.17), but the binned trend is an inverted U (peak at 25–26 years). The coefficient understates the relationship.
5. **Raw Pearson is unreliable for this target:** it exceeds Spearman for attacking totals (driven by the elite tail) and falls below it for playing-time and goalkeeper volumes (monotonic, non-linear on the euro scale).
6. **Position changes strength, not direction:** for example goals 0.33 (defenders) to 0.64 (forwards). Only `accurate_long_passes_per90` crosses zero across positions (-0.19 to 0.15, both weak).
7. **Seasons:** within-season ranges are small for outfield features. Goalkeeper season values (about 40 rows per season) are not interpreted.
8. **Identity sensitivity:** median change 0.016, largest 0.09 (goalkeeper save percentage), no sign change for any \|rho\| > 0.05.
