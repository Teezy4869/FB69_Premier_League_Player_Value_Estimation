# FB69 Phase 4 Entry Checklist

Use this checklist at the start of every Phase 4 step (4.1 EDA and later). Each line points to its condition in `PHASE4_CONDITION_REGISTER.md`. If an item can't be met, stop and report it. Don't work around it.

## Before you start (every step)

- [ ] The owner has issued an instruction for this step. A Phase 4.0 verdict on its own doesn't start Phase 4.1 (P4-C01).
- [ ] Read `data/releases/fb69_player_season_integrated_rs5_v1/docs/PHASE4_CONDITIONS.md`, this checklist and `PHASE4_FEATURE_ELIGIBILITY.md`.
- [ ] Load only `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet`. Check SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd` in code, and stop on a mismatch (P4-A01).
- [ ] Get seasons from `src/research_scope/scope.py` (`load_scope()`), not from a hard-coded list. Run `check_table`/`check_parquet` on every derived table you save (P4-A02).
- [ ] Record the interpreter and package versions in every output. `.venv314` doesn't run on this machine; `.venv` (Python 3.13.13, same package freeze) was used for Phase 4.0 pending owner confirmation (ENV-P4-01).
- [ ] Write outputs to new paths only, such as `reports/phase_04/step_XX/`. Never write to the release, `data/research_rs5/`, `configs/` or historical folders (P4-A10).
- [ ] Don't install packages or replace `.venv314` without approval.
- [ ] Tests: `tests/research_scope` can run directly. The full suite runs only through `src/phase3/step3_qa_run_full_tests.py <evidence_dir>`. Never run plain `unittest discover -s tests` (ISS-18).

## During EDA (Phase 4.1): MUST

- [ ] Frame everything as Objective A, end-of-season estimation. Not forecasting, and not "performance determines value" (P4-A06).
- [ ] State the RD-03 caveat next to every feature-target relationship. The label is a valuation from a median of 150 days before season end; 44.10% of appearances and 43.66% of minutes come after it.
- [ ] Describe the target on raw and log scales. Report staleness by season, and note the league-wide valuation batches (P4-B03, ISS-21).
- [ ] Analyse season-aware. Season and valuation timing are confounded: the share over 90 days ranges from 2.91% in 2020/21 to 78.03% in 2021/22 (ISS-21, ISS-22).
- [ ] Describe missingness by `s_*` status, season, position and target availability. Count MISSING, UNVERIFIED_POSITION, CONFLICTING, UNSUPPORTED and OBSERVED_ZERO separately (P4-A07, ISS-25, ISS-27, P4-B02).
- [ ] Treat goalkeepers separately where metrics differ. GK-only nulls on outfield rows mean "not applicable" (ISS-11).
- [ ] Label the 5 RD-04 metrics and the 8 club-context columns "pending decision" wherever they appear.
- [ ] Flag the 8 source-reported rates as not independently verified (ISS-29).
- [ ] Keep all 2,747 rows. Report the 50 missing targets by reason (37 only later valuations, 11 no history, 2 no identity). Analyses that need a target use the 2,697 usable rows, and say so.
- [ ] Keep the 12 targets older than 365 days and label them weak labels. The 2019-05-23 valuation is on a 2020/21 row, not a 2019/20 record (RD-01).
- [ ] Where a conclusion depends on target values, check it against the identity sensitivity subset (533 rows not AUTO_EXACT_VALIDATED or INCONCLUSIVE). Mapping coverage is not mapping precision (P4-B01, ISS-01).
- [ ] Keep elite-player tails. Use robust statistics or transforms for description (P4-A09).
- [ ] State that the dataset isn't claimed to be leakage-free in the broad sense.

## During EDA (Phase 4.1): MUST NOT

- [ ] Use any 2019/20 data, comparison or sensitivity analysis, or six-season integrated v1 (P4-A01, P4-A02).
- [ ] Use `target_*`, `temporal_*`, ids, identity, provenance or population-evidence columns, or `nationality_profile_present_day`, as predictors or as "features" in any ranking (P4-A03–A05).
- [ ] Use `m_key_passes` (no data) (ISS-28).
- [ ] Impute, zero-fill, or drop rows or columns silently. Don't convert UNKNOWN, UNVERIFIED or null to zero (P4-A07).
- [ ] Filter by staleness or introduce an age cap (P4-A08, ISS-22, RD-01).
- [ ] Remove outliers (P4-A09).
- [ ] Change D4, D6, the scope, the crosswalk or any mapping. Don't adjudicate El Mohamady, Wesley, Chesters or Tauriainen (RD-02, ISS-04).
- [ ] Decide RD-01, RD-02, RD-03, RD-04, RS5-12, ISS-04 or the ISS-01 labels, or record any of them as approved.
- [ ] Use random row-level train/test splits, even for "quick checks" (RS5-11).
- [ ] Do feature selection, feature engineering, preprocessing, model training or model evaluation. Those belong to later steps.
- [ ] Present correlations as causal, or as evidence that full-season performance caused the earlier valuation (RD-03).
- [ ] Redistribute raw data or imply that Transfermarkt licensed it (ISS-16).

## Before later phases

| Before | Must be resolved | Conditions |
|---|---|---|
| Preprocessing | Per-metric missingness plan; role of the `s_*` columns | ISS-25, ISS-27, P4-D01 |
| Feature selection / final modeling | Owner decisions on RD-04 and RS5-12; reliability of the 8 source-reported rates | RD-04, RS5-12, ISS-29, P4-D03 |
| Model evaluation | Split strategy: grouped by `canonical_player_id` and/or temporal by season | RS5-11, P4-D02 |
| Final modeling dataset acceptance | Human identity labels; decisions recorded on RD-01 and RD-02; identity sensitivity run | ISS-01, RD-01, RD-02, P4-B01 |
| Final modeling report | Owner's position on RD-03 (keep D4 and report, the default, or a new rule as a new version) | RD-03 |
| Next protection check | Add the Phase 4 output root to `protect.py`, or take a new baseline | P4-D04 |
| Final acceptance | Re-run the full suite with the protected runner | ENV-P4-02 |
