"""Run the whole repository test suite without disturbing historical files.

Plain `unittest discover` makes legacy tests rewrite 10 Phase 2 files. This wrapper backs them up first, restores
them afterwards and verifies their hashes. It logs to reports/phase_03, because src.collection.full_test_runner
would overwrite the historical log in reports/final_acceptance_fix.

Usage: python -I src/phase3/step3_qa_run_full_tests.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.phase3.tm_common import ROOT, file_hash, verify_fotmob_unchanged, write_json  # noqa: E402

EVIDENCE = ROOT / "reports/phase_03/step_03_qa/evidence"
MUTABLE = [ROOT / "data/phase_02b1/remediation" / n for n in ("player_match_appearances_provisional.parquet", "complete_player_season_classification_v3.parquet", "confirmed_appeared_player_seasons_v3.parquet", "unverified_player_seasons_v3.parquet", "non_appeared_player_seasons_v3.parquet", "substitution_evidence_registry.parquet")] + [
    ROOT / "reports/phase_02b1_remediation" / n for n in ("appearance_resolution_audit.csv", "appearance_coverage_v3.csv", "population_reconciliation_v3.csv")] + [
    ROOT / "data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet"]  # also rewritten; missing from the repo's own runner


def main() -> int:
    before = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in MUTABLE}
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="fb69_full_test_backup_") as folder:
        for index, path in enumerate(MUTABLE):
            shutil.copy2(path, Path(folder) / str(index))
        try:
            result = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
        finally:
            for index, path in enumerate(MUTABLE):
                shutil.copy2(Path(folder) / str(index), path)
    after = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in MUTABLE}
    tail = result.stderr[-6000:]
    ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", result.stderr)
    failed = re.search(r"FAILED \(([^)]*)\)", result.stderr)
    report = {
        "command": "python -W ignore -m unittest discover -s tests -t .", "started_utc": started, "ended_utc": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode,
        "tests_run": int(ran.group(1)) if ran else None, "seconds": float(ran.group(2)) if ran else None, "failed_summary": failed.group(1) if failed else None, "ok": bool(re.search(r"^OK", result.stderr, re.M)),
        "failing_tests": re.findall(r"^(?:FAIL|ERROR): (.+)$", result.stderr, re.M), "mutable_files_unchanged": before == after, "changed_mutable_files": [k for k in before if before[k] != after[k]], "fotmob_release": verify_fotmob_unchanged(),
    }
    # An optional folder keeps each run's evidence, so a later run can't overwrite an earlier one.
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "full_repository_test_run.json", report)
    (output / "full_repository_test_run.log").write_text(f"STDOUT:\n{result.stdout[-4000:]}\nSTDERR (last part):\n{tail}", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
