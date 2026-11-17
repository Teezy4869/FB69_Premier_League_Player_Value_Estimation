# Phase 3 Execution Tracker

Updated 2026-11-05. SOP phases are mapped to the owner's step prompts.

| Task | SOP phase | Status | Evidence | Gate |
|---|---|---|---|---|
| Foundation and input audit | 3.0 | PASS | `step_01/FOTMOB_INPUT_AUDIT.md`, `configs/phase_03_seasons.yaml`, `step_05/DATA_CONTRACT.md` | G0 |
| Transfermarkt source audit | 3.1 | CONDITIONAL_PASS, owner-approved | `step_01/TM_SOURCE_AUDIT.md`, decisions D1 and D2 | G1 |
| Normalization | 3.2 | PASS | `step_02/TM_NORMALIZATION_REPORT.md` | G2 |
| Entity resolution | 3.3 | CONDITIONAL_PASS | `step_03/`, `step_03_qa/G3_FINAL_ASSESSMENT.md` | G3 |
| Target construction | 3.4 | PASS | `step_04/`, `step_04/audit_4_1/STEP_04_1_FINAL_DECISION.md` | G4 |
| Integration | 3.5 | PASS | `step_05/INTEGRATION_AUDIT.md` | G5 |
| Final QA | 3.6 | CONDITIONAL_PASS | `step_05/PHASE3_FINAL_REPORT.md`, `step_05/VALIDATION_SUMMARY.md` | Final |

**Open:** human labels for 300 sampled identity pairs, review of 3 identities, and owner review of the final gate.

## Decision log

| ID | Decision | By | Date |
|---|---|---|---|
| D1 | Use seven pinned R2 CSV files | Owner | 2026-11-04 |
| D2 | CC0 accepted as the maintainer's declaration for internal academic research, with attribution; upstream rights unverified | Owner | 2026-11-04 |
| D3 | Project-local `.venv` | Owner | 2026-11-04 |
| D4 | Keep the latest-on-or-before-cutoff rule; report timing as a limitation | Owner | 2026-11-04 |
| D5 | No git | Owner | 2026-11-04 |
| D6 | Research objective A: end-of-season estimation | Owner | 2026-11-05 |
| D7 | Keep 2019/20 with original values and flags; xG and xA unavailable for comparison; sensitivity with and without | Owner | 2026-11-05 |
| D8 | Start Step 5 | Owner | 2026-11-05 |
| A1 | `AUTO_ADJUDICATED` status added for automated evidence-based decisions, kept separate from human review | Agent, under delegated authority | 2026-11-04 |
| A2 | `AUTO_HIGH_CONFIDENCE` stays off | Agent | 2026-11-04 |
| A3 | 90 days only labels `STALE_TARGET`; it excludes nothing | Agent, following `CLAUDE.md` | 2026-11-04 |
| A4 | `multi_club_class` added; 61 and 80 both kept | Agent, as requested | 2026-11-05 |
| A5 | D7 flag extends to npxG and xGOT, which share the same 2019/20 coverage | Agent | 2026-11-05 |
