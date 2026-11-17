"""Audit Execution 03 task states and every referenced raw response checksum."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.statistics_catalog import load_statistics_config

RESOURCES = {"PLAYER_PROFILE", "PLAYER_SEASON_STATS", "CANDIDATE_LEADERBOARD",
             "SEASON_METRIC_LEADERBOARD"}


def audit() -> dict:
    cfg = load_full_config()
    manifest = Manifest(ROOT / cfg["manifest_path"])
    failures = []
    counts = Counter()
    verified = 0
    try:
        tasks = [t for t in manifest.all_tasks() if t["resource_type"] in RESOURCES]
        for task in tasks:
            counts[(task["season_label"], task["resource_type"], task["execution_state"])] += 1
            refs = task["raw_evidence_refs"]
            if task["execution_state"] == "VALIDATED" and not refs:
                failures.append({"task_id": task["task_id"], "error": "VALIDATED_WITHOUT_RAW"})
            for ref in refs:
                path = ROOT / ref
                if not path.is_file():
                    failures.append({"task_id": task["task_id"], "error": "RAW_MISSING", "path": ref})
                    continue
                metadata = path.with_name("metadata.json")
                if not metadata.is_file():
                    metadata = path.with_name(path.stem + ".meta.json")
                if not metadata.is_file():
                    failures.append({"task_id": task["task_id"], "error": "METADATA_MISSING", "path": ref})
                    continue
                meta = json.loads(metadata.read_text(encoding="utf-8"))
                expected = meta.get("content_sha256") or meta.get("sha256")
                if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    failures.append({"task_id": task["task_id"], "error": "RAW_SHA256_MISMATCH", "path": ref})
                    continue
                verified += 1
        result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                  "phase": "phase_02b1_execution_03", "tasks": len(tasks),
                  "raw_evidence_refs_verified": verified, "integrity_failures": failures,
                  "by_season_resource_state": [
                      {"season_label": s, "resource_type": r, "execution_state": state, "count": n}
                      for (s, r, state), n in sorted(counts.items())]}
        atomic_write(ROOT / load_statistics_config()["report_dir"] / "statistics_checkpoint_audit.json",
                     json_bytes(result))
        return result
    finally:
        manifest.close()


if __name__ == "__main__":
    outcome = audit()
    print(json.dumps({"tasks": outcome["tasks"],
                      "raw_evidence_refs_verified": outcome["raw_evidence_refs_verified"],
                      "integrity_failures": outcome["integrity_failures"]}, indent=2))
    raise SystemExit(0 if not outcome["integrity_failures"] else 2)
