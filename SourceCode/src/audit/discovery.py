"""Small endpoint and six-season availability audit."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .client import AuditClient, BudgetExceeded, utc_now
from .validation import availability, deep_stats_facts, league_facts


SOURCES = [
    "https://github.com/pseudo-r/Public-FotMob-API",
    "https://github.com/ccdejene/fotmob-mcp",
    "https://github.com/petmorr/FotMobDataAnalysis",
]

ENDPOINTS = {
    "allLeagues": {"purpose": "Global league directory and ID lookup", "parameters": {}, "level_2_plus": "supporting league identification"},
    "leagues": {"purpose": "League season metadata, standings and match index", "parameters": {"id": "league ID", "season": "YYYY/YYYY for historical requests"}, "level_2_plus": "match index and team metadata"},
    "leagueseasondeepstats": {"purpose": "Season player stat table", "parameters": {"id": "league ID", "season": "numeric TournamentId", "type": "players", "stat": "goals"}, "level_2_plus": "season player statistics"},
    "teams": {"purpose": "Team profile and squad", "parameters": {"id": "team ID"}, "level_2_plus": "team and player identifiers"},
    "playerData": {"purpose": "Player profile and season references", "parameters": {"id": "player ID"}, "level_2_plus": "player profile"},
    "playerMatches": {"purpose": "Paginated player match history", "parameters": {"playerId": "player ID", "parentLeagueId": "league ID", "before": "optional Unix timestamp cursor"}, "level_2_plus": "player match index"},
    "matchDetails": {"purpose": "One match facts, teams and events", "parameters": {"matchId": "match ID"}, "level_2_plus": "match metadata and details"},
}


def _excerpt(value, depth=0, max_depth=5):
    """Keep exact source values in a bounded structural excerpt."""
    if depth >= max_depth:
        return {"_omitted_nested_value": True}
    if isinstance(value, list):
        return {"_original_length": len(value), "items": [_excerpt(item, depth + 1, max_depth) for item in value[:2]]}
    if isinstance(value, dict):
        keys = list(value)
        result = {key: _excerpt(value[key], depth + 1, max_depth) for key in keys[:24]}
        if len(keys) > 24:
            result["_omitted_key_count"] = len(keys) - 24
        return result
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "… [truncated]"
    return value


def save_sample(result: dict, name: str, directory: Path, max_bytes: int, root: Path) -> str | None:
    payload = result["payload"]
    if payload is None and not result["record"].get("response_error"):
        return None
    directory.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = {"error": result["record"]["response_error"]}
    full_pretty_bytes = len(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    needs_excerpt = full_pretty_bytes > max_bytes - 1000
    excerpt = payload
    if needs_excerpt:
        for depth in (5, 4, 3, 2, 1):
            excerpt = _excerpt(payload, max_depth=depth)
            if len(json.dumps(excerpt, ensure_ascii=False, indent=2).encode("utf-8")) <= max_bytes - 1000:
                break
    sample = {"source_url": result["record"]["source_url"],
              "collected_at_utc": result["record"]["timestamp_utc"],
              "http_status": result["record"].get("http_status"),
              "content_type": result["record"].get("content_type"),
              "response_bytes": result["record"].get("response_bytes"),
              "sample_kind": "error_response" if result["payload"] is None else ("structural_excerpt" if needs_excerpt else "complete_response"),
              "payload": excerpt}
    path = directory / f"{name}.json"
    path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.relative_to(root).as_posix()


def endpoint_status(key: str, payload: dict | list | None) -> str:
    if payload is None:
        return "FAILED"
    if not payload:
        return "EMPTY"
    if not isinstance(payload, dict):
        return "PARTIAL"
    checks = {
        "allLeagues": lambda p: bool(p.get("countries")),
        "leagues": lambda p: bool((p.get("details") or {}).get("id") and (p.get("fixtures") or {}).get("allMatches")),
        "leagueseasondeepstats": lambda p: deep_stats_facts(p)["has_stats_data"],
        "teams": lambda p: bool((p.get("details") or {}).get("id") and p.get("squad")),
        "playerData": lambda p: bool(p.get("id") and p.get("name")),
        "playerMatches": lambda p: bool(p.get("matches")),
        "matchDetails": lambda p: bool(p.get("header") and (p.get("content") or {}).get("matchFacts")),
    }
    return "AVAILABLE" if checks[key](payload) else "PARTIAL"


def run(config: dict, root: Path) -> dict:
    dirs = {key: root / value for key, value in config["output_directories"].items()}
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    client = AuditClient(config, dirs["logs"] / "fotmob_requests.jsonl")
    catalog = {key: {"path": f"/api/data/{key}", "documented_by": SOURCES,
                     "documentation_status": "candidate, independently tested below",
                     "live_status": "UNVERIFIED", **spec}
               for key, spec in ENDPOINTS.items()}
    observations = []

    def probe(key: str, params: dict, sample_name: str | None = None):
        try:
            result = client.get(key, params)
        except BudgetExceeded as exc:
            result = {"record": {"timestamp_utc": utc_now(), "source_url": None,
                                  "outcome": "UNVERIFIED", "error": str(exc)}, "payload": None}
        record = result["record"]
        sample = save_sample(result, sample_name, dirs["raw_samples"], config["sample_max_bytes"], root) if sample_name else None
        observations.append({"endpoint": key, "params": params, "sample": sample, **record})
        entry = catalog[key]
        entry["requests_tested"] = entry.get("requests_tested", 0) + (1 if record.get("source_url") else 0)
        entry["last_observed_at_utc"] = record["timestamp_utc"]
        entry["last_source_url"] = record.get("source_url")
        entry["http_status"] = record.get("http_status")
        entry["content_type"] = record.get("content_type")
        entry["response_bytes"] = record.get("response_bytes")
        entry["top_level_keys"] = list(result["payload"])[:30] if isinstance(result["payload"], dict) else []
        if isinstance(result["payload"], dict):
            nested = {}
            for field in ("details", "stats", "fixtures", "squad", "content", "header", "statsData", "matchFilters"):
                value = result["payload"].get(field)
                if isinstance(value, dict):
                    nested[field] = list(value)[:25]
                elif isinstance(value, list):
                    nested[field] = {"record_count": len(value), "first_record_keys": list(value[0])[:25] if value and isinstance(value[0], dict) else []}
            entry["nested_fields_observed"] = nested
        entry["sample"] = sample or entry.get("sample")
        entry["error"] = record.get("error")
        entry["response_error"] = record.get("response_error")
        entry["live_status"] = endpoint_status(key, result["payload"]) if record["outcome"] == "OK" else record["outcome"]
        return result

    directory = probe("allLeagues", {}, "all_leagues")
    league_name_found = False
    if isinstance(directory["payload"], dict):
        for country in directory["payload"].get("countries") or []:
            for league in country.get("leagues") or []:
                if str(league.get("id")) == str(config["league_id_candidate"]) and league.get("name") == "Premier League":
                    league_name_found = True
    current = probe("leagues", {"id": config["league_id_candidate"]}, "league_current")
    current_details = (current["payload"] or {}).get("details") or {}
    league_verified = (league_name_found and str(current_details.get("id")) == str(config["league_id_candidate"])
                       and current_details.get("name") == "Premier League")
    rows = []
    representative = {"team_id": None, "player_id": None, "match_id": None}
    for season in config["seasons"]:
        name = season.replace("/", "_")
        league = probe("leagues", {"id": config["league_id_candidate"], "season": season}, f"league_{name}")
        payload = league["payload"]
        facts = league_facts(payload, config["league_id_candidate"], season) if isinstance(payload, dict) else {}
        if payload is not None and facts.get("season_link"):
            sample_path = dirs["raw_samples"] / f"league_{name}.json"
            sample_doc = json.loads(sample_path.read_text(encoding="utf-8"))
            sample_doc["season_id_evidence"] = facts["season_link"]
            sample_doc["selected_season_evidence"] = facts["selected_season"]
            sample_path.write_text(json.dumps(sample_doc, indent=2, ensure_ascii=False), encoding="utf-8")
        sid = facts.get("season_id")
        deep = None
        stats_count = None
        if isinstance(sid, int):
            deep = probe("leagueseasondeepstats", {"id": config["league_id_candidate"], "season": sid,
                                                    "type": "players", "stat": "goals"}, f"deep_stats_{name}")
            if isinstance(deep["payload"], dict):
                deep_facts = deep_stats_facts(deep["payload"])
                stats_count = deep_facts["stats_data_count"]
                catalog["leagueseasondeepstats"].update({"stats_data_count": stats_count,
                                                            "pagination_observed": list(deep["payload"].keys())})
                if stats_count and representative["player_id"] is None:
                    stats_data = deep["payload"].get("statsData")
                    values = stats_data if isinstance(stats_data, list) else []
                    if values and isinstance(values[0], dict):
                        representative["player_id"] = values[0].get("id") or values[0].get("playerId")
        row = {"season": season, "league_id": config["league_id_candidate"] if league_verified else "",
               "numeric_season_id": sid or "", "metadata_status": "AVAILABLE" if facts.get("valid_league_season") else ("FAILED" if payload is None else "PARTIAL"),
               "team_count": facts.get("team_count", 0), "team_status": "AVAILABLE" if facts.get("team_count") else ("FAILED" if payload is None else "EMPTY"),
               "fixture_count": facts.get("fixture_count", 0), "fixture_status": "AVAILABLE" if facts.get("fixture_count") else ("FAILED" if payload is None else "EMPTY"),
               "player_stat_count": "" if stats_count is None else stats_count,
               "player_stats_status": "UNVERIFIED" if deep is None else ("FAILED" if deep["payload"] is None else ("AVAILABLE" if stats_count else "EMPTY")),
               "overall_status": availability(bool(facts.get("valid_league_season")), facts.get("team_count", 0), facts.get("fixture_count", 0), stats_count),
               "league_http_status": league["record"].get("http_status") or "",
               "deep_stats_http_status": deep["record"].get("http_status") if deep else "",
               "error": "; ".join(x for x in [league["record"].get("error"), deep["record"].get("error") if deep else None] if x),
               "collected_at_utc": league["record"]["timestamp_utc"],
               "league_source_url": league["record"].get("source_url") or "",
               "deep_stats_source_url": deep["record"].get("source_url") if deep else "",
               "league_sample": (dirs["raw_samples"] / f"league_{name}.json").relative_to(root).as_posix() if payload else "",
               "deep_stats_sample": (dirs["raw_samples"] / f"deep_stats_{name}.json").relative_to(root).as_posix() if deep and deep["payload"] else ""}
        rows.append(row)
        if representative["team_id"] is None:
            representative["team_id"] = facts.get("first_team_id")
        if representative["match_id"] is None:
            representative["match_id"] = facts.get("first_match_id")
        if representative["player_id"] is None and isinstance(payload, dict):
            players = (payload.get("stats") or {}).get("players") or []
            if players:
                representative["player_id"] = (players[0].get("participant") or {}).get("id")

    if representative["team_id"]:
        team = probe("teams", {"id": representative["team_id"]}, "team")
        if isinstance(team["payload"], dict):
            catalog["teams"]["has_squad"] = bool(team["payload"].get("squad"))
    if representative["player_id"]:
        player = probe("playerData", {"id": representative["player_id"]}, "player_data")
        if isinstance(player["payload"], dict):
            catalog["playerData"]["has_profile"] = bool(player["payload"].get("name"))
        matches = probe("playerMatches", {"playerId": representative["player_id"],
                                          "parentLeagueId": config["league_id_candidate"]})
        if matches["record"].get("http_status") == 400:
            matches = probe("playerMatches", {"playerId": representative["player_id"],
                                              "before": 1596240000,
                                              "parentLeagueId": config["league_id_candidate"]}, "player_matches")
        if isinstance(matches["payload"], dict):
            catalog["playerMatches"]["pagination_fields"] = [key for key in matches["payload"] if "next" in key.lower() or "before" in key.lower() or "page" in key.lower()]
    if representative["match_id"]:
        match = probe("matchDetails", {"matchId": representative["match_id"]}, "match_details")
        if isinstance(match["payload"], dict):
            catalog["matchDetails"]["has_match_facts"] = bool((match["payload"].get("content") or {}).get("matchFacts"))

    pagination_notes = {
        "allLeagues": "No pagination field observed in the sampled directory; response_bytes is logged.",
        "leagues": "No pagination field observed; sampled response contains allMatches. Large response size is logged.",
        "leagueseasondeepstats": "One stat=goals table per request; no pagination field observed. Other metrics were not probed.",
        "teams": "No pagination field observed in the sampled team response; large response size is logged.",
        "playerData": "No pagination field observed in profile; matchesUrl and initialMatchesPage fields were observed.",
        "playerMatches": "Pagination unverified: both tested parameter variants returned HTTP 400; reference documentation mentions a before cursor.",
        "matchDetails": "One match per request; no pagination field observed.",
    }
    for key, note in pagination_notes.items():
        catalog[key]["pagination_or_size_notes"] = note

    report_dir = dirs["reports"]
    (report_dir / "fotmob_endpoint_catalog.json").write_text(json.dumps({
        "generated_at_utc": utc_now(), "competition": config["competition"],
        "league_id_verified": league_verified, "documentation_sources": SOURCES,
        "http_attempts": client.attempts, "request_budget": config["request_budget"],
        "endpoints": catalog, "observations": observations}, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(rows).to_csv(report_dir / "season_availability.csv", index=False, encoding="utf-8")
    return {"catalog": catalog, "rows": rows, "league_verified": league_verified,
            "attempts": client.attempts, "report_dir": report_dir}
