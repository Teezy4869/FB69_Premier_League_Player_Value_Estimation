"""Record the 2026-11-09 owner decisions in the canonical condition register YAML (one-time, idempotent).

Text insertion keeps every existing line, comment, id, evidence reference and status of the YAML unchanged;
it only adds an `owner_decision` block to the named conditions, a `status` to ENV-P4-02 (evidence: Phase 4.7
protected full-suite runs), and the top-level `owner_decision_record` and `phase4_acceptance` sections.
Usage: python -I apply_owner_decisions.py <phase4_condition_register.yaml>
"""
import sys
from pathlib import Path

import yaml

P = Path(sys.argv[1])
text = P.read_text(encoding="utf-8")
if "owner_decision_record:" in text:
    sys.exit("already applied")

DATE = "2026-11-09"
SRC = ("FB69_PHASE4_OWNER_DECISION_REGISTER (2026-11-09, status APPROVED FOR CONTROLLED TRANSITION) and the owner prompt "
       "'MASTER PROMPT - FB69 CONTROLLED TRANSITION'")
ODR = "reports/phase_04/step_07/PHASE4_OWNER_DECISION_REGISTER.md"


def d(odr_id, decision, rationale, boundary, limitation, decision_status, residual_status, residual_blocks, evidence):
    return {"odr_id": odr_id, "decision": decision, "rationale": rationale, "implementation_boundary": boundary,
            "remaining_limitation": limitation, "decision_status": decision_status, "residual_status": residual_status,
            "residual_blocks_final_modeling": residual_blocks, "evidence": evidence, "date": DATE, "source": SRC}


