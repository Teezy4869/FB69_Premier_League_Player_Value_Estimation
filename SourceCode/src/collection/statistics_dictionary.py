"""Extend metric dictionary v2 with observed, semantically narrow season metrics."""
from __future__ import annotations

import csv

from src.collection.collection_config import ROOT
from src.collection.normalize_pilot import METRICS
from src.collection.statistics_catalog import board_spec, load_statistics_config, write_csv


# Each added field was observed in saved playerStats, a saved statsList, or both.
# Source titles are narrow; we do not equate a season total to a per-90 ranking.
EXTRAS = {
    "big_chances_created": ("big_chance_created_team_title", "Big chances created", "count", "total", "ALL", "ATTACK"),
    "non_penalty_xg": ("non_penalty_xg", "xG excl. penalty", "expected goals", "total", "ALL", "EXPECTED"),
    "expected_goals_on_target": ("expected_goals_on_target", "xGOT", "expected goals", "total", "ALL", "EXPECTED"),
    "save_percentage": ("save_percentage", "Save percentage", "percent", "percentage", "GK_ONLY", "GOALKEEPING"),
    "penalty_saves": ("penalty_saves", "Penalty saves", "count", "total", "GK_ONLY", "GOALKEEPING"),
    "successful_crosses": ("crosses_succeeeded", "Successful crosses", "count", "total", "ALL", "PASSING"),
    "cross_accuracy": ("crosses_succeeeded_accuracy", "Cross accuracy", "percent", "percentage", "ALL", "PASSING"),
    "long_ball_accuracy": ("long_ball_succeeeded_accuracy", "Long ball accuracy", "percent", "percentage", "ALL", "PASSING"),
    "recoveries": ("recoveries", "Recoveries", "count", "total", "ALL", "DEFENDING"),
    "fouls_committed": ("fouls", "Fouls committed", "count", "total", "ALL", "DEFENDING"),
    "fouls_won": ("fouls_won", "Fouls won", "count", "total", "ALL", "DEFENDING"),
    "yellow_cards": ("yellow_cards", "Yellow cards", "count", "total", "ALL", "GENERAL"),
    "red_cards": ("red_cards", "Red cards", "count", "total", "ALL", "GENERAL"),
    "aerials_won": ("aerials_won", "Aerials won", "count", "total", "ALL", "DEFENDING"),
    "aerials_won_percent": ("aerials_won_percent", "Aerials won %", "percent", "percentage", "ALL", "DEFENDING"),
    "touches": ("touches", "Touches", "count", "total", "ALL", "GENERAL"),
    "touches_opposition_box": ("touches_opp_box", "Touches in opposition box", "count", "total", "ALL", "ATTACK"),
    "dribbles_succeeded": ("dribbles_succeeded", "Dribbles", "count", "total", "ALL", "ATTACK"),
    "duels_won_percent": ("duel_won_percent", "Duels won %", "percent", "percentage", "ALL", "DEFENDING"),
    "shots_per90": ("shots.per90", "Shots per 90", "count", "per90", "ALL", "ATTACK"),
    "shots_on_target_per90": ("ShotsOnTarget.per90", "Shots on target per 90", "count", "per90", "ALL", "ATTACK"),
    "accurate_passes_per90": ("successful_passes.per90", "Accurate passes per 90", "count", "per90", "ALL", "PASSING"),
    "accurate_long_passes_per90": ("long_balls_accurate.per90", "Accurate long balls per 90", "count", "per90", "ALL", "PASSING"),
    "tackles_per90": ("matchstats.headers.tackles.per90", "Tackles per 90", "count", "per90", "ALL", "DEFENDING"),
    "interceptions_per90": ("interceptions.per90", "Interceptions per 90", "count", "per90", "ALL", "DEFENDING"),
    "clearances_per90": ("clearances.per90", "Clearances per 90", "count", "per90", "ALL", "DEFENDING"),
    "blocks_per90": ("blocked_shots.per90", "Blocks per 90", "count", "per90", "ALL", "DEFENDING"),
    "recoveries_per90": ("recoveries.per90", "Recoveries per 90", "count", "per90", "ALL", "DEFENDING"),
    "goals_conceded_per90": ("goals_conceded.per90", "Goals conceded per 90", "count", "per90", "GK_ONLY", "GOALKEEPING"),
}

