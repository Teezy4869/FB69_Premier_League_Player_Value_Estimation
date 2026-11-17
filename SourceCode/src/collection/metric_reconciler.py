"""Versioned metric semantics and conservative cross-source comparisons."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from src.audit.normalization import leaderboard_rows, player_stat_items
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.normalize_pilot import METRICS
from src.collection.player_reference import write_csv
from src.collection.source_registry import SourceRegistry, load_hardening_config

VERSION = "2.0"
DICT_FIELDS = ["dictionary_version", "normalized_field", "original_source_fields", "source_titles",
               "unit", "aggregation_type", "applicable_positions", "candidate_source_endpoints",
               "historical_seasons_with_values", "sample_available", "sample_missing",
               "sample_not_applicable", "sample_unsupported", "validation_status", "source_preference",
               "normalization_rule", "allowed_missing_states", "conflict_rule", "provenance_requirements"]
RECON_FIELDS = ["season_label", "season_id", "player_id", "team_id", "metric",
                "leaderboard_original_field", "leaderboard_raw_value", "leaderboard_main_value",
                "player_stats_original_field", "player_stats_raw_value", "unit", "aggregation_type",
                "leaderboard_source_id", "player_stats_source_id", "leaderboard_evidence_path",
                "player_stats_evidence_path", "profile_season_entry", "context_status",
                "comparison_status", "difference", "resolution", "source_preference"]


def classify_metric(metric: str) -> str:
    if metric in ("appearances", "starts"):
        return "VERIFIED"
    if metric == "key_passes":
        return "UNVERIFIED"
    if metric == "rating":
        return "EXCLUDED_FOR_NOW"
    if METRICS[metric][3]:
        return "POSITION_SPECIFIC"
    return "PARTIAL"


def dictionary_rows() -> list[dict]:
    config = load_config()
    obs = pq.read_table(ROOT / config["normalized_dir"] / "metric_observations.parquet").to_pylist()
    by_metric = defaultdict(list)
    for r in obs:
        by_metric[r["metric"]].append(r)
    rows = []
    for metric, (fields, unit, kind, goalkeeper_only) in METRICS.items():
        values = by_metric[metric]
        counts = Counter(r["status"] for r in values)
        observed_fields = sorted({r["original_field"] for r in values if r["original_field"]})
        titles = sorted({r["source_title"] for r in values if r["source_title"]})
        endpoints = sorted({r["source_endpoint"] for r in values if r["source_endpoint"]})
        seasons = {r["season_label"] for r in values if r["status"] == "AVAILABLE"}
        rows.append({"dictionary_version": VERSION, "normalized_field": metric,
                     "original_source_fields": "|".join(observed_fields or fields),
                     "source_titles": "|".join(titles), "unit": unit,
                     "aggregation_type": kind, "applicable_positions": "GK_ONLY" if goalkeeper_only else "ALL",
                     "candidate_source_endpoints": "|".join(endpoints),
                     "historical_seasons_with_values": len(seasons),
                     "sample_available": counts["AVAILABLE"], "sample_missing": counts["MISSING"],
                     "sample_not_applicable": counts["NOT_APPLICABLE"],
                     "sample_unsupported": counts["UNSUPPORTED"],
                     "validation_status": classify_metric(metric),
                     "source_preference": "NONE_UNRESOLVED" if metric == "minutes_played" else
                                          "PLAYER_STATS_ONLY_OBSERVED" if endpoints == ["playerStats"] else
                                          "NO_CONFLICT_OBSERVED_IN_PILOT",
                     "normalization_rule": "Read playerStats.statValue as season value; retain source_per90 separately; "
                                           "no zero imputation. Leaderboard saves compare substatValue only when "
                                           "substatTitle=Total saves. Narrow source fields are not generic synonyms.",
                     "allowed_missing_states": "MISSING|NOT_APPLICABLE|UNSUPPORTED|UNPARSEABLE",
                     "conflict_rule": "Compare only same player, season, team, unit and aggregation; "
                                      "retain both raw values; unequal numeric values are UNRESOLVED",
                     "provenance_requirements": "source_id, raw path, UTC timestamp, original field/value, unit, season entry"})
    return rows


def reconciliation_rows() -> list[dict]:
    config = load_config()
    pilot = PilotStore(config)
    registry = SourceRegistry(load_hardening_config())
    path_by_source = {m["source_id"]: m["raw_path"] for m, _ in registry.captures()
                      if m["endpoint"] in ("playerStats", "leagueseasondeepstats")}
    boards = {}
    for meta, payload in pilot.cached_payloads("leagueseasondeepstats"):
        metric = meta["params"].get("stat")
        if metric not in ("mins_played", "goals", "saves"):
            continue
        boards[(meta["season_label"], metric)] = (meta, payload,
            {(str(r["id"]), str(r["teamId"])): r for r in leaderboard_rows(payload)})
    stats = {m["source_id"]: (m, p) for m, p in pilot.cached_payloads("playerStats")}
    sample = []
    import csv
    with (ROOT / "reports/phase_02a/pilot_sample_manifest.csv").open(encoding="utf-8", newline="") as handle:
        sample = list(csv.DictReader(handle))
    rows = []
    for r in sample:
        season, pid, tid = r["season_label"], r["fotmob_player_id"], r["fotmob_team_id"]
        stats_id = f"stats_{season.replace('/', '_')}_{pid}"
        if stats_id not in stats:
            continue
        stats_meta, stats_payload = stats[stats_id]
        items = player_stat_items(stats_payload)
        for board_metric, profile_field, unit in (("mins_played", "minutes_played", "minutes"),
                                                   ("goals", "goals", "count"),
                                                   ("saves", "saves", "count")):
            board = boards.get((season, board_metric))
            if board is None or profile_field not in items:
                continue
            board_meta, board_payload, by_key = board
            item = by_key.get((pid, tid))
            if item is None:
                continue
            if board_metric == "saves":
                if board_payload.get("substatTitle") != "Total saves":
                    continue
                raw_board = (item.get("substatValue") or {}).get("value")
                board_field = "substatValue.value (Total saves)"
            else:
                raw_board = (item.get("statValue") or {}).get("value")
                board_field = "statValue.value"
            raw_profile = items[profile_field].get("statValue")
            if raw_board is None or raw_profile is None:
                continue
            try:
                left = float(str(raw_board).replace(",", ""))
                right = float(str(raw_profile).replace(",", ""))
                same = left == right
                difference = left - right
            except ValueError:
                same = str(raw_board) == str(raw_profile)
                difference = ""
            rows.append({"season_label": season, "season_id": r["fotmob_season_id"],
                         "player_id": pid, "team_id": tid, "metric": "minutes_played" if
                         board_metric == "mins_played" else board_metric,
                         "leaderboard_original_field": board_field,
                         "leaderboard_raw_value": raw_board,
                         "leaderboard_main_value": (item.get("statValue") or {}).get("value"),
                         "player_stats_original_field": profile_field + ".statValue",
                         "player_stats_raw_value": raw_profile,
                         "unit": unit, "aggregation_type": "total",
                         "leaderboard_source_id": board_meta["source_id"],
                         "player_stats_source_id": stats_id,
                         "leaderboard_evidence_path": path_by_source[board_meta["source_id"]],
                         "player_stats_evidence_path": path_by_source[stats_id],
                         "profile_season_entry": stats_meta["params"]["seasonId"],
                         "context_status": "SAME_SEASON_PLAYER_TEAM_BOARD_AND_VERIFIED_PROFILE_ENTRY",
                         "comparison_status": "AGREE" if same else "UNRESOLVED",
                         "difference": difference,
                         "resolution": "Same raw values" if same else
                                       "Retain both; integer minute difference has no documented rounding or team-split explanation",
                         "source_preference": "NONE"})
    return rows


def execute() -> dict:
    dictionary = dictionary_rows()
    comparisons = reconciliation_rows()
    report_dir = ROOT / "reports/phase_02b0"
    write_csv(report_dir / "metric_dictionary_v2.csv", DICT_FIELDS, dictionary)
    write_csv(report_dir / "metric_reconciliation_report.csv", RECON_FIELDS, comparisons)
    return {"metrics": len(dictionary), "classification_counts": dict(Counter(r["validation_status"] for r in dictionary)),
            "comparisons": len(comparisons), "conflicts": [r for r in comparisons if r["comparison_status"] != "AGREE"]}


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2))
