"""Validate a complete, season-scoped seven-table output before acceptance.

This is a read-only gate. A future normalizer writes the seven Parquet files and
the population checkpoint; absent or partial output remains BLOCKED.
"""
from __future__ import annotations

import csv
import json
import math

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.historical_lineup_validator import fixture_lookup
from src.collection.historical_lineup_validator import verify_detail
from src.collection.normalize_pilot import schemas


KEYS = {
    "players": ("player_id",),
    "teams": ("team_id",),
    "player_seasons": ("player_id", "season_id"),
    "player_team_seasons": ("player_id", "team_id", "season_id"),
    "matches": ("match_id",),
    "player_match_links": ("player_id", "match_id", "team_id"),
}
SEASON_TABLES = ("player_seasons", "player_team_seasons", "matches",
                 "player_match_links", "metric_observations")


def _tokens(value: object) -> list[str]:
    return [part for part in str(value or "").split("|") if part]


def validate_full_season(cfg: dict, season: str, current, old) -> dict:
    """Return issues and row counts. Never changes a capture, manifest, or table."""
    issues: list[str] = []
    counts: dict[str, int] = {}
    folder = ROOT / cfg["normalized_dir"] / season.replace("/", "_")
    checkpoint = ROOT / cfg["checkpoint_dir"] / season.replace("/", "_") / "appeared_population.json"
    if not checkpoint.is_file():
        issues.append("Missing complete appeared-population checkpoint")
    tables = {}
    for name, expected in schemas().items():
        path = folder / f"{name}.parquet"
        if not path.is_file():
            issues.append(f"Missing full-season table: {name}")
            continue
        try:
            table = pq.read_table(path)
        except (OSError, ValueError) as exc:
            issues.append(f"Unreadable {name}: {exc}")
            continue
        missing = set(expected.names) - set(table.schema.names)
        if missing:
            issues.append(f"{name} missing columns: {sorted(missing)}")
            continue
        tables[name] = table.to_pylist()
        counts[name] = table.num_rows
    if issues:
        return {"issues": issues, "counts": counts}

    try:
        population = json.loads(checkpoint.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return {"issues": [f"Invalid population checkpoint: {exc}"], "counts": counts}
    season_id = str(cfg["seasons"][season])
    if population.get("season_label") != season or population.get("validated_match_count") != 380:
        issues.append("Population checkpoint has wrong season or incomplete match count")
    if population.get("unknown_match_links"):
        issues.append(f"Unresolved participation for {len(population['unknown_match_links'])} lineup entries")

    for name, columns in KEYS.items():
        seen = set()
        for row in tables[name]:
            key = tuple(str(row.get(column) or "") for column in columns)
            if any(not value for value in key):
                issues.append(f"{name} has null primary identity")
                break
            if key in seen:
                issues.append(f"{name} has duplicate primary identity {key}")
                break
            seen.add(key)
    for name in SEASON_TABLES:
        if any(str(row.get("season_id")) != season_id or row.get("season_label") != season
               for row in tables[name]):
            issues.append(f"{name} has wrong season identity")

    expected_fixtures = {row["match_id"]: row for row in
                         fixture_lookup(PilotStore(load_config()))[season]}
    raw_links = set()
    raw_sources = {}
    for match_id, fixture in expected_fixtures.items():
        item = current.lookup("matchDetails", {"matchId": int(match_id)}, season) or old.lookup(
            "matchDetails", {"matchId": int(match_id)}, season)
        if item is None:
            issues.append(f"Missing raw match detail for fixture {match_id}")
            break
        meta, payload = item
        if verify_detail(payload, fixture)[0] != "ACCEPTED":
            issues.append(f"Unverified raw fixture context: {match_id}")
            break
        lineup = (payload.get("content") or {}).get("lineup") or {}
        if lineup.get("lineupType") != "standard":
            issues.append(f"Non-standard raw lineup: {match_id}")
            break
        raw_sources[match_id] = meta["source_id"]
        for side, team_id in (("homeTeam", fixture["home_team_id"]),
                              ("awayTeam", fixture["away_team_id"])):
            team = lineup.get(side) or {}
            if str(team.get("id")) != team_id:
                issues.append(f"Raw lineup team mismatch: {match_id}")
                break
            if not isinstance(team.get("starters"), list) or len(team["starters"]) != 11 or not isinstance(team.get("subs"), list):
                issues.append(f"Incomplete raw lineup lists: {match_id}")
                break
            for role in ("starters", "subs"):
                for member in team.get(role) or []:
                    player_id = str(member.get("id"))
                    if not player_id.isdigit():
                        issues.append(f"Invalid raw lineup player ID: {match_id}")
                        break
                    entered = role == "starters" or any(
                        event.get("type") == "subIn" for event in
                        ((member.get("performance") or {}).get("substitutionEvents") or [])
                        if isinstance(event, dict))
                    if entered:
                        raw_links.add((player_id, match_id, team_id))
        if issues:
            break
    matches = {str(row["match_id"]): row for row in tables["matches"]}
    if len(expected_fixtures) != 380 or set(matches) != set(expected_fixtures):
        issues.append("Match table does not equal the 380 finished fixtures")
    else:
        for match_id, fixture in expected_fixtures.items():
            row = matches[match_id]
            if (row.get("status") != "FINISHED" or
                str(row.get("home_team_id")) != fixture["home_team_id"] or
                str(row.get("away_team_id")) != fixture["away_team_id"] or
                str(row.get("match_date_utc"))[:10] != fixture["match_date_utc"][:10]):
                issues.append(f"Fixture context mismatch: {match_id}")
                break

    appeared_links = {tuple(map(str, item)) for item in population.get("appeared_match_links", [])}
    if not raw_links or raw_links != appeared_links:
        issues.append(f"Population checkpoint differs from raw lineups: raw={len(raw_links)}, checkpoint={len(appeared_links)}")
    actual_links = {(str(row["player_id"]), str(row["match_id"]), str(row["team_id"]))
                    for row in tables["player_match_links"]}
    if actual_links != appeared_links:
        issues.append(f"Appearance coverage differs: checkpoint={len(appeared_links)}, table={len(actual_links)}")
    if any(row.get("source_id") != raw_sources.get(str(row["match_id"]))
           for row in tables["player_match_links"]):
        issues.append("Player-match lineage differs from raw match detail")
    relations = {tuple(map(str, item)) for item in population.get("appeared_relations", [])}
    if relations != {(pid, team_id) for pid, _, team_id in raw_links}:
        issues.append("Appeared club relations differ from raw lineups")
    actual_relations = {(str(row["player_id"]), str(row["team_id"]))
                        for row in tables["player_team_seasons"]}
    if not relations.issubset(actual_relations):
        issues.append(f"Missing {len(relations - actual_relations)} appeared player-club relations")
    appeared_players = set(map(str, population.get("appeared_player_ids", [])))
    if appeared_players != {pid for pid, _, _ in raw_links}:
        issues.append("Appeared player IDs differ from raw lineups")
    for name in ("players", "player_seasons"):
        actual = {str(row["player_id"]) for row in tables[name]}
        if not appeared_players.issubset(actual):
            issues.append(f"{name} misses {len(appeared_players - actual)} appeared players")

    with (ROOT / "reports/phase_02b0/metric_dictionary_v2.csv").open(encoding="utf-8", newline="") as handle:
        metric_units = {row["normalized_field"]: row["unit"] for row in csv.DictReader(handle)}
    for row in tables["metric_observations"]:
        status = row.get("status")
        value = row.get("value")
        if status not in ("AVAILABLE", "MISSING", "NOT_APPLICABLE", "UNSUPPORTED", "UNPARSEABLE"):
            issues.append(f"Unknown metric status: {status}")
            break
        if (status == "AVAILABLE") != (value is not None):
            issues.append("Metric status and value disagree; missing values cannot be zero-filled")
            break
        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
            issues.append("Metric has a non-finite or non-numeric value")
            break
        expected_unit = metric_units.get(row.get("metric"))
        if expected_unit is None:
            issues.append(f"Metric is absent from dictionary: {row.get('metric')}")
            break
        if expected_unit and row.get("unit") != expected_unit:
            issues.append(f"Metric unit mismatch: {row.get('metric')}")
            break

    known_sources = {meta["source_id"] for registry in (old, current)
                     for meta, _ in registry.captures() if meta.get("source_id")}
    for name, field in (("players", "profile_source_id"), ("teams", "source_ids"),
                        ("player_seasons", "stats_source_id"),
                        ("player_team_seasons", "reference_source_ids"),
                        ("matches", "source_id"), ("player_match_links", "source_id"),
                        ("metric_observations", "source_id")):
        for row in tables[name]:
            ids = _tokens(row.get(field))
            required = name in ("matches", "player_match_links") or (
                name in ("players", "player_seasons") and str(row.get("player_id")) in appeared_players) or (
                name == "metric_observations" and row.get("status") == "AVAILABLE")
            if required and not ids:
                issues.append(f"{name} has missing source lineage")
                break
            if any(source not in known_sources for source in ids):
                issues.append(f"{name} has unresolved source lineage")
                break
    return {"issues": issues, "counts": counts}
