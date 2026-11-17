"""Evidence-scoped normalization for the 120-row Phase 2A pilot manifest."""
from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq

from src.audit.normalization import leaderboard_rows, player_stat_items, season_profile_entry
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write, json_bytes
from src.collection.phase_02a_03_06 import cache_by_source, match_plan, sample_rows
from src.collection.player_reference import write_csv

# Source-field variants are mapped only when they retain the same meaning.
# Generic key passes, long passes and duels are deliberately absent.
METRICS = {
    "appearances": (("matches_uppercase",), "count", "total", False),
    "minutes_played": (("minutes_played", "mins_played"), "minutes", "total", False),
    "starts": (("player_started_matches",), "count", "total", False),
    "rating": (("rating",), "FotMob rating points", "rating", False),
    "goals": (("goals",), "count", "total", False),
    "assists": (("assists",), "count", "total", False),
    "shots": (("shots",), "count", "total", False),
    "shots_on_target": (("ShotsOnTarget", "ontarget_scoring_att"), "count", "total", False),
    "expected_goals": (("expected_goals",), "expected goals; provider definition unverified", "total", False),
    "expected_assists": (("expected_assists",), "expected assists; provider definition unverified", "total", False),
    "accurate_passes": (("successful_passes", "accurate_pass"), "count", "total", False),
    "passing_accuracy": (("successful_passes_accuracy",), "percent; denominator not supplied", "percentage", False),
    "chances_created": (("chances_created", "total_att_assist"), "count", "total", False),
    "key_passes": ((), "unknown", "unknown", False),
    "accurate_long_passes": (("long_balls_accurate", "accurate_long_balls"), "count", "total", False),
    "tackles": (("matchstats.headers.tackles", "total_tackle"), "count", "total", False),
    "interceptions": (("interceptions", "interception"), "count", "total", False),
    "clearances": (("clearances", "effective_clearance"), "count", "total", False),
    "blocked_shots": (("blocked_shots", "outfielder_block"), "count", "total", False),
    "duels_won": (("duel_won",), "count", "total", False),
    "saves": (("saves",), "count", "total", True),
    "goals_conceded": (("goals_conceded",), "count", "total", True),
    "clean_sheets": (("clean_sheet_title",), "count", "total", True),
    "goals_prevented": (("goals_prevented", "_goals_prevented"), "goal-equivalent; provider definition unverified", "total", True),
}
PROFILE_FIELDS = ["season_label", "season_id", "player_id", "historical_name", "profile_name",
                  "birth_date", "nationality_current", "current_position", "historical_position_code",
                  "historical_team_id", "historical_team_name", "current_team_id", "current_team_name",
                  "season_entry_id", "profile_status", "historical_team_status", "current_team_status",
                  "current_position_status", "nationality_status", "season_association_status",
                  "profile_source_id", "profile_collected_at_utc"]
IDENTITY_FIELDS = ["season_label", "season_id", "player_id", "historical_team_id", "current_team_id",
                   "current_vs_historical_team", "historical_name", "profile_name", "name_match",
                   "birth_date", "birth_date_status", "nationality_status", "position_status",
                   "historical_team_status", "season_association_status", "reference_multi_team_count",
                   "career_history_league_team_candidates", "career_history_transfer_flag", "audit_note"]
LINK_AUDIT_FIELDS = ["season_label", "match_id", "match_status", "home_team_id", "away_team_id",
                     "detail_status", "lineup_player_count", "selected_player_links", "selected_team_players",
                     "lineup_duplicate_entries", "source_id", "note"]
COVERAGE_FIELDS = ["season_label", "metric", "available", "missing", "not_applicable", "unsupported",
                   "unparseable", "sample_rows", "source_endpoints", "unit", "statistic_type", "note"]
NORM_FIELDS = ["dataset", "row_count", "primary_key", "duplicate_key_count", "null_key_count", "status", "note"]


def parse_number(raw) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if value == value and abs(value) != float("inf") else None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        text = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None
    return float(text)


