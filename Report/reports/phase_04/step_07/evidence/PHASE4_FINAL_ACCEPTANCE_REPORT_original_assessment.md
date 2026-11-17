# FB69 Phase 4 Final Acceptance Report (Phase 4.7: EDA Synthesis & Final Acceptance)

Date: 2026-11-09. Reviewer role: independent senior research reviewer (Claude Code). Authorization: owner prompt "PHASE 4.7 - EDA SYNTHESIS & FINAL ACCEPTANCE" under P4-C04. Official dataset `player_season_integrated_rs5_v1` (SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd`), scope `rs5_v1`.

## 1. Final verdict

**G4.7: CONDITIONAL PASS.**

The EDA is complete, internally consistent, supported by evidence and reproducible; scope and data integrity held; the full protected test suite passes; historical protection is verified. The verdict is not a full PASS for three precise reasons:

1. **Owner approval of sub-phases is not explicit.** Phases 4.2–4.4 were started by owner prompts that followed each handoff, and the owner instructed that 4.4–4.7 run without approval between phases. No gate G4.1–G4.7 has a separate written owner acceptance. The 4.7 prompt requires explicit approval of each sub-phase; the owner's later instruction to proceed without inter-phase approval was treated as authorization to execute, not as acceptance of results.
2. **The dataset itself is conditionally accepted** (Phase 4.0), and 12 open conditions block final modeling, 10 of which need owner decisions.
3. **Notebook environment:** the notebook runs in a fresh kernel, but only with the base Python 3.14.6 plus `.venv314` site-packages on `PYTHONPATH` (ENV-P4-03); no project virtual environment contains matplotlib or a Jupyter kernel.

What would change the verdict to PASS: written owner acceptance of G4.1–G4.7 and of ENV-P4-03 (or an approved environment that contains the notebook dependencies). The open research decisions do not block acceptance of the EDA itself; they block Phase 5 modeling.

## 2. Pre-flight

| Sub-phase | Gate | Owner approval evidence |
|---|---|---|
| 4.1 | PASS | Owner issued the 4.2 prompt after the handoff (no written acceptance) |
| 4.2 | PASS | Owner issued the 4.3 prompt after the handoff (no written acceptance) |
| 4.3 | PASS | Owner issued the 4.4 prompt after the handoff (no written acceptance) |
| 4.4 | PASS | Owner instruction (2026-11-09): proceed through 4.4–4.7 without approval between phases |
| 4.5 | PASS | Same instruction |
| 4.6 | PASS | Same instruction |

Under the 4.7 prompt's literal rule ("if any sub-phase was not approved, STOP"), explicit approvals are missing. Execution continued because the owner's later instruction explicitly waived inter-phase approvals; the missing written acceptances are therefore carried as the first condition of the verdict rather than as a stop. All acceptance reports, the notebook, the condition register, the feature assessment matrix, the feasibility report and all evidence were reviewed.

## 3. Gate G4.7

| Criterion | Met | Evidence |
|---|---|---|
| All seven sub-phases completed and owner-approved | **Partly** | All completed with gates PASS (4.1–4.6); no explicit written owner acceptance (section 2) |
| Notebook complete and reproducible | Yes, with ENV-P4-03 | 319 cells, 138 code cells executed in order in a fresh kernel, 0 errors, no hidden state, no absolute paths in code, no text output > 20 KB; every Phase 4 section has objectives, markdown before code, interpretations, limitations (4.1: carried in its conclusion) and a conclusion (`evidence/notebook_section_audit.csv`) |
| Data integrity preserved | Yes | Dataset SHA-256 unchanged; release, scope, mappings, target method and historical files unchanged (protection check); eligibility register byte-identical to a fresh rebuild |
| Official scope enforced | Yes | `load_scope()` in every sub-phase; 0 rows of 2019/20; 0 excluded-season strings in any Phase 4 evidence table |
| EDA findings supported by evidence | Yes | 23 cross-phase checks consistent with each other and with a fresh recomputation (`evidence/cross_phase_consistency.csv`); 5 documented definitional differences |
| Research limitations documented | Yes | Every sub-phase report; notebook 4.7.D/F; issue tracker |
| Feature assessment completed | Yes | Phase 4.6 matrix (53 features x 12 dimensions) |
| Modeling feasibility assessed | Yes | Phase 4.6 feasibility, split and risk reports |
| All unresolved decisions documented | Yes | `PHASE4_ISSUE_TRACKER.md`; notebook 4.7.F |
| Full protected test suite executed | Yes | 488 tests, OK (`evidence/full_suite_final/`) |
| Historical protection verified | Yes | `evidence/protection_check_phase4_07.json` |

## 4. Research integrity review

| Constraint | Result |
|---|---|
| Official five-season scope only; no 2019/20 rows in research outputs | Held |
| Official rs5 dataset only; SHA-256 correct | Held (verified before and after every sub-phase) |
| No target, temporal-audit, identity, provenance or present-day nationality columns as predictors | Held (`evidence/predictor_integrity.csv`) |
| No blind zero imputation; no unauthorized row exclusions; no staleness filter; no outlier removal | Held (dataset-unchanged tests in every sub-phase; P4-B01 rows kept; tails kept) |
| No change to D4 or D6; no mapping change; no RD-04 or RS5-12 decision | Held |
| No model training, feature engineering or final preprocessing | Held (no estimator in any Phase 4 module; groups and log scale computed on the fly for description only) |
| No change to historical releases | Held (protection check: 0 removed, 0 unexpected changes) |

## 5. Corrections made during the review

| Item | Correction | Why necessary |
|---|---|---|
| `tests/phase4/test_feasibility_46.py::test_eligibility_file_unchanged` | Now rebuilds the eligibility register with its Phase 4.0 script and compares bytes | The 4.6 version compared the file with itself (always true) |
| Notebook cell `fb69-p46-002` | Shows five columns instead of a 29 KB text table; full matrix stays in evidence and figure | Unexplained large output |
| Notebook cell `fb69-082` | "relationships belong to Phase 4.1" → "Phase 4 (sections 4.2 to 4.4)" | Inaccurate statement |
| Status sentences (contents, status table, Phase 4 table, 4.6 closing line) | Updated to include 4.7 | Consistency |

No calculation, evidence table or conclusion of an earlier sub-phase had to be changed.

## 6. Tests and protection

| Run | Result |
|---|---|
| Protected full suite, first run (`evidence/full_suite_run_1/`) | 484 tests, OK; mutable Phase 2 files restored and unchanged; FotMob release 38 files, 0 mismatches |
| Protected full suite, final run after review corrections (`evidence/full_suite_final/`) | **488 tests, OK** (437 historical + 51 Phase 4); mutable files unchanged; FotMob release unchanged |
| Phase 4 tests | 51 (4.1: 9, 4.2: 9, 4.3: 9, 4.4: 7, 4.5: 7, 4.6: 6, 4.7: 4) |
| Protection check (`evidence/protection_check_phase4_07.json`) | 16,290 historical files, 0 removed, 0 unexpected changes, 0 unexpected additions; only the documented `CLAUDE.md` edit and the Phase 4.1 `protect.py` root extension (P4-D04) |
| Phase 4 output root in the protection mechanism | Yes (`PHASE4_OUTPUT_ROOTS` in `src/research_scope/protect.py`); historical baseline unchanged |

ENV-P4-02 (full suite not re-run during 4.0–4.6) is satisfied by these runs.

## 7. Phase 4 summary

| Sub-phase | Result |
|---|---|
| 4.1 | 2,747 rows, 1,228 players, 175 columns, five balanced seasons; structurally clean; repeated players, low-minute rows and goalkeepers flagged |
| 4.2 | Target strongly right-skewed (median EUR 13m), coarse, genuine tail; 53 features in three distribution types; zero-recording pattern (P4-B07) |
| 4.3 | Playing time, attacking output, xA, rating strongest; most volume associations are playing time (P4-B08); age inverted U; 54 strong redundant pairs |
| 4.4 | Heterogeneity along position, playing-time role and age, with interactions; season level not explained by composition; metric drift (P4-B09) |
| 4.5 | Status semantics clean; missingness follows playing time; RD-03 values reproduced exactly; identity results robust but subset non-random; RD-04, club context, source-reported rates assessed (P4-B10, P4-D05) |
| 4.6 | 13 core candidates for consideration; regression feasible but conditional; grouped + temporal evaluation; 18 risks |
| 4.7 | Consistent, integral, reproducible; CONDITIONAL PASS |

## 8. Locations

- Notebook: `FB69_report.ipynb` (Phase 4 section at the end; 4.7 synthesis last).
- Reports and evidence: `reports/phase_04/` (index `README.md`), `step_00` to `step_07`.
- Code: `src/phase4/`; tests: `tests/phase4/`.
- Issue tracker: `step_07/PHASE4_ISSUE_TRACKER.md` (source: `step_00/phase4_condition_register.yaml`).

## 9. Outstanding conditions and owner decisions

55 conditions; 48 open; 7 resolved; 12 open conditions block final modeling. Owner decisions: written acceptance of G4.1–G4.7; ENV-P4-03; RD-04; RS5-12; P4-D03 (ISS-29 reclassification); P4-D05; P4-B05; P4-D02 (split confirmation); RD-03 (default keep D4); RD-01; RD-02; ISS-04; ISS-01 (labelling); ISS-22 (only if a staleness filter is proposed).

## 10. Phase 5 readiness recommendation

| Question | Recommendation |
|---|---|
| Is Phase 5 authorized to begin? | **No.** It requires explicit owner authorization. Technically, Phase 5 design work may begin once the owner accepts Phase 4 |
| Conditions to resolve first | Written acceptance of Phase 4; RD-04 and RS5-12 (before feature selection); P4-D02 (before any evaluation); P4-D01 and P4-B05 (before preprocessing); P4-D05 (before GK features); RD-01/RD-02 (before the final modeling dataset) |
| Owner decisions still open | As in section 9 |
| Feature groups for consideration | Playing time (one representation), age (non-linear), position context, attacking output and xG, chance creation and xA, passing quality, rating; goalkeeper metrics in a GK-specific design; defensive volumes only with playing-time context |
| Split strategy | Grouped-by-player K-fold (primary) and 2024/25 temporal hold-out (secondary), reported by position, season and returning vs new players; never random rows |
| Risks to carry forward | Repeated players, temporal mismatch, season batches, heavy-tailed target, informative missingness (high); redundancy, position heterogeneity, GK limits, identity, RD-04, club context, metric drift, small denominators, effective sample size (medium); source-reported rates, old labels, revisions, environment (low) |

Phase 4 ends here. Phase 5 has not been started.
