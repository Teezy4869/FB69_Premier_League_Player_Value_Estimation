"""Normalize varied FotMob JSON shapes without converting excerpts into full data."""

from __future__ import annotations

from collections import defaultdict


def leaderboard_rows(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("statsData")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("players", "data", "items"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    return []


def stat_catalog(payload: dict | None) -> dict[str, dict]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("statsList")
    if isinstance(data, dict):
        data = data.get("items") or []
    if not isinstance(data, list):
        return {}
    return {x["name"]: x for x in data if isinstance(x, dict) and isinstance(x.get("name"), str)}


def player_stat_items(payload: dict | None) -> dict[str, dict]:
    if not isinstance(payload, dict):
        return {}
    result = {}

    def walk(value):
        if isinstance(value, dict):
            key = value.get("localizedTitleId")
            if isinstance(key, str) and "statValue" in value:
                result[key] = value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload.get("topStatCard"))
    walk(payload.get("statsSection"))
    return result


def season_profile_entry(profile: dict | None, season: str, league_id: int) -> dict | None:
    if not isinstance(profile, dict):
        return None
    for entry in profile.get("statSeasons") or []:
        if not isinstance(entry, dict) or entry.get("seasonName") != season:
            continue
        for tournament in entry.get("tournaments") or []:
            if isinstance(tournament, dict) and str(tournament.get("tournamentId")) == str(league_id):
                return tournament
    return None


def coverage_facts(boards: dict[str, list[dict]]) -> dict:
    player_teams: dict[str, set[str]] = defaultdict(set)
    player_positions: dict[str, set[str]] = defaultdict(set)
    all_teams = set()
    by_metric = {}
    missing = {"id": 0, "teamId": 0, "position": 0, "statValue.value": 0}
    for metric, rows in boards.items():
        ids = [str(row["id"]) for row in rows if row.get("id") is not None]
        teams = {str(row["teamId"]) for row in rows if row.get("teamId") is not None}
        by_metric[metric] = {"row_count": len(rows), "unique_player_count": len(set(ids)),
                             "duplicate_player_rows": len(ids) - len(set(ids)),
                             "team_count": len(teams)}
        all_teams.update(teams)
        for row in rows:
            for field in ("id", "teamId", "position"):
                if row.get(field) is None:
                    missing[field] += 1
            if (row.get("statValue") or {}).get("value") is None:
                missing["statValue.value"] += 1
            if row.get("id") is None:
                continue
            pid = str(row["id"])
            if row.get("teamId") is not None:
                player_teams[pid].add(str(row["teamId"]))
            if row.get("position") is not None:
                player_positions[pid].add(str(row["position"]))
    return {"by_metric": by_metric, "sample_unique_player_count": len(player_teams),
            "sample_team_count": len(all_teams),
            "sample_team_ids": sorted(all_teams), "sample_missing_fields": missing,
            "sample_multi_team_player_count": sum(len(teams) > 1 for teams in player_teams.values()),
            "sample_multi_team_player_ids": [pid for pid, teams in player_teams.items() if len(teams) > 1][:20],
            "position_codes_observed": sorted({code for values in player_positions.values() for code in values}),
            "unique_ids": set(player_teams)}


def fixture_facts(league_payload: dict | None) -> dict:
    fixtures = ((league_payload or {}).get("fixtures") or {}).get("allMatches") or []
    if not isinstance(fixtures, list):
        fixtures = []
    ids = [str(x["id"]) for x in fixtures if isinstance(x, dict) and x.get("id") is not None]
    dated = sum(bool((x.get("status") or {}).get("utcTime")) for x in fixtures if isinstance(x, dict))
    teams = {str(team.get("id")) for x in fixtures if isinstance(x, dict)
             for team in (x.get("home") or {}, x.get("away") or {}) if isinstance(team, dict) and team.get("id") is not None}
    results = sum(bool((x.get("status") or {}).get("scoreStr")) for x in fixtures if isinstance(x, dict))
    return {"fixtures": fixtures, "record_count": len(fixtures), "unique_match_ids": len(set(ids)),
            "dated_count": dated, "team_id_count": len(teams), "result_count": results,
            "first_match_id": ids[0] if ids else None}


def lineup_player_ids(match_payload: dict | None) -> set[str]:
    lineup = (((match_payload or {}).get("content") or {}).get("lineup") or {})
    result = set()
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for group in ("starters", "subs"):
            for player in team.get(group) or []:
                if isinstance(player, dict) and player.get("id") is not None:
                    result.add(str(player["id"]))
    return result
