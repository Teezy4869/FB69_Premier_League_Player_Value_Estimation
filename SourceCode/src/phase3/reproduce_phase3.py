"""Rebuild every Phase 3 stage from frozen inputs in a temporary folder and compare with stored outputs.

Does not touch real outputs. The acquisition step isn't re-downloaded; the raw snapshot's hashes are checked instead.

Usage: python -I src/phase3/reproduce_phase3.py <report.json>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.entity_resolution import CONFIG_PATH, run  # noqa: E402
from src.phase3.integrate import RELEASE, build as build_integration  # noqa: E402
from src.phase3.normalize_tm import build as build_normalized  # noqa: E402
from src.phase3.season_targets import OUTPUT as TARGET_OUTPUT, SCHEMA, build as build_targets  # noqa: E402
from src.phase3.tm_common import ROOT, file_hash, verify_fotmob_unchanged  # noqa: E402

SNAPSHOT = ROOT / "data/transfermarkt/source/tm_r2_20260905"
METADATA = ROOT / "data/transfermarkt/metadata/tm_r2_20260905"
RUN_DIR = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none"
AUDIT = ROOT / "reports/phase_03/step_04/audit_4_1/evidence"
QA = ROOT / "reports/phase_03/step_03_qa/evidence"


def compare(report: list, stage: str, name: str, fresh: Path, stored: Path) -> None:
    same = file_hash(fresh) == file_hash(stored)
    report.append({"stage": stage, "output": name, "identical": same})
    print(stage, name, "identical" if same else "DIFFERENT", flush=True)


def script(name: str, *args: str) -> None:
    subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "src/phase3" / name), *args], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def main() -> int:
    report_path = Path(sys.argv[1])
    report: list = []
    fotmob = verify_fotmob_unchanged()
    manifest = json.loads((METADATA / "source_manifest.json").read_text(encoding="utf-8"))
    raw_ok = all(file_hash(SNAPSHOT / f["file"]) == f["sha256"] for f in manifest["files"])
    report.append({"stage": "1 raw snapshot", "output": "7 files, hash check", "identical": raw_ok})
    with tempfile.TemporaryDirectory(prefix="fb69_reproduce_") as folder:
        temp = Path(folder)
        normalized = build_normalized(SNAPSHOT, temp / "normalized")
        stored = json.loads((METADATA / "normalization_manifest.json").read_text(encoding="utf-8"))["output_sha256"]
        report.append({"stage": "2 normalization", "output": f"{len(stored)} tables", "identical": normalized["output_sha256"] == stored})
        print("normalization", normalized["output_sha256"] == stored, flush=True)
        evidence = temp / "qa"
        script("step3_qa_validate.py", str(evidence))
        compare(report, "3 identity validation", "auto_match_validation_all_1299.csv", evidence / "auto_match_validation_all_1299.csv", QA / "auto_match_validation_all_1299.csv")
        adjudications = temp / "automated_adjudications.csv"
        script("step3_qa_adjudicate.py", str(evidence), str(adjudications))
        compare(report, "3 adjudication", "automated_adjudications.csv", adjudications, ROOT / "data/phase_03/review/automated_adjudications.csv")
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        fresh = Path(run(config, temp / "er", temp / "review", adjudications)["run_dir"])
        for name in ("player_crosswalk.parquet", "matching_candidates.parquet", "unresolved_identities.csv"):
            compare(report, "3 entity resolution", name, fresh / name, RUN_DIR / name)
        rows, _ = build_targets()
        target_path = temp / "player_season_target.parquet"
        pq.write_table(pa.table({f.name: pa.array([r[f.name] for r in rows], f.type) for f in SCHEMA}), target_path, compression="zstd")
        compare(report, "4 targets", "player_season_target.parquet", target_path, TARGET_OUTPUT / "player_season_target.parquet")
        audit = temp / "audit"
        script("step4_1_audit.py", str(audit))
        script("step4_1_followups.py", str(audit))
        for name in ("temporal_alignment_by_player_season.parquet", "target_quality_flags.parquet"):
            compare(report, "4.1 audit", name, audit / name, AUDIT / name)
        integrated = temp / "integrated"
        record = build_integration(integrated)
        for name in record["output_sha256"]:
            compare(report, "5 integration", name, integrated / name, RELEASE / name)
    failed = [r for r in report if not r["identical"]]
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "fotmob_preflight": fotmob, "stages_checked": len(report), "all_identical": not failed, "failed": failed, "results": report}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print("all identical" if not failed else f"DIFFERENCES: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
