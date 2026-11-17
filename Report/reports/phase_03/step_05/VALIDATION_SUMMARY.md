# Final Validation Summary (Phase 3, Step 5)

Date: 2026-11-05. All commands ran in the project `.venv`. Plain `unittest discover` was not used.

| Check | Command | Result | Evidence |
|---|---|---|---|
| **Full repository tests** | `step3_qa_run_full_tests.py reports/phase_03/step_05/evidence` | **366 of 366 passed**, 351 seconds, exit 0 | `evidence/full_repository_test_run.json` |
| **Dataset validation** | `validate_integration.py` | **31 of 31 checks passed** | `evidence/validation_summary.json` |
| **Full-chain reproduction** | `reproduce_phase3.py` | **All 12 checks identical** | `evidence/phase3_reproduction.json` |
| **Test safety** | `step4_1_test_safety.py` | 0 of 433 watched files changed; 10 protected files byte-identical to backup | `evidence/test_safety_after.json` |
| **Frozen FotMob v3.1** | Manifest hash check | 38 of 38 valid | Same |

## Tests by area

| Area | Tests |
|---|---|
| Phase 1 and 2 (existing) | 190 |
| Phase 3 Steps 2–4, including QA and temporal | 147 |
| Phase 3 Step 5 integration | 29 |
| **Total** | **366** |

## Requested test coverage

| Requirement | Test |
|---|---|
| Confirmed-only population | `test_confirmed_only` |
| Row count against frozen source | `test_row_count_matches_frozen_source` |
| No Unverified rows | `test_confirmed_only` |
| One row per player-season | `test_one_row_per_canonical_player_season` |
| No unintended many-to-many | `CheckedJoinTests`, `test_every_join_kept_the_row_count` |
| Crosswalk and target keys | Checked at each join; validator checks |
| No valuation after cutoff | `test_no_valuation_after_cutoff`, plus Step 4 tests |
| Staleness correct | `test_staleness_is_correct` |
| No future fallback | `test_no_future_information_columns`, plus Step 4 tests |
| Missing targets stay missing | `test_missing_targets_stay_missing` |
| Features not zero-filled | `test_features_are_unchanged_and_nulls_are_not_zero` |
| Unmatched and ambiguous remain auditable | `test_unresolved_identities_remain_auditable` |
| Rebuild from frozen inputs | `test_integration_rebuilds_byte_identically`, `test_full_chain_reproduction_passed` |
| Manifests and counts consistent | `test_manifest_matches_outputs` |
| Validation scripts run | `test_validation_summary_has_no_failures` |

## Reproduction checks

Each stage was rebuilt in a temporary folder and compared byte for byte, except the raw snapshot, which was hash-checked rather than re-downloaded.

| Stage | Output | Identical |
|---|---|---|
| Raw snapshot | 7 files, hash check | Yes |
| Normalization | 13 tables | Yes |
| Identity validation | `auto_match_validation_all_1299.csv` | Yes |
| Adjudication | `automated_adjudications.csv` | Yes |
| Entity resolution | Crosswalk, candidates, unresolved list | Yes |
| Targets | `player_season_target.parquet` | Yes |
| Step 4.1 audit | Temporal alignment, quality flags | Yes |
| Integration | Dataset, club evidence | Yes |

## What these don't cover

- The source wasn't re-downloaded. External lookups for 9 identities are recorded in the adjudication file, and that file's automated decision logic was rerun, but searches weren't repeated.
- Generation timestamps in manifests naturally differ between runs. Data files don't.
- Reproduction was on one machine and environment (`requirements_freeze.txt`).
- Identity precision isn't tested by any of this: human labels don't exist.
