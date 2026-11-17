"""Bounded, resumable season-level profile-entry and playerStats collection."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import run
from src.collection.statistics_catalog import load_statistics_config

PENDING = {"PLANNED", "RUNNING", "FETCHED", "RETRY_PENDING"}
ALLOW_REVIEW = {"MISSING_SEASON_ENTRY", "HISTORICAL_SCOPE_UNVERIFIED", "REQUEST_BUDGET_EXCEEDED",
                "NO_STATS_PAYLOAD"}


def progress(manifest: Manifest, cfg: dict, batches: list[dict], stop_reason: str) -> dict:
    seasons = {}
    for season in cfg["seasons"]:
        tasks = manifest.all_tasks(season)
        profiles = [t for t in tasks if t["resource_type"] == "PLAYER_PROFILE"]
        stats = [t for t in tasks if t["resource_type"] == "PLAYER_SEASON_STATS"]
        boards = [t for t in tasks if t["resource_type"] in ("CANDIDATE_LEADERBOARD", "SEASON_METRIC_LEADERBOARD")]
        seasons[season] = {"appeared_players": len(profiles),
                           "profiles_by_state": dict(Counter(t["execution_state"] for t in profiles)),
                           "stats_tasks": len(stats),
                           "stats_by_state": dict(Counter(t["execution_state"] for t in stats)),
                           "leaderboards_by_state": dict(Counter(t["execution_state"] for t in boards)),
                           "collection_state": "COMPLETE" if len(stats) == len(profiles) and
                               all(t["execution_state"] == "VALIDATED" for t in profiles + stats + boards)
                               else "PARTIAL"}
    result = {"phase": "phase_02b1_execution_03", "seasons": seasons,
              "batches_this_run": batches, "stop_reason": stop_reason,
              "http_attempts_this_run": sum(b["http_attempts"] for b in batches)}
    atomic_write(ROOT / load_statistics_config()["report_dir"] / "season_statistics_collection_progress.json",
                 json_bytes(result))
    return result


def collect(manifest: Manifest, cfg: dict, *, max_batches: int, max_requests: int) -> dict:
    batches = []
    stop_reason = "BATCH_LIMIT_OR_COLLECTION_COMPLETE"
    for season in cfg["seasons"]:
        for stage, resource in (("D", "PLAYER_PROFILE"), ("C", "PLAYER_SEASON_STATS")):
            while len(batches) < max_batches:
                tasks = [t for t in manifest.all_tasks(season, stage) if t["resource_type"] == resource]
                if not any(t["execution_state"] in PENDING for t in tasks):
                    break
                result = run(cfg, manifest, season=season, stage=stage,
                             batch_size=cfg["max_batch_size"], resume=True, execute=True,
                             max_requests=max_requests)
                decision = result["batch_decision"]
                row = {"season": season, "stage": stage, "resource": resource,
                       "batch_report": result["batch_report"],
                       "http_attempts": result["http_attempts"], "decision": decision}
                batches.append(row)
                print(json.dumps({"batch": len(batches), **row}), flush=True)
                progress(manifest, cfg, batches, "RUNNING")
                if (decision["decision"] == "STOP" or
                    (decision["decision"] == "REVIEW" and
                     not set(decision["errors"]).issubset(ALLOW_REVIEW)) or
                    decision["task_count"] == 0):
                    stop_reason = "QUALITY_STOP_OR_NO_PROGRESS"
                    return progress(manifest, cfg, batches, stop_reason)
                time.sleep(cfg["min_request_interval_seconds"])
            if len(batches) >= max_batches:
                return progress(manifest, cfg, batches, stop_reason)
            # These local gates have no HTTP side effect and become eligible only
            # after every corresponding player task is validated.
            gate_result = run(cfg, manifest, season=season, stage=stage, batch_size=1,
                              resume=True, execute=False, max_requests=0)
            if gate_result["batch_decision"]["decision"] == "STOP":
                return progress(manifest, cfg, batches, "LOCAL_GATE_STOP")
    return progress(manifest, cfg, batches, stop_reason)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--max-requests", type=int, default=50)
    args = parser.parse_args()
    cfg = load_full_config()
    if args.execute == args.status or not 0 < args.max_batches <= 100 or not 0 < args.max_requests <= 50:
        parser.error("Choose --execute or --status with bounded positive limits")
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        result = (collect(manifest, cfg, max_batches=args.max_batches, max_requests=args.max_requests)
                  if args.execute else progress(manifest, cfg, [], "STATUS_ONLY"))
        print(json.dumps({"stop_reason": result["stop_reason"],
                          "http_attempts_this_run": result["http_attempts_this_run"],
                          "season_states": {s: r["collection_state"] for s, r in result["seasons"].items()}},
                         indent=2))
        return 0 if result["stop_reason"] != "QUALITY_STOP_OR_NO_PROGRESS" else 2
    finally:
        manifest.close()


if __name__ == "__main__":
    raise SystemExit(main())
