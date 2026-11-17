"""Protect historical artifacts: hash every repository file before the rs5 migration, and verify later.

Everything that existed before the migration is historical. The rs5 work may only ADD files under its own
output roots (NEW_OUTPUT_ROOTS). `verify` reports any historical file that changed or disappeared.

Usage:
  python -I src/research_scope/protect.py snapshot <out.json>
  python -I src/research_scope/protect.py verify <baseline.json> <out.json>
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".venv", ".venv314", "__pycache__"}
# Files the rs5 migration is allowed to create. Nothing outside these roots may be added or changed,
# except the two documented, backed-up edits listed in DOCUMENTED_EDITS.
RS5_OUTPUT_ROOTS = ("configs/research_scope.yaml", "src/research_scope/", "tests/research_scope/", "reports/research_scope_rs5/",
                    "data/research_rs5/", "data/releases/fotmob_epl_2020_2025_rs5_v1/", "data/releases/fb69_player_season_integrated_rs5_v1/")
# Phase 4 outputs (condition P4-D04, added in Phase 4.1). Phase 4 only adds files; it never edits rs5 or historical data.
PHASE4_OUTPUT_ROOTS = ("reports/phase_04/", "src/phase4/", "tests/phase4/", "FB69_report.ipynb")
NEW_OUTPUT_ROOTS = RS5_OUTPUT_ROOTS + PHASE4_OUTPUT_ROOTS
DOCUMENTED_EDITS = ("CLAUDE.md",)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path = ROOT):
    stack = [root]
    while stack:
        folder = stack.pop()
        for path in sorted(folder.iterdir()):
            if path.is_dir():
                if path.name not in SKIP_DIRS:
                    stack.append(path)
            elif path.is_file():
                yield path


def snapshot(root: Path = ROOT) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_hash(p) for p in iter_files(root)}


def is_new_output(rel: str) -> bool:
    return any(rel == r or (r.endswith("/") and rel.startswith(r)) for r in NEW_OUTPUT_ROOTS)


def compare(before: dict[str, str], after: dict[str, str]) -> dict:
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    unexpected_changes = [k for k in changed if k not in DOCUMENTED_EDITS and not is_new_output(k)]
    unexpected_added = [k for k in added if not is_new_output(k)]
    return {"historical_files": len(before), "current_files": len(after), "changed": changed, "removed": removed, "added_count": len(added),
            "unexpected_changes": unexpected_changes, "unexpected_added": unexpected_added, "documented_edits_changed": [k for k in changed if k in DOCUMENTED_EDITS],
            "historical_protected": not unexpected_changes and not removed}


def main() -> int:
    mode = sys.argv[1]
    if mode == "snapshot":
        hashes = snapshot()
        out = Path(sys.argv[2])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"generated_at_utc": datetime.now(timezone.utc).isoformat(), "files": len(hashes), "skipped_dirs": sorted(SKIP_DIRS), "sha256": hashes}, indent=0) + "\n", encoding="utf-8")
        print("snapshot files", len(hashes))
        return 0
    before = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["sha256"]
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), **compare(before, snapshot())}
    out = Path(sys.argv[3])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("changed",)}, indent=1)[:3000])
    return 0 if report["historical_protected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
