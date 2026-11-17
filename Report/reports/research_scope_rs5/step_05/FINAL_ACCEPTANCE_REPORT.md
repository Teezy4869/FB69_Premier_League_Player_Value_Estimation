# FB69 Five-Season Research Release: Final Acceptance Report

Date: 2026-11-07. Reviewer role: technical lead and independent release reviewer. Every result below was re-checked against the repository in this step, not taken from earlier handoffs.

**Final verdict: CONDITIONAL PASS.** Phase 4 can start on `data/releases/fb69_player_season_integrated_rs5_v1/`, under the conditions in section 10.

---

## 1. Executive summary

**What changed.** The official research scope moved from six EPL seasons (2019/20 to 2024/25) to five (2020/21 to 2024/25). The owner decision is recorded as D9; it supersedes D7. One central configuration now defines the scope. New, versioned research artifacts were built from the frozen sources. Every historical artifact was left byte-identical.

**Why.** It's the owner's decision. Context from Phase 3, not offered as justification: 491 of 498 usable 2019/20 targets sit on a single 2020-04-08 pandemic revaluation batch (ISS-19). The 2019/20 xG family covers only 4 of 380 matches (ISS-20).

**Release status.** `player_season_integrated_rs5_v1`: 2,747 player-seasons, 1,228 players, 98.18% usable targets. All 27 integration checks and 437 of 437 tests pass. A full rebuild matched 69 of 69 files byte for byte. It is conditional because identities are validated automatically, not by a person, and because of a documented label/feature timing mismatch.

## 2. Research scope

| Item | Value |
|---|---|
| Included seasons | 2020/21, 2021/22, 2022/23, 2023/24, 2024/25 |
| Excluded season | 2019/20, permanently, with no separate workstream |
| Objective | **A: end-of-season estimation (D6)**, unchanged |
| Cutoff and target rule | Official season end; latest valid valuation on or before it (D4), unchanged |
| Source of truth | `configs/research_scope.yaml` via `src/research_scope/scope.py`; snapshot in the release |

## 3. Dataset statistics

| Measure | Value |
|---|---:|
| Player-season rows | **2,747** |
| Unique players | **1,228** |
| Rows per season | 524 / 537 / 554 / 570 / 562 |
| Usable targets | **2,697** |
| Missing targets | **50**: 37 only later valuations, 11 no history, 2 no identity |
| Integration coverage (usable / rows) | **98.18%** |
| Mapping coverage | 1,226 of 1,228 identities (99.84%); 2,745 of 2,747 rows (99.93%) |
| Identities: AUTO_EXACT / AUTO_ADJUDICATED / REVIEW_REQUIRED | 1,190 / 36 / 2 |
| Columns | 175 (108 candidate predictors: 53 metrics, 53 statuses, 2 context) |
| Target, EUR | median 13.0m, mean 19.3m, max 200m |

Reconciliation: on all 168 shared non-identity columns, the rs5 rows equal the historical v1 rows for the same seasons exactly. The removal of 2019/20 changed no in-scope value.

## 4. Data quality

| Dimension | Result |
|---|---|
| Duplicates | 0 duplicate keys, 0 duplicate rows |
| Referential integrity | 12 of 12 FotMob checks; every TM id exists; crosswalk = dataset = target |
| Invalid values | 0 in every rule. **One exception:** 6 rows (all 2020/21) where `m_starts` > `m_appearances`, kept as published |
| Missingness | 33.00% of metric cells null; 17.03 null metrics per row with a target vs 42.10 without; goalkeepers 34.49. Not random. Nothing imputed |
| Conflicts | 36 `CONFLICTING` cells (null, traceable) |
| Unverified records | 691 Unverified player-seasons outside the population; 20,184 UNKNOWN bench participations; 17,899 `UNVERIFIED_POSITION` cells |
| Coverage gaps | `key_passes` empty; `clearances` only in 3 of 5 seasons |
| Source limitations | Retrospective collection (November 2026; 95 cells revised by the source); TM same-day deduplication upstream; `datum_mw` semantics unknown; upstream rights unverified (D2) |

## 5. Temporal validity

All figures were recomputed on the five seasons, and recomputed independently from match dates.

| Indicator (denominator) | rs5 |
|---|---:|
| Targets over 90 days old (usable targets, 2,697) | **56.62%** |
| Appearances after the valuation (confirmed appearances of usable rows, 55,073) | **44.10%** |
| Minutes after the valuation | 43.66% |
| Median valuation age | 150 days |
| Valuations after cutoff / appearances after cutoff | **0 / 0** |
| Targets over 365 days | 12 |

- **Cutoffs:** in every season, the last completed match is on the cutoff date, and the dataset cutoff equals the scope cutoff.
- **Observation windows:** 265 metric-seasons were re-tested against match sums, identical to the historical rows for these seasons. The xG family is verified in every season, except xGOT in 2022/23 (92.06%).
- **Remaining risk (RD-03):** the label is a mid-season valuation (league-wide batches between November and March), but the features cover the whole season. This is a construct mismatch under A, documented and not changed.

## 6. Leakage assessment

No candidate feature carries target information or information from after the cutoff. The largest |Spearman| with log target is 0.671 (`m_clean_sheets`). **The dataset is not declared leakage-free in the broad sense.**

| Class | Candidate predictors (108) |
|---|---:|
| PASS | 1 (`age_at_season_end_years`) |
| WARNING | 102: alignment limit (all `m_*`); 8 source-reported rates not verifiable; `key_passes` empty; `s_*` statuses |
| REQUIRES RESEARCH DECISION | **5**: `clearances`, `clearances_per90`, `expected_goals_on_target`, `touches_opposition_box`, `goals_prevented` (RD-04) |
| FAIL | 0 |

