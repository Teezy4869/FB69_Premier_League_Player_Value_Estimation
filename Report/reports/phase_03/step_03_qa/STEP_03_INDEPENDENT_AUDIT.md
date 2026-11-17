# Step 3 Independent Audit

Date: 2026-11-04. Audited version: `matching_v1`. Final version: `matching_v2_1`.

## 1. Executive decision

| Decision | Result |
|---|---|
| **G3** | **`CONDITIONAL_PASS`.** Integrity is fully verified. Direct validation falls short of 99%, and no human labels exist |
| **Step 4** | **Authorized and completed** on eligible mappings. G4 is `PASS` on temporal criteria |
| **G0** | Upgraded to **`PASS`**: all six cutoffs now have Premier League sources |

No automatic mapping was shown to be wrong, and none changed. All decisions here are **automated adjudication, not human review**.

## 2. Original versus final mappings

| Status | `matching_v1` players / rows | `matching_v2_1` players / rows |
|---|---:|---:|
| `AUTO_EXACT` | 1,299 / 3,161 | 1,299 / 3,161 (identical mappings) |
| `AUTO_ADJUDICATED` (new, automated) | 0 / 0 | 41 / 98 |
| `REVIEW_REQUIRED` | 44 / 101 | 3 / 3 |
| `MANUAL_CONFIRMED`, `AMBIGUOUS`, `UNMATCHED` | 0 | 0 |
| **Total** | **1,343 / 3,262** | **1,343 / 3,262** |

`matching_v1` and its code snapshot, and the superseded draft `matching_v2`, are all retained in `data/phase_03/entity_resolution/`.

## 3. Reproducibility audit

Before any code changed, v1 was rebuilt from its documented inputs (`evidence/reproduction_audit.json`).

| Check | Result |
|---|---|
| 1,343 players, 1,299 `AUTO_EXACT`, 44 unresolved | Reproduced |
| 3,161 mapped rows, 101 unresolved rows | Reproduced |
| Crosswalk, candidates, queue, sample and unresolved list | **Byte-identical** |
| Duplicate FotMob, canonical or TM IDs | 0 |
| FotMob release (38 files), TM raw (7), TM normalized (13), v1 inputs, outputs and code | 0 hash mismatches |
| Birth dates re-derived from raw FotMob JSON and the original TM CSV | 0 mismatches |
| Ledger append-only behavior | Tested; no ledger exists because no person has reviewed |

**The 44, 93 and 101 aren't a discrepancy.** They count different things, and nothing is missing or duplicated:

| Number | Meaning |
|---|---|
| **44** | People (unresolved FotMob identities) |
| **93** | Candidate rows in the queue: 16 people × 1 row, 15 × 2, 8 × 3, 2 × 4, 3 × 5 |
| **101** | Those 44 people's player-season rows, because many played several seasons |

The queue's top-5 cap hid 1 candidate. Without the cap the queue has 94 rows, and all 44 people remain in it so a person can overturn automated decisions.

## 4. Defects found and corrected

| ID | Severity | Defect | Effect on mappings |
|---|---|---|---|
| FIX-01 | MEDIUM | My validator missed TM club abbreviations, creating a false non-match | None; validator only |
| FIX-02 | LOW | `DOB_NEAR` flagged exact dates when day equals month | None |
| FIX-03 | MEDIUM | Confirm and reject of one pair silently counted as confirmed | None; no decisions existed |
| FIX-04 | LOW | Unknown identity in a decision gave an unclear error | None |
| FIX-05 | LOW | Queue cap hid 1 candidate | None |
| FIX-06 | MEDIUM | Manifest hashed only 2 outputs; review files had no per-run copy | None |
| FIX-07 | LOW | `confidence_score` implied a probability | Renamed `ranking_score` |
| FIX-08 | MEDIUM | No status separated automated decisions from human ones | Added `AUTO_ADJUDICATED` |
| FIX-09 | MEDIUM | My first adjudication draft confirmed all 44, including thin cases | Tightened; 3 kept for review |

