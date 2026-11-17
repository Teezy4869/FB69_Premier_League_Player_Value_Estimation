# FB69 Research Scope Migration (rs5): Report Index

Five-season research scope (D9): 2020/21 to 2024/25; 2019/20 excluded. Objective A unchanged.

| Step | Gate | Verdict | Start here |
|---|---|---|---|
| 1. Baseline audit and scope migration | G1 | PASS | `step_01/G1_HANDOFF.md` |
| 2. FotMob and Transfermarkt rebuild | G2 | PASS | `step_02/G2_HANDOFF.md` |
| 3. Entity resolution and integration | G3 | CONDITIONAL PASS | `step_03/G3_HANDOFF.md` |
| 4. Quality, temporal and leakage audit | G4 | CONDITIONAL PASS | `step_04/G4_HANDOFF.md` |
| 5. Final acceptance and release | G5 | **CONDITIONAL PASS** | `step_05/FINAL_ACCEPTANCE_REPORT.md` |

Data contract: `DATA_CONTRACT_RS5.md`. Official dataset: `data/releases/fb69_player_season_integrated_rs5_v1/`.

## Rebuild (repository root, `.venv314`)

```powershell
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\build_fotmob_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\build_targets_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\entity_resolution_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\build_targets_rs5.py --crosswalk data\research_rs5\entity_resolution\matching_v2_1_rs5__reviews_none\player_crosswalk.parquet --matching-version matching_v2_1_rs5 --validation data\research_rs5\entity_resolution\matching_v2_1_rs5_identity_validation.csv
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\integrate_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\validate_rs5.py reports\research_scope_rs5\step_03\evidence\integration_validation.json
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\audit_rs5.py reports\research_scope_rs5\step_04\evidence
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\reproduce_rs5.py reports\research_scope_rs5\step_05\evidence\rs5_reproduction.json
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\finalize_release_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\phase3\step3_qa_run_full_tests.py <evidence_dir>
```

Every builder refuses to overwrite an existing version that has different content. Don't run plain `unittest discover`: it rewrites 10 Phase 2 files (ISS-18). Use the protected runner.
