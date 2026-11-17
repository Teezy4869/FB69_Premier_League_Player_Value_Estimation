# FB69 Phase 4 Owner Decision Register

Date: 2026-11-09. Authorization source: FB69_PHASE4_OWNER_DECISION_REGISTER (2026-11-09, status APPROVED FOR CONTROLLED TRANSITION) and the owner prompt 'MASTER PROMPT - FB69 CONTROLLED TRANSITION'. Recorded by Claude Code. Rendered from the `owner_decision` blocks of `step_00/phase4_condition_register.yaml` (the single source); edit the YAML, not this file.

## Overarching decisions

- Option A, controlled transition. Phase 4 deliverables and the results of G4.1-G4.7 accepted, subject to the documented conditions.
- D4 and D6 preserved; official RS5 dataset and SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd` preserved.
- Original data, mappings, target construction, releases and historical evidence must not be modified.
- Phase 5.0 Modeling Design authorized. Preprocessing, feature transformation, modeling dataset construction, training, tuning and evaluation NOT authorized.

Status legend: `OWNER_DECIDED` Governance decision taken; nothing further to implement for this condition.; `OWNER_DECIDED_IMPLEMENTATION_PENDING` Policy decided; its design or implementation still needs work and owner review.; `CARRIED_FORWARD` The limitation stays and must be reported; no open action beyond that.; `OPEN_PENDING_EVIDENCE` Cannot be closed without new evidence (for example human validation).; `OPEN_PENDING_OWNER_REVIEW` Waits for owner review of a Phase 5.0 design deliverable.

## Decisions

| Decision ID | Condition(s) | Original issue | Owner decision | Rationale | Scope of impact | Implementation restrictions | Remaining limitation | Decision status | Residual status | Still blocks final modeling | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ODR-01 | RD-03 | Temporal construct mismatch (also ISS-02) | KEEP D4: latest valid valuation on or before the official season end. | Owner accepted the Phase 4.5 reproduction of the RD-03 references (150 days, 56.62%, 44.10%, 43.66%) and the default recommendation. | Target vs all m_* and position_group_season | No change to target construction. Report the temporal construct mismatch with every relationship and result. | Construct mismatch persists: later full-season performance must never be read as causing an earlier valuation. | OWNER_DECIDED | CARRIED_FORWARD | No | step_05/TEMPORAL_RELIABILITY_REPORT.md |
| ODR-02 | P4-A06 | Objective A framing only (D6) | KEEP D6: Objective A, end-of-season market value estimation. | Owner reaffirmed the objective. | All reporting | Do not reframe the task as forecasting or causal estimation; the 2024/25 hold-out is read under Objective A. | None beyond RD-03. | OWNER_DECIDED | CARRIED_FORWARD | No | configs/research_scope.yaml; PHASE4_CONDITIONS.md |
| ODR-03 | RD-01 | Targets older than 365 days | KEEP ALL targets older than 365 days; flag them as weak labels in analysis and reporting. | Default recommendation; a filter would change the season mix (ISS-22). | 12 rows | No age cap or exclusion without a new owner decision. Weak-label flag is a reporting attribute, not a new dataset column. | Old labels remain weak; Phase 5 results must report them (planned in PHASE5_EVALUATION_PROTOCOL.md). | OWNER_DECIDED_IMPLEMENTATION_PENDING | CARRIED_FORWARD | No | step_05/evidence (old valuations) |
| ODR-04 | ISS-22 | Staleness filters change the season mix | NO staleness filter. | Default recommendation; consistent with RD-01 and P4-A08. | Any filter on target age | Any future filter needs a separate documented analysis and owner approval. | Staleness stays in the data and is reported. | OWNER_DECIDED | CARRIED_FORWARD | No | step_05/TEMPORAL_RELIABILITY_REPORT.md |
| ODR-05 | RD-02 | Two inconclusive RULE adjudications (El Mohamady, Wesley) | KEEP the existing El Mohamady and Wesley mappings. | Default recommendation; no new evidence. | 3 rows | No mapping change and no new mapping version. | Their adjudication stays INCONCLUSIVE; no human confirmation may be claimed. | OWNER_DECIDED | CARRIED_FORWARD | No | reports/research_scope_rs5 (adjudication records) |
| ODR-06 | ISS-04 | Two unresolved identities | KEEP UNRESOLVED: Daniel Chesters and Jimi Tauriainen stay in the review queue. | No human adjudication is available. | 2 rows | No automatic adjudication. Any resolution requires a new version and audit. | The two identities remain unresolved. | OWNER_DECIDED | OPEN_PENDING_EVIDENCE | No | data/research_rs5/review/matching_review_queue.csv |
| ODR-07 | ISS-01 | Identity mappings not human-validated | KEEP all rows, including the 533-row identity sensitivity subset; use the subset for sensitivity analysis where relevant. | Phase 4.3-4.5 identity sensitivity was small (median \|delta rho\| 0.016) but the subset is non-random. | 2,745 mapped rows | Main dataset unchanged. Mapping coverage must not be described as precision. | Identity mappings are not fully human-validated; precision is not established. | OWNER_DECIDED | OPEN_PENDING_EVIDENCE | Yes | step_05/IDENTITY_SENSITIVITY_REPORT.md |
| ODR-08 | P4-B01 | Identity sensitivity | Retain all rows; plan a comparison of the full target-usable population with the population excluding the 533-row subset. | Owner decision ISS-01 / P4-B01. | 533 rows | Do not remove the subset from the source dataset; do not claim identity precision. | Sensitivity comparison not yet designed in detail or run. | OWNER_DECIDED_IMPLEMENTATION_PENDING | CARRIED_FORWARD | Yes | step_05/IDENTITY_SENSITIVITY_REPORT.md; reports/phase_05/step_00/PHASE5_EVALUATION_PROTOCOL.md |
| ODR-09 | RD-04 | Five features with incomplete window evidence | EXCLUDE FROM BASELINE: clearances, clearances_per90, expected_goals_on_target, touches_opposition_box, goals_prevented. | Incomplete feature-window evidence (rs5 feature_window_audit; Phase 4.5 RD-04 assessment). | m_clearances, m_clearances_per90, m_expected_goals_on_target, m_touches_opposition_box, m_goals_prevented (and their s_* columns) | Columns and metadata stay in the dataset. Sensitivity use requires a separately approved design. | Source-quality limitation of the five metrics remains. | OWNER_DECIDED | CARRIED_FORWARD | No | reports/research_scope_rs5/step_04/evidence/feature_window_audit_rs5.csv; step_05/METRIC_RELIABILITY_REPORT.md |
| ODR-10 | RS5-12 | Club context usage | EXCLUDE FROM BASELINE: all eight club-context columns. | Club context is not a player-performance feature and was never a default candidate. | 8 columns | Columns stay in the dataset. Any later use requires a separate owner decision. | None for the baseline. | OWNER_DECIDED | CARRIED_FORWARD | No | step_05/evidence (club context) |
| ODR-11 | P4-D05 | Goalkeeper minutes are available only in lineup evidence (found in Phase 4.5) | Represent goalkeeper playing time with starts and appearances in the baseline. | Avoids a new feature version derived from lineup evidence. | m_minutes_played for goalkeepers; any playing-time feature for goalkeepers | Do not derive goalkeeper minutes from lineup evidence; no new feature version. | GK playing time is coarser than minutes. | OWNER_DECIDED | CARRIED_FORWARD | No | step_05/METRIC_RELIABILITY_REPORT.md |
| ODR-12 | P4-D03 | Final feature inclusion | CONTROLLED FEATURE DESIGN: prepare an explicit feature-level proposal from the Phase 4.6 assessment and these decisions. | Final inclusion needs column-level review. | 21 conditional columns + s_* | Final column-level inclusion must be reviewed by the owner before preprocessing. | Not closed until the feature proposal is owner-reviewed. | OWNER_DECIDED_IMPLEMENTATION_PENDING | OPEN_PENDING_OWNER_REVIEW | Yes | step_06/FEATURE_ASSESSMENT_MATRIX.md; reports/phase_05/step_00/PHASE5_FEATURE_PROPOSAL.md |
| ODR-13 | P4-D01 | Status-column (s_*) role | Do not use all s_* columns as direct predictors by default; use them to interpret source missingness. Any indicator is proposed per metric with justification. | Phase 4.5: status semantics clean on 145,591 cells; missingness follows playing time. | 53 columns | No indicator is created or transformed now. | Not closed until the metric-level indicator policy is designed and approved. | OWNER_DECIDED_IMPLEMENTATION_PENDING | OPEN_PENDING_OWNER_REVIEW | Yes | step_05/MISSINGNESS_ANALYSIS_REPORT.md; reports/phase_05/step_00/PHASE5_MISSINGNESS_POLICY.md |
| ODR-14 | RS5-11, P4-D02 | No random row-level split as an evaluation strategy; Split strategy | As P4-D02: grouped-by-player K-fold (primary) and 2024/25 temporal hold-out (secondary); no random row split. | Owner decision P4-D02 / RS5-11. | Any split, cross-validation or EDA holdout; Model evaluation | Split not implemented. | Protocol must be approved before any evaluation. | OWNER_DECIDED_IMPLEMENTATION_PENDING | OPEN_PENDING_OWNER_REVIEW | Yes | step_06/SPLIT_STRATEGY_ASSESSMENT.md |
| ODR-15 | ISS-27, ISS-25 | Missingness is not random; A null may mean "no event" | No blanket complete-case deletion; consider missingness by season, position, playing time and target availability; GK and outfield separately. | Phase 4.5: missingness follows playing time, not season. | Complete-case analyses; Count metrics | Any metric-specific rule must be proposed and approved before implementation. | Per-metric rules not yet approved. | OWNER_DECIDED_IMPLEMENTATION_PENDING | OPEN_PENDING_OWNER_REVIEW | Yes | step_05/MISSINGNESS_ANALYSIS_REPORT.md |
| ODR-16 | ENV-P4-03 | Phase 4.3 interpreter on the current machine | ACCEPTED: notebook runs with base Python 3.14.6 and .venv314 site-packages on PYTHONPATH. | Owner accepted the documented arrangement for the Phase 4 reproducibility record. | Reproducibility record of Phase 4.3 | No package installation, environment replacement or dependency change. | No single project environment contains the notebook dependencies. | OWNER_DECIDED | CARRIED_FORWARD | No | reports/phase_04/README.md; step_07/PHASE4_FINAL_ACCEPTANCE_REPORT.md |

## Phase 4 acceptance

| Gate | Record |
|---|---|
| G4.0 | CONDITIONAL PASS (dataset acceptance; not part of the owner's G4.1-G4.7 acceptance; dataset conditions remain) |
| G4.1 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.2 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.3 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.4 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.5 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.6 | PASS (Claude) -> OWNER_ACCEPTED |
| G4.7 | CONDITIONAL PASS (Claude, before owner acceptance) -> PASS after verification of the four owner conditions |
| Phase 4 overall | ACCEPTED |
| ENV-P4-03 | OWNER_ACCEPTED |

Acceptance closes the administrative conditions of G4.7 only. It does not resolve research limitations or authorize final modeling.

## Not decided by the owner (still open)

. P4-B05 (minimum-minutes threshold) and ISS-29 (GK rate reclassification) are proposed, not decided, in the Phase 5.0 package.

