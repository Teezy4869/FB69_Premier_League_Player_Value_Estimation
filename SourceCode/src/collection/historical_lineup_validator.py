"""Bounded, deterministic six-season lineup evidence for Phase 2B.0."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.client import BudgetExceeded
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.player_reference import candidate_views, write_csv
from src.collection.source_registry import SourceRegistry, load_hardening_config

MATCH_FIELDS = ["season_label", "season_id", "window", "match_id", "match_date_utc",
                "home_team_id", "away_team_id", "fixture_status", "context",
                "fixture_source_id", "detail_capture_id", "detail_scope_status", "detail_raw_path"]
LINEUP_FIELDS = ["season_label", "season_id", "match_id", "match_date_utc", "team_id",
                 "player_id", "player_name", "lineup_role", "substitution_events", "appearance_status",
                 "in_candidate_population", "candidate_team_relation", "evidence_reference",
                 "capture_id", "request_key", "collection_timestamp", "scope_status"]
POP_FIELDS = ["season_id", "season_label", "player_id", "team_id", "reference_source",
              "evidence_reference", "verification_status", "missing_from_candidate_population",
              "collection_timestamp", "observed_metrics", "sampled_match_ids"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_lookup(store: PilotStore) -> dict[str, list[dict]]:
    result = {}
    for meta, payload in store.cached_payloads("leagues"):
        season = meta["season_label"]
        if (payload.get("details") or {}).get("selectedSeason") != season:
            raise ValueError(f"League response season mismatch: {season}")
        fixtures = []
        for item in (payload.get("fixtures") or {}).get("allMatches") or []:
            status = item.get("status") or {}
            if status.get("finished") and not status.get("cancelled"):
                fixtures.append({"season_label": season, "season_id": str(store.config["seasons"][season]),
                                 "match_id": str(item["id"]), "match_date_utc": status["utcTime"],
                                 "home_team_id": str((item.get("home") or {}).get("id")),
                                 "away_team_id": str((item.get("away") or {}).get("id")),
                                 "fixture_status": "FINISHED", "fixture_source_id": meta["source_id"]})
        result[season] = sorted(fixtures, key=lambda r: (r["match_date_utc"], r["match_id"]))
    return result


def select_matches(pilot: PilotStore, hardening: dict) -> list[dict]:
    """One cached mid-season detail plus two bounded early/late targets per season."""
    fixtures = fixture_lookup(pilot)
    cached_ids = {str(m["params"]["matchId"]) for m, _ in pilot.cached_payloads("matchDetails")}
    manifest = read_csv(ROOT / "reports/phase_02a/pilot_sample_manifest.csv")
    identity = read_csv(ROOT / "reports/phase_02a/historical_identity_audit.csv")
    plan = []
    seed = hardening["lineup_sample_seed"]
    for season in pilot.config["seasons"]:
        season_fixtures = fixtures[season]
        if len(season_fixtures) != 380:
            raise ValueError(f"Expected 380 finished fixtures for {season}")
        indexed = {r["match_id"]: i for i, r in enumerate(season_fixtures)}
        cached = [r for r in season_fixtures if r["match_id"] in cached_ids]
        if not cached:
            raise ValueError(f"No reusable historical detail for {season}")
        mid = min(cached, key=lambda r: (abs(indexed[r["match_id"]] - 190), r["match_id"]))
        transfer_teams = {r["historical_team_id"] for r in identity
                          if r["season_label"] == season and r["career_history_transfer_flag"] == "INFERRED_CANDIDATE"}
        low_teams = {r["fotmob_team_id"] for r in manifest
                     if r["season_label"] == season and r["low_minutes"] == "True"}
        preferred = transfer_teams or low_teams
        for window, bucket, target_index in (("EARLY", season_fixtures[:95], 48),
                                             ("MID", [mid], 190),
                                             ("LATE", season_fixtures[285:], 333)):
            if window == "MID":
                chosen = mid
            else:
                # Prefer a transfer/low-minute club, alternate home/away context,
                # then use a deterministic hash only to break equivalent choices.
                def rank(r):
                    teams = {r["home_team_id"], r["away_team_id"]}
                    return (not bool(teams & preferred),
                            r["home_team_id"] == mid["home_team_id"],
                            not (r["away_team_id"] in preferred if window == "EARLY" else
                                 r["home_team_id"] in preferred),
                            abs(indexed[r["match_id"]] - target_index),
                            hashlib.sha256(f"{seed}:{season}:{window}:{r['match_id']}".encode()).hexdigest())
                chosen = min(bucket, key=rank)
            context = "transfer_candidate_club" if transfer_teams & {chosen["home_team_id"], chosen["away_team_id"]} else (
                "low_minute_sample_club" if low_teams & {chosen["home_team_id"], chosen["away_team_id"]} else
                "club_and_time_stratum")
            plan.append({**chosen, "window": window, "context": context,
                         "detail_capture_id": "", "detail_scope_status": "PENDING", "detail_raw_path": ""})
    if len(plan) != 18 or len({r["match_id"] for r in plan}) != 18:
        raise ValueError("Expected 18 distinct stratified fixtures")
    return plan


def verify_detail(detail: dict, fixture: dict) -> tuple[str, str]:
    general = detail.get("general") or {}
    expected = (fixture["match_id"], fixture["home_team_id"], fixture["away_team_id"],
                fixture["match_date_utc"][:10], "47")
    observed = (str(general.get("matchId")), str((general.get("homeTeam") or {}).get("id")),
                str((general.get("awayTeam") or {}).get("id")),
                (general.get("matchTimeUTCDate") or "")[:10], str(general.get("leagueId")))
    if observed != expected:
        return "HISTORICAL_SCOPE_MISMATCH", f"expected={expected}; observed={observed}"
    status = (detail.get("header") or {}).get("status") or {}
    if not status.get("finished") or status.get("cancelled"):
        return "REJECTED", "Detail is not a completed, non-cancelled match"
    return "ACCEPTED", "Match, teams, date, league and status agree with season fixture index"


def lineup_members(detail: dict, fixture: dict, capture: dict,
                   candidates: dict[tuple[str, str], list[dict]]) -> list[dict]:
    lineup = (detail.get("content") or {}).get("lineup") or {}
    if lineup.get("lineupType") != "standard":
        return []
    result, seen = [], set()
    for side, team_id in (("homeTeam", fixture["home_team_id"]),
                          ("awayTeam", fixture["away_team_id"])):
        team = lineup.get(side) or {}
        if str(team.get("id")) != team_id:
            raise ValueError(f"Lineup team mismatch for match {fixture['match_id']}")
        for role, members in (("STARTER", team.get("starters") or []),
                              ("SUBSTITUTE", team.get("subs") or [])):
            for player in members:
                pid = str(player.get("id"))
                key = (team_id, pid)
                if not pid.isdigit() or key in seen:
                    raise ValueError(f"Invalid or duplicate lineup identity: {fixture['match_id']} {key}")
                seen.add(key)
                events = (player.get("performance") or {}).get("substitutionEvents") or []
                event_types = {e.get("type") for e in events if isinstance(e, dict)}
                appeared = role == "STARTER" or "subIn" in event_types
                relations = candidates.get((fixture["season_label"], pid), [])
                exact = any(r["fotmob_team_id"] == team_id for r in relations)
                result.append({"season_label": fixture["season_label"], "season_id": fixture["season_id"],
                               "match_id": fixture["match_id"], "match_date_utc": fixture["match_date_utc"],
                               "team_id": team_id, "player_id": pid,
                               "player_name": player.get("name") or "", "lineup_role": role,
                               "substitution_events": "|".join(sorted(event_types)),
                               "appearance_status": "APPEARED" if appeared else "UNUSED_SUBSTITUTE",
                               "in_candidate_population": bool(relations),
                               "candidate_team_relation": "EXACT" if exact else ("OTHER_TEAM" if relations else "ABSENT"),
                               "evidence_reference": capture["raw_path"],
                               "capture_id": capture["capture_id"], "request_key": capture["request_key"],
                               "collection_timestamp": capture["collected_at_utc"],
                               "scope_status": "ACCEPTED"})
    return result


def build_population_rows(candidate_rows: list[dict], lineup_rows: list[dict],
                          source_paths: dict[str, str]) -> list[dict]:
    appeared = defaultdict(list)
    for row in lineup_rows:
        if row["appearance_status"] == "APPEARED":
            appeared[(row["season_label"], row["player_id"], row["team_id"])].append(row)
    candidates = {(r["season_label"], r["fotmob_player_id"], r["fotmob_team_id"]): r
                  for r in candidate_rows}
    by_player = {(s, p) for s, p, _ in candidates}
    result = []
    for key, r in candidates.items():
        sightings = appeared.get(key, [])
        refs = [source_paths[src] for src in r["evidence_source_ids"].split("|")]
        refs += [a["evidence_reference"] for a in sightings]
        result.append({"season_id": r["fotmob_season_id"], "season_label": r["season_label"],
                       "player_id": r["fotmob_player_id"], "team_id": r["fotmob_team_id"],
                       "reference_source": r["reference_source"],
                       "evidence_reference": "|".join(sorted(set(refs))),
                       "verification_status": "VERIFIED_APPEARANCE" if sightings else "LEADERBOARD_CANDIDATE_ONLY",
                       "missing_from_candidate_population": False,
                       "collection_timestamp": r["reference_timestamp"],
                       "observed_metrics": r["observed_metrics"],
                       "sampled_match_ids": "|".join(sorted({a["match_id"] for a in sightings}))})
    for key, sightings in appeared.items():
        if key in candidates:
            continue
        season, pid, team = key
        first = sightings[0]
        result.append({"season_id": first["season_id"], "season_label": season,
                       "player_id": pid, "team_id": team, "reference_source": "matchDetails.lineup",
                       "evidence_reference": "|".join(sorted({a["evidence_reference"] for a in sightings})),
                       "verification_status": "VERIFIED_APPEARANCE_OTHER_TEAM" if (season, pid) in by_player else
                                              "VERIFIED_APPEARANCE_MISSING_CANDIDATE",
                       "missing_from_candidate_population": (season, pid) not in by_player,
                       "collection_timestamp": first["collection_timestamp"], "observed_metrics": "",
                       "sampled_match_ids": "|".join(sorted({a["match_id"] for a in sightings}))})
    return sorted(result, key=lambda r: (r["season_label"], int(r["player_id"]), int(r["team_id"])))


def execute(collect: bool = False) -> dict:
    config = load_config()
    hardening = load_hardening_config()
    pilot = PilotStore(config)
    registry = SourceRegistry(hardening)
    report_dir = ROOT / hardening["report_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    plan = select_matches(pilot, hardening)
    candidates, by_player = candidate_views(pilot)
    captures = list(registry.captures())
    source_paths = {m["source_id"]: m["raw_path"] for m, _ in captures if m["endpoint"] == "leagueseasondeepstats"}
    lineup = []
    new_attempts = 0
    collection_errors = []
    for fixture in plan:
        params = {"matchId": int(fixture["match_id"])}
        item = registry.lookup("matchDetails", params, fixture["season_label"])
        if item is None and collect:
            if new_attempts >= hardening["lineup_request_budget"]:
                break
            try:
                item = registry.fetch("matchDetails", params, fixture["season_label"],
                                      {"date": fixture["match_date_utc"][:10],
                                       "home_team_id": fixture["home_team_id"],
                                       "away_team_id": fixture["away_team_id"]})
            except BudgetExceeded:
                collection_errors.append(f"HTTP attempt budget exhausted before match {fixture['match_id']}")
                break
            new_attempts = registry.client.attempts
            if item is None:
                collection_errors.append(f"No successful response for match {fixture['match_id']}")
        if item is None:
            continue
        meta, detail = item
        status, note = verify_detail(detail, fixture)
        fixture.update(detail_capture_id=meta["capture_id"], detail_scope_status=status,
                       detail_raw_path=meta["raw_path"])
        if status != "ACCEPTED":
            continue
        lineup.extend(lineup_members(detail, fixture, meta, by_player))
    write_csv(report_dir / "historical_match_sample.csv", MATCH_FIELDS, plan)
    write_csv(report_dir / "historical_lineup_comparison.csv", LINEUP_FIELDS, lineup)
    population = build_population_rows(candidates, lineup, source_paths)
    write_csv(report_dir / "historical_population_validation.csv", POP_FIELDS, population)
    return {"matches_planned": len(plan), "matches_validated": sum(r["detail_scope_status"] == "ACCEPTED" for r in plan),
            "new_http_attempts": new_attempts, "collection_errors": collection_errors,
            "candidate_relations": len(candidates),
            "lineup_members": len(lineup), "appeared_rows": sum(r["appearance_status"] == "APPEARED" for r in lineup),
            "missing_player_season": len({(r["season_label"], r["player_id"]) for r in population
                                          if r["missing_from_candidate_population"]}),
            "population_rows": len(population)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true", help="allow at most 12 missing match-detail requests")
    args = parser.parse_args()
    print(json.dumps(execute(args.collect), indent=2))
