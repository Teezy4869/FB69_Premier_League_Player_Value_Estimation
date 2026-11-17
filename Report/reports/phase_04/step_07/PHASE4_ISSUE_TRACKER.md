# FB69 Phase 4 Issue Tracker

Date: 2026-11-09 (Phase 4.7; updated for the owner decisions of 2026-11-09). Rendered from `step_00/phase4_condition_register.yaml` by `evidence/scripts/render_tracker_and_odr.py`; the YAML remains the single source. An owner decision records a governance policy; it does not resolve the empirical issue, so decided conditions stay open here unless they carry a status.

Phase 4 status: **ACCEPTED** (G4.7 CONDITIONAL PASS (Claude, before owner acceptance) -> PASS after verification of the four owner conditions). ENV-P4-03: OWNER_ACCEPTED.

Conditions: 55; open: 47; resolved: 8; open with an owner decision: 17; open and still needing an owner decision: 0.

Blocking final modeling: 12 before the owner decisions (RS5-11, ISS-01, P4-B01, ISS-27, ISS-25, RD-01, RD-04, RS5-12, RD-02, P4-D01, P4-D02, P4-D03); 8 still blocking after them (RS5-11, ISS-01, P4-B01, ISS-27, ISS-25, P4-D01, P4-D02, P4-D03). The others are decided but their limitations are carried forward.

## Open: owner decided (policy set; limitation or implementation remains) (17)

| ID | Class | Title | Required action | Owner decision (2026-11-09) | Originally blocked final modeling | Still blocks final modeling | Target phase |
|---|---|---|---|---|---|---|---|
| P4-A06 | A | Objective A framing only (D6) | State the objective and the RD-03 caveat in every Phase 4 report. | ODR-02 OWNER_DECIDED / CARRIED_FORWARD | No | No | 4.1 onward |
| RS5-11 | A | No random row-level split as an evaluation strategy | Prohibit random row splits. Later, assess (a) grouped split by canonical_player_id and (b) temporal split by season. Not implemented in Phase 4.0. | ODR-14 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Before model evaluation |
| RD-03 | B | Temporal construct mismatch (also ISS-02) | Report the mismatch with every relationship; never read it as performance causing the earlier valuation. Owner decision still open: keep D4 and report (default) or approve a new rule (new version). Claude Code must not change D4/D6. | ODR-01 OWNER_DECIDED / CARRIED_FORWARD | No | No | 4.1 onward (interpretation); decision before final modeling report |
| ISS-01 | B | Identity mappings not human-validated | Safe: describing coverage, counts and automated-validator results. Caution: any target-based conclusion carries a small wrong-target risk. Run identity sensitivity (P4-B01) where results matter. Owner labels the sample. | ODR-07 OWNER_DECIDED / OPEN_PENDING_EVIDENCE | Yes | Yes | Before final modeling dataset acceptance |
| P4-B01 | B | Identity sensitivity | Use as a sensitivity subset where identity matters; do not drop these rows from the main analysis. | ODR-08 OWNER_DECIDED_IMPLEMENTATION_PENDING / CARRIED_FORWARD | Yes | Yes | Before final results |
| ISS-22 | B | Staleness filters change the season mix | No filter. Any proposed filter needs a documented analysis and owner approval. | ODR-04 OWNER_DECIDED / CARRIED_FORWARD | No | No | Only if a filter is proposed |
| ISS-27 | B | Missingness is not random | Report missingness patterns; plan treatment before preprocessing. | ODR-15 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Plan before preprocessing |
| ISS-25 | B | A null may mean "no event" | Decide per metric in a later step; never zero-fill silently. | ODR-15 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Before preprocessing |
| RD-01 | B | Targets older than 365 days | Keep them. Flag as weak labels in interpretation. No age cap unless the owner approves one. | ODR-03 OWNER_DECIDED_IMPLEMENTATION_PENDING / CARRIED_FORWARD | Yes | No | Decision recorded before final modeling dataset |
| RD-04 | C | Five features with incomplete window evidence | Owner chooses: exclude, or use with season-aware handling. Until then, neither include nor exclude automatically. EDA may describe them, labelled pending. | ODR-09 OWNER_DECIDED / CARRIED_FORWARD | Yes | No | Before feature selection / final modeling |
| RS5-12 | C | Club context usage | Not candidate predictors by default. Owner decides any use. | ODR-10 OWNER_DECIDED / CARRIED_FORWARD | Yes | No | Before feature selection / final modeling |
| RD-02 | C | Two inconclusive RULE adjudications (El Mohamady, Wesley) | Mappings unchanged. Owner chooses keep (default) or REVIEW_REQUIRED (needs a new version). Note: 6 further AUTO_ADJUDICATED_EXTERNAL rows (5 players) are also INCONCLUSIVE; the rule was already inconclusive for them historically. They are covered by P4-B01, not RD-02. | ODR-05 OWNER_DECIDED / CARRIED_FORWARD | Yes | No | Decision recorded before final modeling dataset |
| ISS-04 | C | Two unresolved identities | Human review of the queue rows (data/research_rs5/review/matching_review_queue.csv). Do not adjudicate automatically. | ODR-06 OWNER_DECIDED / OPEN_PENDING_EVIDENCE | No | No | Any time; a resolution needs a new version |
| P4-D01 | D | Status-column (s_*) role | Use s_* in EDA to interpret nulls. Decide their modeling role, with justification, before preprocessing. | ODR-13 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Before preprocessing |
| P4-D02 | D | Split strategy | Document the split before any model is evaluated. | ODR-14 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Before model evaluation |
| P4-D03 | D | Final feature inclusion | Record decisions with owner approval where marked. | ODR-12 OWNER_DECIDED_IMPLEMENTATION_PENDING / OPEN_PENDING_OWNER_REVIEW | Yes | Yes | Before final modeling |
| P4-D05 | D | Goalkeeper minutes are available only in lineup evidence (found in Phase 4.5) | Owner decides whether a season-total minutes value may be derived from lineup evidence for goalkeepers (a new feature version, documented), or whether goalkeeper playing time is represented by starts and appearances only. Claude Code must not derive it automatically. | ODR-11 OWNER_DECIDED / CARRIED_FORWARD | No | No | Before feature engineering |