Each has a test. See `ISSUE_TRACKER.md`.

## 5. Incident during this audit

**My full-suite runs rewrote 10 historical files.** I first ran plain `unittest discover`, and legacy tests regenerate 7 files in `data/phase_02b1/remediation/` and 3 in `reports/phase_02b1_remediation/`. The repo's `full_test_runner.py` protects 9 of these, and I should have read it first. The tenth, `curated/player_season_metrics_wide_provisional.parquet`, is missing from that runner's list and was rewritten during my later protected run. Change detection caught it.

| Check | Result |
|---|---|
| Content compared to the `FB69.rar` backup of 3 November | **All 10 byte-identical** |
| Frozen FotMob v3.1 release | Unchanged; 38 of 38 hashes match |
| Phase 3 outputs affected | None; they don't read these files |
| Other files changed outside Phase 3 outputs, by a scan of the whole tree | None, apart from your `CLAUDE.md` and the `requirements.txt` edits from Steps 2 and 3 |
| Lasting effect | Modification times on the 10 files now read 2026-11-04 |

No restore was needed. `src/phase3/step3_qa_run_full_tests.py` now backs up, restores and verifies all 10. The archive was extracted to the session scratchpad only, and is unchanged.

## 6. Independent validation

**Method:** a fixed rule using career, physical and performance evidence, with no use of name, birth date or game overlap as a family. Negative controls test whether it can say no. Full details are in `AUTO_MATCH_VALIDATION_REPORT.md`.

| Result | Value |
|---|---|
| Random sample of 300: confirmed / non-match / inconclusive | **228 / 0 / 72** |
| 95% lower bound on precision among the decided | **98.70%** (below the 99% target) |
| 95% lower bound on verified share, making no assumption about inconclusive pairs | 71.6% |
| All 1,299: confirmed / non-match / inconclusive | 980 / 0 / 319 |
| False confirmations in controls (random; teammate; most similar body) | 0; 0; 3 of 1,299 |
| Model-based minimum precision (hardest control) | 99.15%, assumption-based |

**Limits:** no human labels; providers may share upstream data; inconclusive pairs skew to young and fringe players.

## 7. Unresolved identities

3 identities (3 rows) remain `REVIEW_REQUIRED`: **Jimi Tauriainen, Jota, Daniel Chesters**. All look likely to be correct but don't meet the automated standard. Birth-date conflicts for 4 players are split across external sources and can't be attributed to either dataset. See `UNRESOLVED_IDENTITY_INVESTIGATION.md`.

## 8. Test results

All run in `.venv`. Results: `evidence/full_repository_test_run.json`.

| Suite | Result |
|---|---|
| **Full repository** (all Phase 1 to 3 tests) | **337 of 337 passed**, 522 seconds, exit code 0 |
| Phase 3 tests, including the QA and temporal tests | 147 of 147 passed |
| FotMob release and final acceptance tests | 28 of 28 passed |

No test was skipped by choice. After that run, the only code change was adding the tenth file to the wrapper's protected list, and the wrapper has not been rerun since.

## 9. Data lineage and checksums

| Layer | Status |
|---|---|
| FotMob v3.1 | Unchanged |
| TM raw snapshot | Unchanged, read-only |
| TM normalized | Unchanged |
| `matching_v1` | Unchanged; code and review snapshots added alongside it |
| `matching_v2_1` | New; manifest hashes all outputs, inputs and code; rebuild is byte-identical |
| Targets | New; manifest hashes inputs and outputs; rebuild is byte-identical |

There is no git commit (D5), so script hashes stand in for code versions.

## 10. Related reports

`AUTO_MATCH_VALIDATION_REPORT.md`, `UNRESOLVED_IDENTITY_INVESTIGATION.md`, `MATCHING_ARCHITECTURE_REVIEW.md`, `G3_FINAL_ASSESSMENT.md`, `STEP_04_READINESS_DECISION.md`, `ISSUE_TRACKER.md`, and `evidence/`. Step 4 results are in `reports/phase_03/step_04/`.
