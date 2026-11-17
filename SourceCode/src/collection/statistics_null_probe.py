"""One bounded retry of a preserved playerStats null burst using the existing runner."""
from __future__ import annotations

import argparse
import hashlib
import json

from src.audit.client import AuditClient
from src.collection.batch_quality import write_batch_report
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import process_task, registries


def probe(player_id: str, season: str) -> dict:
    cfg = load_full_config()
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        if season not in cfg["seasons"]:
            raise ValueError("Season outside fixed collection scope")
        matches = [t for t in manifest.all_tasks(season, "C") if
                   t["resource_type"] == "PLAYER_SEASON_STATS" and
                   str(t["params"]["playerId"]) == player_id]
        if len(matches) != 1:
            raise ValueError("Expected exactly one target player-season task")
        task = matches[0]
        if task["execution_state"] != "QUARANTINED" or task["error_classification"] != "NO_STATS_PAYLOAD" or task["attempt_count"] != 1:
            raise ValueError("Target must have one preserved null response and no prior retry")
        if len(task["raw_evidence_refs"]) != 1:
            raise ValueError("Target raw evidence count differs")
        raw = ROOT / task["raw_evidence_refs"][0]
        meta = json.loads(raw.with_name("metadata.json").read_text(encoding="utf-8"))
        if (raw.read_bytes().strip() != b"null" or meta["request_key"] != task["request_key"] or
                hashlib.sha256(raw.read_bytes()).hexdigest() != meta["content_sha256"]):
            raise ValueError("Original null evidence failed verification")
        pilot = load_config()
        client_cfg = dict(pilot)
        client_cfg.update({"request_budget": 1, "max_retries": 0,
                           "min_request_interval_seconds": cfg["min_request_interval_seconds"],
                           "request_timeout_seconds": cfg["request_timeout_seconds"],
                           "max_response_bytes": cfg["max_response_bytes"]})
        client = AuditClient(client_cfg, ROOT / cfg["log_path"])
        current, old = registries(cfg, client)
        manifest.transition(task["task_id"], "RETRY_PENDING", error="TRANSIENT_NULL_BURST",
                            note="One targeted source-health probe after contiguous null burst")
        outcome = process_task(manifest.task(task["task_id"]), manifest, cfg, current, old, client, True)
        path, decision = write_batch_report([outcome], cfg)
        result = {"player_id": player_id, "season_label": season, "task_id": task["task_id"],
                  "original_raw": task["raw_evidence_refs"][0], "new_state": manifest.task(task["task_id"])["execution_state"],
                  "http_attempts": client.attempts, "quality_decision": decision,
                  "batch_report": path.relative_to(ROOT).as_posix()}
        atomic_write(ROOT / cfg["report_dir"] / f"null_probe_{season.replace('/', '_')}_{player_id}.json",
                     json_bytes(result))
        return result
    finally:
        manifest.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, choices=list(load_full_config()["seasons"]))
    parser.add_argument("player_id")
    args = parser.parse_args()
    print(json.dumps(probe(args.player_id, args.season), indent=2))
