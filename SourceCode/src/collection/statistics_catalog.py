"""Season-scoped metric plan grounded in saved FotMob catalogs and dictionary v2."""
from __future__ import annotations

import csv
import io
from collections import Counter
from functools import lru_cache

import pyarrow.parquet as pq
import yaml

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.source_registry import SourceRegistry, load_hardening_config


@lru_cache(maxsize=1)
def load_statistics_config() -> dict:
    cfg = yaml.safe_load((ROOT / "configs/statistics_collection.yaml").read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or len({x["stat"] for x in cfg["leaderboard_specs"]}) != len(cfg["leaderboard_specs"]):
        raise ValueError("Invalid or duplicate leaderboard metric specifications")
    return cfg


def board_spec(stat: str) -> dict | None:
    return next((spec for spec in load_statistics_config()["leaderboard_specs"] if spec["stat"] == stat), None)


def write_csv(path, rows: list[dict], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader(); writer.writerows(rows)
    atomic_write(path, buffer.getvalue().encode("utf-8"))


def build_plan(manifest: Manifest, *, append: bool) -> dict:
    full = load_full_config()
    cfg = load_statistics_config()
    old = SourceRegistry(load_hardening_config())
    appeared = pq.read_table(ROOT / cfg["population_path"], columns=["season_label", "player_id"]).to_pylist()
    population = Counter(row["season_label"] for row in appeared)
    rows = []
    appended = 0
    for season, season_id in full["seasons"].items():
        board = old.lookup("leagueseasondeepstats", {"id": 47, "season": season_id,
            "type": "players", "stat": "mins_played"}, season)
        if board is None:
            raise ValueError(f"No saved season-scoped metric catalog: {season}")
        _, payload = board
        if str(payload.get("currentSeasonId")) != str(season_id):
            raise ValueError(f"Saved metric catalog has wrong season: {season}")
        catalog = {item["name"]: item for item in payload.get("statsList") or []
                   if isinstance(item, dict) and isinstance(item.get("name"), str)}
        gate = next(t for t in manifest.all_tasks(season, "C") if t["resource_type"] == "SEASON_STATS_GATE")
        for priority, spec in enumerate(cfg["leaderboard_specs"], 1):
            stat = spec["stat"]
            supported = stat in catalog
            params = {"id": 47, "season": season_id, "type": "players", "stat": stat}
            existing = old.lookup("leagueseasondeepstats", params, season)
            state = "CACHED" if existing else "PLANNED" if supported else "UNSUPPORTED_CATALOG"
            if append and supported and stat not in full["candidate_leaderboard_metrics"]:
                league = next(t for t in manifest.all_tasks(season, "A") if t["resource_type"] == "SEASON_FIXTURES")
                task_id = manifest.add(season, season_id, "C", "SEASON_METRIC_LEADERBOARD",
                                       "leagueseasondeepstats", params,
                                       {"identity": f"metric_{stat}", "metric": spec["metric"],
                                        "aggregation": spec["aggregation"]}, [league["task_id"]])
                manifest.add(season, season_id, "C", "SEASON_STATS_GATE", context=gate["context"],
                             dependencies=[task_id])
                appended += 1
            rows.append({"season_label": season, "season_id": season_id, "priority": priority,
                         "group": spec["group"], "metric_name": spec["metric"], "leaderboard_stat": stat,
                         "source_title": catalog.get(stat, {}).get("title", ""),
                         "unit": spec["unit"], "aggregation_type": spec["aggregation"],
                         "source_field": spec["source_field"], "expected_appeared_players": population[season],
                         "catalog_status": "PRESENT" if supported else "ABSENT", "collection_state": state,
                         "pagination_contract": "UNVERIFIED", "team_filter_contract": "UNVERIFIED"})
    fields = list(rows[0])
    report = ROOT / cfg["report_dir"]
    write_csv(report / "metric_collection_plan.csv", rows, fields)
    if append:
        manifest.export_csv(report / "collection_manifest.csv")
    return {"plan_rows": len(rows), "appended_tasks": appended,
            "catalog_present": sum(r["catalog_status"] == "PRESENT" for r in rows),
            "cached_responses": sum(r["collection_state"] == "CACHED" for r in rows),
            "by_group": dict(Counter(r["group"] for r in rows))}


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()
    manifest = Manifest(ROOT / load_full_config()["manifest_path"])
    try:
        print(json.dumps(build_plan(manifest, append=args.append), indent=2))
    finally:
        manifest.close()
