# Phase 4.3 Bivariate Analysis Report

Date: 2026-11-09. Official dataset `player_season_integrated_rs5_v1` (SHA-256 `4d94ec73…eedd`, verified before reading and unchanged after), scope `rs5_v1` (2020/21–2024/25, from `load_scope()`; `check_parquet()` on the dataset, `check_table()` on the derived position-season table). Code: `src/phase4/bivariate.py`. Notebook: section 4.3 of `FB69_report.ipynb`. Evidence: `evidence/` (28 tables, `bivariate_summary.json`). Figures: `figures/fig43_01`–`fig43_07`. Detail: `FEATURE_TARGET_ASSOCIATION_SUMMARY.md`, `FEATURE_REDUNDANCY_SUMMARY.md`.

> **Objective A, RD-03.** The target is the latest valuation on or before season end. In practice it is mostly a mid-season valuation (median 150 days before season end), while the metrics cover the whole season, about 44% of it after the valuation date. Every result below is a descriptive association. None of them shows that performance caused or determined the valuation, and later performance cannot have produced an earlier valuation.

## 1. Research questions and answers

| Question | Short answer |
|---|---|
| Which variables are associated with market value? | Playing time (Spearman about 0.53), rating (0.58), xA (0.56), shots and goals (0.50–0.51), and most attacking and creative totals (0.40–0.50). Among goalkeepers: clean sheets (0.67), saves (0.53). Defensive per-90 rates are weakly negative. Age is weakly negative overall but inverted-U shaped |
| Linear or monotonic? | Mostly monotonic, not linear on the euro scale. 21 of 53 binned trends rise monotonically; age is clearly non-monotonic |
| Do Pearson and Spearman differ? | Yes, in both directions, by up to 0.13. Raw Pearson is inflated by the elite tail for attacking totals and understated for playing-time and goalkeeper volumes. Log10 Pearson is close to Spearman |
| Variation by position and season? | Position changes the strength (goals: 0.33 for defenders, 0.64 for forwards), not the direction. Within-season associations are stable; seasons shift the target level (batch timing, ISS-21) |
| Redundant features? | 54 outfield pairs with \|Spearman\| >= 0.8 and four clusters at >= 0.9: playing-time volumes, shots and xG, shot rates, xA and chances created |
| Suspicious associations? | Volume associations that vanish or reverse given playing time (P4-B08), goalkeeper saves and goals conceded, informative missingness, rating as a composite, season level shifts, RD-04 features (section 8) |

## 2. Methodology

- **Variables:** the 53 features analysed in Phase 4.2 (40 candidate, 13 conditional predictors in the Phase 4.0 register). Excluded from predictor analysis: 16 target and 8 `temporal_*` columns (P4-A03), 33 id and identity columns (P4-A05), `nationality_profile_present_day` (P4-A04), `key_passes` (ISS-28), 8 club-context columns (RS5-12, pending), 53 `s_*` status columns (P4-D01). RD-04 and ISS-29 features are analysed and flagged, not approved.
- **Rows:** usable target (2,697 of 2,747) and non-null feature, pairwise-complete. Goalkeeper metrics on goalkeeper rows only. No null was filled, no row dropped from the dataset, no value capped; the 533 P4-B01 rows stay in every main result.
- **Feature-target statistics:** Pearson (raw EUR and log10, computed on the fly), Spearman with a player-cluster bootstrap 95% interval (500 replicates, seed 43; players are resampled because 687 of them have several seasons, RS5-11), binned target quantiles (equal-count bins, at least 30 rows per bin), partial Spearman given minutes and given starts, within-position and within-season Spearman (groups below 30 pairs left empty), and Spearman without the P4-B01 rows.
- **Categories:** target quantiles with counts; rank effect size epsilon-squared (Kruskal-Wallis H / (N-1)). No p-values are reported, because rows of the same player are not independent.
- **Feature-feature:** Spearman and Pearson matrices with pair counts, on outfield rows (46 features) and on goalkeeper rows (11 variables).
- **Thresholds:** fixed before reading the results and recorded in `bivariate_summary.json`. Minimum group size 30, strong pair 0.8, redundancy cluster 0.9, strength words <0.3 weak, 0.3–0.5 moderate, >=0.5 strong.

## 3. Numerical features vs target

Full table: `FEATURE_TARGET_ASSOCIATION_SUMMARY.md`. Figure: `fig43_01`.

