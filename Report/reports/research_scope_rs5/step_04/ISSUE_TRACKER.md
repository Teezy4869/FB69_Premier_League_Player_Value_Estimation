# rs5 Issue Tracker

Updated 2026-11-07. Scope: `player_season_integrated_rs5_v1`. Historical tracker (`reports/phase_03/step_05/ISSUE_TRACKER.md`) is unchanged; issues carried from it keep their ID. Type: **TD** = technical defect; **SL** = inherent source-data limitation; **RD** = research decision needed; **MT** = methodology.

**No open issue is CRITICAL.** No technical defect blocks EDA.

## Open

| ID | Type | Severity | Description | Affected | Evidence | Research impact | Proposed remediation | Status |
|---|---|---|---|---|---|---|---|---|
| ISS-01 | SL | HIGH | No human identity labels; fresh random-300 lower bound 98.73% (SOP 99%); 66 of 300 inconclusive | Crosswalk; 2,745 mapped rows | `step_03/ENTITY_RESOLUTION_REPORT.md` | Small risk of wrong targets; keeps G3 conditional | Owner labels `data/research_rs5/review/validation_sample_for_labeling.csv`; identity sensitivity in Phase 4 | Open |
| ISS-02 / RD-03 | MT | HIGH | Label is the latest valuation on or before season end (median 150 days before); 44.10% of appearances and 43.66% of minutes come after it | Target vs all `m_*` | `TEMPORAL_ALIGNMENT_REPORT.md` | Construct mismatch under A; don't claim performance determines value | Decide: keep D4 and report (default), or approve another rule. Not changed | Open, escalated |
| RS5-11 | MT | HIGH | 687 players appear in 2+ seasons (2,206 rows) | Any random split | `LEAKAGE_AUDIT.md` | Identity leakage across train and test | Phase 4 must use player-grouped or season-based splits | Open (Phase 4 condition) |
| RD-04 | RD | MEDIUM | Window evidence incomplete for xGOT (2022/23: 92.06%), touches_opposition_box (4 seasons disagree), goals_prevented (verified in 1 season); clearances absent in 2 seasons | 5 metrics | `feature_window_audit_rs5.csv` | Biased or season-dependent features | Exclude, or use with season-aware handling | Open |
| RD-02 | RD | MEDIUM | 2 RULE adjudications (El Mohamady, Wesley) are inconclusive on in-scope evidence; no contradiction | 3 rows | `ENTITY_RESOLUTION_REPORT.md` | Negligible on counts | Keep (default) or set to REVIEW_REQUIRED; a change needs a new version | Open |
| RD-01 | RD | LOW | 12 usable targets are over 365 days old (max 731; one dated 2019-05-23); no age cap in the rule | 12 rows | `step_02/TARGET_CONSTRUCTION_REPORT.md` | Weak labels for a few fringe players | Keep, or approve a maximum age | Open |
| ISS-04 | SL | MEDIUM | 2 identities unresolved (Tauriainen, Chesters) | 2 rows without target | `step_03/UNMATCHED_PLAYER_REPORT.md` | 0.07% of rows | Human review of 3 queue rows | Open |
| ISS-27 | SL | MEDIUM | Missingness not random: missing-target rows have 42.10 of 53 metrics null; GK 34.49 | Complete-case analyses | `MISSINGNESS_REPORT.md` | Selection bias if rows are dropped | Plan missingness handling; don't drop silently | Open |
| ISS-28 | SL | MEDIUM | Uneven metric coverage: clearances 3 of 5 seasons; key_passes none | 3 metrics | `MISSINGNESS_REPORT.md` | Season-dependent availability | See RD-04 | Open |
| ISS-21 | SL | MEDIUM | Valuation dates are league-wide batches; age tracks season | Target timing | `step_02/TARGET_COVERAGE_REPORT.md` | Season and target timing confounded | Season-aware analysis | Open |
| ISS-22 | MT | MEDIUM | Staleness filters would change season mix (2020/21 has 2.91% over 90 days; 2021/22 has 78.03%) | Any filter | `TEMPORAL_ALIGNMENT_REPORT.md` | Selection bias | No filter applied; analyze before deciding | Open |
| ISS-25 | SL | MEDIUM | A null may mean "no event" (penalty_saves null for 31.55% of GK rows; xG null 17.95%) | Count metrics | `MISSINGNESS_REPORT.md` | Misreading null as missing or as zero | Decide per metric in Phase 4; never zero-fill silently | Open |
| RS5-12 | RD | MEDIUM | Club context may encode a post-valuation transfer and proxy value (73 multi-club rows) | 8 CLUB_CONTEXT columns | `LEAKAGE_AUDIT.md` | Possible proxy leakage if used | Phase 4 decision; not candidate predictors by default | Open |
| ISS-23 | SL | MEDIUM | Source removes same-day duplicates and empty values before publishing | Target | Phase 3 | Conflicts can't be seen | None | Open (documented) |
| ISS-24 | SL | MEDIUM | `datum_mw` semantics (effective vs publication date) unknown | Target date | Phase 3 | Age interpretation | None | Open (documented) |
| ISS-09 / ISS-10 | SL | MEDIUM | Height differs between sources for some pairs; FotMob and TM assists differ in some seasons | Identity evidence | Phase 3 | Don't mix sources | FotMob stays the feature source | Open |
| RS5-13 | SL | LOW | Metrics collected retrospectively (2026-11-02/03); 95 cells revised by the source | All `m_*` | `DATA_QUALITY_REPORT.md` | Values may differ from what was visible at season end | Document | Open |
| DQ-RS5-04 | SL | LOW | `m_starts` > `m_appearances` in 6 rows (2020/21) | 6 rows | `DATA_QUALITY_REPORT.md` | Negligible | Keep as published | Open |
| ISS-11 | SL | LOW | Goalkeepers mostly lack minutes, so GK per90 rates can't be checked | GK rows | `LEAKAGE_AUDIT.md` | GK features limited | Noted | Open |
| ISS-07 | SL | LOW | 4 birth dates disputed across sources (historical finding) | Age, identity | Phase 3 | Small | Official records if needed | Open |
| RS5-09 | SL | LOW | 387 player profiles stored in 2019_2020-named capture folders (player-level, not season data) | Provenance paths | `step_02/FOTMOB_COVERAGE_REPORT.md` | None on values | Documented; tested | Open (documented) |
| RS5-01 | TD | LOW | Original `.venv` points to a missing interpreter; `.venv314` created | Environment | `step_01/BASELINE_AUDIT_REPORT.md` | Reproduction needs `.venv314` | Use `.venv314`; historical rebuild byte-identical | Mitigated |
| ISS-18 | TD | LOW | Plain `unittest discover` rewrites 10 Phase 2 files | Tests | Phase 3 | Historical files at risk | Use `src/phase3/step3_qa_run_full_tests.py` | Mitigated |
| ISS-13 | SL | LOW | No git (D5); script hashes stand in | Provenance | Manifests | Weaker code provenance | Decided | Accepted |
| ISS-16 | SL | LOW | Upstream Transfermarkt rights unverified (D2) | Distribution | Phase 3 | Internal academic use only | Decided | Accepted |
| ISS-15 / ISS-26 / ISS-30 / ISS-31 / ISS-14 | SL | LOW | Search-summary evidence; 2 minutes gaps in 2023/24; starts differ from confirmed on 13 rows; no separate population file; raw `marketValues` not carried | Various | Phase 3 | Negligible | Documented | Open (documented) |

## Closed by the scope change (D9)

| ID | Issue | Resolution |
|---|---|---|
| ISS-19 | 2019/20 targets on the 2020-04-08 birth-year cut | Season excluded; 0 in-scope rows on that batch |
| ISS-20 | 2019/20 xG family from 4 of 380 matches | Season excluded; xG family verified in all rs5 seasons (xGOT 2022/23 → RD-04) |
| D7 handling | Flags and with/without sensitivity | Superseded by D9; columns removed |
| ISS-29 (partly) | per90 rates not verified | 8 per90 rates now verified indirectly against verified totals; 8 source-reported rates remain unverified |
