"""Historical profile cautions and representative match-index checks."""

from __future__ import annotations

from .normalization import fixture_facts, lineup_player_ids, season_profile_entry


def profile_row(season: str, role: str, historical_player: dict, profile: dict | None,
                stats_payload: dict | None, profile_evidence: dict, stats_evidence: dict) -> dict:
    entry = season_profile_entry(profile, season, 47)
    current_team = (profile or {}).get("primaryTeam") or {}
    position = ((profile or {}).get("positionDescription") or {}).get("primaryPosition") or {}
    historical_team_id = historical_player.get("teamId")
    current_team_id = current_team.get("teamId")
    status = "FAILED" if profile is None else ("PARTIAL" if entry else "UNVERIFIED")
    return {"season": season, "sample_role": role, "status": status,
            "player_id": historical_player.get("id", ""),
            "player_name": (profile or {}).get("name", ""),
            "birth_date_utc": ((profile or {}).get("birthDate") or {}).get("utcTime", ""),
            "current_primary_position": position.get("label", ""),
            "current_team_id": current_team_id or "", "current_team_name": current_team.get("teamName", ""),
            "historical_leaderboard_team_id": historical_team_id or "",
            "historical_leaderboard_team_name": historical_player.get("teamName", ""),
            "current_vs_historical_team_id": "DIFFERENT" if current_team_id and historical_team_id and str(current_team_id) != str(historical_team_id) else ("SAME" if current_team_id and historical_team_id else "UNVERIFIED"),
            "season_profile_entry_id": (entry or {}).get("entryId", ""),
            "season_profile_has_deep_stats": (entry or {}).get("hasDeepStats", ""),
            "player_stats_status": "AVAILABLE" if stats_payload else ("FAILED" if entry else "UNVERIFIED"),
            "historical_attribute_scope": "birth date stable; season entry confirms association; primaryTeam and primaryPosition are current profile attributes",
            "profile_source_url": profile_evidence.get("source_url", ""),
            "profile_sample_file": profile_evidence.get("sample_file", ""),
            "stats_source_url": stats_evidence.get("source_url", ""),
            "stats_sample_file": stats_evidence.get("sample_file", ""),
            "collected_at_utc": profile_evidence.get("timestamp_utc", "")}


def match_row(season: str, league: dict | None, detail: dict | None,
              league_evidence: dict, detail_evidence: dict, player_matches_evidence: dict | None) -> dict:
    facts = fixture_facts(league)
    details = (detail or {}).get("general") or {}
    lineups = lineup_player_ids(detail)
    first = facts["fixtures"][0] if facts["fixtures"] else {}
    status = "AVAILABLE" if facts["record_count"] and facts["dated_count"] and facts["team_id_count"] else ("PARTIAL" if facts["record_count"] else ("FAILED" if league is None else "EMPTY"))
    return {"season": season, "status": status, "competition_id": (league or {}).get("details", {}).get("id", ""),
            "fixture_record_count": facts["record_count"], "unique_match_ids": facts["unique_match_ids"],
            "fixtures_with_date": facts["dated_count"], "fixtures_with_result": facts["result_count"],
            "team_ids_represented": facts["team_id_count"],
            "sample_match_id": facts["first_match_id"] or "",
            "sample_match_date_utc": ((first.get("status") or {}).get("utcTime") if isinstance(first, dict) else "") or "",
            "sample_home_team_id": (first.get("home") or {}).get("id", "") if isinstance(first, dict) else "",
            "sample_away_team_id": (first.get("away") or {}).get("id", "") if isinstance(first, dict) else "",
            "sample_result": (first.get("status") or {}).get("scoreStr", "") if isinstance(first, dict) else "",
            "detail_status": "AVAILABLE" if details and str(details.get("matchId")) == str(facts["first_match_id"]) else ("UNVERIFIED" if not detail_evidence else "PARTIAL"),
            "detail_league_id": details.get("leagueId", ""),
            "lineup_player_ids_count": len(lineups),
            "lineup_player_ids_sample": "|".join(sorted(lineups)[:5]),
            "player_to_match_status": "PARTIAL" if lineups else "UNVERIFIED",
            "player_matches_endpoint_status": (player_matches_evidence or {}).get("outcome", "UNVERIFIED"),
            "pagination_note": "league fixtures returned as one allMatches array; no cursor observed; playerMatches pagination unresolved",
            "historical_retrieval_note": "season query returned historical fixture index; season assigned from request, not fixture item",
            "level_2_expansion_feasibility": "PARTIAL" if facts["record_count"] and (details or lineups) else "UNVERIFIED",
            "league_source_url": league_evidence.get("source_url", ""),
            "league_sample_file": league_evidence.get("sample_file", ""),
            "detail_source_url": detail_evidence.get("source_url", ""),
            "detail_sample_file": detail_evidence.get("sample_file", ""),
            "collected_at_utc": league_evidence.get("timestamp_utc", "")}