| Reading | Features |
|---|---|
| Strong positive (>= 0.5) | rating 0.58, xA 0.56, minutes 0.54, appearances 0.53, starts 0.53, shots 0.51, goals 0.50; GK: clean sheets 0.67, saves 0.53 |
| Moderate positive | touches in the box 0.50 (RD-04), xG 0.49, accurate passes 0.48, non-penalty xG 0.47, touches 0.47, assists 0.46, duels won 0.44, shots on target 0.44, dribbles 0.43, fouls won 0.42, chances created 0.42, xG on target 0.41 (RD-04), big chances 0.40, recoveries 0.38, fouls committed 0.36, long-ball accuracy 0.35, tackles 0.32, passing accuracy 0.30; GK: goals conceded 0.47, save % 0.35 |
| Weak | yellow cards 0.30, shots per 90 0.29, accurate passes per 90 0.23, long passes 0.22, shots on target per 90 0.21, interceptions 0.19, crosses 0.18, aerials won 0.18, clearances 0.12 (RD-04), red cards 0.07; negative: age -0.17, interceptions per 90 -0.18, clearances per 90 -0.21 (RD-04), blocks per 90 -0.26, tackles per 90 -0.10, long passes per 90 -0.08, cross accuracy -0.07, aerials won % -0.07; GK: goals conceded per 90 -0.48 (moderate) |
| No clear association (interval contains 0) | duels won %, recoveries per 90, blocked shots; GK: goals prevented (RD-04), penalty saves |

**Scatterplots and trends (`fig43_02`):** playing time rises cleanly from a median of about EUR 2m to EUR 28–30m across bins, but the spread inside each bin stays wide (interquartile ratio about 3–5). Attacking totals are zero-heavy; their trend becomes steep only in the top bins. Rating rises steadily. Tackles per 90 is flat to slightly negative.

## 4. Pearson vs Spearman, linearity, age

- Spearman exceeds raw Pearson by 0.09–0.13 for goalkeeper volumes, defensive totals and appearances: monotonic, but non-linear on the euro scale.
- Raw Pearson exceeds Spearman by 0.08–0.10 for shots on target, xG on target and big chances created: a few elite attackers dominate the raw scale. On log10 these values drop to about the Spearman level.
- Binned trends: 21 monotonic, 14 mostly monotonic with minor reversals, 15 irregular (near-zero associations or noisy goalkeeper bins), 3 inverted U.
- **Age** (`fig43_03`): median EUR 4.75m for ages 17–21, about EUR 20–22m at 23–26, EUR 2m above 32.5. The inverted U holds in every outfield position; goalkeepers peak later (28–30). Spearman -0.17 understates this. Age band explains far more rank variation (epsilon-squared 0.20) than position (0.03). Within position: GK -0.41, DEF -0.25, MID -0.09, FWD 0.01.

## 5. Playing time as a common driver (`fig43_04`, P4-B08)

| Feature | Spearman | Partial given starts |
|---|---:|---:|
| appearances | 0.53 | 0.14 |
| duels won | 0.44 | 0.09 |
| recoveries | 0.38 | -0.05 |
| tackles | 0.32 | -0.05 |
| interceptions | 0.19 | -0.18 |
| blocked shots | 0.05 | -0.22 |
| GK saves | 0.53 | -0.22 |
| GK goals conceded | 0.47 | -0.29 |
| GK clean sheets | 0.67 | 0.34 |
| rating | 0.58 | 0.41 |
| long-ball accuracy | 0.35 | 0.37 |
| shots / xA / touches in box | 0.51 / 0.56 / 0.50 | 0.33 / 0.33 / 0.33 |
| age | -0.17 | -0.34 |

Most volume associations are playing time. Associations that remain given starts concern attacking output, creativity, passing quality and rating. Defensive and goalkeeper volumes turn negative for a given playing time. This is consistent with a team-strength or team-style confounder, but club context is pending (RS5-12), so the hypothesis cannot be tested here. Per-90 rates correlate with minutes at -0.18 to 0.16 (totals: 0.48–0.90).

## 6. Position and season (`fig43_05`)

- Position modulates strength: goals 0.33 (DEF) to 0.64 (FWD); assists 0.28 to 0.57; touches in the box 0.42 to 0.64; rating 0.39 (GK) to 0.68 (FWD); passing measures are relatively strong for defenders (accurate passes per 90 0.48, passing accuracy 0.44). Only `accurate_long_passes_per90` crosses zero (-0.19 GK to 0.15 DEF, both weak).
- Seasons: outfield within-season ranges are at most about 0.1–0.2. Goalkeeper season ranges reach 0.47, but rest on about 40 rows per season and are not interpreted.

