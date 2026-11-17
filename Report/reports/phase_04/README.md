# FB69 Phase 4: Exploratory Data Analysis (report index)

Official dataset: `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet` (SHA-256 `4d94ec73…eedd`). Scope `rs5_v1` (five seasons, 2020/21–2024/25). Primary observation interface: the Phase 4 section of `FB69_report.ipynb`.

| Step | Topic | Gate | Start here |
|---|---|---|---|
| 4.0 | Dataset acceptance and conditions | CONDITIONAL PASS | `step_00/PHASE4_00_ACCEPTANCE_REPORT.md` |
| 4.1 | Dataset profiling and structural EDA | PASS | `step_01/PHASE4_01_ACCEPTANCE_REPORT.md` |
| 4.2 | Target and univariate analysis | PASS | `step_02/PHASE4_02_ACCEPTANCE_REPORT.md` |
| 4.3 | Bivariate analysis | PASS | `step_03/PHASE4_03_ACCEPTANCE_REPORT.md` |
| 4.4 | Multivariate and group analysis | PASS | `step_04/PHASE4_04_ACCEPTANCE_REPORT.md` |
| 4.5 | Missingness, temporal and data reliability | PASS | `step_05/PHASE4_05_ACCEPTANCE_REPORT.md` |
| 4.6 | Feature assessment and modeling feasibility | PASS | `step_06/PHASE4_06_ACCEPTANCE_REPORT.md` |
| 4.7 | EDA synthesis and final acceptance | PASS (owner accepted 2026-11-09; assessed CONDITIONAL PASS before acceptance) | `step_07/PHASE4_FINAL_ACCEPTANCE_REPORT.md` |
| 5.0 | Modeling design and protocol (design only) | see Phase 5 | `../phase_05/step_00/PHASE5_00_ACCEPTANCE_REPORT.md` |

Phase 4 overall: ACCEPTED (G4.1-G4.6 OWNER_ACCEPTED). Owner decisions: `step_07/PHASE4_OWNER_DECISION_REGISTER.md`.

Conditions: `step_00/phase4_condition_register.yaml` (rendered to `PHASE4_CONDITION_REGISTER.md`); action view: `step_07/PHASE4_ISSUE_TRACKER.md`. Checklist: `step_00/PHASE4_ENTRY_CHECKLIST.md`.

## Deliverable map

| Deliverable | File |
|---|---|
| Dataset profiling report | `step_01/DATASET_PROFILING_REPORT.md` (+ `POPULATION_ANALYSIS.md`) |
| Data quality report | `step_01/STRUCTURAL_DATA_QUALITY_REPORT.md` |
| Target analysis report | `step_02/TARGET_ANALYSIS_REPORT.md` (+ `UNIVARIATE_FEATURE_ANALYSIS_REPORT.md`) |
| Feature relationship report | `step_03/BIVARIATE_ANALYSIS_REPORT.md` (+ association and redundancy summaries) |
| Multivariate analysis report | `step_04/MULTIVARIATE_ANALYSIS_REPORT.md` (+ position, season, group reports) |
| Missingness report | `step_05/MISSINGNESS_ANALYSIS_REPORT.md` |
| Temporal sensitivity report | `step_05/TEMPORAL_RELIABILITY_REPORT.md` (+ identity and metric reliability reports) |
| Feature assessment matrix | `step_06/FEATURE_ASSESSMENT_MATRIX.md` (+ `evidence/feature_assessment_matrix.csv`) |
| Modeling feasibility report | `step_06/MODELING_FEASIBILITY_REPORT.md` (+ split assessment, risk register, candidate groups) |
| Phase 4 issue tracker | `step_07/PHASE4_ISSUE_TRACKER.md` (source: the condition register YAML) |
| Phase 4 final acceptance report | `step_07/PHASE4_FINAL_ACCEPTANCE_REPORT.md` |

## Reproduce (repository root)

```powershell
# evidence (pinned packages). 4.1/4.2 originally ran under .venv (Python 3.13.13, ENV-P4-01);
# 4.3-4.7 ran under .venv314 (Python 3.14.6, identical freeze), because .venv cannot start on the current machine (ENV-P4-03).
.venv314\Scripts\python.exe -I -X utf8 src\phase4\profiling.py    reports\phase_04\step_01\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\univariate.py   reports\phase_04\step_02\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\bivariate.py    reports\phase_04\step_03\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\multivariate.py reports\phase_04\step_04\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\reliability.py  reports\phase_04\step_05\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\feasibility.py  reports\phase_04\step_06\evidence
.venv314\Scripts\python.exe -I -X utf8 src\phase4\synthesis.py    reports\phase_04\step_07\evidence   # after executing the notebook
# tests: Phase 4 alone, or the protected full suite (never plain discover on tests/, ISS-18)
.venv314\Scripts\python.exe -m unittest discover -s tests\phase4 -t .
.venv314\Scripts\python.exe -I src\phase3\step3_qa_run_full_tests.py <evidence_dir>
```

The notebook needs matplotlib and a Jupyter kernel, which neither virtual environment has. Phase 4.3–4.7 executed it in a fresh kernel (nbclient) with the base Python 3.14.6 and `.venv314\Lib\site-packages` first on `PYTHONPATH` (ENV-P4-03); 4.1/4.2 used the same approach with Python 3.13.13 (ENV-P4-01).
