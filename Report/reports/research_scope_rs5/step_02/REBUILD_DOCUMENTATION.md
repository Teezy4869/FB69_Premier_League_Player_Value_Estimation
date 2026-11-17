# rs5 Step 2: Rebuild Documentation

## Environment

`D:\PTIT\Hoc_may\FB69\.venv314` (Python 3.14.6): duckdb 2.0.0, pyarrow 24.0.0, pandas 3.1.0, PyYAML 6.0.3, RapidFuzz 3.14.6, numpy 2.5.4. These are the Phase 3 frozen versions (`reports/phase_03/step_05/requirements_freeze.txt`).

## Commands (from the repository root)

```powershell
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\build_fotmob_rs5.py
.venv314\Scripts\python.exe -I -X utf8 src\research_scope\build_targets_rs5.py
.venv314\Scripts\python.exe -W ignore -m unittest discover -s tests\research_scope -t .
.venv314\Scripts\python.exe -I -X utf8 src\phase3\step3_qa_run_full_tests.py <evidence_dir>
```

Order matters: the target reads the FotMob rs5 release and verifies its manifest first.

## Guarantees

- **Inputs are verified first:** FotMob v3.1 (38 hashes), then the rs5 manifest.
- **Build in a temporary folder, validate, then promote.** A failed check leaves no partial output.
- **No overwrite:** a re-run compares content hashes. Identical content means no change; different content means the build stops (exit 2). A new rule or input needs a new version name.
- **Deterministic:** both builders were re-run and reported identical content. Manifests record a generation time, so they're excluded from the comparison.

## Releases

| Version | Location | Records | Manifest |
|---|---|---|---|
| `fotmob_epl_2020_2025_rs5_v1` | `data/releases/fotmob_epl_2020_2025_rs5_v1` | 2,747 Confirmed player-seasons; 16 tables; 37 files | `metadata/release_manifest.json` |
| `target_rs5_v1__matching_v2_1` | `data/research_rs5/targets/target_rs5_v1__matching_v2_1` | 2,747 targets; temporal and audit evidence | `target_manifest.json` |

Dictionaries: `metadata/data_dictionary_rs5.csv` (every table and column), `manifests/metric_dictionary_rs5.csv` (53 metrics, with rs5 season counts), `target_data_dictionary.csv`.

Each manifest records: version, scope id and scope-config SHA-256, seasons, source references and hashes, code hashes, environment, row counts (by season for FotMob), output hashes, and validation results.

## Not done here (by instruction)

No crawling. No entity resolution change. No integration.
