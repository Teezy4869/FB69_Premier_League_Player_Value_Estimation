# Repository Inventory (Phase 3, Step 1)

Inspected 2026-11-04. Read-only, apart from the Step 1 files listed at the end.

## Root and version control

| Item | Finding |
|---|---|
| Project root | `F:\PTIT\Hoc_may\FB69` |
| Git | **Not a git repository** (`git rev-parse` fails). There is no status, history or commit ID. Outputs can only record a null commit. |
| Size | 16,199 files before Step 1, about 1.15 GB. Mostly raw FotMob JSON (15,332 files, 809 MB). |
| Moved paths | The v3.1 reproduction guide and manifest reference `D:\PTIT\Hoc_may\FB69`; the project is now on `F:`. Paths inside the release are relative, and all 1,343 Confirmed profile raw files resolve. |
| Free disk on F: | About 81 GB |

## Layout

| Path | Contents | Note for Phase 3 |
|---|---|---|
| `CLAUDE.md` | Project guide | Authoritative |
| `README.md` | Phase 1 audit instructions | Does not cover later phases |
| `configs/` | 7 JSON and YAML configs | Convention to reuse |
| `src/audit/`, `src/collection/` | Phase 1 and 2 code, 87 `.py` files including tests | `release_manifest.py` is reusable |
| `tests/audit/`, `tests/collection/` | `unittest` suites | Runnable under pytest as well |
| `data/releases/` | `fotmob_epl_2019_2025_{v1,v2,v3,v3_1}` | **v3_1 is the input** |
| `data/staging/` | `fotmob_v3_1_candidate_y7xem2iy`, `fotmob_epl_2019_2025_v3_1_provisional` | Build intermediates. Do not use as inputs. |
| `data/phase_02b0/`, `data/phase_02b1/` | Raw captures, manifests, quarantine | Lineage targets |
| `reports/phase_01/` to `phase_02b1_remediation/`, `final_acceptance_fix/` | Prior reports | Convention: `reports/phase_XX/` |
| `logs/` | Request logs | |

`CLAUDE.md` suggests `data/fotmob/releases/v3_1`. The real path is `data/releases/fotmob_epl_2019_2025_v3_1`. I did not restructure anything, and Phase 3 should use the real path.

## Conventions worth keeping

- Versioned, immutable release folders with `metadata/release_manifest.json` holding SHA-256 hashes and row counts.
- Identifiers stored as strings; explicit status vocabularies; null is never zero.
- A candidate is validated before promotion, and an existing different release is never overwritten.
- Reports live in `reports/phase_XX`.

## Python environment

| Item | Finding |
|---|---|
| Interpreter | Global Python 3.13.13; no project virtual environment |
| Global packages found | `pandas 3.0.5`, `numpy 2.5.2`, `pytest 9.1.1` |
| Missing from global Python | `pyarrow`, `duckdb`, `pyyaml`, `requests`, `rapidfuzz`, although `requirements.txt` lists the first, third and fourth |
| `requirements.txt` | `requests`, `pandas`, `PyYAML`, `pyarrow>=17,<25`; no `duckdb` |
| Used in Step 1 | Throwaway venv in the session scratchpad: pyarrow 26.0.1, duckdb 2.0.0, pandas 3.1.0, plus pyyaml and requests |

**Environment caveat:** the scratch venv's pyarrow 26.0.1 is outside the repo's `<25` pin. Step 2 should create a project-local `.venv` that respects the pin and adds `duckdb`.

## Files added by Step 1

Nothing existing was modified. See `PHASE3_STEP1_REPORT.md` for the list.
