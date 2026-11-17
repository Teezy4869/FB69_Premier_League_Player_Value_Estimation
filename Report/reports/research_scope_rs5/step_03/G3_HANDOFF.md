# rs5 Step 3 Handoff: G3 Identity and Integration Gate

Date: 2026-11-07. Prerequisites checked: G1 PASS, G2 PASS (reports present; both manifests verify). **G3: CONDITIONAL PASS.**

## G3 criteria

| Criterion | Evidence | Met |
|---|---|---|
| Entity resolution reassessed | Unchanged matcher and validator re-run on in-scope evidence; 1,228 identities compared | Yes |
| Mapping evidence traceable | `MAPPING_EVIDENCE_REPORT.md`; candidates, evidence JSON, manifests | Yes |
| Unresolved identities explicitly retained | 2 `REVIEW_REQUIRED`, rows kept with reasons | Yes |
| Integrated dataset rebuilt | `fb69_player_season_integrated_rs5_v1` | Yes |
| Player-season grain respected | 2,747 rows = 2,747 keys | Yes |
| No excluded season present | 0 rows; tested | Yes |
| All integration validations pass | 27 of 27; 422 of 422 tests | Yes |

**Why conditional, not full:** identity correctness is still automated, not human-validated, as in Phase 3 (ISS-01). On a fresh random sample of 300 AUTO_EXACT pairs, the 95% lower bound among decided pairs is 98.73%, below the SOP's 99%; 66 of the 300 are inconclusive. Two identities are unresolved, and two RULE adjudications rest on evidence that is inconclusive in scope (RD-02). Phase 4 can still start, under the conditions in the final report.

## Outputs

| Output | Location |
|---|---|
| Research crosswalk | `data/research_rs5/entity_resolution/matching_v2_1_rs5__reviews_none/` and `crosswalk_rs5_manifest.json` |
| rs5 identity validation labels | `data/research_rs5/entity_resolution/matching_v2_1_rs5_identity_validation.csv` |
| Review inputs | `data/research_rs5/review/` |
| Target used for integration | `data/research_rs5/targets/target_rs5_v1__matching_v2_1_rs5/` (supersedes `__matching_v2_1` from Step 2; only identity columns differ) |
| **Integrated research dataset** | `data/releases/fb69_player_season_integrated_rs5_v1/` |
| Reports | `reports/research_scope_rs5/step_03/` |

## Statistics

2,747 rows, 1,228 players. Mapped rows 2,745 (99.93%). Usable targets 2,697 (98.18%); missing 50 (37 later valuations only, 11 no history, 2 no identity). Duplicates 0.

## Next actions for Prompt 04

1. Audit `player_season_integrated_rs5_v1.parquet` only.
2. Re-run the feature-window audit (`src/phase3/feature_window_audit.py` logic) on the rs5 release, to re-derive each feature's verification status for five seasons.
3. Recompute temporal indicators with the definitions in `step_02/TARGET_COVERAGE_REPORT.md` (56.62% of targets over 90 days; 44.10% of appearances after valuation; recompute independently).
4. Carry RD-01 and RD-02 and the open historical issues into the rs5 issue tracker.
