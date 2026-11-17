"""Step 4.1: hash everything a test run must not change, and compare protected files to the 3 November backup.

Usage:
  python -I src/phase3/step4_1_test_safety.py snapshot <out.json>
  python -I src/phase3/step4_1_test_safety.py verify <before.json> <extract_dir> <out.json>
<extract_dir> holds the 10 protected files extracted from FB69.rar, keyed by file name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.phase3.step3_qa_run_full_tests import MUTABLE  # noqa: E402
from src.phase3.tm_common import ROOT, file_hash, verify_fotmob_unchanged, write_json  # noqa: E402

WATCHED = ["data/phase_03", "data/transfermarkt", "data/releases/fotmob_epl_2019_2025_v3_1", "data/releases/fb69_player_season_integrated_v1", "data/staging", "reports/phase_03", "reports/final_acceptance_fix", "reports/phase_02b1_remediation", "data/phase_02b1/remediation", "configs", "src", "tests"]
EXCLUDED_PARTS = ("__pycache__", "audit_4_1", "step_03_qa/evidence/full_repository_test_run", "step_05/evidence/full_repository_test_run", "step_05/evidence/test_safety_")


def snapshot() -> dict:
    hashes = {}
    for folder in WATCHED:
        for path in sorted((ROOT / folder).rglob("*")):
            rel = path.relative_to(ROOT).as_posix()
            if path.is_file() and not any(part in rel for part in EXCLUDED_PARTS):
                hashes[rel] = file_hash(path)
    return hashes


def main() -> None:
    if sys.argv[1] == "snapshot":
        hashes = snapshot()
        write_json(Path(sys.argv[2]), {"files": len(hashes), "sha256": hashes})
        print("snapshot files", len(hashes))
        return
    before = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["sha256"]
    extract = Path(sys.argv[3])
    after = snapshot()
    protected = {}
    for path in MUTABLE:
        backups = list(extract.rglob(path.name))
        protected[path.relative_to(ROOT).as_posix()] = file_hash(path) == file_hash(backups[0]) if len(backups) == 1 else f"backup copies found: {len(backups)}"
    report = {
        "files_compared": len(before), "changed": sorted(k for k in before if k in after and before[k] != after[k]), "removed": sorted(set(before) - set(after)), "added": sorted(set(after) - set(before)),
        "protected_file_count": len(MUTABLE), "protected_byte_identical_to_backup": protected, "all_protected_identical": all(v is True for v in protected.values()), "fotmob_release": verify_fotmob_unchanged(),
    }
    write_json(Path(sys.argv[4]), report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