Excluded by role and classified FAIL: 16 target columns, 8 `temporal_*` columns, 3 player ids and `nationality_profile_present_day`. Club context (8 columns) requires a decision. **Identity leakage:** 687 players span several seasons, so Phase 4 must group splits by player or split by season.

## 7. Testing and reproducibility

| Check | Result | Evidence |
|---|---|---|
| Full repository tests (protected runner) | **437 run, 437 passed, 0 failed, 0 skipped** (366 historical + 71 rs5) | `evidence/final_test_run/` |
| Integration validation | 27 of 27 | `../step_03/evidence/integration_validation.json` |
| End-to-end rebuild in a temporary folder, each stage reading the rebuilt previous stage | **69 of 69 files identical** (bytes; JSON manifests without timestamps) | `evidence/rs5_reproduction.json` |
| Builder re-runs on real paths | "identical content" for FotMob, both targets, integration | build logs |
| rs5 manifests (outputs, inputs) | All outputs and inputs match | `rs5_reproduction.json` → `manifest_checks` |
| Release manifest | 21 files, all SHA-256 verified (test) | `release_manifest.json` |
| Historical Phase 3 rebuild | **12 of 12 stages byte-identical** | `evidence/historical_phase3_reproduction_final.json` |
| Historical protection (16,290 baseline files) | 0 changed except the documented `CLAUDE.md` edit (backed up); 0 removed | `evidence/protection_check_final.json` |
| Frozen inputs | FotMob v3.1 38 of 38 hashes; TM raw 7 of 7 | same |

Byte-level reproducibility holds with the pinned environment (`.venv314`: Python 3.14.6, duckdb 2.0.0, pyarrow 24.0.0). Only manifest timestamps differ between runs.

**Code-hash note:** the Step 2 target's manifest records an earlier hash of `build_targets_rs5.py`. A `--validation` option was added later, and the current script reproduces that target byte for byte. There's no git (D5).

## 8. Issues and limitations

Full tracker: `../step_04/ISSUE_TRACKER.md`. No open issue is critical.

| ID | Severity | Issue | Implication | Recommended action |
|---|---|---|---|---|
| ISS-01 | HIGH | Identities validated automatically only; random-300 lower bound 98.73% (< 99%) | Small risk of wrong targets | Owner labels the 300-pair sample |
| RD-03 / ISS-02 | HIGH | Mid-season label vs full-season features | Can't read results as performance driving value | Keep D4 and report, or decide a new rule (new version) |
| RS5-11 | HIGH | Same players across seasons | Random splits leak identity | Grouped or temporal splits |
| RD-04 | MEDIUM | 5 metrics with incomplete window evidence | Possible bias | Decide exclusion before modeling |
| RD-02 | MEDIUM | 2 adjudications inconclusive in scope (3 rows) | Negligible | Keep, or send to review |
| ISS-04 | MEDIUM | 2 unresolved identities (2 rows) | No target for them | Human review |
| ISS-27 / ISS-25 | MEDIUM | Non-random missingness; null may mean "none" | Bias if handled carelessly | Explicit missingness plan |
| RD-01 | LOW | 12 targets over 365 days old | Weak labels | Keep, or approve an age cap |
| RS5-01 | LOW | Original `.venv` unusable here | Reproduce with `.venv314` | Keep `.venv314` |

## 9. Final verdict: **CONDITIONAL PASS**

| G5 requirement | Met |
|---|---|
| Five-season scope enforced | Yes: central config; builders and tests reject out-of-scope seasons |
| No 2019/20 in official research artifacts | Yes: 0 rows; tested on every table, CSV and release document |
| New integrated dataset validated | Yes: 27 of 27 checks |
| Target construction validated | Yes: unchanged rule; 14 of 14 checks; rows equal historical in scope |
| Entity resolution evidence documented | Yes; traceable; unresolved retained |
| Data quality, temporal and leakage audits completed | Yes |
| Automated tests passing | Yes, 437 of 437 |
| Release manifest and checksums verified | Yes |
| Reproducibility demonstrated | Yes, byte-level end to end |
| Final acceptance report complete | Yes |

**Why not PASS:** non-critical limitations remain: identities aren't human-validated (G3 conditional), there's the label/feature construct mismatch (G4 conditional), and four research decisions are open. They are quantified and don't invalidate EDA. **Why not FAIL:** no integrity, scope, target-validity or reproducibility requirement is unmet.

## 10. Phase 4 readiness

- **Can Phase 4 start?** Yes, for EDA and feasibility work, once the owner instructs it. Nothing in Phase 4 was started here.
- **Dataset to use:** `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet` (SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd`). Not integrated v1.
- **Limitations to carry forward:** ISS-01, RD-03, RS5-11, RD-04, RD-02, RD-01, ISS-27, ISS-25, ISS-21 and ISS-22 (`docs/PHASE4_CONDITIONS.md`).
- **Features needing caution:** decide on the 5 RD-04 metrics first; exclude `key_passes`; read `s_*` before treating nulls; club context needs a decision; never use `target_*`, `temporal_*`, `identity_*`, ids or nationality as predictors.

## Paths

| Item | Path |
|---|---|
| Official release | `data/releases/fb69_player_season_integrated_rs5_v1/` |
| Scope configuration | `configs/research_scope.yaml` |
| FotMob research release | `data/releases/fotmob_epl_2020_2025_rs5_v1/` |
| Crosswalk, targets, review files | `data/research_rs5/` |
| Reports, by step | `reports/research_scope_rs5/step_01` … `step_05`, `DATA_CONTRACT_RS5.md` |
| Code and tests | `src/research_scope/`, `tests/research_scope/` |
| Historical releases (unchanged) | `data/releases/fb69_player_season_integrated_v1/`, `data/releases/fotmob_epl_2019_2025_v3_1/` |
