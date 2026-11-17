"""Checks that distinguish populated historical data from an HTTP 200."""

from __future__ import annotations


def season_link(payload: dict, season: str) -> dict | None:
    stats = payload.get("stats") or {}
    for link in stats.get("seasonStatLinks") or []:
        if isinstance(link, dict) and link.get("Name") == season:
            return link
    return None


def league_facts(payload: dict, expected_league_id: int, season: str) -> dict:
    details = payload.get("details") or {}
    table = payload.get("table") or []
    teams = []
    for section in table:
        if not isinstance(section, dict):
            continue
        data = section.get("data") or {}
        standings = data.get("table") or {}
        if isinstance(standings, dict):
            teams.extend(standings.get("all") or [])
    fixtures = (payload.get("fixtures") or {}).get("allMatches") or []
    link = season_link(payload, season)
    valid = (str(details.get("id")) == str(expected_league_id)
             and details.get("selectedSeason") == season
             and details.get("name") == "Premier League")
    return {"valid_league_season": valid, "selected_season": details.get("selectedSeason"),
            "season_id": link.get("TournamentId") if link else None,
            "season_link": link, "team_count": len(teams), "fixture_count": len(fixtures),
            "first_team_id": teams[0].get("id") if teams and isinstance(teams[0], dict) else None,
            "first_match_id": fixtures[0].get("id") if fixtures and isinstance(fixtures[0], dict) else None}


def deep_stats_facts(payload: dict) -> dict:
    stats_data = payload.get("statsData")
    if isinstance(stats_data, list):
        count = len(stats_data)
    elif isinstance(stats_data, dict):
        count = sum(len(value) for value in stats_data.values() if isinstance(value, list))
    else:
        count = 0
    return {"stats_data_count": count, "has_stats_data": count > 0,
            "top_level_keys": list(payload) if isinstance(payload, dict) else []}


def availability(metadata: bool, team_count: int, fixture_count: int, stats_count: int | None) -> str:
    if not metadata:
        return "FAILED"
    if team_count and fixture_count and stats_count and stats_count > 0:
        return "AVAILABLE"
    if team_count or fixture_count or (stats_count and stats_count > 0):
        return "PARTIAL"
    return "EMPTY"