def iso_utc(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def nationality(profile: dict) -> str | None:
    for item in profile.get("playerInformation") or []:
        if item.get("translationKey") == "country_sentencecase":
            return (item.get("value") or {}).get("fallback")
    return None


def career_team_candidates(profile: dict, season: str, league_team_ids: set[str],
                           fixture_window: tuple[str, str] | None = None) -> list[str]:
    entries = (((profile.get("careerHistory") or {}).get("careerItems") or {}).get("senior") or {}).get("teamEntries") or []
    start, end = fixture_window or (season[:4] + "-07-01", season[5:] + "-06-30")
    result = set()
    for item in entries:
        team_id = str(item.get("teamId"))
        first = str(item.get("startDate") or "")[:10]
        last = str(item.get("endDate") or "9999-12-31")[:10]
        if team_id in league_team_ids and first and first <= end and last >= start:
            result.add(team_id)
    return sorted(result, key=int)


def fixture_state(status: dict) -> str:
    reason = (status.get("reason") or {}).get("longKey") or ""
    if status.get("cancelled"):
        return "CANCELLED_OR_ABANDONED"
    if status.get("finished"):
        return "FINISHED"
    return "POSTPONED" if "postpon" in reason else "OTHER"


def write_parquet(path, schema: pa.Schema, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), temp, compression="zstd")
    os.replace(temp, path)


def schemas() -> dict[str, pa.Schema]:
    st, fl, it = pa.string(), pa.float64(), pa.int64()
    return {
        "players": pa.schema([(x, st) for x in ("player_id", "profile_name", "birth_date",
                              "nationality_current", "current_position", "current_team_id",
                              "profile_source_id", "profile_collected_at_utc")]),
        "teams": pa.schema([(x, st) for x in ("team_id", "team_name", "observed_names", "source_ids")]),
        "player_seasons": pa.schema([(x, st) for x in ("player_id", "season_label", "season_id",
                                      "season_entry_id", "stats_status", "stats_source_id")]
                                    + [(x, fl) for x in METRICS]),
        "player_team_seasons": pa.schema([(x, st) for x in ("player_id", "team_id", "season_id",
                                           "season_label", "historical_name", "team_name",
                                           "historical_position_code", "sample_position_group",
                                           "reference_minutes_raw", "team_stat_allocation_status",
                                           "reference_source_ids")]),
        "matches": pa.schema([(x, st) for x in ("match_id", "season_id", "season_label",
                                "match_date_utc", "home_team_id", "away_team_id", "status",
                                "status_reason", "result", "source_id", "collected_at_utc")]),
        "player_match_links": pa.schema([(x, st) for x in ("player_id", "match_id", "season_id",
                                           "season_label", "team_id", "lineup_role", "link_status",
                                           "source_id", "collected_at_utc")]),
        "metric_observations": pa.schema([(x, st) for x in ("player_id", "season_id", "season_label",
                                            "metric", "original_field", "raw_value", "unit",
                                            "statistic_type", "source_format", "source_title", "status",
                                            "missing_reason", "source_endpoint", "source_id",
                                            "collected_at_utc")]
                                          + [("value", fl), ("source_per90", fl)]),
    }


