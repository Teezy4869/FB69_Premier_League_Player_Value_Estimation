"""Exact-code, match-evidence position registry; never classify by numeric ranges."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write, json_bytes
from src.collection.historical_identity import read_csv
from src.collection.player_reference import candidate_views, write_csv
from src.collection.source_registry import SourceRegistry, load_hardening_config

VERSION = "2.0"
# These are empirical broad labels for *usualPlayingPositionId in historical lineup
# responses*, not arithmetic bands for lineup or leaderboard positionId.
USUAL_GROUP = {"0": "GK", "1": "DEF", "2": "MID", "3": "FWD"}
GROUP_NAME = {"GK": "Goalkeeper", "DEF": "Defender", "MID": "Midfielder", "FWD": "Forward"}
REPORT_FIELDS = ["season_label", "season_id", "player_id", "player_name", "leaderboard_position_code",
                 "pilot_code_band_group", "historical_lineup_position_codes", "historical_usual_position_codes",
                 "historical_group_inferred", "historical_evidence_paths", "current_profile_position",
                 "validation_status", "pilot_group_conflict", "note"]


def historical_starters(registry: SourceRegistry) -> list[dict]:
    rows = []
    for meta, payload in registry.captures():
        if meta["endpoint"] != "matchDetails":
            continue
        lineup = ((payload.get("content") or {}).get("lineup") or {})
        if lineup.get("lineupType") != "standard":
            continue
        for side in ("homeTeam", "awayTeam"):
            team = lineup.get(side) or {}
            for player in team.get("starters") or []:
                pid = player.get("id")
                if pid is None:
                    continue
                rows.append({"season_label": meta["season_label"], "player_id": str(pid),
                             "team_id": str(team.get("id")), "match_id": str(meta["params"]["matchId"]),
                             "position_id": str(player.get("positionId")) if player.get("positionId") is not None else "",
                             "usual_id": str(player.get("usualPlayingPositionId")) if
                                         player.get("usualPlayingPositionId") is not None else "",
                             "raw_path": meta["raw_path"]})
    return rows


def exact_code_mapping(code: str, observations: list[dict], source_field: str) -> dict:
    usual = Counter(r["usual_id"] for r in observations if r["usual_id"] in USUAL_GROUP)
    groups = {USUAL_GROUP[k] for k in usual}
    group = next(iter(groups)) if len(groups) == 1 and sum(usual.values()) >= 2 else "UNKNOWN"
    return {"original_fotmob_code": code, "source_field": source_field,
            "normalized_position_name": GROUP_NAME.get(group, "UNKNOWN") if group != "UNKNOWN" else "UNKNOWN",
            "broader_position_group": group, "source_endpoint": "matchDetails" if source_field == "positionId" else
                                                            "leagueseasondeepstats",
            "supporting_raw_evidence": sorted({r["raw_path"] for r in observations}),
            "historical_applicability": "MATCH_SCOPED" if source_field == "positionId" else
                                        "SEASON_BOARD_CODE_WITH_MATCH_CORROBORATION",
            "mapping_status": "HISTORICAL_INFERRED" if group != "UNKNOWN" else "UNKNOWN",
            "mapping_version": VERSION, "observed_count": len(observations),
            "usual_playing_position_id_counts": dict(sorted(usual.items())),
            "rule": "Exact code only; unanimous observed usualPlayingPositionId group and >=2 historical lineup observations"}


def build() -> tuple[dict, list[dict], dict]:
    pilot = PilotStore(load_config())
    registry = SourceRegistry(load_hardening_config())
    candidates, _ = candidate_views(pilot)
    starters = historical_starters(registry)
    by_player = defaultdict(list)
    by_position = defaultdict(list)
    for r in starters:
        by_player[(r["season_label"], r["player_id"])].append(r)
        if r["position_id"]:
            by_position[r["position_id"]].append(r)
    registry_rows = [exact_code_mapping(code, obs, "positionId") for code, obs in
                     sorted(by_position.items(), key=lambda kv: int(kv[0]))]
    # Corroborate leaderboard code with lineups of the *same player and season*.
    by_board_code = defaultdict(list)
    for r in candidates:
        code = str(r["position"])
        for observation in by_player.get((r["season_label"], r["fotmob_player_id"]), []):
            by_board_code[code].append(observation)
    all_codes = {str(r["position"]) for r in candidates if str(r["position"])}
    registry_rows += [exact_code_mapping(code, by_board_code.get(code, []), "leaderboard.position")
                      for code in sorted(all_codes, key=int)]
    # Values of usualPlayingPositionId are retained separately from exact formation slots.
    for usual_code, group in USUAL_GROUP.items():
        supporting = [r for r in starters if r["usual_id"] == usual_code]
        registry_rows.append({"original_fotmob_code": usual_code,
            "source_field": "usualPlayingPositionId", "normalized_position_name": GROUP_NAME[group],
            "broader_position_group": group, "source_endpoint": "matchDetails",
            "supporting_raw_evidence": sorted({r["raw_path"] for r in supporting}),
            "historical_applicability": "HISTORICAL_LINEUP_USUAL_ROLE_FIELD_NOT_FORMATION_SLOT",
            "mapping_status": "HISTORICAL_INFERRED" if supporting else "UNKNOWN",
            "mapping_version": VERSION, "observed_count": len(supporting),
            "usual_playing_position_id_counts": {usual_code: len(supporting)},
            "rule": "Empirical source role code; broad group inferred from corroborating historical lineup slots, not a numeric range"})
    profiles = read_csv(ROOT / "reports/phase_02a/pilot_player_profiles.csv")
    profile_by_key = {(r["season_label"], r["player_id"]): r for r in profiles}
    sample = read_csv(ROOT / "reports/phase_02a/pilot_sample_manifest.csv")
    report = []
    for r in sample:
        season, pid = r["season_label"], r["fotmob_player_id"]
        obs = by_player.get((season, pid), [])
        usual_codes = sorted({o["usual_id"] for o in obs if o["usual_id"]}, key=int)
        groups = sorted({USUAL_GROUP[c] for c in usual_codes if c in USUAL_GROUP})
        inferred = "|".join(groups) if groups else "UNKNOWN"
        old_group = r["position_group"]
        conflict = inferred != "UNKNOWN" and old_group != inferred
        current_profile = profile_by_key.get((season, pid), {})
        report.append({"season_label": season, "season_id": r["fotmob_season_id"],
                       "player_id": pid, "player_name": r["player_name"],
                       "leaderboard_position_code": r["historical_position_code"],
                       "pilot_code_band_group": old_group,
                       "historical_lineup_position_codes": "|".join(sorted({o["position_id"] for o in obs if o["position_id"]}, key=int)),
                       "historical_usual_position_codes": "|".join(usual_codes),
                       "historical_group_inferred": inferred,
                       "historical_evidence_paths": "|".join(sorted({o["raw_path"] for o in obs})),
                       "current_profile_position": current_profile.get("current_position", ""),
                       "validation_status": "HISTORICAL_INFERRED" if obs and inferred != "UNKNOWN" else "UNKNOWN",
                       "pilot_group_conflict": conflict,
                       "note": "All observed match codes retained; current profile role is not historical"})
    data = {"mapping_version": VERSION,
            "scope_note": "Exact source codes only. Group labels are inferred from historical lineup usualPlayingPositionId; no numeric-range mapping is accepted as verified history. Multiple observed match positions are retained.",
            "mappings": registry_rows}
    return data, report, {"lineup_starter_observations": len(starters),
                          "mapping_rows": len(registry_rows), "sample_rows": len(report),
                          "sample_with_lineup": sum(bool(r["historical_evidence_paths"]) for r in report),
                          "pilot_group_conflicts": sum(r["pilot_group_conflict"] for r in report)}


def execute() -> dict:
    data, report, facts = build()
    report_dir = ROOT / "reports/phase_02b0"
    atomic_write(report_dir / "position_mapping_registry.json", json_bytes(data))
    write_csv(report_dir / "position_validation_report.csv", REPORT_FIELDS, report)
    return facts


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2))
