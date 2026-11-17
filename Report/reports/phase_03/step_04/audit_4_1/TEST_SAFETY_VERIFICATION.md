# Test Safety Verification (Step 4.1)

Date: 2026-11-05. Results: `evidence/full_repository_test_run.json`, `evidence/test_safety_before.json`, `evidence/test_safety_after.json`.

**Conclusion:** the protective runner works with the tenth file added. The full suite passes, and nothing it protects or watches changed.

## 1. The runner

`src/phase3/step3_qa_run_full_tests.py`:

- Backs up the protected files, runs the suite, restores them in a `finally` block, and compares hashes.
- The tenth file, `data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet`, is in its list, and was not run in that state before today. **It now has been.**

**One further change, disclosed:** I added an optional output folder, so this run's evidence wouldn't overwrite the previous run's. Behavior is otherwise unchanged. The edit came before the hash snapshot and this run.

## 2. Test run

| Item | Result |
|---|---|
| Command | `.venv/Scripts/python.exe -I src/phase3/step3_qa_run_full_tests.py reports/phase_03/step_04/audit_4_1/evidence` |
| Tests run | **337** |
| Result | **All passed**, exit code 0, 502 seconds |
| Failures or errors | 0 |

No unprotected command was used. Running the suite does rewrite the protected files while tests are in progress; they're restored at the end.

## 3. Verification

| Check | Result |
|---|---|
| 10 protected files, hash before vs after | Unchanged |
| 10 protected files vs the `FB69.rar` backup of 3 November, extracted fresh to the scratchpad | **All 10 byte-identical** |
| Frozen FotMob v3.1 | 38 of 38 hashes valid |
| 411 watched files, before vs after | **0 changed, 0 removed** |
| Added during the run | 2: `step4_1_audit.py` and `step4_1_followups.py`, which I wrote while it ran |
| Scan of the whole project for files modified today, outside this audit's folder | Only the 4 scripts from this audit |

**Watched folders:** `data/phase_03`, `data/transfermarkt`, the v3.1 release, `data/staging`, `reports/phase_03`, `reports/final_acceptance_fix`, `reports/phase_02b1_remediation`, `data/phase_02b1/remediation`, `configs`, `src`, `tests`.

## 4. Remaining weaknesses

- **Plain `unittest discover` is still unsafe.** The legacy tests aren't fixed, because that would mean changing Phase 2 test code. The warning is in `step_02/ENVIRONMENT_SETUP.md`.
- **The repo's own `full_test_runner.py` protects only 9 of the 10 files,** and also overwrites its historical log. I did not change it, because it's Phase 2 code. Please avoid it.
- **A killed run would leave the files in their rewritten state.** Today's run finished normally. Past rewrites produced identical bytes, but that can't be guaranteed.
- **Modification times** on the 10 files still read 2026-11-04 from the earlier incident. Content is what's verified.
