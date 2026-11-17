"""Render PHASE4_CONDITION_REGISTER.md from phase4_condition_register.yaml (the YAML is the source).
Usage: python -I render_condition_register.py <step_00_dir>
"""
import sys
from collections import Counter
from pathlib import Path

import yaml

D = Path(sys.argv[1])
reg = yaml.safe_load((D / "phase4_condition_register.yaml").read_text(encoding="utf-8"))
C = reg["conditions"]
ids = [c["id"] for c in C]
assert len(ids) == len(set(ids)), "duplicate condition id"
req = {"id", "title", "classification", "description", "evidence", "affected", "required_action", "responsible_stage",
       "owner_approval_required", "blocks_phase_4_1", "blocks_final_modeling", "target_phase"}
for c in C:
    missing = req - set(c)
    assert not missing, (c["id"], missing)
    assert c["classification"] in "ABCD"

esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
yn = lambda b: "**Yes**" if b is True else ("No" if b is False else esc(b))
names = {"A": "A. Mandatory research constraints", "B": "B. Mandatory caution and interpretation", "C": "C. Pending owner decisions", "D": "D. Later-phase requirements"}
n = Counter(c["classification"] for c in C)
out = [
    "# FB69 Phase 4 Condition Register",
    "",
    f"Date: {reg['created']}. Updated: {reg.get('updated', reg['created'])}. Phase {reg['phase']}. Dataset `{reg['dataset']['path']}` (SHA-256 `{reg['dataset']['sha256']}`).",
    "",
    "This table is rendered from `phase4_condition_register.yaml` by `evidence/scripts/render_condition_register.py`. Edit the YAML, not this file. "
    "Issue ids from `reports/research_scope_rs5/step_04/ISSUE_TRACKER.md` are kept; `P4-*` and `ENV-P4-*` ids are new and cover conditions that had none. "
    "**Status:** a condition without a status is OPEN. Resolutions are recorded only when an owner prompt states them or when they are delegated technical decisions (the resolution text says which).",
    "",
    f"Conditions: {len(C)} (A {n['A']}, B {n['B']}, C {n['C']}, D {n['D']}); resolved: {sum('status' in c for c in C)}. \"Also\" gives secondary classes. "
    f"With an owner decision (2026-11-09): {sum('owner_decision' in c for c in C)}. Open and blocking Phase 4.1: {sum(c['blocks_phase_4_1'] is True and 'status' not in c for c in C)}. Blocking final modeling: {sum(c['blocks_final_modeling'] is True for c in C)}.",
    "",
]
for k in "ABCD":
    out += [f"## {names[k]}", "", "| ID | Status | Description | Also | Evidence | Affected | Required action | Stage | Owner approval | Blocks 4.1 | Blocks final modeling | Target phase |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in C:
        if c["classification"] != k:
            continue
        status = esc(c.get("status", "OPEN")) + (f": {esc(c['resolution'])}" if c.get("resolution") else "")
        if c.get("owner_decision"):
            o = c["owner_decision"]
            status += f" ({o['odr_id']} {o['decision_status']}; residual {o['residual_status']}: {esc(o['decision'])})"
        out.append(f"| {esc(c['id'])} | {status} | **{esc(c['title'])}.** {esc(c['description'])} | {esc(c.get('also', ''))} | {esc(c['evidence'])} | {esc(c['affected'])} | "
                   f"{esc(c['required_action'])} | {esc(c['responsible_stage'])} | {yn(c['owner_approval_required'])} | {yn(c['blocks_phase_4_1'])} | {yn(c['blocks_final_modeling'])} | {esc(c['target_phase'])} |")
    out.append("")
(D / "PHASE4_CONDITION_REGISTER.md").write_text("\n".join(out), encoding="utf-8")
print(len(C), dict(n))
