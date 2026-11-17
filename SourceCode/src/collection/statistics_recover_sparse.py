"""Revalidate top-card-only playerStats responses already preserved in quarantine."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from src.collection.batch_quality import inspect_capture
from src.collection.collection_config import ROOT
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import profile_for_stats, registries
from src.collection.reliability_runner import schema_state


def recover() -> dict:
    cfg = load_full_config()
    manifest = Manifest(ROOT / cfg["manifest_path"])
    current, old = registries(cfg)
    log_index = {}
    for line in (ROOT / cfg["log_path"]).open(encoding="utf-8"):
        row = json.loads(line)
        log_index[(row["timestamp_utc"], row["endpoint"])] = row
    counts = {"reviewed": 0, "validated": 0, "null_payload_reclassified": 0,
              "uncommitted_capture_recovered": 0, "still_quarantined": 0}
    try:
        for task in manifest.all_tasks():
            if task["resource_type"] != "PLAYER_SEASON_STATS" or task["execution_state"] != "QUARANTINED" or task["error_classification"] != "SCHEMA_ERROR":
                continue
            counts["reviewed"] += 1
            path = next((ROOT / ref for ref in task["raw_evidence_refs"] if "/quarantine/" in ref), None)
            if path is None or not path.is_file():
                counts["still_quarantined"] += 1
                continue
            source = json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))
            body = path.read_bytes()
            if (hashlib.sha256(body).hexdigest() != source["content_sha256"] or
                source["task_id"] != task["task_id"] or source["request_key"] != task["request_key"] or
                source["params"] != task["params"] or source["season_label"] != task["season_label"]):
                counts["still_quarantined"] += 1
                continue
            if body.strip() == b"null" and source.get("http_status") == 200:
                log = log_index.get((source["timestamp_utc"], "playerStats"))
                if log and log.get("json_parse_success") and log.get("http_status") == 200:
                    manifest.transition(task["task_id"], "QUARANTINED", error="NO_STATS_PAYLOAD",
                        note="HTTP 200 JSON null; no season-statistics payload available")
                    counts["null_payload_reclassified"] += 1
                    continue
            payload = json.loads(body)
            schema, _ = schema_state("playerStats", payload, task["params"])
            log = log_index.get((source["timestamp_utc"], "playerStats"))
            if schema != "SPARSE_DATA" or log is None or log.get("http_status") != 200 or not log.get("json_parse_success"):
                counts["still_quarantined"] += 1
                continue
            profile = profile_for_stats(task, manifest, current, old)
            if profile is None:
                counts["still_quarantined"] += 1
                continue
            record = dict(log)
            item = current.capture("playerStats", task["params"], task["season_label"],
                                   {"payload": payload, "raw_body": body, "record": record})
            meta, captured = item
            assessment = inspect_capture(task, meta, captured, profile)
            if assessment["decision"] == "VALIDATED":
                manifest.transition(task["task_id"], "VALIDATED", raw_path=meta["raw_path"],
                    validation=assessment["scope_status"], note="Revalidated preserved top-card-only response")
                counts["validated"] += 1
            else:
                counts["still_quarantined"] += 1
        for task in manifest.all_tasks():
            if (task["resource_type"] != "PLAYER_SEASON_STATS" or task["execution_state"] != "QUARANTINED" or
                    task["error_classification"] != "RAW_CAPTURE_ERROR"):
                continue
            counts["reviewed"] += 1
            raw_root = (ROOT / cfg["raw_dir"]).resolve()
            candidates = list((raw_root / task["season_label"].replace("/", "_") / "playerStats").glob(".cap_*.tmp"))
            recovered = False
            for source_dir in candidates:
                meta_path, response_path = source_dir / "metadata.json", source_dir / "response.json"
                if not meta_path.is_file() or not response_path.is_file():
                    continue
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("request_key") != task["request_key"] or meta.get("params") != task["params"]:
                    continue
                target = (ROOT / meta["raw_path"]).parent.resolve()
                if (not source_dir.resolve().is_relative_to(raw_root) or not target.is_relative_to(raw_root) or
                        target.exists() or target.parent != source_dir.parent.resolve()):
                    continue
                body = response_path.read_bytes()
                if hashlib.sha256(body).hexdigest() != meta["content_sha256"]:
                    continue
                payload = json.loads(body)
                profile = profile_for_stats(task, manifest, current, old)
                if profile is None:
                    continue
                # The checked temp directory is an interrupted atomic rename, not a new HTTP request.
                for attempt in range(5):
                    try:
                        os.rename(source_dir, target)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.5 * (attempt + 1))
                assessment = inspect_capture(task, meta, payload, profile)
                if assessment["decision"] == "VALIDATED":
                    manifest.transition(task["task_id"], "VALIDATED", raw_path=meta["raw_path"],
                        validation=assessment["scope_status"], note="Recovered checked interrupted raw rename")
                    counts["uncommitted_capture_recovered"] += 1
                    recovered = True
                break
            if not recovered:
                counts["still_quarantined"] += 1
        return counts
    finally:
        manifest.close()


if __name__ == "__main__":
    print(json.dumps(recover()))
