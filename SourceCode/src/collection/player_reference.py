"""Build season-scoped player/team references without inventing a population denominator."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path

from src.audit.normalization import leaderboard_rows
from src.collection.foundation import PilotStore, atomic_write

REFERENCE_FIELDS = [
    "fotmob_player_id", "fotmob_team_id", "fotmob_season_id", "season_label",
    "player_name", "team_name", "position", "position_source", "reference_source",
    "reference_timestamp", "historical_validity_status", "observed_metrics",
    "minutes_played", "evidence_source_ids",
]
COVERAGE_FIELDS = [
    "season_label", "fotmob_season_id", "league_team_count", "reference_team_count",
    "unique_player_count", "player_team_season_count", "leaderboard_unique_player_count",
    "reference_population_count", "population_denominator", "population_coverage_percent",
    "reference_population_coverage", "mins_played_rows", "goals_rows", "saves_rows",
    "goals_share_of_observed_union_percent", "saves_share_of_observed_union_percent",
    "multi_team_player_count", "missing_reference_fields", "coverage_status",
]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, output.getvalue().encode("utf-8"))


def team_names(league: dict) -> dict[str, str]:
    names = {}
    for block in league.get("table") or []:
        for team in (((block.get("data") or {}).get("table") or {}).get("all") or []):
            if team.get("id") is not None and team.get("name"):
                names[str(team["id"])] = team["name"]
    return names


def build_reference(store: PilotStore) -> tuple[list[dict], list[dict]]:
    leagues = {}
    boards = defaultdict(dict)
    for meta, payload in store.cached_payloads():
        season = meta["season_label"]
        if meta["endpoint"] == "leagues" and meta["params"].get("season") == season:
            if (payload.get("details") or {}).get("selectedSeason") != season:
                raise ValueError(f"League response is not scoped to {season}")
            leagues[season] = payload
        elif meta["endpoint"] == "leagueseasondeepstats":
            metric = meta["params"].get("stat")
            if metric in store.config["reference_metrics"]:
                if (str(payload.get("currentSeasonId")) != str(store.config["seasons"][season]) or
                        payload.get("currentStatName") != metric):
                    raise ValueError(f"Season/stat mismatch for {meta['source_id']}")
                boards[season][metric] = (meta, leaderboard_rows(payload))
    references, coverage = [], []
    for season, season_id in store.config["seasons"].items():
        league = leagues.get(season, {})
        teams = team_names(league)
        entries = {}
        leaderboard_ids = set()
        for metric in store.config["reference_metrics"]:
            if metric not in boards[season]:
                continue
            meta, rows = boards[season][metric]
            metric_keys = set()
            for row in rows:
                player_id, team_id = row.get("id"), row.get("teamId")
                if player_id is None or team_id is None:
                    raise ValueError(f"Missing player/team ID in {meta['source_id']}")
                player_id, team_id = str(player_id), str(team_id)
                leaderboard_ids.add(player_id)
                key = (player_id, team_id)
                if key in metric_keys:
                    raise ValueError(f"Duplicate player/team row in {meta['source_id']}: {key}")
                metric_keys.add(key)
                if key not in entries:
                    entries[key] = {
                        "fotmob_player_id": player_id, "fotmob_team_id": team_id,
                        "fotmob_season_id": season_id, "season_label": season,
                        "player_name": row.get("name") or "", "team_name": teams.get(team_id, ""),
                        "position": row.get("position") if row.get("position") is not None else "",
                        "position_source": "season_scoped_leaderboard_code" if row.get("position") is not None else "",
                        "reference_source": "leagueseasondeepstats",
                        "reference_timestamp": meta["collected_at_utc"],
                        "historical_validity_status": "SEASON_STAT_OBSERVED_PARTIAL_POPULATION",
                        "observed_metrics": set(), "minutes_played": "", "evidence_source_ids": set(),
                    }
                entry = entries[key]
                entry["observed_metrics"].add(metric)
                entry["evidence_source_ids"].add(meta["source_id"])
                if metric == "mins_played":
                    entry["minutes_played"] = (row.get("statValue") or {}).get("value", "")
        for entry in entries.values():
            entry["observed_metrics"] = "|".join(sorted(entry["observed_metrics"]))
            entry["evidence_source_ids"] = "|".join(sorted(entry["evidence_source_ids"]))
            references.append(entry)
        player_teams = defaultdict(set)
        for player_id, team_id in entries:
            player_teams[player_id].add(team_id)
        missing = sum(not x["player_name"] or not x["team_name"] or x["position"] == "" for x in entries.values())
        complete = (len(teams) == 20 and len({t for _, t in entries}) == 20 and missing == 0 and
                    all(m in boards[season] for m in store.config["reference_metrics"]))
        coverage.append({
            "season_label": season, "fotmob_season_id": season_id,
            "league_team_count": len(teams),
            "reference_team_count": len({t for _, t in entries}),
            "unique_player_count": len(player_teams),
            "player_team_season_count": len(entries),
            "leaderboard_unique_player_count": len(leaderboard_ids),
            "reference_population_count": "", "population_denominator": "UNKNOWN",
            "population_coverage_percent": "",
            "reference_population_coverage": "UNKNOWN_DENOMINATOR",
            "mins_played_rows": len(boards[season].get("mins_played", (None, []))[1]),
            "goals_rows": len(boards[season].get("goals", (None, []))[1]),
            "saves_rows": len(boards[season].get("saves", (None, []))[1]),
            "goals_share_of_observed_union_percent": round(
                100 * len(boards[season].get("goals", (None, []))[1]) / len(leaderboard_ids), 2
            ) if leaderboard_ids else "",
            "saves_share_of_observed_union_percent": round(
                100 * len(boards[season].get("saves", (None, []))[1]) / len(leaderboard_ids), 2
            ) if leaderboard_ids else "",
            "multi_team_player_count": sum(len(v) > 1 for v in player_teams.values()),
            "missing_reference_fields": missing,
            "coverage_status": "BOUNDED_REFERENCE_COMPLETE_NOT_POPULATION" if complete else "INCOMPLETE_REFERENCE_SOURCES",
        })
    references.sort(key=lambda x: (x["season_label"], int(x["fotmob_team_id"]), int(x["fotmob_player_id"])))
    return references, coverage


def save_reference(store: PilotStore) -> tuple[list[dict], list[dict]]:
    rows, coverage = build_reference(store)
    report_dir = store.root / store.config["report_dir"]
    write_csv(report_dir / "player_reference_index.csv", REFERENCE_FIELDS, rows)
    write_csv(report_dir / "reference_coverage_report.csv", COVERAGE_FIELDS, coverage)
    write_csv(store.root / store.config["normalized_dir"] / "player_reference_index.csv", REFERENCE_FIELDS, rows)
    return rows, coverage


def candidate_views(store: PilotStore) -> tuple[list[dict], dict[tuple[str, str], list[dict]]]:
    """Rebuild leaderboard-only candidates while retaining every observed team relation."""
    rows, _ = build_reference(store)
    by_player_season: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen_relations = set()
    for row in rows:
        key = (row["season_label"], row["fotmob_player_id"], row["fotmob_team_id"])
        if key in seen_relations:
            raise ValueError(f"Repeated player-team-season candidate: {key}")
        seen_relations.add(key)
        by_player_season[key[:2]].append(row)
    return rows, dict(by_player_season)
