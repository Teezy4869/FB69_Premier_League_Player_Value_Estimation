"""Prompt 05 Task D: finalize the official five-season research release.

Adds the release documentation next to the integrated dataset (which is not modified), and writes
`release_manifest.json` with every file's SHA-256 and row count. Refuses to run unless the integration manifest still
matches the dataset and the end-to-end reproduction report says all files were identical.

Usage: python -I src/research_scope/finalize_release_rs5.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402

from src.phase3.tm_common import file_hash  # noqa: E402
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.integrate_rs5 import DATASET_VERSION, RELEASE  # noqa: E402
from src.research_scope.scope import ROOT, SCOPE_PATH, load_scope  # noqa: E402

REPORTS = ROOT / "reports/research_scope_rs5"
REPRODUCTION = REPORTS / "step_05/evidence/rs5_reproduction.json"
INTEGRATION_CHECKS = REPORTS / "step_03/evidence/integration_validation.json"
AUDIT_SUMMARY = REPORTS / "step_04/evidence/audit_summary.json"
LAST_FULL_RUN = REPORTS / "step_04/evidence/full_test_run/full_repository_test_run.json"
DOCS = {"DATA_CONTRACT_RS5.md": REPORTS / "DATA_CONTRACT_RS5.md", "DATA_QUALITY_REPORT.md": REPORTS / "step_04/DATA_QUALITY_REPORT.md", "MISSINGNESS_REPORT.md": REPORTS / "step_04/MISSINGNESS_REPORT.md",
        "TEMPORAL_ALIGNMENT_REPORT.md": REPORTS / "step_04/TEMPORAL_ALIGNMENT_REPORT.md", "LEAKAGE_AUDIT.md": REPORTS / "step_04/LEAKAGE_AUDIT.md", "FEATURE_RELIABILITY_ASSESSMENT.md": REPORTS / "step_04/FEATURE_RELIABILITY_ASSESSMENT.md",
        "ISSUE_TRACKER.md": REPORTS / "step_04/ISSUE_TRACKER.md", "PHASE4_CONDITIONS.md": REPORTS / "step_04/PHASE4_CONDITIONS.md", "ENTITY_RESOLUTION_REPORT.md": REPORTS / "step_03/ENTITY_RESOLUTION_REPORT.md",
        "TARGET_CONSTRUCTION_REPORT.md": REPORTS / "step_02/TARGET_CONSTRUCTION_REPORT.md", "leakage_audit.csv": REPORTS / "step_04/evidence/leakage_audit.csv", "feature_reliability.csv": REPORTS / "step_04/evidence/feature_reliability.csv"}


def main() -> int:
    scope = load_scope()
    integration = json.loads((RELEASE / "integration_manifest.json").read_text(encoding="utf-8"))
    if any(file_hash(RELEASE / n) != s for n, s in integration["output_sha256"].items()):
        raise RuntimeError("Integrated dataset no longer matches its integration manifest")
    reproduction = json.loads(REPRODUCTION.read_text(encoding="utf-8"))
    if not reproduction["all_identical"]:
        raise RuntimeError("End-to-end reproduction is not identical; release not finalized")
    checks = json.loads(INTEGRATION_CHECKS.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_SUMMARY.read_text(encoding="utf-8"))
    if audit["dataset_sha256"] != integration["output_sha256"][f"{DATASET_VERSION}.parquet"]:
        raise RuntimeError("Audit evidence is not for this dataset")
    tests = json.loads(LAST_FULL_RUN.read_text(encoding="utf-8"))
    docs = RELEASE / "docs"
    docs.mkdir(exist_ok=True)
    for name, src in DOCS.items():
        shutil.copy2(src, docs / name)
    shutil.copy2(SCOPE_PATH, RELEASE / "research_scope.yaml")
    stats = integration
    (RELEASE / "SCOPE_DECLARATION.md").write_text("\n".join([
        "# Research Scope Declaration", "",
        f"- **Scope id:** `{scope.scope_id}` (owner decision D9, 2026-11-07; supersedes D7).",
        f"- **Included seasons:** {', '.join(scope.labels)} (FotMob season ids {', '.join(scope.season_ids)}).",
        f"- **Excluded season:** {', '.join(scope.excluded_labels)}, permanently. No row of this release belongs to it. No season-keyed record of it was used: FotMob season data, or Transfermarkt games, appearances and club-seasons. It isn't available for EDA, feature work, training, validation, testing, evaluation, or sensitivity or comparative analysis.",
        "- **Player-level time series:** Transfermarkt valuations, transfers and profiles aren't season-partitioned. Each target reads only the latest valuation on or before its own in-scope cutoff. One usable target is dated 2019-05-23 (RD-01).",
        "- **Identity decisions:** re-derived from in-scope evidence. 36 historical automated adjudications are kept. They were first decided on six-season evidence; 29 are re-confirmed by the validator on in-scope evidence, 5 rest on external biographies, and 2 are inconclusive in scope (RD-02).",
        "- **Research objective:** A, end-of-season estimation (D6). Unchanged.",
        "- **Cutoff:** official season end (`configs/phase_03_seasons.yaml`): " + ", ".join(f"{s.season} {s.season_end_date}" for s in scope.seasons) + ".",
        f"- **Target rule:** `{scope.selection_rule_version}` (D4); staleness ({scope.stale_label_days} days) is a label, not an exclusion.",
        "- **Snapshot of the scope configuration:** `research_scope.yaml` (copied from `configs/research_scope.yaml`).", ""]), encoding="utf-8")
    (RELEASE / "PROVENANCE.md").write_text("\n".join([
        "# Provenance", "",
        "| Layer | Artifact | Integrity |", "|---|---|---|",
        "| FotMob raw | `data/phase_02b0`, `data/phase_02b1/raw`, `data/pilot/raw` (saved API responses, collected 2026-11) | Referenced by `raw_path`; never copied or modified |",
        f"| FotMob frozen | `data/releases/fotmob_epl_2019_2025_v3_1` | 38 file hashes verified (manifest `{integration['fotmob_v3_1_preflight']['manifest_sha256'][:12]}…`) |",
        f"| FotMob research | `data/releases/{FOTMOB_RS5.name}` (season filter of v3.1) | Manifest `{file_hash(FOTMOB_RS5 / 'metadata/release_manifest.json')[:12]}…` |",
        "| Transfermarkt raw | `data/transfermarkt/source/tm_r2_20260905` (dcaribou/transfermarkt-datasets, commit e44f186; D1) | 7 SHA-256 pins; CC0 declared by maintainer, upstream rights unverified (D2) |",
        "| Transfermarkt normalized | `data/transfermarkt/{staging,curated}/tm_r2_20260905` | Reused unchanged |",
        "| Crosswalk | `data/research_rs5/entity_resolution/matching_v2_1_rs5__reviews_none` | `crosswalk_rs5_manifest.json` |",
        "| Target | `data/research_rs5/targets/target_rs5_v1__matching_v2_1_rs5` | `target_manifest.json` |",
        f"| Integrated | `{DATASET_VERSION}.parquet` | `integration_manifest.json`, `release_manifest.json` |", "",
        "Code: `src/research_scope/` (rs5 builders), reusing frozen `src/phase3/` functions unchanged. No git (D5): every manifest records script SHA-256.",
        "Environment: `.venv314`, Python " + integration["environment"]["python"] + ", duckdb " + integration["environment"]["duckdb"] + ", pyarrow " + integration["environment"]["pyarrow"] + ".",
        "Rebuild: `python -I src/research_scope/reproduce_rs5.py <report.json>` rebuilds every stage in a temporary folder and compares bytes.", ""]), encoding="utf-8")
    summary = {"dataset_version": DATASET_VERSION, "scope_id": scope.scope_id, "integration_checks": {"passed": checks["passed"], "total": checks["total"], "failed": [c["check"] for c in checks["checks"] if c["status"] != "PASS"]},
               "statistics": checks["statistics"], "reproduction": {"files_compared": reproduction["files_compared"], "all_identical": reproduction["all_identical"], "report": REPRODUCTION.relative_to(ROOT).as_posix(),
                                                                    "manifest_checks": reproduction["manifest_checks"]},
               "audit": {k: audit[k] for k in ("leakage_classification", "candidate_leakage_classification", "reliability_status", "temporal_overall")},
               "tests_before_finalization": {"run": tests["tests_run"], "ok": tests["ok"], "failing": tests["failing_tests"], "evidence": LAST_FULL_RUN.relative_to(ROOT).as_posix(),
                                             "note": "The final run after finalization is recorded in reports/research_scope_rs5/step_05/evidence/final_test_run/"},
               "gates": {"G1": "PASS", "G2": "PASS", "G3": "CONDITIONAL_PASS", "G4": "CONDITIONAL_PASS"}}
    (RELEASE / "VALIDATION_SUMMARY.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    s = checks["statistics"]
    (RELEASE / "README.md").write_text("\n".join([
        f"# FB69 integrated research release `{DATASET_VERSION}`", "",
        f"Official five-season research dataset (scope `{scope.scope_id}`): {', '.join(scope.labels)}. **2019/20 is excluded.** Objective A, end-of-season estimation.", "",
        f"One row per player-season: {s['rows']:,} rows, {s['unique_players']:,} players, {s['columns']} columns. Usable targets {s['usable_targets']:,} ({s['integration_coverage_pct']}%); missing {s['missing_targets']} (each with a reason).", "",
        "| File | Content |", "|---|---|",
        f"| `{DATASET_VERSION}.parquet` | The dataset |", "| `player_team_season_evidence.parquet` | Club detail per player-season (multi-club rows stay one row in the dataset) |",
        "| `data_dictionary.csv` | Column, role, type, candidate-predictor flag |", "| `integration_manifest.json` | Inputs, joins, code and output hashes |",
        "| `release_manifest.json` | Every file in this release with SHA-256 |", "| `SCOPE_DECLARATION.md`, `research_scope.yaml` | Scope |", "| `PROVENANCE.md` | Source chain |",
        "| `VALIDATION_SUMMARY.json` | Integration checks, reproduction, audit, tests |", "| `docs/` | Data contract, quality, missingness, temporal, leakage, reliability, issues, Phase 4 conditions |", "",
        "**Read `docs/PHASE4_CONDITIONS.md` before any analysis.** Only `FEATURE_*` and `CONTEXT_FEATURE` columns are candidate predictors.", ""]), encoding="utf-8")
    con = duckdb.connect()
    files = []
    for path in sorted(RELEASE.rglob("*")):
        if path.is_file() and path.name != "release_manifest.json":
            entry = {"path": path.relative_to(RELEASE).as_posix(), "bytes": path.stat().st_size, "sha256": file_hash(path)}
            if path.suffix == ".parquet":
                entry["rows"] = con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0]
            files.append(entry)
    (RELEASE / "release_manifest.json").write_text(json.dumps({
        "release": DATASET_VERSION, "status": "OFFICIAL_RESEARCH_RELEASE (final verdict in reports/research_scope_rs5/step_05/FINAL_ACCEPTANCE_REPORT.md)", "scope_id": scope.scope_id,
        "seasons": list(scope.labels), "excluded_seasons": list(scope.excluded_labels), "research_objective": "A (D6)", "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_releases_preserved": ["data/releases/fb69_player_season_integrated_v1", "data/releases/fotmob_epl_2019_2025_v3_1"],
        "inventory_policy": "Every file is checksummed except this manifest.", "files": files}, indent=1) + "\n", encoding="utf-8")
    print(f"release finalized: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
