"""Prompt 05: rebuild the whole rs5 chain in a temporary folder and compare it byte-for-byte with the stored outputs.

Each stage reads the *temporary* output of the stage before it, so the comparison covers the chain end to end:
  FotMob rs5 -> target (historical identity) -> crosswalk + validation labels -> target (rs5 identity) -> integration -> audit.
Real outputs are never touched. Files that embed a generation timestamp (manifests) are compared with that field removed.
It also re-checks every rs5 manifest against the current files, and the historical inputs.

Usage: python -I src/research_scope/reproduce_rs5.py <report.json>
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.phase3 import season_targets  # noqa: E402
from src.phase3.tm_common import file_hash, verify_fotmob_unchanged  # noqa: E402
from src.research_scope import audit_rs5, build_fotmob_rs5, build_targets_rs5, entity_resolution_rs5, integrate_rs5  # noqa: E402
from src.research_scope.build_targets_rs5 import patched  # noqa: E402
from src.research_scope.scope import ROOT, load_scope  # noqa: E402

TARGETS = ROOT / "data/research_rs5/targets"
TM_SOURCE = ROOT / "data/transfermarkt/metadata/tm_r2_20260905/source_manifest.json"
TIMESTAMP_KEYS = ("generated_at_utc", "created_at_utc", "imported_at_utc")


def strip_times(value):
    if isinstance(value, dict):
        return {k: strip_times(v) for k, v in value.items() if k not in TIMESTAMP_KEYS}
    if isinstance(value, list):
        return [strip_times(v) for v in value]
    return value


def compare_dirs(report: list, stage: str, fresh: Path, stored: Path, skip: tuple[str, ...] = ()) -> None:
    files = sorted({p.relative_to(stored).as_posix() for p in stored.rglob("*") if p.is_file()} | {p.relative_to(fresh).as_posix() for p in fresh.rglob("*") if p.is_file()})
    for rel in files:
        if any(rel.endswith(s) for s in skip):
            continue
        a, b = fresh / rel, stored / rel
        if not a.exists() or not b.exists():
            report.append({"stage": stage, "file": rel, "identical": False, "note": "missing in " + ("rebuild" if not a.exists() else "stored")})
            continue
        if rel.endswith(".json"):
            same = strip_times(json.loads(a.read_text(encoding="utf-8"))) == strip_times(json.loads(b.read_text(encoding="utf-8")))
            report.append({"stage": stage, "file": rel, "identical": same, "comparison": "JSON without timestamps"})
        else:
            same = file_hash(a) == file_hash(b)
            entry = {"stage": stage, "file": rel, "identical": same, "comparison": "bytes"}
            if not same and rel.endswith(".csv"):
                # Review CSVs carry an import timestamp column; compare with it removed.
                read = lambda p: [{k: v for k, v in r.items() if k not in TIMESTAMP_KEYS} for r in csv.DictReader(p.open(encoding="utf-8-sig", newline=""))]  # noqa: E731
                entry.update(identical=read(a) == read(b), comparison="CSV rows without timestamp columns")
            report.append(entry)


def manifest_checks() -> list[dict]:
    """Every rs5 manifest's output hashes must match the files; input hashes must match unless the input is a later rs5 code file."""
    checks = []
    m = json.loads((build_fotmob_rs5.RELEASE / "metadata/release_manifest.json").read_text(encoding="utf-8"))
    bad = [f["path"] for f in m["files"] if file_hash(build_fotmob_rs5.RELEASE / f["path"]) != f["sha256"]]
    checks.append({"manifest": "fotmob_epl_2020_2025_rs5_v1/metadata/release_manifest.json", "outputs_ok": not bad, "bad": bad,
                   "source_manifest_ok": m["source"]["release_manifest_sha256"] == file_hash(build_fotmob_rs5.SOURCE / "metadata/release_manifest.json")})
    for folder in sorted(TARGETS.glob("target_rs5_v1__*")):
        t = json.loads((folder / "target_manifest.json").read_text(encoding="utf-8"))
        checks.append({"manifest": f"{folder.name}/target_manifest.json", "outputs_ok": all(file_hash(folder / n) == s for n, s in t["output_sha256"].items()),
                       "inputs_ok": all(file_hash(ROOT / p) == s for p, s in t["input_sha256"].items()),
                       "code_hash_drift": sorted(p for p, s in t["code_sha256"].items() if file_hash(ROOT / p) != s)})
    c = json.loads((entity_resolution_rs5.OUT / "crosswalk_rs5_manifest.json").read_text(encoding="utf-8"))
    checks.append({"manifest": "entity_resolution/crosswalk_rs5_manifest.json", "outputs_ok": all(file_hash(entity_resolution_rs5.OUT / p) == s for p, s in c["output_sha256"].items()),
                   "code_hash_drift": sorted(p for p, s in c["code_sha256"].items() if file_hash(ROOT / p) != s)})
    i = json.loads((integrate_rs5.RELEASE / "integration_manifest.json").read_text(encoding="utf-8"))
    checks.append({"manifest": "fb69_player_season_integrated_rs5_v1/integration_manifest.json", "outputs_ok": all(file_hash(integrate_rs5.RELEASE / n) == s for n, s in i["output_sha256"].items()),
                   "inputs_ok": all(file_hash(ROOT / p) == s for p, s in i["input_sha256"].items()), "code_hash_drift": sorted(p for p, s in i["code_sha256"].items() if file_hash(ROOT / p) != s)})
    return checks