DECISIONS = {
    "RD-03": d("ODR-01", "KEEP D4: latest valid valuation on or before the official season end.",
               "Owner accepted the Phase 4.5 reproduction of the RD-03 references (150 days, 56.62%, 44.10%, 43.66%) and the default recommendation.",
               "No change to target construction. Report the temporal construct mismatch with every relationship and result.",
               "Construct mismatch persists: later full-season performance must never be read as causing an earlier valuation.",
               "OWNER_DECIDED", "CARRIED_FORWARD", False, "step_05/TEMPORAL_RELIABILITY_REPORT.md"),
    "P4-A06": d("ODR-02", "KEEP D6: Objective A, end-of-season market value estimation.",
                "Owner reaffirmed the objective.", "Do not reframe the task as forecasting or causal estimation; the 2024/25 hold-out is read under Objective A.",
                "None beyond RD-03.", "OWNER_DECIDED", "CARRIED_FORWARD", False, "configs/research_scope.yaml; PHASE4_CONDITIONS.md"),
    "RD-01": d("ODR-03", "KEEP ALL targets older than 365 days; flag them as weak labels in analysis and reporting.",
               "Default recommendation; a filter would change the season mix (ISS-22).",
               "No age cap or exclusion without a new owner decision. Weak-label flag is a reporting attribute, not a new dataset column.",
               "Old labels remain weak; Phase 5 results must report them (planned in PHASE5_EVALUATION_PROTOCOL.md).",
               "OWNER_DECIDED_IMPLEMENTATION_PENDING", "CARRIED_FORWARD", False, "step_05/evidence (old valuations)"),
    "ISS-22": d("ODR-04", "NO staleness filter.", "Default recommendation; consistent with RD-01 and P4-A08.",
                "Any future filter needs a separate documented analysis and owner approval.", "Staleness stays in the data and is reported.",
                "OWNER_DECIDED", "CARRIED_FORWARD", False, "step_05/TEMPORAL_RELIABILITY_REPORT.md"),
    "RD-02": d("ODR-05", "KEEP the existing El Mohamady and Wesley mappings.", "Default recommendation; no new evidence.",
               "No mapping change and no new mapping version.", "Their adjudication stays INCONCLUSIVE; no human confirmation may be claimed.",
               "OWNER_DECIDED", "CARRIED_FORWARD", False, "reports/research_scope_rs5 (adjudication records)"),
    "ISS-04": d("ODR-06", "KEEP UNRESOLVED: Daniel Chesters and Jimi Tauriainen stay in the review queue.", "No human adjudication is available.",
                "No automatic adjudication. Any resolution requires a new version and audit.", "The two identities remain unresolved.",
                "OWNER_DECIDED", "OPEN_PENDING_EVIDENCE", False, "data/research_rs5/review/matching_review_queue.csv"),
    "ISS-01": d("ODR-07", "KEEP all rows, including the 533-row identity sensitivity subset; use the subset for sensitivity analysis where relevant.",
                "Phase 4.3-4.5 identity sensitivity was small (median |delta rho| 0.016) but the subset is non-random.",
                "Main dataset unchanged. Mapping coverage must not be described as precision.",
                "Identity mappings are not fully human-validated; precision is not established.",
                "OWNER_DECIDED", "OPEN_PENDING_EVIDENCE", True, "step_05/IDENTITY_SENSITIVITY_REPORT.md"),
    "P4-B01": d("ODR-08", "Retain all rows; plan a comparison of the full target-usable population with the population excluding the 533-row subset.",
                "Owner decision ISS-01 / P4-B01.", "Do not remove the subset from the source dataset; do not claim identity precision.",
                "Sensitivity comparison not yet designed in detail or run.", "OWNER_DECIDED_IMPLEMENTATION_PENDING", "CARRIED_FORWARD", True,
                "step_05/IDENTITY_SENSITIVITY_REPORT.md; reports/phase_05/step_00/PHASE5_EVALUATION_PROTOCOL.md"),
    "RD-04": d("ODR-09", "EXCLUDE FROM BASELINE: clearances, clearances_per90, expected_goals_on_target, touches_opposition_box, goals_prevented.",
               "Incomplete feature-window evidence (rs5 feature_window_audit; Phase 4.5 RD-04 assessment).",
               "Columns and metadata stay in the dataset. Sensitivity use requires a separately approved design.",
               "Source-quality limitation of the five metrics remains.", "OWNER_DECIDED", "CARRIED_FORWARD", False,
               "reports/research_scope_rs5/step_04/evidence/feature_window_audit_rs5.csv; step_05/METRIC_RELIABILITY_REPORT.md"),
    "RS5-12": d("ODR-10", "EXCLUDE FROM BASELINE: all eight club-context columns.", "Club context is not a player-performance feature and was never a default candidate.",
                "Columns stay in the dataset. Any later use requires a separate owner decision.", "None for the baseline.",
                "OWNER_DECIDED", "CARRIED_FORWARD", False, "step_05/evidence (club context)"),
    "P4-D05": d("ODR-11", "Represent goalkeeper playing time with starts and appearances in the baseline.", "Avoids a new feature version derived from lineup evidence.",
                "Do not derive goalkeeper minutes from lineup evidence; no new feature version.", "GK playing time is coarser than minutes.",
                "OWNER_DECIDED", "CARRIED_FORWARD", False, "step_05/METRIC_RELIABILITY_REPORT.md"),
    "P4-D03": d("ODR-12", "CONTROLLED FEATURE DESIGN: prepare an explicit feature-level proposal from the Phase 4.6 assessment and these decisions.",
                "Final inclusion needs column-level review.", "Final column-level inclusion must be reviewed by the owner before preprocessing.",
                "Not closed until the feature proposal is owner-reviewed.", "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True,
                "step_06/FEATURE_ASSESSMENT_MATRIX.md; reports/phase_05/step_00/PHASE5_FEATURE_PROPOSAL.md"),
    "P4-D01": d("ODR-13", "Do not use all s_* columns as direct predictors by default; use them to interpret source missingness. Any indicator is proposed per metric with justification.",
                "Phase 4.5: status semantics clean on 145,591 cells; missingness follows playing time.",
                "No indicator is created or transformed now.", "Not closed until the metric-level indicator policy is designed and approved.",
                "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True,
                "step_05/MISSINGNESS_ANALYSIS_REPORT.md; reports/phase_05/step_00/PHASE5_MISSINGNESS_POLICY.md"),
    "P4-D02": d("ODR-14", "Primary: grouped-by-player K-fold on canonical_player_id. Secondary: temporal hold-out (develop 2020/21-2023/24, hold out 2024/25), returning and new players reported separately; hold-out never used for iterative tuning.",
                "Phase 4.6: random row split would put about 76% of test rows' players in training.",
                "Split not implemented; fold count and balancing are Claude recommendations for owner review.", "Protocol must be approved before any evaluation.",
                "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True,
                "step_06/SPLIT_STRATEGY_ASSESSMENT.md; reports/phase_05/step_00/PHASE5_EVALUATION_PROTOCOL.md"),
    "RS5-11": d("ODR-14", "As P4-D02: grouped-by-player K-fold (primary) and 2024/25 temporal hold-out (secondary); no random row split.",
                "Owner decision P4-D02 / RS5-11.", "Split not implemented.", "Protocol must be approved before any evaluation.",
                "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True, "step_06/SPLIT_STRATEGY_ASSESSMENT.md"),
    "ISS-25": d("ODR-15", "No blanket zero fill; no assumption that null means zero; interpret nulls per metric with s_* status.",
                "Phase 4.2 P4-B07: count metrics record no zeros; nulls sit where zeros would be expected for some metrics only.",
                "Any metric-specific rule must be proposed and approved before implementation.", "Per-metric rules not yet approved.",
                "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True, "step_02 and step_05 missingness evidence"),
    "ISS-27": d("ODR-15", "No blanket complete-case deletion; consider missingness by season, position, playing time and target availability; GK and outfield separately.",
                "Phase 4.5: missingness follows playing time, not season.", "Any metric-specific rule must be proposed and approved before implementation.",
                "Per-metric rules not yet approved.", "OWNER_DECIDED_IMPLEMENTATION_PENDING", "OPEN_PENDING_OWNER_REVIEW", True,
                "step_05/MISSINGNESS_ANALYSIS_REPORT.md"),
    "ENV-P4-03": d("ODR-16", "ACCEPTED: notebook runs with base Python 3.14.6 and .venv314 site-packages on PYTHONPATH.",
                   "Owner accepted the documented arrangement for the Phase 4 reproducibility record.",
                   "No package installation, environment replacement or dependency change.",
                   "No single project environment contains the notebook dependencies.", "OWNER_DECIDED", "CARRIED_FORWARD", False,
                   "reports/phase_04/README.md; step_07/PHASE4_FINAL_ACCEPTANCE_REPORT.md"),
}

ENV2_STATUS = ("  status: RESOLVED\n  resolution: \"Satisfied by the Phase 4.7 protected full-suite runs (484 OK, then 488 OK; "
               "step_07/evidence/full_suite_run_1 and full_suite_final). Evidence-based, not an owner policy.\"\n")

lines = text.splitlines(keepends=True)
starts = {ln.strip()[len("- id: "):].strip().strip('"'): i for i, ln in enumerate(lines) if ln.startswith("  - id: ")}
missing = set(DECISIONS) - set(starts)
assert not missing, missing


def end_of(i):
    j = i + 1
    while j < len(lines) and not lines[j].startswith("  - id: ") and not lines[j].startswith("  # ") and lines[j].startswith((" ", "\n")) and lines[j].strip() != "":
        j += 1
    return j


inserts = {}
for cid, block in DECISIONS.items():
    dumped = yaml.safe_dump({"owner_decision": block}, sort_keys=False, allow_unicode=True, width=10000)
    inserts[end_of(starts[cid])] = "".join("    " + ln + "\n" for ln in dumped.splitlines())
inserts[end_of(starts["ENV-P4-02"])] = inserts.get(end_of(starts["ENV-P4-02"]), "") + ENV2_STATUS.replace("\n  ", "\n    ").replace("  status", "    status", 1)

out = []
for i, ln in enumerate(lines):
    if i in inserts:
        out.append(inserts[i])
    out.append(ln)
if len(lines) in inserts:
    if not out[-1].endswith("\n"):
        out.append("\n")
    out.append(inserts[len(lines)])
new = "".join(out)

old_updated = next(ln for ln in lines if ln.startswith("updated: "))
new = new.replace(old_updated, old_updated.rstrip()[:-1] + ". 2026-11-09 owner decisions: owner_decision blocks added to 18 conditions (ODR-01 to ODR-16); "
                  "ENV-P4-02 resolved by evidence; phase4_acceptance recorded; no existing field changed)\"\n", 1)

tail = {
    "owner_decision_record": {"date": DATE, "source": SRC, "readable_register": ODR,
                              "decision_status_legend": {
                                  "OWNER_DECIDED": "Governance decision taken; nothing further to implement for this condition.",
                                  "OWNER_DECIDED_IMPLEMENTATION_PENDING": "Policy decided; its design or implementation still needs work and owner review.",
                              },
                              "residual_status_legend": {
                                  "CARRIED_FORWARD": "The limitation stays and must be reported; no open action beyond that.",
                                  "OPEN_PENDING_EVIDENCE": "Cannot be closed without new evidence (for example human validation).",
                                  "OPEN_PENDING_OWNER_REVIEW": "Waits for owner review of a Phase 5.0 design deliverable.",
                              },
                              "note": "A condition with an owner_decision block but no status is still OPEN in the register sense: the decision does not resolve the empirical issue."},
    "phase4_acceptance": {"date": DATE, "source": SRC,
                          "gates": {"G4.0": "CONDITIONAL PASS (dataset acceptance; not part of the owner's G4.1-G4.7 acceptance; dataset conditions remain)",
                                    **{f"G4.{k}": "PASS (Claude) -> OWNER_ACCEPTED" for k in range(1, 7)},
                                    "G4.7": "CONDITIONAL PASS (Claude, before owner acceptance) -> PASS after verification of the four owner conditions"},
                          "phase4_overall": "ACCEPTED",
                          "env_p4_03": "OWNER_ACCEPTED",
                          "note": "Acceptance closes the administrative conditions of G4.7 only. It does not resolve research limitations or authorize final modeling."},
}
new += "\n" + yaml.safe_dump(tail, sort_keys=False, allow_unicode=True, width=10000)
P.write_text(new, encoding="utf-8")
check = yaml.safe_load(new)
assert sum("owner_decision" in c for c in check["conditions"]) == len(DECISIONS)
print("ok", len(DECISIONS))