GROUPS = {
    "appearances": "GENERAL", "minutes_played": "GENERAL", "starts": "GENERAL", "rating": "GENERAL",
    "goals": "ATTACK", "assists": "ATTACK", "shots": "ATTACK", "shots_on_target": "ATTACK",
    "expected_goals": "EXPECTED", "expected_assists": "EXPECTED", "accurate_passes": "PASSING",
    "passing_accuracy": "PASSING", "chances_created": "PASSING", "key_passes": "PASSING",
    "accurate_long_passes": "PASSING", "tackles": "DEFENDING", "interceptions": "DEFENDING",
    "clearances": "DEFENDING", "blocked_shots": "DEFENDING", "duels_won": "DEFENDING",
    "saves": "GOALKEEPING", "goals_conceded": "GOALKEEPING", "clean_sheets": "GOALKEEPING",
    "goals_prevented": "GOALKEEPING",
}


def player_field_map() -> dict[str, str]:
    mapping = {}
    for metric, (aliases, _, _, _) in METRICS.items():
        for alias in aliases:
            if alias not in ("mins_played", "accurate_pass", "total_att_assist", "accurate_long_balls",
                             "total_tackle", "interception", "effective_clearance", "outfielder_block",
                             "ontarget_scoring_att", "_goals_prevented"):
                mapping[alias] = metric
    for metric, (field, _, _, _, _, _) in EXTRAS.items():
        if not field.endswith(".per90"):
            mapping[field] = metric
    return mapping


def dictionary_rows() -> list[dict]:
    cfg = load_statistics_config()
    with (ROOT / cfg["source_dictionary"]).open(encoding="utf-8", newline="") as handle:
        previous = list(csv.DictReader(handle))
    by_metric = {row["normalized_field"]: dict(row) for row in previous}
    for row in by_metric.values():
        row["dictionary_version"] = "3.0"
        row["metric_group"] = GROUPS[row["normalized_field"]]
        row["provider_definition_status"] = (
            "UNSUPPORTED_SOURCE_FIELD" if row["normalized_field"] == "key_passes" else
            "UNVERIFIED_DEFINITION" if row["normalized_field"] in (
                "expected_goals", "expected_assists", "goals_prevented") else "SOURCE_TITLE_OBSERVED")
    for metric, (field, title, unit, aggregation, positions, group) in EXTRAS.items():
        by_metric[metric] = {"dictionary_version": "3.0", "normalized_field": metric,
            "original_source_fields": field, "source_titles": title, "unit": unit,
            "aggregation_type": aggregation, "applicable_positions": positions,
            "candidate_source_endpoints": "playerStats" if not field.endswith(".per90") else
                "playerStats|leagueseasondeepstats", "historical_seasons_with_values": "",
            "sample_available": "", "sample_missing": "", "sample_not_applicable": "",
            "sample_unsupported": "", "validation_status": "OBSERVED_SOURCE_FIELD",
            "source_preference": "NONE_UNTIL_RECONCILED",
            "normalization_rule": "Retain raw statValue and per90 separately; null is not zero",
            "allowed_missing_states": "MISSING|NOT_APPLICABLE|UNSUPPORTED|UNVERIFIED|COLLECTION_FAILED",
            "conflict_rule": "Preserve both sources and mark unequal comparable values CONFLICTING",
            "provenance_requirements": "request_key, capture_id, raw path, UTC timestamp, source field, season entry",
            "metric_group": group, "provider_definition_status": "SOURCE_TITLE_OBSERVED"}
    specs = {spec["metric"]: spec for spec in cfg["leaderboard_specs"]}
    for metric, row in by_metric.items():
        if metric in specs:
            row["unit"] = specs[metric]["unit"]
            row["aggregation_type"] = specs[metric]["aggregation"]
        elif metric == "passing_accuracy":
            row["unit"] = "percent"
        row["leaderboard_stat"] = specs.get(metric, {}).get("stat", "")
        row["leaderboard_aggregation"] = specs.get(metric, {}).get("aggregation", "")
    return [by_metric[key] for key in sorted(by_metric)]


def write_dictionary() -> list[dict]:
    rows = dictionary_rows()
    fields = list(rows[0])
    write_csv(ROOT / load_statistics_config()["dictionary_v3"], rows, fields)
    return rows


if __name__ == "__main__":
    import json
    rows = write_dictionary()
    print(json.dumps({"dictionary_version": "3.0", "metrics": len(rows),
                      "new_metrics": len(EXTRAS), "original_metrics": len(METRICS)}))
