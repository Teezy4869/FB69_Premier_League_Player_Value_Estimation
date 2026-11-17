"""Phase 4.0: build the column-level eligibility register from the release dictionary, leakage audit and reliability table.

Read-only on the release. Writes one CSV to argv[2]. It encodes acceptance rules; it does not select features.
Usage: python -I p40_eligibility.py <repo_root> <out_csv>
"""
import csv, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
REL = ROOT / "data/releases/fb69_player_season_integrated_rs5_v1"
read = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
dic = read(REL / "data_dictionary.csv")
leak = {x["column"]: x for x in read(REL / "docs/leakage_audit.csv")}
rel = {x["feature"]: x for x in read(REL / "docs/feature_reliability.csv")}

RD04 = {"m_clearances", "m_clearances_per90", "m_expected_goals_on_target", "m_touches_opposition_box", "m_goals_prevented"}
GK_ONLY = {k for k, v in rel.items() if v["applicable_positions"] == "GK_ONLY"}


def classify(c, role):
    r = rel.get(c, {})
    status = r.get("reliability_status", "")
    if c in ("m_key_passes", "s_key_passes"):
        return "EXCLUDED_PREDICTOR", "ACCEPTANCE_RULE", "ISS-28", "no", "Source has no value in any season (status UNSUPPORTED on all 2,747 rows)"
    if c == "nationality_profile_present_day":
        return "EXCLUDED_PREDICTOR", "ACCEPTANCE_RULE", "P4-A04", "no", "Present-day profile value collected 2026-11; not a historical fact (leakage FAIL)"
    if role in ("TARGET", "TARGET_METADATA", "TARGET_AUDIT_NOT_A_PREDICTOR"):
        return "TARGET", "NEVER_PREDICTOR", "P4-A03", "no", "Target, target metadata or target audit column (leakage FAIL)"
    if role == "TEMPORAL_ALIGNMENT_NOT_A_PREDICTOR":
        return "TEMPORAL_AUDIT", "NEVER_PREDICTOR", "P4-A03;RD-03", "no", "Derived from the target valuation date (leakage FAIL); use only to describe RD-03"
    if role == "CLUB_CONTEXT":
        return "CONDITIONAL_PREDICTOR", "OWNER_DECISION_REQUIRED", "RS5-12", "yes", "Club can proxy value and can reflect a move after the valuation; not a candidate by default"
    if c in RD04:
        why = {"m_clearances": "No values in 2020/21 and 2022/23", "m_clearances_per90": "No values in 2020/21 and 2022/23",
               "m_expected_goals_on_target": "Window agreement 92.06% in 2022/23 (threshold 98%)",
               "m_touches_opposition_box": "Disagrees with match sums in 2020/21-2023/24; verified only in 2024/25",
               "m_goals_prevented": "GK only; verified only in 2024/25"}[c]
        return "CONDITIONAL_PREDICTOR", "OWNER_DECISION_REQUIRED", "RD-04" + (";ISS-28" if "clearances" in c else ""), "yes", f"{status}: {why}"
    if status == "SOURCE_REPORTED_NOT_VERIFIED":
        extra = "; GK only, GK minutes mostly missing (ISS-11)" if c in GK_ONLY else ""
        return "CONDITIONAL_PREDICTOR", "RELIABILITY_ASSESSMENT", "ISS-29;P4-B06" + (";ISS-11" if c in GK_ONLY else ""), "no", "Source-reported rate or total without an independent window check" + extra
    if role == "FEATURE_STATUS_FOTMOB":
        m = "m_" + c[2:]
        return "STATUS_MISSINGNESS", "INTERPRETATION_REQUIRED", "ISS-25;ISS-27;P4-A07;P4-D01", "no", f"Categorical source status for {m}; explains why {m} is null; not a numeric performance feature; modeling role decided before preprocessing (P4-D01); follows the eligibility of {m}"
    if role == "QUALITY_FLAG":
        return "STATUS_MISSINGNESS", "NOT_A_PREDICTOR", "ISS-27", "no", "Count of null m_* in the row; missingness diagnostic only"
    if role == "FEATURE_FOTMOB_METRIC" or role == "CONTEXT_FEATURE":
        notes = []
        if c == "age_at_season_end_years":
            notes.append("Leakage PASS; 4 birth dates disputed historically (ISS-07)")
        elif c == "position_group_season":
            notes.append("Modal lineup position over the whole season, partly after the valuation")
        else:
            notes.append(status + "; season total includes post-valuation matches (RD-03)")
        if c in GK_ONLY:
            notes.append("GK only (null for outfield rows by design)")
        if c == "m_starts":
            notes.append("6 rows with m_starts > m_appearances kept as published (DQ-RS5-04)")
        if c == "m_penalty_saves":
            notes.append("null on 31.55% of GK rows probably means none faced; not converted (ISS-25)")
        ids = "RD-03" if c != "age_at_season_end_years" else "ISS-07"
        return "CANDIDATE_PREDICTOR", "WITH_WARNINGS", ids, "no", "; ".join(notes)
    # identity, keys, population evidence, identity quality, provenance
    use = {"KEY": "Grouping, split and join key; never a predictor (season as a predictor needs an owner decision, ISS-21)",
           "IDENTITY_LINK": "Transfermarkt id; never a predictor", "IDENTITY_CONTEXT": "Name or birth-date context; never a predictor",
           "POPULATION_EVIDENCE": "Population audit fields (counts duplicate m_appearances/m_starts); not candidate predictors per dictionary",
           "IDENTITY_QUALITY": "Identity sensitivity grouping only (ISS-01, RD-02)", "PROVENANCE": "Provenance only"}[role]
    return "IDENTITY_METADATA", "NEVER_PREDICTOR", "P4-A05", "no", use


rows = []
for d in dic:
    c, role = d["column"], d["role"]
    cat, ctype, ids, owner, reason = classify(c, role)
    rows.append({"column": c, "role": role, "type": d["type"], "dictionary_candidate_predictor": d["candidate_predictor"],
                 "leakage_classification": leak.get(c, {}).get("classification", ""), "reliability_status": rel.get(c, {}).get("reliability_status", ""),
                 "eligibility_category": cat, "condition_type": ctype, "condition_ids": ids, "owner_decision_required": owner, "reason": reason})
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
from collections import Counter
print(len(rows), Counter(r["eligibility_category"] for r in rows), Counter((r["eligibility_category"], r["condition_type"]) for r in rows), sep="\n")