## Open: owner decision still required (0)

| ID | Class | Title | Required action | Owner decision (2026-11-09) | Originally blocked final modeling | Still blocks final modeling | Target phase |
|---|---|---|---|---|---|---|---|

## Open: blocks final modeling (no owner decision required) (0)

| ID | Class | Title | Required action | Owner decision (2026-11-09) | Originally blocked final modeling | Still blocks final modeling | Target phase |
|---|---|---|---|---|---|---|---|

## Open: constraints and cautions to carry forward (30)

| ID | Class | Title | Required action | Owner decision (2026-11-09) | Originally blocked final modeling | Still blocks final modeling | Target phase |
|---|---|---|---|---|---|---|---|
| P4-A01 | A | Official dataset only | Verify the hash at the start of every Phase 4 notebook or script; stop if it differs. |  | No | No | 4.1 onward |
| P4-A02 | A | Five-season scope from configs/research_scope.yaml (D9) | Load the scope via load_scope(); run check_parquet/check_table on any derived table. |  | No | No | 4.1 onward |
| P4-A03 | A | No target or temporal-audit columns as predictors | Exclude by role in every feature list; temporal_* may only describe RD-03. |  | No | No | 4.1 onward |
| P4-A04 | A | nationality_profile_present_day is not a predictor | Exclude from predictors. |  | No | No | 4.1 onward |
| P4-A05 | A | No ids, keys, identity, population-evidence or provenance columns as predictors | Use ids only as group keys; identity-quality columns only for sensitivity grouping. |  | No | No | 4.1 onward |
| P4-A07 | A | No blind imputation, zero-fill or silent row drop | In EDA, describe missingness by status, season, position and target availability; do not transform. |  | No | No | 4.1 onward |
| ISS-28 | A | key_passes has no data; clearances in 3 of 5 seasons | Exclude key_passes from predictors. Never impute absent seasons of clearances. |  | No | No | 4.1 onward |
| P4-A08 | A | Target rule unchanged; no staleness filter or age cap by default | Keep all 2,697 usable targets; report staleness, do not filter. |  | No | No | 4.1 onward |
| P4-A09 | A | Keep elite-player tails | Describe tails in EDA; no outlier removal. |  | No | No | 4.1 onward |
| P4-A10 | A | Release, scope, mappings and target method are read-only | Write Phase 4 outputs under new paths only. |  | No | No | 4.1 onward |
| ISS-16 | A | Internal academic use only (D2) | Attribute sources; do not publish raw rows. |  | No | No | 4.1 onward |
| ISS-18 | A | Use the protected full-suite test runner | Never run plain discover on tests/. |  | No | No | 4.1 onward |
| ISS-21 | B | Valuation dates are league-wide batches | Analyse season-aware; do not compare seasons without noting batch timing. |  | No | No | 4.1 onward |
| ISS-29 | B | Source-reported rates not independently verifiable | Assess reliability (consistency with totals where possible) before relying on them; flag in interpretation. |  | No | No | 4.1 onward |
| ISS-11 | B | Goalkeeper minutes mostly missing | Treat GK analysis separately; note limits. |  | No | No | 4.1 onward |
| RS5-13 | B | Retrospective collection | Document in interpretation. |  | No | No | 4.1 onward |
| DQ-RS5-04 | B | m_starts > m_appearances in 6 rows | Do not correct; note if starts/appearances ratios are used. |  | No | No | 4.1 onward |
| P4-B02 | B | Conflicting and unverified-position cells | Keep as null; count separately from MISSING in EDA. |  | No | No | 4.1 onward |
| P4-B03 | B | Target skew and batch structure | Describe on raw and log scales; do not transform the stored column. |  | No | No | 4.1 onward |
| P4-B04 | B | position_group_season is a whole-season modal position | Note the RD-03 caveat when used. |  | No | No | 4.1 onward |
| P4-B05 | B | Per-90 rates on very small minute denominators (found in Phase 4.1) | Describe per-90 distributions together with minutes in Phase 4.2; never delete or cap these values silently. Any minimum-minutes rule for analysis or modeling is a research decision for the owner. |  | No | No | 4.2 onward |
| P4-B07 | B | Count metrics record no zeros; nulls sit where zeros would be expected (found in Phase 4.2) | Keep nulls as nulls (P4-A07). Read each null with its s_* status; the meaning of a null differs by metric. Treatment (for example a status-based indicator) is a preprocessing design decision (P4-D01). |  | No | No | 4.3 onward |
| P4-B08 | B | Playing time drives most volume-value associations; defensive and goalkeeper volumes reverse given playing time (found in Phase 4.3) | Read volume associations together with playing time; never report a raw volume correlation as a performance effect. Do not remove or merge correlated features in EDA; the representation (totals, rates, or both) is a feature-design decision (P4-D03). Revisit the team-context hypothesis if RS5-12 is decided. |  | No | No | 4.4 onward |
| P4-B09 | B | Rate-metric drift across seasons among regular outfield players (found in Phase 4.4) | Read season comparisons of these metrics with the drift in mind; assess source consistency in Phase 4.5; consider season-aware evaluation (P4-D02). Do not rescale or correct values. |  | No | No | 4.5 onward |
| P4-B10 | B | Status coding asymmetries on goalkeeper rows and conflicts concentrated in 2024/25 (found in Phase 4.5) | Read MISSING on goalkeeper rows for outfield metrics as 'not recorded for the position', never as zero or as unknown goalkeeper performance. Consider this in the s_* role decision (P4-D01) and in any position-specific design. |  | No | No | 4.6 onward |
| ISS-23 | B | Source removes same-day duplicates and empty values upstream | Document. |  | No | No | 4.1 onward |
| ISS-24 | B | datum_mw semantics unknown | Document with any age-based statement. |  | No | No | 4.1 onward |
| ISS-09/ISS-10 | B | Cross-source differences (height, assists) | Keep FotMob as the only feature source; do not mix sources. |  | No | No | 4.1 onward |
| ISS-07 | B | 4 birth dates disputed across sources | Note; use official records only if needed. |  | No | No | 4.1 onward |
| ISS-15/26/30/31/14, RS5-09, ISS-13 | B | Low-impact documented limitations | Document only. |  | No | No | 4.1 onward |

