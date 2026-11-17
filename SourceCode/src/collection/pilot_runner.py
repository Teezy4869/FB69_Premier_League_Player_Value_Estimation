"""CLI for Phase 2A Steps 01-02 only: bounded sources, references and sampling."""
from __future__ import annotations

import argparse
import json
import sys

from src.audit.client import BudgetExceeded
from src.collection.collection_config import load_config
from src.collection.foundation import PilotStore
from src.collection.player_reference import save_reference


def request_plan(config: dict) -> list[tuple[str, dict, str, str]]:
    plan = []
    for season, season_id in config["seasons"].items():
        plan.append(("leagues", {"id": config["league_id"], "season": season}, season,
                     f"league_{season.replace('/', '_')}"))
        for metric in config["reference_metrics"]:
            plan.append(("leagueseasondeepstats", {"id": config["league_id"], "season": season_id,
                     "type": "players", "stat": metric}, season,
                     f"{metric}_{season.replace('/', '_')}"))
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("discover", "sample", "execute"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-requests", type=int, default=None,
                        help="For execute only: at most this many HTTP requests")
    args = parser.parse_args(argv)
    config = load_config()
    if args.max_requests is not None and (args.mode != "execute" or not 0 <= args.max_requests <= config["pilot_execution_limit"]):
        parser.error("--max-requests applies to execute and must respect pilot_execution_limit")
    plan = request_plan(config)
    if args.dry_run:
        print(json.dumps({"mode": args.mode, "planned_reference_sources": len(plan),
                          "max_http_requests": (args.max_requests if args.max_requests is not None else
                                                config["pilot_execution_limit"]) if args.mode == "execute" else (
                                                    0 if args.mode == "sample" else config["request_budget"]),
                          "seasons": list(config["seasons"]), "will_use_cache": True}, indent=2))
        return 0
    if args.mode == "execute":
        config["request_budget"] = args.max_requests if args.max_requests is not None else config["pilot_execution_limit"]
    store = PilotStore(config)
    if args.mode in ("discover", "execute"):
        max_requests = config["request_budget"] if args.mode == "discover" else (
            args.max_requests if args.max_requests is not None else config["pilot_execution_limit"])
        for endpoint, params, season, source_id in plan:
            if store.client.attempts >= max_requests:
                break
            try:
                store.fetch(endpoint, params, season, source_id)
            except BudgetExceeded:
                break
        rows, coverage = save_reference(store)
        print(json.dumps({"http_attempts": store.client.attempts, "cache_hits": sum(
            x["outcome"] == "CACHE_HIT" for x in store.events), "reference_rows": len(rows),
            "source_failures": [x for x in store.events if x["outcome"] not in ("CACHE_HIT", "OK")],
            "season_status": {x["season_label"]: x["coverage_status"] for x in coverage}}, indent=2))
        if any(x["coverage_status"] == "INCOMPLETE_REFERENCE_SOURCES" for x in coverage):
            return 2
        return 0
    from src.collection.pilot_sampler import save_sample
    count = save_sample(store)
    print(json.dumps({"sample_rows": count, "http_attempts": 0}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
