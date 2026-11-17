# Phase 2B.1-R final acceptance fix: Prompt 1 handoff

This opening section records the historical Part 1 checkpoint. The current Part 2 release decision and reproduction commands are in **Part 2 final release handoff** below.

## Scope and verdict

**CONDITIONAL_PASS** for provisional appearance and player-season integrity. All 2,280 completed EPL matches were audited offline; unsupported negative classifications were removed from corrected staging. No final v3.1 release was published. Negative participation and season-wide non-appearance remain unverified because the stored source does not establish complete substitution coverage.

## Repository and preserved sources

- Workspace: `D:\PTIT\Hoc_may\FB69`; Python 3.14.6; dependencies in `requirements.txt`.
- Immutable historical matchDetails: `data/phase_02b1/raw/<season>/matchDetails/<capture>/response.json`, with sibling `metadata.json`; some pilot legacy captures use `data/pilot/raw/` and `.meta.json`.
- Original v2: `data/releases/fotmob_epl_2019_2025_v2`.
- Original v3: `data/releases/fotmob_epl_2019_2025_v3`.
- Full per-file SHA-256 snapshot of both releases: `reports/final_acceptance_fix/release_preservation_snapshot.json` (35 v2 + 39 v3 files).
- Preservation check: `preservation_and_resume_verification.json`; 74 release files unchanged and all 2,280 raw response checksums matched their capture metadata.
- Release manifests: `data/releases/fotmob_epl_2019_2025_v2/metadata/release_manifest.json` and v3 counterpart. Fixture index and appearance/population tables are under each release's `normalized/` directory.
- Previous reports: `reports/phase_02b1_remediation/REMEDIATION_HANDOFF.md` and `phase_02b1_remediation_final_report.md`; their appearance GO conclusion is superseded for corrected staging. The 16,314-row prior transition record is `appearance_resolution_audit.csv` in that directory.

## Audit outcome

| Season | Completed | Lineups | With fact substitutions | COMPLETE_VERIFIED | PARTIAL | STARTED | SUBSTITUTED_ON | UNKNOWN | Confirmed appeared PS | Unverified PS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/2020 | 380 | 380 | 380 | 0 | 380 | 8,360 | 2,254 | 3,420 | 515 | 99 |
| 2020/2021 | 380 | 380 | 380 | 0 | 380 | 8,360 | 2,033 | 4,250 | 524 | 117 |
| 2021/2022 | 380 | 380 | 380 | 0 | 380 | 8,360 | 2,125 | 4,677 | 537 | 142 |
| 2022/2023 | 380 | 380 | 380 | 0 | 380 | 8,360 | 2,985 | 3,840 | 554 | 145 |
| 2023/2024 | 380 | 380 | 380 | 0 | 380 | 8,360 | 3,024 | 3,796 | 570 | 164 |
| 2024/2025 | 380 | 380 | 380 | 0 | 380 | 8,360 | 3,207 | 3,621 | 562 | 123 |
| Total | 2,280 | 2,280 | 2,280 | 0 | 2,280 | 50,160 | 15,628 | 23,604 | 3,262 | 790 |

Corrected `UNUSED_SUBSTITUTE` and `CONFLICTING`: 0 each. Corrected `CONFIRMED_NON_APPEARED` and `CONFLICTING` player-seasons: 0 each. Partition: 3,262 + 790 = 4,052. The 4,135 original player-team-season links are preserved in staging. All six seasons have 380 eligible matches; abandoned Bournemouth–Luton match 4193691 is excluded and replay 4421797 is included.

## Defect and provenance

Legacy `classify_participation()` in `src/collection/remediation_substitutions.py` assigned UNUSED when an 11-player starting lineup and nonempty event feed contained no sub-in for the listed substitute, swaps were structurally valid, and no active stats existed. This does not prove the feed contains every substitution. The old transition log records 16,305 UNKNOWN→UNUSED under `COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_NO_APPEARANCE` and 9 under the bench-card variant. All 16,314 are reconstructed in the new transition audit. The additional 7,290 v2 UNUSED entries are also unsupported by complete negative evidence.

Both positive feeds agree for entering and exiting players in 2,280/2,280 matches, but may share an incomplete upstream source. No documented explicit unused flag or complete-substitution marker was found. The `COMPLETE_VERIFIED` rule requires such a documented marker or an independently complete participation source with coverage semantics. Hence no current match qualifies. Direct starter and substitution-on evidence remains accepted; the latter includes four players without active stats but with direct sub-in events.

