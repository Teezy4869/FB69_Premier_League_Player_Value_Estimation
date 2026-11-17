# Environment Setup (Phase 3)

Windows, from the project root, with Git Bash. Nothing is installed globally. Exact versions used are in `requirements_freeze.txt`.

## Create the environment

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

`requirements.txt` gained one line for Phase 3, `duckdb>=1.1,<3`. Existing constraints were not changed. `pyarrow` resolved to 24.0.0, inside the existing `<25` pin, and the Step 1 scratch environment's out-of-range 26.0.1 is no longer used.

## Rebuild Step 2

```bash
.venv/Scripts/python.exe -I src/phase3/acquire_tm.py          # stops if the snapshot exists
.venv/Scripts/python.exe -I src/phase3/inspect_tm_schema.py
.venv/Scripts/python.exe -I src/phase3/normalize_tm.py        # stops rather than replace different output
.venv/Scripts/python.exe -I src/phase3/tm_quality.py
```

`-I` keeps Python from importing anything from the current or script folder while it reads downloaded data.

## Rebuild Step 3

`requirements.txt` gained `rapidfuzz>=3,<4` for Step 3. Exact versions are in `reports/phase_03/step_03/requirements_freeze.txt`.

```bash
.venv/Scripts/python.exe -I src/phase3/entity_resolution.py   # keeps human decisions; stops rather than replace different output
.venv/Scripts/python.exe -I src/phase3/evaluate_matching.py data/phase_03/entity_resolution/matching_v1__reviews_none/player_crosswalk.parquet
```

## Run the tests

**Do not run plain `unittest discover -s tests` for the whole repository.** Legacy tests rewrite 10 Phase 2 files. For the full suite, use `.venv/Scripts/python.exe -I src/phase3/step3_qa_run_full_tests.py`, which protects them. The commands below are safe.

```bash
.venv/Scripts/python.exe -I -m unittest discover -s tests/phase3 -t . -v
.venv/Scripts/python.exe -m unittest tests.collection.test_final_acceptance_release tests.collection.test_final_acceptance_fix
```
