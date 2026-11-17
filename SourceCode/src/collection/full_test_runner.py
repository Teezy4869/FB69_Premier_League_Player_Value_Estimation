"""Capture an actual full unittest run while preserving legacy Step 07 artifacts."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas
import pyarrow
import requests
import yaml

from src.collection.collection_config import ROOT


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(root: Path = ROOT) -> dict:
    report = root / "reports/final_acceptance_fix"
    report.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    mutable = [
        root / "data/phase_02b1/remediation" / n for n in (
            "player_match_appearances_provisional.parquet", "complete_player_season_classification_v3.parquet",
            "confirmed_appeared_player_seasons_v3.parquet", "unverified_player_seasons_v3.parquet",
            "non_appeared_player_seasons_v3.parquet", "substitution_evidence_registry.parquet")
    ] + [root / "reports/phase_02b1_remediation" / n for n in (
        "appearance_resolution_audit.csv", "appearance_coverage_v3.csv", "population_reconciliation_v3.csv")]
    started = utc_now()
    with tempfile.TemporaryDirectory(prefix="fb69_full_test_backup_") as tmp:
        backup = Path(tmp)
        for i, path in enumerate(mutable):
            if path.exists():
                shutil.copy2(path, backup / str(i))
        try:
            result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
        finally:
            for i, path in enumerate(mutable):
                saved = backup / str(i)
                if saved.exists():
                    shutil.copy2(saved, path)
    ended = utc_now()
    log = f"COMMAND: {' '.join(command)}\nPYTHON_EXECUTABLE: {sys.executable}\nSTARTED_UTC: {started}\nENDED_UTC: {ended}\nEXIT_CODE: {result.returncode}\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    (report / "full_test_execution.log").write_text(log, encoding="utf-8")
    match = re.search(r"Ran (\d+) tests? in", result.stderr)
    discovered = int(match.group(1)) if match else None
    failure_section = re.search(r"FAILED \(([^)]*)\)", result.stderr)
    failures = int(re.search(r"failures=(\d+)", failure_section.group(1)).group(1)) if failure_section and "failures=" in failure_section.group(1) else 0
    errors = int(re.search(r"errors=(\d+)", failure_section.group(1)).group(1)) if failure_section and "errors=" in failure_section.group(1) else 0
    skipped_match = re.search(r"skipped=(\d+)", result.stderr)
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    info = {"command": " ".join(command), "python_executable": sys.executable,
            "python_version": sys.version, "dependencies": {"pyarrow": pyarrow.__version__,
            "pandas": pandas.__version__, "requests": requests.__version__,
            "pyyaml": yaml.__version__}, "started_utc": started, "ended_utc": ended,
            "discovered_tests": discovered, "executed_tests": discovered,
            "passed": discovered - failures - errors - skipped if discovered is not None else None,
            "failed": failures, "errored": errors, "skipped": skipped,
            "exit_code": result.returncode,
            "log_path": "reports/final_acceptance_fix/full_test_execution.log"}
    (report / "test_environment_report.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