## Code and provisional output

- Modified `src/collection/remediation_substitutions.py`: added `classify_participation_verified()` with explicit evidence classes. The legacy function remains for v3 reproducibility and must not be used for a new release.
- Added `src/collection/final_acceptance_fix.py`: raw/fixture/checksum verification, full-match evidence crosscheck, six deterministic season batches with checkpoint, corrected provisional tables and reports.
- Added `tests/collection/test_final_acceptance_fix.py`.
- Corrected staged data: `data/staging/fotmob_epl_2019_2025_v3_1_provisional/` (player-match appearances, substitution registry, complete and partitioned player-seasons, preserved player-team-seasons). This is **not** a final release.
- Reports: `reports/final_acceptance_fix/` including baseline reverification, match audit, crosscheck, 89,392-row transition audit, population reconciliation, quality report, issue tracker, test log and state JSON.

## Tests and checkpoint

`python -m unittest tests.collection.test_final_acceptance_fix tests.collection.test_population_execution02 -v` exited 0: 25 tests, 0 failures. Exact stdout/stderr and command are saved in `test_execution_log.txt`. A second execution of `python -m src.collection.final_acceptance_fix --workspace D:\PTIT\Hoc_may\FB69` exited 0 and reproduced all 31 staged file hashes; results are in `preservation_and_resume_verification.json`.

Current checkpoint is `acceptance_fix_state.json`, status `AUDITED`, all six seasons completed. Resume command:

```powershell
cd D:\PTIT\Hoc_may\FB69
python -m src.collection.final_acceptance_fix --workspace D:\PTIT\Hoc_may\FB69
```

No network requests were made. The checkpoint refuses changed input Parquet hashes and missing per-season batch files.

## Prompt 2 instructions

1. Use the provisional v3.1 staging tables and this transition evidence as inputs; keep v2/v3 and raw captures immutable.
2. Recompute appearance coverage, population eligibility, all dependent cross-season coverage and final quality gates. Do not inherit v3's zero-UNKNOWN or 790 confirmed non-appeared assertions.
3. Treat all 23,604 UNKNOWN player-matches and 790 UNVERIFIED player-seasons as unresolved unless stronger documented independent evidence is found. Evaluate any source marker and coverage semantics before assigning `COMPLETE_VERIFIED` or restoring UNUSED.
4. Review issue tracker AF-01 through AF-04 and the four sub-in cases lacking active stats. Keep player-team-season links and match eligibility intact.
5. Do not publish a corrected release until the next acceptance prompt authorizes and validates the release-specific work. Do not begin Transfermarkt or ML work.

## Part 2 final release handoff

Verdict: **CONDITIONAL_GO**. Release: `data/releases/fotmob_epl_2019_2025_v3_1/`. All six seasons: CONDITIONAL_PASS. Full suite: 190/190 passed, exit 0. Manifest: 39 files / 16 Parquet; parent v2/v3 unchanged. See `final_acceptance_report.md` and `release_reproducibility_report.md`. Controlled Transfermarkt Data Integration may begin as a separate phase with UNKNOWN/UNVERIFIED and xG/xA coverage-quality flags retained.

The active manifest generator is `src/collection/release_manifest.py`, invoked by `src/collection/final_acceptance_release.py`. The original v3 generator is guarded against overwriting its audited release. The v3.1 release has 30/30 data quality gates PASS and all 16/16 Parquet table grain/type/source-path contracts PASS. All 41 historical >100% coverage cells were rechecked against the corrected 318-row metric-season matrix and resolved. Offline metric reconstruction found zero value/status differences across 4,052 player-seasons and reproduced all 575 conflict entries.

Exact validation commands from repository root:

```powershell
python -m src.collection.final_acceptance_fix --workspace D:\PTIT\Hoc_may\FB69
python -m src.collection.full_test_runner
python -m src.collection.final_acceptance_release --workspace D:\PTIT\Hoc_may\FB69
python -m src.collection.final_acceptance_repro
python -m src.collection.final_acceptance_table_audit
python -m src.collection.final_acceptance_reporting --workspace D:\PTIT\Hoc_may\FB69 --candidate D:\PTIT\Hoc_may\FB69\data\staging\fotmob_v3_1_candidate_y7xem2iy
```

The final test execution evidence is `full_test_execution.log` plus `test_environment_report.json`. `acceptance_fix_state.json` records the release path, test counts, gate results and final verdict. The candidate path above is retained only as independent rebuild evidence; the accepted versioned dataset is the release path.
