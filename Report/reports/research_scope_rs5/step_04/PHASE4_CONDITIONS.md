# Recommended Conditions for Phase 4 (EDA and later modeling)

These conditions follow from the rs5 audit. Phase 4 hasn't started.

1. **Dataset.** Use only `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet`. Integrated v1 is historical and must not be used for research.
2. **Scope.** Five seasons, read from `configs/research_scope.yaml`. No 2019/20 data, comparison or sensitivity analysis.
3. **Objective A only.** Present results as end-of-season estimation. They aren't forecasts, and they don't show performance causing value (RD-03).
4. **Column roles.** Candidate predictors are only the `FEATURE_*` and `CONTEXT_FEATURE` columns. Never use `target_*`, `temporal_*` or `identity_*` columns, ids, or `nationality_profile_present_day` as predictors. Club context needs a decision first (RS5-12).
5. **Splits.** Group by `canonical_player_id`, or split by season. A random row split leaks identity (687 players span several seasons).
6. **Missingness.** Read `s_*` before treating a null. Don't zero-fill, impute or drop silently; report any handling. Missingness concentrates in goalkeepers and fringe players.
7. **Features needing a decision (RD-04).** `clearances`, `clearances_per90`, `expected_goals_on_target`, `touches_opposition_box`, `goals_prevented`. Exclude `key_passes`.
8. **Target.** Heavily right-skewed; a log scale is natural for analysis. Keep staleness as reported; no filter without a documented analysis (ISS-22). Account for season-level valuation batches.
9. **Identity sensitivity.** Compare results with and without rows whose `identity_evidence_tier` isn't `AUTO_EXACT_VALIDATED`, or whose `identity_rs5_validation_label` is `INCONCLUSIVE` (ISS-01, RD-02).
10. **Outliers.** Keep elite-player tails. Use robust methods or transformations instead of deleting.
