# Phase 3 Issue Tracker

Updated 2026-11-04. This is the first Phase 3 tracker: none existed before, and earlier issues are gathered here from the Step 1–3 reports. The FotMob release has its own trackers in `reports/final_acceptance_fix/`.

Severity follows the SOP: CRITICAL can make a target or identity wrong; HIGH has a large effect on coverage or validity.

## Open

| ID | Severity | Issue | Impact | Owner | Next action |
|---|---|---|---|---|---|
| ISS-01 | HIGH | No human labels; direct precision bound is 98.70%, under the SOP's 99% | Keeps G3 conditional. 584 rows lack independent identity confirmation | Project owner | Label the 300 sampled pairs |
| ISS-02 | HIGH | 63.35% of usable targets are over 90 days old, and 41.09% of appearances come after the valuation date | Temporal alignment and interpretation limitation; not leakage | Owner, Phase 4 | Report in Phase 4; decide any filtering there (D4) |
| ISS-03 | HIGH | xG/xA observation windows unverified; 2019/20 xG on 69 of 515 rows | Feature validity. The SOP treats missing xG as HIGH, but it can't be fixed without new data | Agent, then owner | Leakage audit in Step 5, then record as an accepted limitation |
| ISS-04 | MEDIUM | 3 identities unresolved: Tauriainen, Jota, Chesters | 3 rows have no target | Project owner | Review in the queue |
| ISS-05 | MEDIUM | Multi-club counts differ (80 vs 61) | Reporting definition | Agent | Investigate before Step 5, as you requested |
| ISS-06 | MEDIUM | 2019/20 targets cluster on 2020-04-08 (491 of 498), possibly a pandemic revaluation; not verified | 2019/20 values may differ for non-performance reasons | Phase 4 | Test for a season effect |
| ISS-07 | MEDIUM | Birth dates disagree for 4 players, and external sources are split | The exact rule can't map such players automatically | Owner, optional | Check official records if ever needed |
| ISS-08 | MEDIUM | TM has no EPL game rows for 32 player-seasons; cause unknown | No effect on targets. Limits game-based identity evidence | Agent | Documented; no action needed |
| ISS-09 | MEDIUM | Height differs by 5 cm or more on 5.6% of mapped pairs | Height is unreliable as a feature or as evidence | Phase 4 | Use with care |
| ISS-10 | MEDIUM | Assists differ between sources in some seasons | Don't mix FotMob and TM assists | Phase 4 | FotMob stays the feature source |
| ISS-11 | LOW | `m_key_passes` is empty; goalkeepers mostly lack `m_minutes_played` | Feature availability | Step 5, Phase 4 | Missingness report |
| ISS-12 | LOW | 51 player-seasons have only post-cutoff valuations; 13 have no valuation history | Stay missing, by rule | None | Reported |
| ISS-13 | LOW | No git (D5), and frozen files aren't write-protected | Script hashes stand in for commits | Owner | Decision already made |
| ISS-14 | LOW | Raw FotMob profiles contain `marketValues` and a "Market value" field | Possible leakage if ever used; not in curated tables or this pipeline | Step 5 | Note in the leakage audit |
| ISS-15 | LOW | External evidence came from search summaries; one Premier League result had a mislabeled URL | Applies to 9 identities and to four cutoff dates | Agent | Disclosed. Cutoffs also agree with two datasets |
| ISS-16 | LOW | Upstream Transfermarkt rights unverified (D2) | Internal academic use only | Owner | Decision already made |
| ISS-17 | LOW | SOP items not produced: `fotmob_confirmed_population.parquet`, `DATA_CONTRACT.md`, `PHASE3_EXECUTION_TRACKER.md`; SOP preference for DuckDB snapshot over CSV | Documentation only; CSV was your D1 decision | Agent | Do before or during Step 5 |
| ISS-18 | LOW | Plain `unittest discover` makes legacy tests rewrite 10 Phase 2 files, and the suite takes about 9 minutes. The repo's own runner protects only 9 | My test runs did this. Content is byte-identical to the backup; only modification times changed | Agent | Use `step3_qa_run_full_tests.py`. See the incident section of the main audit |

## Resolved in this audit

| ID | Severity | Defect | Fix | Test |
|---|---|---|---|---|
| FIX-01 | MEDIUM | Validator missed TM club abbreviations, causing a false non-match | `rule_v2` club comparison | `ClubNameDefectTests` |
| FIX-02 | LOW | `DOB_NEAR` flagged exact dates when day equals month | Skip that swap | `DobNearDefectTests` |
| FIX-03 | MEDIUM | Confirm and reject of one pair was silently treated as confirmed | Now stops the run | `ReviewDefectTests` |
| FIX-04 | LOW | A decision for an unknown identity gave an unclear error | Clear error | `ReviewDefectTests` |
| FIX-05 | LOW | Queue cap hid 1 candidate | Cap raised | Output checks |
| FIX-06 | MEDIUM | Manifest hashed only 2 outputs; review files had no per-run copy | All outputs hashed; files snapshotted | `test_manifest_hashes_cover_every_output` |
| FIX-07 | LOW | `confidence_score` implied a probability | Renamed `ranking_score` | `test_score_is_not_presented_as_confidence` |
| FIX-08 | MEDIUM | Automated decisions had no separate status | `AUTO_ADJUDICATED` with adjudicator fields | `test_automated_rows_are_labeled_as_automated` |
| FIX-09 | MEDIUM | Draft `matching_v2` confirmed thin cases | Stricter rule in `matching_v2_1` | `AdjudicationTests` |
| ISS-R3 | MEDIUM | TM appearance shortfall was unexplained | Located: 32 player-seasons with no rows | Step 3 report |
| ISS-G0 | MEDIUM | Cutoffs lacked official sources | All six sourced from Premier League pages | `test_cutoffs_match_the_verified_config_and_fixtures` |
