"""Report bounded leaderboard samples without claiming full league coverage."""

from __future__ import annotations

from .normalization import coverage_facts, leaderboard_rows


def coverage_row(season: str, league_team_count: int, boards: dict,
                 evidence: dict, goalkeeper_profile_confirmed: bool) -> dict:
    rows = {key: leaderboard_rows(boards.get(key)) for key in ("goals", "mins_played", "saves")}
    facts = coverage_facts(rows)
    board_facts = facts["by_metric"]
    return {"season": season, "status": "SAMPLE_COVERAGE" if facts["sample_unique_player_count"] else "UNKNOWN_DENOMINATOR",
            "denominator_status": "UNKNOWN_DENOMINATOR", "reference_player_count": "",
            "reference_team_count": league_team_count,
            "sample_unique_player_ids": facts["sample_unique_player_count"],
            "sample_player_id_list": "|".join(sorted(facts["unique_ids"])),
            "sample_teams_represented": facts["sample_team_count"],
            "sample_team_id_list": "|".join(facts["sample_team_ids"]),
            "goals_rows": board_facts["goals"]["row_count"],
            "goals_unique_ids": board_facts["goals"]["unique_player_count"],
            "minutes_rows": board_facts["mins_played"]["row_count"],
            "minutes_unique_ids": board_facts["mins_played"]["unique_player_count"],
            "saves_rows": board_facts["saves"]["row_count"],
            "saves_unique_ids": board_facts["saves"]["unique_player_count"],
            "duplicate_id_rows_within_boards": sum(v["duplicate_player_rows"] for v in board_facts.values()),
            "multi_team_ids_across_boards": facts["sample_multi_team_player_count"],
            "multi_team_ids_sample": "|".join(facts["sample_multi_team_player_ids"]),
            "position_codes_observed": "|".join(facts["position_codes_observed"]),
            "missing_id_rows": facts["sample_missing_fields"]["id"],
            "missing_team_id_rows": facts["sample_missing_fields"]["teamId"],
            "missing_position_rows": facts["sample_missing_fields"]["position"],
            "missing_stat_value_rows": facts["sample_missing_fields"]["statValue.value"],
            "goalkeeper_profile_confirmed": goalkeeper_profile_confirmed,
            "general_statistics_checked": "goals|mins_played|saves; other general fields from catalog/profile samples",
            "missing_field_scope": "Missing counts cover only three sampled leaderboard tables; other feature row-level missingness unknown",
            "coverage_warning": "Union of three leaderboard responses is a sampled numerator, not total league player population",
            "source_endpoint": "leagueseasondeepstats",
            "sample_files": "|".join(evidence.get(k, {}).get("sample_file", "") for k in ("goals", "mins_played", "saves")),
            "source_urls": "|".join(evidence.get(k, {}).get("source_url", "") for k in ("goals", "mins_played", "saves")),
            "collected_at_utc": evidence.get("goals", {}).get("timestamp_utc", "")}
