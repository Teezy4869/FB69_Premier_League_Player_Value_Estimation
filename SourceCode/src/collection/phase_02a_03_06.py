"""Bounded Phase 2A collection: pilot profiles, season stats and selected match details."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone

from src.audit.client import BudgetExceeded
from src.audit.normalization import season_profile_entry
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore


def sample_rows(config: dict) -> list[dict]:
    with (ROOT / config["report_dir"] / "pilot_sample_manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 120 or {r["season_label"] for r in rows} != set(config["seasons"]):
        raise ValueError("Pilot manifest differs from the approved six-season sample")
    return rows


def cache_by_source(store: PilotStore, endpoint: str) -> dict[str, tuple[dict, dict]]:
    return {meta["source_id"]: (meta, payload) for meta, payload in store.cached_payloads(endpoint)}


def profile_plan(rows: list[dict]) -> list[tuple[str, dict, str, str]]:
    seen = set()
    plan = []
    for row in rows:
        pid = row["fotmob_player_id"]
        if pid not in seen:
            seen.add(pid)
            plan.append(("playerData", {"id": int(pid)}, row["season_label"], f"profile_{pid}"))
    return plan


def stats_plan(rows: list[dict], profiles: dict) -> tuple[list[tuple], list[dict]]:
    plan, skipped = [], []
    for row in rows:
        pid, season = row["fotmob_player_id"], row["season_label"]
        item = profiles.get(f"profile_{pid}")
        if item is None:
            skipped.append({"player_id": pid, "season": season, "reason": "PROFILE_NOT_COLLECTED"})
            continue
        _, profile = item
        if str(profile.get("id")) != pid:
            skipped.append({"player_id": pid, "season": season, "reason": "PROFILE_ID_MISMATCH"})
            continue
        entry = season_profile_entry(profile, season, 47)
        if not entry or not entry.get("entryId") or not entry.get("hasDeepStats"):
            skipped.append({"player_id": pid, "season": season, "reason": "NO_VERIFIED_SEASON_ENTRY"})
            continue
        plan.append(("playerStats", {"playerId": int(pid), "seasonId": entry["entryId"]},
                     season, f"stats_{season.replace('/', '_')}_{pid}"))
    return plan, skipped


def match_plan(rows: list[dict], leagues: dict) -> list[tuple]:
    by_season = defaultdict(list)
    for row in rows:
        by_season[row["season_label"]].append(row)
    plan = []
    for season in sorted(by_season):
        item = leagues.get(f"league_{season.replace('/', '_')}")
        if not item:
            continue
        _, league = item
        rank_one = next(r["fotmob_team_id"] for r in by_season[season] if r["club_context_rank"] == "1")
        fixtures = [f for f in ((league.get("fixtures") or {}).get("allMatches") or [])
                    if isinstance(f, dict) and (f.get("status") or {}).get("finished") and
                    not (f.get("status") or {}).get("cancelled") and
                    str((f.get("home") or {}).get("id")) == rank_one]
        fixtures.sort(key=lambda f: (f["status"].get("utcTime") or "", str(f.get("id"))))
        target_dates = [season[:4] + "-12-01"]
        if season in {"2019/2020", "2022/2023", "2024/2025"}:
            target_dates.append(season[5:] + "-03-01")
        for target_date in target_dates:
            eligible = [f for f in fixtures if (f["status"].get("utcTime") or "")[:10] >= target_date]
            if eligible:
                fixture = eligible[0]
                match_id = str(fixture["id"])
                plan.append(("matchDetails", {"matchId": int(match_id)}, season,
                             f"match_{season.replace('/', '_')}_{match_id}"))
    # The replay is a separate raw fixture ID; the abandoned game is retained in the league index.
    if "league_2023_2024" in leagues:
        plan.append(("matchDetails", {"matchId": 4421797}, "2023/2024", "match_2023_2024_4421797"))
    return list(dict(((p[2], p[1]["matchId"]), p) for p in plan).values())


def run(stage: str, max_requests: int, dry_run: bool = False) -> dict:
    config = load_config()
    if not 0 <= max_requests <= config["request_budget"]:
        raise ValueError("Batch budget exceeds the configured 40 HTTP attempts")
    rows = sample_rows(config)
    if dry_run:
        return {"stage": stage, "sample_rows": len(rows), "max_http_attempts": max_requests}
    config["request_budget"] = max_requests
    store = PilotStore(config)
    if stage == "profiles":
        plan = profile_plan(rows)
        preexisting = set(cache_by_source(store, "playerData"))
        skipped = []
    elif stage == "stats":
        plan, skipped = stats_plan(rows, cache_by_source(store, "playerData"))
        preexisting = set(cache_by_source(store, "playerStats"))
    elif stage == "matches":
        plan = match_plan(rows, cache_by_source(store, "leagues"))
        preexisting = set(cache_by_source(store, "matchDetails"))
        skipped = []
    else:
        raise ValueError(stage)
    attempted = 0
    for endpoint, params, season, source_id in plan:
        if source_id in preexisting:
            continue
        if store.client.attempts >= max_requests:
            break
        try:
            store.fetch(endpoint, params, season, source_id)
        except BudgetExceeded:
            break
        attempted += 1
    available = set(cache_by_source(store, {"profiles": "playerData", "stats": "playerStats",
                                            "matches": "matchDetails"}[stage]))
    return {"stage": stage, "planned": len(plan), "available": len(available & {p[3] for p in plan}),
            "still_missing": sum(p[3] not in available for p in plan),
            "http_attempts": store.client.attempts, "attempted_sources": attempted,
            "skipped_without_verified_prior_source": skipped[:30],
            "errors": [x for x in store.events if x["outcome"] not in ("OK", "CACHE_HIT")]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("profiles", "stats", "matches", "normalize"))
    parser.add_argument("--max-requests", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.stage == "normalize":
        if args.dry_run:
            print(json.dumps({"stage": "normalize", "http_attempts": 0}))
            return 0
        from src.collection.normalize_pilot import normalize
        print(json.dumps(normalize(), indent=2))
        return 0
    print(json.dumps(run(args.stage, args.max_requests, args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
