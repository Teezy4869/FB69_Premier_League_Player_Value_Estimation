"""Render PHASE4_ISSUE_TRACKER.md and PHASE4_OWNER_DECISION_REGISTER.md from the canonical condition register YAML.
Usage (repository root): python -I render_tracker_and_odr.py
"""
from pathlib import Path

import yaml

reg = yaml.safe_load(Path("reports/phase_04/step_00/phase4_condition_register.yaml").read_text(encoding="utf-8"))
C = reg["conditions"]
esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
yn = lambda b: "Yes" if b is True else "No"  # noqa: E731
OUT = Path("reports/phase_04/step_07")


def residual_blocks(c):
    o = c.get("owner_decision")
    return o["residual_blocks_final_modeling"] if o else c["blocks_final_modeling"] is True


def decision(c):
    o = c.get("owner_decision")
    return f"{o['odr_id']} {o['decision_status']} / {o['residual_status']}" if o else ""


def table(rows, title):
    out = [f"## {title} ({len(rows)})", "",
           "| ID | Class | Title | Required action | Owner decision (2026-11-09) | Originally blocked final modeling | Still blocks final modeling | Target phase |",
           "|---|---|---|---|---|---|---|---|"]
    out += [f"| {esc(c['id'])} | {c['classification']} | {esc(c['title'])} | {esc(c['required_action'])} | {esc(decision(c))} | "
            f"{yn(c['blocks_final_modeling'])} | {yn(residual_blocks(c))} | {esc(c['target_phase'])} |" for c in rows]
    return out + [""]


open_ = [c for c in C if "status" not in c]
resolved = [c for c in C if "status" in c]
decided = [c for c in open_ if "owner_decision" in c]
undecided_owner = [c for c in open_ if "owner_decision" not in c and c["owner_approval_required"] is True]
blocking = [c for c in open_ if c not in decided and c not in undecided_owner and c["blocks_final_modeling"] is True]
rest = [c for c in open_ if c not in decided and c not in undecided_owner and c not in blocking]
orig_block = [c["id"] for c in open_ if c["blocks_final_modeling"] is True]
still_block = [c["id"] for c in open_ if residual_blocks(c)]
acc = reg["phase4_acceptance"]

lines = ["# FB69 Phase 4 Issue Tracker", "",
         "Date: 2026-11-09 (Phase 4.7; updated for the owner decisions of 2026-11-09). Rendered from `step_00/phase4_condition_register.yaml` "
         "by `evidence/scripts/render_tracker_and_odr.py`; the YAML remains the single source. An owner decision records a governance "
         "policy; it does not resolve the empirical issue, so decided conditions stay open here unless they carry a status.", "",
         f"Phase 4 status: **{acc['phase4_overall']}** (G4.7 {acc['gates']['G4.7']}). ENV-P4-03: {acc['env_p4_03']}.", "",
         f"Conditions: {len(C)}; open: {len(open_)}; resolved: {len(resolved)}; open with an owner decision: {len(decided)}; "
         f"open and still needing an owner decision: {len(undecided_owner)}.", "",
         f"Blocking final modeling: {len(orig_block)} before the owner decisions ({', '.join(orig_block)}); "
         f"{len(still_block)} still blocking after them ({', '.join(still_block)}). The others are decided but their limitations are carried forward.", ""]
lines += table(decided, "Open: owner decided (policy set; limitation or implementation remains)")
lines += table(undecided_owner, "Open: owner decision still required")
lines += table(blocking, "Open: blocks final modeling (no owner decision required)")
lines += table(rest, "Open: constraints and cautions to carry forward")
lines += ["## Resolved (" + str(len(resolved)) + ")", "", "| ID | Status | Resolution |", "|---|---|---|"]
lines += [f"| {esc(c['id'])} | {esc(c['status'])} | {esc(c.get('resolution', ''))} |" for c in resolved]
(OUT / "PHASE4_ISSUE_TRACKER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Owner decision register: one row per ODR id, grouping conditions that share a decision.
groups = {}
for c in C:
    if "owner_decision" in c:
        groups.setdefault(c["owner_decision"]["odr_id"], []).append(c)
rec = reg["owner_decision_record"]
od = ["# FB69 Phase 4 Owner Decision Register", "",
      f"Date: {rec['date']}. Authorization source: {rec['source']}. Recorded by Claude Code. Rendered from the `owner_decision` blocks of "
      "`step_00/phase4_condition_register.yaml` (the single source); edit the YAML, not this file.", "",
      "## Overarching decisions", "",
      "- Option A, controlled transition. Phase 4 deliverables and the results of G4.1-G4.7 accepted, subject to the documented conditions.",
      "- D4 and D6 preserved; official RS5 dataset and SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd` preserved.",
      "- Original data, mappings, target construction, releases and historical evidence must not be modified.",
      "- Phase 5.0 Modeling Design authorized. Preprocessing, feature transformation, modeling dataset construction, training, tuning and evaluation NOT authorized.", "",
      "Status legend: " + "; ".join(f"`{k}` {v}" for k, v in {**rec["decision_status_legend"], **rec["residual_status_legend"]}.items()), "",
      "## Decisions", "",
      "| Decision ID | Condition(s) | Original issue | Owner decision | Rationale | Scope of impact | Implementation restrictions | Remaining limitation | Decision status | Residual status | Still blocks final modeling | Evidence |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for odr in sorted(groups):
    cs = groups[odr]
    o = cs[0]["owner_decision"]
    od.append(f"| {odr} | {', '.join(c['id'] for c in cs)} | {esc('; '.join(c['title'] for c in cs))} | {esc(o['decision'])} | {esc(o['rationale'])} | "
              f"{esc('; '.join(c['affected'] for c in cs))} | {esc(o['implementation_boundary'])} | {esc(o['remaining_limitation'])} | "
              f"{o['decision_status']} | {o['residual_status']} | {yn(any(c['owner_decision']['residual_blocks_final_modeling'] for c in cs))} | {esc(o['evidence'])} |")
od += ["", "## Phase 4 acceptance", "", "| Gate | Record |", "|---|---|"]
od += [f"| {g} | {esc(v)} |" for g, v in acc["gates"].items()]
od += [f"| Phase 4 overall | {acc['phase4_overall']} |", f"| ENV-P4-03 | {acc['env_p4_03']} |", "", acc["note"], "",
       "## Not decided by the owner (still open)", "",
       ", ".join(f"`{c['id']}`" for c in undecided_owner) + ". P4-B05 (minimum-minutes threshold) and ISS-29 (GK rate reclassification) are proposed, "
       "not decided, in the Phase 5.0 package.", ""]
(OUT / "PHASE4_OWNER_DECISION_REGISTER.md").write_text("\n".join(od) + "\n", encoding="utf-8")
print(len(C), len(open_), len(resolved), len(decided), len(undecided_owner), orig_block, still_block)