def normalize() -> dict:
    config = load_config()
    store = PilotStore(config)
    sample = sample_rows(config)
    profiles = cache_by_source(store, "playerData")
    stats = cache_by_source(store, "playerStats")
    leagues = cache_by_source(store, "leagues")
    details = cache_by_source(store, "matchDetails")
    boards = {}
    for meta, payload in store.cached_payloads("leagueseasondeepstats"):
        metric = meta["params"].get("stat")
        if metric not in ("mins_played", "goals", "saves"):
            continue
        lookup = {}
        for row in leaderboard_rows(payload):
            key = (str(row.get("id")), str(row.get("teamId")))
            if key in lookup:
                raise ValueError(f"Duplicate leaderboard key in {meta['source_id']}: {key}")
            lookup[key] = row
        boards[(meta["season_label"], metric)] = (meta, payload, lookup)
    league_teams = {}
    fixture_dates = defaultdict(list)
    team_data = defaultdict(lambda: {"names": set(), "sources": set()})
    match_rows, match_keys = [], set()
    for season, season_id in config["seasons"].items():
        item = leagues.get(f"league_{season.replace('/', '_')}")
        if not item:
            continue
        meta, payload = item
        if (payload.get("details") or {}).get("selectedSeason") != season:
            raise ValueError(f"Wrong league season: {season}")
        season_teams = set()
        for block in payload.get("table") or []:
            for team in (((block.get("data") or {}).get("table") or {}).get("all") or []):
                team_id = str(team.get("id"))
                season_teams.add(team_id)
                team_data[team_id]["names"].add(team.get("name") or "")
                team_data[team_id]["sources"].add(meta["source_id"])
        league_teams[season] = season_teams
        for fixture in ((payload.get("fixtures") or {}).get("allMatches") or []):
            match_id = str(fixture.get("id"))
            if match_id in match_keys:
                raise ValueError(f"Duplicate fixture ID: {match_id}")
            match_keys.add(match_id)
            status = fixture.get("status") or {}
            reason = (status.get("reason") or {}).get("longKey") or ""
            state = fixture_state(status)
            match_rows.append({"match_id": match_id, "season_id": str(season_id), "season_label": season,
                               "match_date_utc": iso_utc(status.get("utcTime")),
                               "home_team_id": str((fixture.get("home") or {}).get("id")),
                               "away_team_id": str((fixture.get("away") or {}).get("id")),
                               "status": state, "status_reason": reason, "result": status.get("scoreStr"),
                               "source_id": meta["source_id"], "collected_at_utc": meta["collected_at_utc"]})
            if state == "FINISHED" and status.get("utcTime"):
                fixture_dates[season].append(status["utcTime"][:10])
    fixture_windows = {season: (min(dates), max(dates)) for season, dates in fixture_dates.items() if dates}
    players, player_seasons, player_team_seasons = {}, [], []
    profile_audit, identity_audit, metric_rows = [], [], []
    sample_keys, season_player_keys = set(), set()
    ref_multi = Counter((r["season_label"], r["fotmob_player_id"]) for r in sample)
    for row in sample:
        pid, tid, season, season_id = (row["fotmob_player_id"], row["fotmob_team_id"],
                                       row["season_label"], row["fotmob_season_id"])
        key = (pid, tid, season_id)
        if key in sample_keys:
            raise ValueError(f"Duplicate player-team-season sample key: {key}")
        sample_keys.add(key)
        profile_item = profiles.get(f"profile_{pid}")
        profile_meta, profile = profile_item if profile_item else ({}, {})
        profile_valid = str(profile.get("id")) == pid
        entry = season_profile_entry(profile, season, 47) if profile_valid else None
        profile_status = "AVAILABLE" if profile_valid else ("ID_MISMATCH" if profile_item else "NOT_COLLECTED")
        current_team = profile.get("primaryTeam") or {} if profile_valid else {}
        current_id = str(current_team.get("teamId")) if current_team.get("teamId") is not None else None
        current_position = ((profile.get("positionDescription") or {}).get("primaryPosition") or {}).get("label") if profile_valid else None
        birth_date = iso_utc((profile.get("birthDate") or {}).get("utcTime")) if profile_valid else None
        country = nationality(profile) if profile_valid else None
        candidates = career_team_candidates(profile, season, league_teams.get(season, set()),
                                            fixture_windows.get(season)) if profile_valid else []
        profile_row = {"season_label": season, "season_id": season_id, "player_id": pid,
                       "historical_name": row["player_name"], "profile_name": profile.get("name") if profile_valid else None,
                       "birth_date": birth_date, "nationality_current": country,
                       "current_position": current_position, "historical_position_code": row["historical_position_code"],
                       "historical_team_id": tid, "historical_team_name": row["team_name"],
                       "current_team_id": current_id, "current_team_name": current_team.get("teamName"),
                       "season_entry_id": entry.get("entryId") if entry else None, "profile_status": profile_status,
                       "historical_team_status": "HISTORICAL_VERIFIED",
                       "current_team_status": "CURRENT_ONLY" if current_id else "UNKNOWN",
                       "current_position_status": "CURRENT_ONLY" if current_position else "UNKNOWN",
                       "nationality_status": "CURRENT_ONLY" if country else "UNKNOWN",
                       "season_association_status": "HISTORICAL_VERIFIED" if entry else "UNKNOWN",
                       "profile_source_id": profile_meta.get("source_id"),
                       "profile_collected_at_utc": profile_meta.get("collected_at_utc")}
        profile_audit.append(profile_row)
        identity_audit.append({"season_label": season, "season_id": season_id, "player_id": pid,
                               "historical_team_id": tid, "current_team_id": current_id,
                               "current_vs_historical_team": ("SAME" if current_id == tid else "DIFFERENT") if current_id else "UNKNOWN",
                               "historical_name": row["player_name"], "profile_name": profile.get("name") if profile_valid else None,
                               "name_match": str(row["player_name"].casefold() == str(profile.get("name", "")).casefold()) if profile_valid else "UNKNOWN",
                               "birth_date": birth_date, "birth_date_status": "INFERRED" if birth_date else "UNKNOWN",
                               "nationality_status": profile_row["nationality_status"],
                               "position_status": "HISTORICAL_VERIFIED" if row["historical_position_code"] else "UNKNOWN",
                               "historical_team_status": "HISTORICAL_VERIFIED",
                               "season_association_status": profile_row["season_association_status"],
                               "reference_multi_team_count": ref_multi[(season, pid)],
                               "career_history_league_team_candidates": "|".join(candidates),
                               "career_history_transfer_flag": "INFERRED_CANDIDATE" if len(candidates) > 1 else "NONE_OBSERVED",
                               "audit_note": "Career dates are retrospective profile claims, not verified match participation" if len(candidates) > 1 else ""})
        if profile_valid and pid not in players:
            players[pid] = {"player_id": pid, "profile_name": profile.get("name"), "birth_date": birth_date,
                            "nationality_current": country, "current_position": current_position,
                            "current_team_id": current_id, "profile_source_id": profile_meta.get("source_id"),
                            "profile_collected_at_utc": profile_meta.get("collected_at_utc")}
        player_team_seasons.append({"player_id": pid, "team_id": tid, "season_id": season_id,
                                    "season_label": season, "historical_name": row["player_name"],
                                    "team_name": row["team_name"], "historical_position_code": row["historical_position_code"],
                                    "sample_position_group": row["position_group"],
                                    "reference_minutes_raw": row["minutes_played"],
                                    "team_stat_allocation_status": "UNVERIFIED_TEAM_SPLIT",
                                    "reference_source_ids": row["evidence_source_ids"]})
        season_key = (pid, season_id)
        if season_key in season_player_keys:
            # Keep every historical team relationship, but only one season aggregate.
            continue
        season_player_keys.add(season_key)
        stats_source_id = f"stats_{season.replace('/', '_')}_{pid}"
        stats_item = stats.get(stats_source_id)
        stats_meta, stats_payload = stats_item if stats_item else ({}, {})
        if stats_item and (not entry or str(stats_meta["params"].get("playerId")) != pid or
                           stats_meta["params"].get("seasonId") != entry.get("entryId")):
            raise ValueError(f"Unverified playerStats season join: {stats_source_id}")
        items = player_stat_items(stats_payload) if entry and stats_item else {}
        season_values = {"player_id": pid, "season_label": season, "season_id": season_id,
                         "season_entry_id": entry.get("entryId") if entry else None,
                         "stats_status": "AVAILABLE" if items else ("NO_SEASON_ENTRY" if not entry else "NOT_COLLECTED_OR_EMPTY"),
                         "stats_source_id": stats_meta.get("source_id")}
        for metric, (aliases, unit, kind, keeper_only) in METRICS.items():
            source_item, original_field = None, None
            for alias in aliases:
                if alias in items:
                    source_item, original_field = items[alias], alias
                    break
            source_endpoint = "playerStats" if source_item else None
            source_meta = stats_meta if source_item else {}
            raw_value = source_item.get("statValue") if source_item else None
            per90 = parse_number(source_item.get("per90")) if source_item else None
            if source_item is None and metric in ("minutes_played", "goals", "saves"):
                board = boards.get((season, metric if metric != "minutes_played" else "mins_played"))
                if board:
                    board_meta, board_payload, lookup = board
                    board_row = lookup.get((pid, tid))
                    if board_row:
                        if metric == "saves" and board_payload.get("substatTitle") == "Total saves":
                            raw_value = (board_row.get("substatValue") or {}).get("value")
                            original_field = "substatValue.value"
                        elif metric != "saves":
                            raw_value = (board_row.get("statValue") or {}).get("value")
                            original_field = "statValue.value"
                        if original_field:
                            source_endpoint, source_meta = "leagueseasondeepstats", board_meta
            if not aliases:
                status, reason = "UNSUPPORTED", "NO_VERIFIED_SOURCE_FIELD"
            elif keeper_only and row["position_group"] != "GK":
                status, reason = "NOT_APPLICABLE", "GOALKEEPER_SPECIFIC"
                raw_value, original_field, source_endpoint, source_meta = None, None, None, {}
            elif raw_value is None:
                status, reason = "MISSING", "PROFILE_OR_LEADERBOARD_FIELD_ABSENT" if stats_item else "STATS_NOT_COLLECTED"
            elif parse_number(raw_value) is None:
                status, reason = "UNPARSEABLE", "NON_NUMERIC_SOURCE_VALUE"
            else:
                status, reason = "AVAILABLE", ""
            value = parse_number(raw_value) if status == "AVAILABLE" else None
            season_values[metric] = value
            metric_rows.append({"player_id": pid, "season_id": season_id, "season_label": season,
                                "metric": metric, "original_field": original_field,
                                "raw_value": str(raw_value) if raw_value is not None else None,
                                "value": value, "unit": unit, "statistic_type": kind,
                                "source_format": source_item.get("statFormat") if source_item else None,
                                "source_title": source_item.get("title") if source_item else None,
                                "source_per90": per90, "status": status, "missing_reason": reason,
                                "source_endpoint": source_endpoint, "source_id": source_meta.get("source_id"),
                                "collected_at_utc": source_meta.get("collected_at_utc")})
        player_seasons.append(season_values)
    selected_ids = {r["fotmob_player_id"] for r in sample}
    selected_player_teams = {(r["season_label"], r["fotmob_player_id"], r["fotmob_team_id"]) for r in sample}
    match_by_id = {r["match_id"]: r for r in match_rows}
    link_rows, link_audit, link_keys = [], [], set()
    for source_id, (meta, payload) in sorted(details.items()):
        match_id = str(meta["params"].get("matchId"))
        fixture = match_by_id.get(match_id)
        if fixture is None:
            raise ValueError(f"Match detail not in historical league index: {match_id}")
        general = payload.get("general") or {}
        if str(general.get("matchId")) != match_id or str(general.get("leagueId")) != "47":
            raise ValueError(f"Match-detail ID/league mismatch: {match_id}")
        lineup = ((payload.get("content") or {}).get("lineup") or {})
        lineup_count, matched, duplicate = 0, 0, 0
        for side, team_field in (("homeTeam", "home_team_id"), ("awayTeam", "away_team_id")):
            team = lineup.get(side) or {}
            team_id = str(team.get("id")) if team.get("id") is not None else fixture[team_field]
            if team_id != fixture[team_field]:
                raise ValueError(f"Lineup team mismatch for {match_id}")
            for role in ("starters", "subs"):
                for player in team.get(role) or []:
                    pid = str(player.get("id"))
                    if pid == "None":
                        continue
                    lineup_count += 1
                    if (fixture["season_label"], pid, team_id) not in selected_player_teams:
                        continue
                    key = (pid, match_id)
                    if key in link_keys:
                        duplicate += 1
                        continue
                    link_keys.add(key)
                    matched += 1
                    link_rows.append({"player_id": pid, "match_id": match_id,
                                      "season_id": fixture["season_id"], "season_label": fixture["season_label"],
                                      "team_id": team_id, "lineup_role": role.upper(),
                                      "link_status": "HISTORICAL_VERIFIED_LINEUP",
                                      "source_id": source_id, "collected_at_utc": meta["collected_at_utc"]})
        relevant = sum(r["season_label"] == fixture["season_label"] and
                       r["fotmob_team_id"] in (fixture["home_team_id"], fixture["away_team_id"]) for r in sample)
        link_audit.append({"season_label": fixture["season_label"], "match_id": match_id,
                           "match_status": fixture["status"], "home_team_id": fixture["home_team_id"],
                           "away_team_id": fixture["away_team_id"], "detail_status": "AVAILABLE",
                           "lineup_player_count": lineup_count, "selected_player_links": matched,
                           "selected_team_players": relevant, "lineup_duplicate_entries": duplicate,
                           "source_id": source_id,
                           "note": "Only sampled player IDs are emitted as links; absence from lineup is not season absence"})
    for _, params, season, source_id in match_plan(sample, leagues):
        if source_id in details:
            continue
        match_id = str(params["matchId"])
        fixture = match_by_id.get(match_id, {})
        link_audit.append({"season_label": season, "match_id": match_id,
                           "match_status": fixture.get("status"),
                           "home_team_id": fixture.get("home_team_id"),
                           "away_team_id": fixture.get("away_team_id"),
                           "detail_status": "NOT_COLLECTED_OR_FAILED", "lineup_player_count": 0,
                           "selected_player_links": 0, "selected_team_players": 0,
                           "lineup_duplicate_entries": 0, "source_id": source_id,
                           "note": "No match-detail evidence; fixture index alone cannot prove a player link"})
    schemas_by_table = schemas()
    datasets = {
        "players": list(players.values()),
        "teams": [{"team_id": team_id, "team_name": sorted(value["names"])[0],
                   "observed_names": "|".join(sorted(value["names"])),
                   "source_ids": "|".join(sorted(value["sources"]))}
                  for team_id, value in sorted(team_data.items(), key=lambda x: int(x[0]))],
        "player_seasons": player_seasons,
        "player_team_seasons": player_team_seasons,
        "matches": match_rows,
        "player_match_links": link_rows,
        "metric_observations": metric_rows,
    }
    normalized_dir = ROOT / config["normalized_dir"]
    for name, records in datasets.items():
        write_parquet(normalized_dir / f"{name}.parquet", schemas_by_table[name], records)
    report_dir = ROOT / config["report_dir"]
    write_csv(report_dir / "pilot_player_profiles.csv", PROFILE_FIELDS, profile_audit)
    write_csv(report_dir / "historical_identity_audit.csv", IDENTITY_FIELDS, identity_audit)
    write_csv(report_dir / "player_match_link_audit.csv", LINK_AUDIT_FIELDS, link_audit)
    feature_coverage = []
    for season in config["seasons"]:
        for metric, (_, unit, kind, _) in METRICS.items():
            records = [x for x in metric_rows if x["season_label"] == season and x["metric"] == metric]
            counts = Counter(x["status"] for x in records)
            feature_coverage.append({"season_label": season, "metric": metric,
                                     "available": counts["AVAILABLE"], "missing": counts["MISSING"],
                                     "not_applicable": counts["NOT_APPLICABLE"],
                                     "unsupported": counts["UNSUPPORTED"],
                                     "unparseable": counts["UNPARSEABLE"], "sample_rows": len(records),
                                     "source_endpoints": "|".join(sorted({x["source_endpoint"] for x in records if x["source_endpoint"]})),
                                     "unit": unit, "statistic_type": kind,
                                     "note": "No zero imputation; percentages only describe the sampled rows"})
    write_csv(report_dir / "pilot_feature_coverage.csv", COVERAGE_FIELDS, feature_coverage)
    primary_keys = {"players": ("player_id",), "teams": ("team_id",),
                    "player_seasons": ("player_id", "season_id"),
                    "player_team_seasons": ("player_id", "team_id", "season_id"),
                    "matches": ("match_id",), "player_match_links": ("player_id", "match_id"),
                    "metric_observations": ("player_id", "season_id", "metric")}
    norm_report = []
    for name, records in datasets.items():
        keys = primary_keys[name]
        tuples = [tuple(r.get(k) for k in keys) for r in records]
        duplicate = len(tuples) - len(set(tuples))
        null_keys = sum(any(v is None or v == "" for v in key) for key in tuples)
        norm_report.append({"dataset": name, "row_count": len(records), "primary_key": "+".join(keys),
                            "duplicate_key_count": duplicate, "null_key_count": null_keys,
                            "status": "PASS" if not duplicate and not null_keys else "REVIEW",
                            "note": "Sampled lineage only" if name == "player_match_links" else "Raw sources retained"})
    write_csv(report_dir / "normalization_report.csv", NORM_FIELDS, norm_report)
    schema_json = {name: {"primary_key": list(primary_keys[name]),
                          "fields": {field.name: str(field.type) for field in schema},
                          "rows": len(datasets[name])} for name, schema in schemas_by_table.items()}
    schema_json["identity_statuses"] = ["HISTORICAL_VERIFIED", "CURRENT_ONLY", "INFERRED", "UNKNOWN"]
    schema_json["metric_statuses"] = ["AVAILABLE", "MISSING", "NOT_APPLICABLE", "UNSUPPORTED", "UNPARSEABLE"]
    schema_json["metric_mapping"] = {
        name: {"verified_profile_field_candidates": list(aliases), "unit": unit,
               "statistic_type": kind, "goalkeeper_only": keeper_only}
        for name, (aliases, unit, kind, keeper_only) in METRICS.items()}
    schema_json["lineage_note"] = "source_id resolves to data/pilot/raw/*.meta.json; SHA-256 validates the paired JSON payload"
    atomic_write(report_dir / "schema_definition.json", json_bytes(schema_json))
    summary = {
        "sample_rows": len(sample), "unique_sample_players": len(selected_ids),
        "profiles_collected": len(players), "season_stats_collected": sum(x["stats_status"] == "AVAILABLE" for x in player_seasons),
        "available_metric_cells": sum(x["status"] == "AVAILABLE" for x in metric_rows),
        "missing_metric_cells": sum(x["status"] == "MISSING" for x in metric_rows),
        "unsupported_metric_cells": sum(x["status"] == "UNSUPPORTED" for x in metric_rows),
        "not_applicable_metric_cells": sum(x["status"] == "NOT_APPLICABLE" for x in metric_rows),
        "unparseable_metric_cells": sum(x["status"] == "UNPARSEABLE" for x in metric_rows),
        "unique_available_metrics": len({x["metric"] for x in metric_rows if x["status"] == "AVAILABLE"}),
        "match_detail_samples": len(details), "player_match_links": len(link_rows),
        "row_counts": {name: len(records) for name, records in datasets.items()},
        "current_team_mismatches": sum(x["current_vs_historical_team"] == "DIFFERENT" for x in identity_audit),
        "profile_name_mismatches": sum(x["name_match"] == "False" for x in identity_audit),
        "transfer_candidates": sum(x["career_history_transfer_flag"] == "INFERRED_CANDIDATE" for x in identity_audit),
        "cancelled_matches": sum(x["status"] == "CANCELLED_OR_ABANDONED" for x in match_rows),
        "match_dates_missing": sum(x["match_date_utc"] is None for x in match_rows),
        "match_results_missing": sum(x["result"] is None for x in match_rows),
        "raw_response_count": len(list(store.raw_dir.glob("*.meta.json"))),
        "source_failures_in_log": 0,
    }
    log_path = ROOT / config["log_path"]
    if log_path.exists():
        summary["source_failures_in_log"] = sum(json.loads(line).get("outcome") == "FAILED"
                                                for line in log_path.read_text(encoding="utf-8").splitlines())
    per_season = Counter(x["season_label"] for x in sample)
    stats_by_season = Counter(x["season_label"] for x in player_seasons if x["stats_status"] == "AVAILABLE")
    missing_by_metric = Counter(x["metric"] for x in metric_rows if x["status"] == "MISSING")
    unsupported = sorted({x["metric"] for x in metric_rows if x["status"] == "UNSUPPORTED"})
    anomaly = {x["match_id"]: x for x in match_rows if x["match_id"] in ("4193691", "4421797")}
    lines = ["# Phase 2A Steps 03–06 — controlled pilot collection", "",
             f"Normalized from {len(sample)} selected player–season rows and {len(selected_ids)} unique sampled players.",
             "Only the manifest players and selected match details were requested; the league fixture indexes",
             "and three reference boards were reused from Steps 01–02. All successful new responses are cached",
             "whole with request metadata and SHA-256; normalization leaves raw files untouched.", "",
             f"Retained raw response/metadata pairs: {summary['raw_response_count']}. New collection responses",
             "are stored as wire JSON; earlier Step 01–02 full payloads remain in their existing canonical JSON form.", "",
             "## Collection by season", "",
             "| Season | Selected | Season stats available |",
             "|---|---:|---:|"]
    for season in config["seasons"]:
        lines.append(f"| {season} | {per_season[season]} | {stats_by_season[season]} |")
    lines += ["", "## Normalized outputs", "",
              "| Table | Rows |", "|---|---:|"]
    for name, records in datasets.items():
        lines.append(f"| `{name}.parquet` | {len(records)} |")
    lines += ["", "## Metrics and identity", "",
              f"Available metric cells: {summary['available_metric_cells']}; missing: {summary['missing_metric_cells']}; "
              f"not applicable: {summary['not_applicable_metric_cells']}; unsupported: {summary['unsupported_metric_cells']}.",
              f"Distinct metrics with a value: {summary['unique_available_metrics']} of {len(METRICS)} normalized candidates.",
              "The `metric_observations.parquet` table retains each source field, raw value, unit, format,",
              "statistic type, timestamp and missing status. The wide `player_seasons.parquet` keeps nulls.",
              "No missing leaderboard row is interpreted as zero. `key_passes` is unsupported; generic long",
              "passes, duels and blocks are represented only by narrower observed variants when present.",
              "Profile `statValue` totals are separate from its `per90` field. The saves leaderboard's main",
              "value is per 90 while its `Total saves` secondary value is a total; these are never combined.",
              "Passing accuracy retains the provider's percentage and notes that its denominator is not supplied.",
              f"Current team differs from the season-scoped historical team in {summary['current_team_mismatches']} "
              "sample rows; current team, position and nationality are classified CURRENT_ONLY.",
              f"Profile and season-board names differ literally in {summary['profile_name_mismatches']} "
              "sample rows; FotMob IDs remain the join key and both names are retained.",
              f"Retrospective career dates flagged {summary['transfer_candidates']} possible same-season "
              "multi-club cases for review. These did not create unverified team records.",
              "A player with multiple verified team rows retains each player–team–season relationship,",
              "while the player–season aggregate remains one row.", "",
              "Possible multi-club cases from retrospective career dates (INFERRED only):"]
    for record in identity_audit:
        if record["career_history_transfer_flag"] == "INFERRED_CANDIDATE":
            lines.append(f"- {record['season_label']} player `{record['player_id']}` "
                         f"({record['historical_name']}): league team IDs "
                         f"`{record['career_history_league_team_candidates']}`; "
                         f"season-board team `{record['historical_team_id']}`.")
    lines += ["",
              "## Match index", "",
              f"The six cached league responses contain {len(match_rows)} fixture records; "
              f"{summary['cancelled_matches']} are canceled or abandoned.",
              f"Missing match dates: {summary['match_dates_missing']}; missing results: "
              f"{summary['match_results_missing']}.",
              f"Selected match-detail responses: {len(details)}; verified selected-player lineup links: {len(link_rows)}.",
              "The 2023/24 Bournemouth–Luton raw fixture IDs are preserved separately:"]
    for match_id in ("4193691", "4421797"):
        match = anomaly.get(match_id)
        lines.append(f"- `{match_id}`: {match['status'] if match else 'NOT_FOUND'}; "
                     f"{match['match_date_utc'] if match else 'date unknown'}.")
    lines += ["", "`playerMatches` was not retried: Phase 1 recorded HTTP 400 and no verified working",
              "parameter set is available. Fixture membership alone does not establish a player–match link.",
              "Only selected lineups establish the links saved here; match coverage is deliberately partial.", "",
              "## Data quality and remaining blockers", "",
              f"Missing cells by metric: {', '.join(f'{k}={v}' for k, v in sorted(missing_by_metric.items())) or 'none'}.",
              f"Unsupported candidates: {', '.join(unsupported) or 'none'}.",
              f"Failed HTTP attempts in the pilot log: {summary['source_failures_in_log']}.",
              "The full historical player population remains unknown. Season-stat leaderboards and current",
              "profiles cannot establish it. Retrospective transfer claims and inferred position groups",
              "need independent historical validation. Match links cover only the selected details;",
              "`playerMatches` pagination remains unresolved. Metric definitions and percentage denominators",
              "are not fully documented by the checked source responses.", "",
              "## Reproduction", "",
              "```powershell", "python -m src.collection.phase_02a_03_06 profiles --max-requests 40",
              "python -m src.collection.phase_02a_03_06 stats --max-requests 40",
              "python -m src.collection.phase_02a_03_06 matches --max-requests 40",
              "python -m src.collection.phase_02a_03_06 normalize",
              "python -m unittest discover -s tests -v", "```", "",
              "Each collection command resumes from cache; repeat it only while `still_missing` is positive.",
              "The normalized Parquet outputs are written atomically and can be regenerated from cached raw JSON."]
    atomic_write(report_dir / "collection_summary.md", ("\n".join(lines) + "\n").encode("utf-8"))
    return summary