## 7. Categorical features vs target (`fig43_06`)

| Grouping | Epsilon-squared | Note |
|---|---:|---|
| Position | 0.026 | GK median EUR 6m (n 206), DEF 12m (924), MID 15m (817), FWD 15m (750); FWD p90 EUR 55m |
| Season (grouping key) | 0.015 | Medians EUR 10, 10, 15, 13, 17m; confounded with valuation batch timing (ISS-21, RD-03) |
| Position x season | 0.043 | Smallest cell 39 (GK); season medians move by a factor of 1.5 (MID, FWD) to 2.2 (GK, DEF) within a position |
| Age band (derived) | 0.196 | Inverted U |
| Minutes band (derived; missing separate) | 0.249 | Median EUR 2.5m under 90 minutes, EUR 20m at 900+; missing minutes (199 rows, mostly GK) EUR 7m |

Spread within each position is much larger than the difference between positions. Groups below 30 rows (goalkeeper age bands under 25) are not interpreted.

## 8. Feature-feature relationships

See `FEATURE_REDUNDANCY_SUMMARY.md` and `fig43_07`. Outfield matrix: 46 x 46, pair counts 381–2,541, no empty cell. 54 strong pairs, all positive. Relations: 15 within shots-goals-xG, 12 volume vs playing time, 10 totals of different actions, 6 defensive family, 3 playing-time measures, 3 passing, 3 attacking, 2 chance creation and xA. Within-season variation of the strong pairs is at most 0.07. Four redundancy clusters at 0.9. Goalkeepers: 8 strong pairs, all within the playing-time block. No feature was removed or preferred.

## 9. Identity sensitivity (P4-B01)

Without the 533 P4-B01 rows: median absolute change 0.016, largest 0.092 (goalkeeper save percentage), five features above 0.05 (four goalkeeper metrics and age, -0.17 to -0.24), no sign change for any association with \|rho\| > 0.05. The P4-B01 rows are lower-valued (median EUR 8m vs 15m), so excluding them would shift the population; they stay in the main analysis. Identities are still not human-validated (ISS-01).

## 10. Associations requiring further investigation

1. **Informative missingness:** for 51 of 52 features with null rows, the median target is lower on null rows (rating: EUR 2.35m vs 15m). Nulls sit on low-minute fringe players (P4-B07, ISS-27). `goals_prevented` is the exception: 18 of its 26 null goalkeeper rows are in 2024/25.
2. **Goalkeeper volume sign change** under playing-time control; clean sheets probably carry team strength.
3. **Defensive actions negative given playing time:** possible team-style confounder; untestable while RS5-12 is open.
4. **Rating** is a composite source score; its association overlaps the other metrics.
5. **Season level shifts** cannot be separated from valuation batch timing.
6. **RD-04 features** look associated (`touches_opposition_box` 0.50, `expected_goals_on_target` 0.41). Their window evidence remains incomplete; association is not a reason to approve them.
7. **Age** is non-monotonic; linear and rank coefficients misrepresent it.

## 11. Limitations

- RD-03 (label precedes part of the season); RS5-11 (non-independence: intervals only for feature-target Spearman, point values elsewhere).
- Pairwise-complete coefficients use different rows per feature; with non-random missingness (ISS-27), high-null features describe a higher-minutes population.
- Confounders not addressed: team strength and club context (RS5-12), season batches (ISS-21). Partial correlations control only for playing time.
- Goalkeepers: 206 rows, minutes mostly missing (ISS-11); imprecise.
- Coarse target (84 distinct values) creates ties; average ranks used.
- Source limitations unchanged: ISS-29, RS5-13, ISS-07, ISS-01.
- Only monotonic/linear association and binned trends are examined; interactions are not.

## 12. Conclusion

Market value is most strongly associated with playing time, attacking and creative output, and rating. Most volume associations are a playing-time effect, and defensive and goalkeeper volumes reverse once playing time is fixed. Age has an inverted-U relationship. Relationships are monotonic rather than linear in euros, so rank or log-scale summaries are appropriate. Position modulates strength but not direction. Seasons shift the target level in a way confounded with valuation timing. Candidate features overlap heavily and structurally. No feature was selected, removed or transformed, and all results remain descriptive under RD-03.
