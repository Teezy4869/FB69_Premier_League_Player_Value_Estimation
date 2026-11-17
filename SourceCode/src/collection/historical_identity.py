"""Season-scoped team attribution without converting current profiles into history."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write
from src.collection.player_reference import candidate_views, team_names, write_csv
from src.collection.source_registry import SourceRegistry, load_hardening_config

FIELDS = ["fotmob_player_id", "fotmob_team_id", "fotmob_season_id", "season_label",
          "player_name", "team_name", "evidence_source", "evidence_timestamp",
          "historical_validation_status", "appearance_status", "statistic_scope",
          "relationship_origin", "current_team_id", "current_team_is_historical",
          "conflict_note"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_identity_rows() -> tuple[list[dict], dict]:
    config = load_config()
    pilot = PilotStore(config)
    registry = SourceRegistry(load_hardening_config())
    candidates, _ = candidate_views(pilot)
    captures = list(registry.captures())
    by_source = {m["source_id"]: m for m, _ in captures if m["endpoint"] == "leagueseasondeepstats"}
    profiles = {m["source_id"]: (m, p) for m, p in captures if m["endpoint"] == "playerData"}
    team_names_by_season = {}
    for m, payload in pilot.cached_payloads("leagues"):
        team_names_by_season[m["season_label"]] = team_names(payload)
    population = read_csv(ROOT / "reports/phase_02b0/historical_population_validation.csv")
    population_by_key = {(r["season_label"], r["player_id"], r["team_id"]): r for r in population}
    pilot_identity = read_csv(ROOT / "reports/phase_02a/historical_identity_audit.csv")
    current = {(r["season_label"], r["player_id"]): r["current_team_id"] for r in pilot_identity}
    names = {(r["season_label"], r["fotmob_player_id"]): r["player_name"] for r in candidates}
    rows = {}
    for r in candidates:
        season, pid, tid = r["season_label"], r["fotmob_player_id"], r["fotmob_team_id"]
        key = (season, pid, tid)
        sources = [by_source[src] for src in r["evidence_source_ids"].split("|")]
        sighting = population_by_key[key]
        rows[key] = {"fotmob_player_id": pid, "fotmob_team_id": tid,
                     "fotmob_season_id": r["fotmob_season_id"], "season_label": season,
                     "player_name": r["player_name"], "team_name": r["team_name"],
                     "evidence_source": "|".join(sorted(m["raw_path"] for m in sources)),
                     "evidence_timestamp": max(m["collected_at_utc"] for m in sources),
                     "historical_validation_status": "HISTORICAL_VERIFIED",
                     "appearance_status": sighting["verification_status"],
                     "statistic_scope": "UNVERIFIED_TEAM_ALLOCATION",
                     "relationship_origin": "SEASON_SCOPED_LEADERBOARD",
                     "current_team_id": current.get((season, pid), ""),
                     "current_team_is_historical": "False",
                     "conflict_note": "Season-board team relation observed; leaderboard value may be season-wide"}
    # Add actual lineup relationships absent from the bounded leaderboards.
    for r in population:
        if r["verification_status"] not in ("VERIFIED_APPEARANCE_OTHER_TEAM",
                                             "VERIFIED_APPEARANCE_MISSING_CANDIDATE"):
            continue
        season, pid, tid = r["season_label"], r["player_id"], r["team_id"]
        key = (season, pid, tid)
        if key in rows:
            raise ValueError(f"Duplicate verified relationship: {key}")
        rows[key] = {"fotmob_player_id": pid, "fotmob_team_id": tid,
                     "fotmob_season_id": r["season_id"], "season_label": season,
                     "player_name": names.get((season, pid), ""),
                     "team_name": team_names_by_season[season].get(tid, ""),
                     "evidence_source": r["evidence_reference"],
                     "evidence_timestamp": r["collection_timestamp"],
                     "historical_validation_status": "HISTORICAL_VERIFIED",
                     "appearance_status": r["verification_status"],
                     "statistic_scope": "NO_TEAM_SPECIFIC_STAT_VALUE",
                     "relationship_origin": "HISTORICAL_MATCH_LINEUP",
                     "current_team_id": current.get((season, pid), ""),
                     "current_team_is_historical": "False",
                     "conflict_note": "Missing from season leaderboard team relations; do not split aggregate stats"}
    # Career-history dates are retrospective profile claims, not direct participation.
    inferred = []
    for audit in pilot_identity:
        if audit["career_history_transfer_flag"] != "INFERRED_CANDIDATE":
            continue
        season, pid = audit["season_label"], audit["player_id"]
        meta, _ = profiles[f"profile_{pid}"]
        for tid in audit["career_history_league_team_candidates"].split("|"):
            key = (season, pid, tid)
            if key in rows:
                continue
            inferred.append(key)
            rows[key] = {"fotmob_player_id": pid, "fotmob_team_id": tid,
                         "fotmob_season_id": audit["season_id"], "season_label": season,
                         "player_name": audit["historical_name"],
                         "team_name": team_names_by_season[season].get(tid, ""),
                         "evidence_source": meta["raw_path"],
                         "evidence_timestamp": meta["collected_at_utc"],
                         "historical_validation_status": "HISTORICAL_INFERRED",
                         "appearance_status": "UNVERIFIED",
                         "statistic_scope": "NO_TEAM_SPECIFIC_STAT_VALUE",
                         "relationship_origin": "RETROSPECTIVE_CAREER_HISTORY",
                         "current_team_id": current.get((season, pid), ""),
                         "current_team_is_historical": "False",
                         "conflict_note": "Career date overlaps season; match participation for this club not retained"}
    result = sorted(rows.values(), key=lambda r: (r["season_label"], int(r["fotmob_player_id"]),
                                                int(r["fotmob_team_id"])))
    by_player_season = defaultdict(list)
    names_by_player_id = defaultdict(set)
    player_ids_by_season_name = defaultdict(set)
    names_by_team_id = defaultdict(set)
    team_ids_by_season_name = defaultdict(set)
    for row in result:
        season, pid, tid = row["season_label"], row["fotmob_player_id"], row["fotmob_team_id"]
        by_player_season[(season, pid)].append(row)
        if row["player_name"]:
            names_by_player_id[pid].add(row["player_name"].casefold())
            player_ids_by_season_name[(season, row["player_name"].casefold())].add(pid)
        if row["team_name"]:
            names_by_team_id[tid].add(row["team_name"].casefold())
            team_ids_by_season_name[(season, row["team_name"].casefold())].add(tid)
    multi_club = [club_rows for club_rows in by_player_season.values() if len(club_rows) > 1]
    id_name_review_counts = {
        "player_id_multiple_names": sum(len(names) > 1 for names in names_by_player_id.values()),
        "season_name_multiple_player_ids": sum(len(ids) > 1 for ids in player_ids_by_season_name.values()),
        "team_id_multiple_names": sum(len(names) > 1 for names in names_by_team_id.values()),
        "season_team_name_multiple_ids": sum(len(ids) > 1 for ids in team_ids_by_season_name.values()),
    }
    # The profile's mutable fields are never permitted to create a historical row.
    if any(r["relationship_origin"] == "CURRENT_PROFILE" for r in result):
        raise ValueError("Current profile contaminated historical relationship index")
    player_seasons = pq.read_table(ROOT / config["normalized_dir"] / "player_seasons.parquet").to_pylist()
    player_team_seasons = pq.read_table(ROOT / config["normalized_dir"] / "player_team_seasons.parquet").to_pylist()
    ps_keys = [(r["player_id"], r["season_id"]) for r in player_seasons]
    pts_keys = [(r["player_id"], r["team_id"], r["season_id"]) for r in player_team_seasons]
    if len(ps_keys) != len(set(ps_keys)) or len(pts_keys) != len(set(pts_keys)):
        raise ValueError("Duplicate normalized historical identity key")
    if any(r["team_stat_allocation_status"] != "UNVERIFIED_TEAM_SPLIT" for r in player_team_seasons):
        raise ValueError("Team-specific stats were assumed without source evidence")
    counts = Counter(r["historical_validation_status"] for r in result)
    return result, {"status_counts": dict(counts), "candidate_relations": len(candidates),
                    "lineup_added_relations": sum(r["relationship_origin"] == "HISTORICAL_MATCH_LINEUP" for r in result),
                    "inferred_added_relations": len(inferred),
                    "multi_club_player_seasons": len(multi_club),
                    "multi_club_all_verified": sum(all(r["historical_validation_status"] == "HISTORICAL_VERIFIED"
                                                      for r in club_rows) for club_rows in multi_club),
                    "id_name_review_counts": id_name_review_counts,
                    "current_historical_team_mismatches": sum(r["current_vs_historical_team"] == "DIFFERENT" for r in pilot_identity),
                    "duplicate_player_season": len(ps_keys) - len(set(ps_keys)),
                    "duplicate_player_team_season": len(pts_keys) - len(set(pts_keys))}


def execute() -> dict:
    rows, facts = build_identity_rows()
    report_dir = ROOT / "reports/phase_02b0"
    write_csv(report_dir / "historical_identity_validation.csv", FIELDS, rows)
    note = f"""# Historical membership rules — Phase 2B.0 Step 03