## Resolved (8)

| ID | Status | Resolution |
|---|---|---|
| P4-C01 | RESOLVED_FOR_4_1 | Owner prompt 'PHASE 4.1 - DATASET PROFILING & STRUCTURAL EDA' (2026-11-08) is the authorized Phase 4.1 plan. It authorizes 4.1 only; 4.2 needs a new owner authorization. |
| P4-C02 | RESOLVED_FOR_4_2 | Owner prompt 'PHASE 4.2 - TARGET & UNIVARIATE ANALYSIS' (2026-11-08), issued after the Phase 4.1 handoff, authorizes 4.2 only. It contains no separate written statement accepting G4.1 and no answer on ENV-P4-01, so the delegated ENV-P4-01 resolution stands. 4.3 needs a new owner authorization. |
| P4-C03 | RESOLVED_FOR_4_3 | Owner prompt 'PHASE 4.3 - BIVARIATE ANALYSIS' (2026-11-09), issued after the Phase 4.2 handoff, authorizes 4.3 only. It contains no separate written statement accepting G4.2 and no answer on the open owner decisions, which remain open. 4.4 needs a new owner authorization. |
| P4-C04 | RESOLVED_FOR_4_4_TO_4_7 | The owner supplied the Phase 4.4, 4.5, 4.6 and 4.7 prompts and instructed (2026-11-09) that they be executed without an approval between phases. This authorizes 4.4 to 4.7 in sequence; each sub-phase still ends with its own gate, and a FAIL stops the sequence. It is not a written acceptance of G4.3 or of later gates, and it answers none of the open owner decisions. Phase 5 is not authorized. |
| ENV-P4-01 | RESOLVED_DELEGATED_TECHNICAL_DECISION | Re-checked in Phase 4.1: .venv314 still cannot start (base interpreter missing); .venv runs Python 3.13.13 with the pinned freeze. Phase 4.1 evidence and tests ran under .venv. The notebook (needs matplotlib and a Jupyter kernel, absent from .venv) ran on the same base interpreter with .venv site-packages first on PYTHONPATH, so the pinned pandas/numpy/pyarrow/duckdb were used. Nothing was installed or replaced. Taken under the standing delegation of routine technical decisions; the owner may override. Byte-level rebuild reproducibility under 3.14.6 remains untested on this machine. |
| P4-D04 | RESOLVED | Phase 4.1 added PHASE4_OUTPUT_ROOTS (reports/phase_04/, src/phase4/, tests/phase4/, FB69_report.ipynb) to src/research_scope/protect.py. The historical baseline JSON was not modified. Phase 4.1 protection check: reports/phase_04/step_01/evidence/protection_check_phase4_01.json. |
| ENV-P4-02 | RESOLVED | Satisfied by the Phase 4.7 protected full-suite runs (484 OK, then 488 OK; step_07/evidence/full_suite_run_1 and full_suite_final). Evidence-based, not an owner policy. |
| ENV-P4-03 | RESOLVED_DELEGATED_TECHNICAL_DECISION | Phase 4.3 evidence and tests ran under .venv314 (the environment accepted at G5). The notebook (needs matplotlib and a Jupyter kernel, absent from .venv314) ran on the same base interpreter, Python 3.14.6, with .venv314 site-packages first on PYTHONPATH, so the pinned pandas/numpy/pyarrow/duckdb were used. Nothing was installed or replaced. Phase 4.1 and 4.2 outputs re-executed under this interpreter give the same values; only the environment line and the order of tied rows in two sorted display tables differ. Taken under the standing delegation of routine technical decisions; the owner may override. |
