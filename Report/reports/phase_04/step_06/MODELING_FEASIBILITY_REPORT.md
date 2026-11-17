# Phase 4.6 Modeling Feasibility Report

Date: 2026-11-09. Official dataset (SHA-256 verified before and after), scope `rs5_v1`. Code: `src/phase4/feasibility.py`. Notebook: section 4.6. Evidence: `evidence/` (12 tables, `feasibility_summary.json`). Companion documents: `FEATURE_ASSESSMENT_MATRIX.md`, `CANDIDATE_FEATURE_GROUPS.md`, `SPLIT_STRATEGY_ASSESSMENT.md`, `MODELING_RISK_REGISTER.md`. **No model was trained, no feature engineered, no split executed.** Objective A (end-of-season estimation, D6); RD-03 applies throughout.

## 1. Answers

| Question | Answer |
|---|---|
| Promising feature groups | Attacking output and xG, chance creation and xA, passing quality (especially for defenders), rating; plus the playing-time and age axes and position context |
| Sufficient coverage | High (<= 10% null, 5 seasons): playing time, goals, assists, xA, rating, GK metrics; low: shots on target, big chances, crosses, blocked shots, clearances, penalty saves |
| Acceptable reliability | 25 reliable with caveat, 15 reliable with limited coverage, 2 source-reported but consistent; 6 unverifiable source-reported; 5 pending |
| Temporal concerns | All features (RD-03); stronger for RD-04 (incomplete windows) and per-90 rates (P4-B05); season drift P4-B09 |
| Redundant | Playing-time cluster (incl. accurate passes, touches, recoveries, duels won), shots-xG cluster, shot rates, xA-chances |
| Position-specific | GK metrics; goals, assists, shots on target per 90, big chances, dribbles, chances created, clearances per 90 (strength varies >= 0.25 across outfield positions); age |
| Remain conditional | 5 RD-04, 8 ISS-29 (2 may be reclassified by the owner), 8 club context |
| Evaluation risks | 18 in the risk register; 5 high (repeated players, temporal mismatch, batch effects, heavy-tailed target, informative missingness) |
| Split strategies | Grouped-by-player K-fold (primary) + 2024/25 temporal hold-out (secondary); never random rows |

## 2. Feature assessment summary

Phase 5 consideration (53 analysed features): 13 core candidates; 3 playing-time representations; 1 non-linear age; 3 with missingness handling; 5 only with playing-time context; 3 goalkeeper-specific; 12 low expected value; 8 ISS-29 conditional; 5 RD-04 pending. Core candidates: goals, assists, shots, shots per 90, dribbles, xG, non-penalty xG, xA, accurate passes, accurate passes per 90, chances created, touches, rating.

## 3. Regression feasibility

| Aspect | Evidence | Implication |
|---|---|---|
| Size | 2,697 usable targets, 1,196 players (2.3 rows each); GK 206 rows / 95 players | Moderate model complexity; GK too few for a complex separate model |
| Target skew and scale | Skew 2.31 raw, -0.84 log10; max/median 15; top 5% of rows hold 21% of value | Consider log-scale training with raw-scale reporting; compare with raw baseline |
| Heteroscedasticity | Raw IQR grows from EUR 5m to 42m with group level; log10 IQR 0.40–0.78 (mostly 0.5–0.6) | Supports log-scale consideration |
| Coarseness | 84 distinct values | Ties in metrics; prefer error metrics robust to heaping |
| Outliers | 32 rows beyond 3 IQR, genuine | Keep; consider robust losses or log scale |
| Irreducible spread | p75/p25 2.5–4 within regular position x role cells | Prediction will be imperfect; report uncertainty |
| Missingness | Complete-case on core candidates keeps 78% of outfield rows (74% DEF), drops fringe players | Status-aware plan (P4-D01, ISS-25) |
| Position heterogeneity | Levels, metric meanings, missingness differ | Compare pooled-with-position-context and position-specific designs |
| Season heterogeneity | Batch age 66–206 days; level x1.2–1.75 within strata; rate drift | Season-aware evaluation and reporting |
| Temporal mismatch | 44.10% of appearances after valuation; label tracks earlier minutes (0.52 vs 0.38) | State RD-03; no causal or forecasting claims |
| Identity | 533 P4-B01 rows, lower-valued; relationships robust | P4-B01 sensitivity run for every result |
| Redundancy | 54 strong pairs, 4 clusters | Deliberate representations; check collinearity |

## 4. Target transformation considerations

Raw target: interpretable in EUR, but squared errors are dominated by elite players and spread grows with level. Log target: near-constant spread across groups, milder tail, mild left skew (-0.84); predictions must be back-transformed for EUR reporting (median, not mean, unless corrected). Both should be examined in Phase 5. The stored target column is never changed.

## 5. Recommendations for Phase 5 (feasibility only)

1. Record owner decisions: RD-04, RS5-12, P4-D05, P4-B05, ISS-29 reclassification (P4-D03), RD-03 confirmation, RD-01.
2. Fix the evaluation design (P4-D02) before training: grouped-by-player K-fold plus 2024/25 temporal hold-out, reported by position, season and returning vs new players.
3. Design status-aware missingness handling and fit any preprocessing on training folds only.
4. Choose one playing-time representation, a non-linear age form, and representations for the shots-xG and xA-chances families.
5. Compare pooled (with position context) and position-specific designs; handle goalkeepers separately.
6. Report RD-03, P4-B01 sensitivity and season-level errors with every result.

## 6. Conclusion

Regression modeling is **feasible but conditional** on the design constraints above and on the open owner decisions. The evidence supports a modest, well-evaluated model on a log-scale target with deliberate feature representations; it does not support random splits, blind imputation, unreviewed use of RD-04 or club-context columns, or causal and forecasting interpretations.