An observed player–team–season relation is **HISTORICAL_VERIFIED** only when a season-scoped leaderboard row or a completed season-indexed match lineup supports it. A profile's `primaryTeam`, current position and nationality are CURRENT_ONLY. A retrospective career-history date can create a separately marked **HISTORICAL_INFERRED** candidate but never a verified club spell. Unknown or conflicting IDs must remain UNKNOWN/CONFLICTING until a scoped source resolves them.

Rebuilt {facts['candidate_relations']} leaderboard team relations, added {facts['lineup_added_relations']} verified lineup relations and {facts['inferred_added_relations']} retrospective candidates. {facts['current_historical_team_mismatches']} of 120 pilot rows have a current club different from the season board. Duplicate normalized player-season and player-team-season keys: {facts['duplicate_player_season']} and {facts['duplicate_player_team_season']}.

There are {facts['multi_club_player_seasons']} player-season pairs with multiple club relations. Both clubs are season-evidence verified for {facts['multi_club_all_verified']} pairs; the other {facts['multi_club_player_seasons'] - facts['multi_club_all_verified']} retain an inferred second club. In the bounded identity index, ID/name review found {facts['id_name_review_counts']['player_id_multiple_names']} player IDs with multiple names, {facts['id_name_review_counts']['season_name_multiple_player_ids']} season-name keys with multiple player IDs, {facts['id_name_review_counts']['team_id_multiple_names']} team IDs with multiple names, and {facts['id_name_review_counts']['season_team_name_multiple_ids']} season-team-name keys with multiple team IDs. These checks detect review candidates; a shared name alone would not prove an ID conflict.

`player_seasons` retains one season aggregate per player and season. The playerStats response has no returned team split, and leaderboard values are not proven to be per-club totals. `player_team_seasons` retains relationships but its existing `UNVERIFIED_TEAM_SPLIT` marker forbids summing or allocating the season total across clubs. For transfer cases, keep both verified relations and any inferred candidates; only direct season evidence promotes an inferred relation to HISTORICAL_VERIFIED.

The three previously flagged retrospective cases remain unresolved for the *second* club: Cameron Archer 2023/24 (`10252`), Aaron Ramsdale 2024/25 (`9825`), and Cameron Archer 2024/25 (`10252`). Their season-board club and selected lineup appearances are verified. In addition, selected lineups verify Takumi Minamino–Liverpool 2020/21 and Lucas Digne–Everton 2021/22, both omitted as club relations from the leaderboard union. Neither discovery licenses a statistical team split.

No current roster response is used as a historical team source. Original raw and Phase 2A normalized files are unchanged. Evidence paths and statuses are recorded per row in [historical_identity_validation.csv](historical_identity_validation.csv).
"""
    atomic_write(report_dir / "historical_membership_rules.md", note.encode("utf-8"))
    return {"rows": len(rows), **facts}


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2))