def build_target(temp: Path, fotmob: Path, crosswalk: Path, matching: str, validation: Path) -> Path:
    out = temp / f"targets/target_rs5_v1__{matching}"
    out.mkdir(parents=True)
    with patched(build_targets_rs5, FOTMOB_RS5=fotmob):
        rows, _ = build_targets_rs5.build_rows(crosswalk, matching, validation)
        target = out / "player_season_target.parquet"
        build_targets_rs5.write_table(rows, season_targets.SCHEMA, target)
        conflicts = [r for r in rows if r["target_status"] == "AMBIGUOUS_VALUATION"]
        with (out / "same_date_valuation_conflicts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["canonical_player_id", "season", "transfermarkt_player_id", "selected_valuation_date", "conflicting_record_references"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(conflicts)
        build_targets_rs5.write_dictionary(out / "target_data_dictionary.csv")
        build_targets_rs5.temporal_evidence(target, crosswalk, out)
        build_targets_rs5.previous_valuations(target, out)
    return out


def main() -> int:
    report_path = Path(sys.argv[1])
    scope = load_scope()
    report: list = []
    fotmob_v31 = verify_fotmob_unchanged()
    tm = json.loads(TM_SOURCE.read_text(encoding="utf-8"))
    tm_ok = all(file_hash(ROOT / "data/transfermarkt/source/tm_r2_20260905" / f["file"]) == f["sha256"] for f in tm["files"])
    # Inside the repository: the unchanged Phase 3 matcher records input paths relative to it. Removed afterwards.
    with tempfile.TemporaryDirectory(prefix="_reproduce_", dir=ROOT / "data/research_rs5") as folder:
        temp = Path(folder)
        # 1. FotMob rs5
        fm = temp / build_fotmob_rs5.VERSION  # the folder name is recorded in provenance columns
        log = build_fotmob_rs5.build(fm)
        build_fotmob_rs5.write_readme(fm, log)
        compare_dirs(report, "1 FotMob rs5", fm, build_fotmob_rs5.RELEASE, skip=("release_manifest.json",))
        # 2. Target on the historical player-level mapping (Step 2 version)
        t2 = build_target(temp, fm, build_targets_rs5.HISTORICAL_CROSSWALK, "matching_v2_1", season_targets.VALIDATION)
        compare_dirs(report, "2 target (matching_v2_1)", t2, TARGETS / "target_rs5_v1__matching_v2_1", skip=("target_manifest.json",))
        # 3. Crosswalk and validation labels from in-scope evidence
        er_out, er_review = temp / "entity_resolution", temp / "review"
        run_dir = er_out / f"{entity_resolution_rs5.MATCHING_VERSION}__reviews_none"
        validation = er_out / f"{entity_resolution_rs5.MATCHING_VERSION}_identity_validation.csv"
        with patched(entity_resolution_rs5, FOTMOB_RS5=fm, OUT=er_out, REVIEW=er_review, RUN_DIR=run_dir, VALIDATION_OUT=validation):
            ids = entity_resolution_rs5.universe()
            adjudication = er_review / "automated_adjudications_in_scope.csv"
            entity_resolution_rs5.scoped_adjudications(ids, adjudication)
            result = entity_resolution_rs5.run_matching(adjudication)
            labels = entity_resolution_rs5.validation_labels(result["crosswalk"])
            entity_resolution_rs5.write_rows(validation, labels)
            shutil.copy2(adjudication, run_dir / "review_snapshot" / adjudication.name)
        compare_dirs(report, "3 crosswalk", run_dir, entity_resolution_rs5.RUN_DIR, skip=("run_manifest.json",))
        compare_dirs(report, "3 review inputs", er_review, entity_resolution_rs5.REVIEW)
        report.append({"stage": "3 validation labels", "file": validation.name, "identical": file_hash(validation) == file_hash(entity_resolution_rs5.VALIDATION_OUT), "comparison": "bytes"})
        # 4. Target on the revalidated identity (used by integration)
        t3 = build_target(temp, fm, run_dir / "player_crosswalk.parquet", entity_resolution_rs5.MATCHING_VERSION, validation)
        compare_dirs(report, "4 target (matching_v2_1_rs5)", t3, TARGETS / "target_rs5_v1__matching_v2_1_rs5", skip=("target_manifest.json",))
        # 5. Integration
        integrated = temp / "integrated"
        with patched(integrate_rs5, FOTMOB_RS5=fm, CROSSWALK=run_dir / "player_crosswalk.parquet", VALIDATION_OUT=validation, TARGET=t3 / "player_season_target.parquet",
                     TEMPORAL=t3 / "temporal_alignment_by_player_season.parquet", PREVIOUS=t3 / "target_previous_valuation_audit.parquet"):
            record = integrate_rs5.build(integrated)
            integrate_rs5.write_data_dictionary(integrated)
        for name in (*record["output_sha256"], "data_dictionary.csv"):
            report.append({"stage": "5 integration", "file": name, "identical": file_hash(integrated / name) == file_hash(integrate_rs5.RELEASE / name), "comparison": "bytes"})
        # 6. Audit evidence, from the rebuilt dataset
        audit_out = temp / "audit"
        old_argv = sys.argv
        try:
            sys.argv = [old_argv[0], str(audit_out)]
            with patched(audit_rs5, DATASET=integrated / "player_season_integrated_rs5_v1.parquet", FOTMOB_RS5=fm):
                audit_rs5.main()
        finally:
            sys.argv = old_argv
        stored_audit = ROOT / "reports/research_scope_rs5/step_04/evidence"
        for p in sorted(audit_out.iterdir()):
            if p.name == "audit_summary.json":
                a, b = json.loads(p.read_text(encoding="utf-8")), json.loads((stored_audit / p.name).read_text(encoding="utf-8"))
                a.pop("dataset"), b.pop("dataset")
                report.append({"stage": "6 audit", "file": p.name, "identical": a == b, "comparison": "JSON without dataset path (temporary)"})
            else:
                report.append({"stage": "6 audit", "file": p.name, "identical": file_hash(p) == file_hash(stored_audit / p.name), "comparison": "bytes"})
    failed = [r for r in report if not r["identical"]]
    manifests = manifest_checks()
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "scope_id": scope.scope_id, "environment": {"python": sys.version.split()[0], "pyarrow": pa.__version__, "duckdb": __import__("duckdb").__version__},
              "historical_inputs": {"fotmob_v3_1": fotmob_v31, "transfermarkt_raw_7_files_hash_ok": tm_ok}, "files_compared": len(report), "all_identical": not failed, "failed": failed,
              "manifest_checks": manifests, "results": report}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"files compared {len(report)}; identical {len(report) - len(failed)}; failed {len(failed)}")
    for f in failed:
        print("DIFF", f)
    print(json.dumps(manifests, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
