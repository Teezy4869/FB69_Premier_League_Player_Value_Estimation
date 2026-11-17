"""Deterministic, bounded sample from observed season-stat references."""
from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

from src.collection.foundation import PilotStore, atomic_write
from src.collection.player_reference import team_names, write_csv

SAMPLE_FIELDS = [
    "season_label", "fotmob_season_id", "pilot_depth", "club_context_rank",
    "fotmob_team_id", "team_name", "fotmob_player_id", "player_name",
    "historical_position_code", "position_group", "position_group_basis",
    "minutes_played", "low_minutes", "selection_reason", "exception_note",
    "historical_validity_status", "reference_source", "evidence_source_ids",
]


def position_group(code: str) -> str:
    """Conservative code-band inference for sampling only, not a source position label."""
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if value == 11:
        return "GK"
    if 32 <= value <= 39 or 51 <= value <= 53:
        return "DEF"
    if 62 <= value <= 79:
        return "MID"
    if 103 <= value <= 115:
        return "FWD"
    return "UNKNOWN"


def minutes(row: dict) -> float:
    try:
        return float(row["minutes_played"])
    except (ValueError, TypeError, KeyError):
        return float("inf")


def choose(rows: list[dict], target: int, rng: random.Random) -> list[tuple[dict, str, str]]:
    selected: list[tuple[dict, str, str]] = []
    used = set()

    def add(row, reason, exception=""):
        key = (row["fotmob_player_id"], row["fotmob_team_id"])
        if key not in used and len(selected) < target:
            used.add(key)
            selected.append((row, reason, exception))

    low = sorted((r for r in rows if minutes(r) < 90 and position_group(r["position"]) != "UNKNOWN"),
                 key=lambda r: (minutes(r), int(r["fotmob_player_id"])))
    if low:
        add(low[0], "lowest_observed_minutes", "")
    else:
        pass
    quotas = {"GK": 1, "DEF": 2, "MID": 2, "FWD": 2} if target == 8 else {
        "GK": 1, "DEF": 1, "MID": 1, "FWD": 1}
    for group, quota in quotas.items():
        count = sum(position_group(r["position"]) == group for r, _, _ in selected)
        pool = [r for r in rows if position_group(r["position"]) == group and
                (r["fotmob_player_id"], r["fotmob_team_id"]) not in used]
        pool.sort(key=lambda r: (-minutes(r), int(r["fotmob_player_id"])))
        if pool and count < quota:
            add(pool[0], f"highest_minutes_{group}")
        count = sum(position_group(r["position"]) == group for r, _, _ in selected)
        remaining = [r for r in pool if (r["fotmob_player_id"], r["fotmob_team_id"]) not in used]
        rng.shuffle(remaining)
        for row in remaining[:max(0, quota - count)]:
            add(row, f"seeded_{group}")
    fallback = [r for r in rows if (r["fotmob_player_id"], r["fotmob_team_id"]) not in used and
                position_group(r["position"]) != "UNKNOWN"]
    fallback.sort(key=lambda r: (minutes(r), int(r["fotmob_player_id"])))
    rng.shuffle(fallback)
    for row in fallback:
        if len(selected) >= target:
            break
        add(row, "seeded_eighth_slot")
    return selected


def choose_light(rows: list[dict], roles: tuple[str, str], rng: random.Random) -> list[tuple[dict, str, str]]:
    selected = []
    used = set()
    for role in roles:
        if role == "LOW":
            pool = sorted((r for r in rows if minutes(r) < 90 and position_group(r["position"]) != "UNKNOWN" and
                           r["fotmob_player_id"] not in used),
                          key=lambda r: (minutes(r), int(r["fotmob_player_id"])))
            reason = "lowest_observed_minutes"
        else:
            pool = sorted((r for r in rows if position_group(r["position"]) == role and
                           r["fotmob_player_id"] not in used),
                          key=lambda r: (-minutes(r), int(r["fotmob_player_id"])))
            reason = f"highest_minutes_{role}"
        if pool:
            row = pool[0]
            selected.append((row, reason, ""))
            used.add(row["fotmob_player_id"])
        else:
            fallback = [r for r in rows if r["fotmob_player_id"] not in used and
                        position_group(r["position"]) != "UNKNOWN"]
            fallback.sort(key=lambda r: int(r["fotmob_player_id"]))
            rng.shuffle(fallback)
            if fallback:
                row = fallback[0]
                selected.append((row, "seeded_role_fallback", f"requested_{role}_unavailable"))
                used.add(row["fotmob_player_id"])
    return selected


def standings(store: PilotStore) -> dict[str, list[tuple[str, str, int]]]:
    result = {}
    for meta, payload in store.cached_payloads("leagues"):
        season = meta["season_label"]
        if meta["params"].get("season") != season:
            continue
        teams = []
        for block in payload.get("table") or []:
            all_rows = (((block.get("data") or {}).get("table") or {}).get("all") or [])
            if len(all_rows) >= 20:
                teams = [(str(t["id"]), t["name"], int(t.get("idx") or rank))
                         for rank, t in enumerate(all_rows, 1) if t.get("id") is not None]
                break
        result[season] = sorted(teams, key=lambda x: x[2])
    return result


def generate_sample(store: PilotStore, references: list[dict]) -> list[dict]:
    by_season_team = defaultdict(list)
    for row in references:
        by_season_team[(row["season_label"], row["fotmob_team_id"])].append(row)
    league_standings = standings(store)
    rng = random.Random(store.config["random_seed"])
    output = []
    for season in store.config["seasons"]:
        deep = season in store.config["deep_seasons"]
        table = league_standings.get(season) or []
        if len(table) != 20:
            raise ValueError(f"Expected 20 historical standings teams for {season}")
        if deep:
            ranks = [1, 7, 13, 20]
            target = store.config["deep_players_per_club"]
            selected_teams = [table[rank - 1] for rank in ranks]
        else:
            ranks = [1, 7, 13, 20]
            target = 2
            selected_teams = [table[rank - 1] for rank in ranks]
        for team_id, team_name, rank in selected_teams:
            if deep:
                picked = choose(by_season_team[(season, team_id)], target, rng)
            else:
                roles_by_rank = {1: ("GK", "DEF"), 7: ("MID", "FWD"),
                                 13: ("DEF", "MID"), 20: ("FWD", "LOW")}
                picked = choose_light(by_season_team[(season, team_id)], roles_by_rank[rank], rng)
            for player, reason, exception in picked:
                group = position_group(player["position"])
                output.append({
                    "season_label": season, "fotmob_season_id": player["fotmob_season_id"],
                    "pilot_depth": "DEEP" if deep else "LIGHT",
                    "club_context_rank": rank, "fotmob_team_id": team_id,
                    "team_name": team_name, "fotmob_player_id": player["fotmob_player_id"],
                    "player_name": player["player_name"],
                    "historical_position_code": player["position"], "position_group": group,
                    "position_group_basis": "inferred_from_season_stat_code_band",
                    "minutes_played": player["minutes_played"],
                    "low_minutes": minutes(player) < 90,
                    "selection_reason": reason, "exception_note": exception,
                    "historical_validity_status": player["historical_validity_status"],
                    "reference_source": player["reference_source"],
                    "evidence_source_ids": player["evidence_source_ids"],
                })
    output.sort(key=lambda r: (r["season_label"], r["club_context_rank"],
                               int(r["fotmob_player_id"])))
    return output


def save_sample(store: PilotStore) -> int:
    ref_path = store.root / store.config["report_dir"] / "player_reference_index.csv"
    with ref_path.open(encoding="utf-8", newline="") as handle:
        references = list(csv.DictReader(handle))
    sample = generate_sample(store, references)
    report_dir = store.root / store.config["report_dir"]
    write_csv(report_dir / "pilot_sample_manifest.csv", SAMPLE_FIELDS, sample)
    by_season = defaultdict(list)
    for row in sample:
        by_season[row["season_label"]].append(row)
    lines = ["# Phase 2A deterministic pilot sample", "",
             f"Seed: `{store.config['random_seed']}`. Reference: season-scoped goals, minutes and saves boards.",
             "Deep seasons use standings ranks 1, 7, 13 and 20; each club targets eight players.",
             "Light seasons use the same ranks with two players per club: GK/DEF, MID/FWD,",
             "DEF/MID, and FWD/low-minute respectively. This yields a 120-row target.",
             "Within each club, selection prioritizes the lowest observed minutes (<90), then position quotas,",
             "top-minute representatives and seeded draws. Extra slots use seeded draws from supported code bands.",
             "Position groups are code-band inferences for sampling: GK=11, DEF=32–39/51–53,",
             "MID=62–79, FWD=103–115. These are not verified FotMob historical role labels.",
             "No multi-club player was found across these three boards; none was invented for the sample.", "",
             "| Season | Depth | Rows | GK | DEF | MID | FWD | Low-minute |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for season in store.config["seasons"]:
        rows = by_season[season]
        counts = Counter(r["position_group"] for r in rows)
        lines.append(f"| {season} | {'DEEP' if season in store.config['deep_seasons'] else 'LIGHT'} | "
                     f"{len(rows)} | {counts['GK']} | {counts['DEF']} | {counts['MID']} | {counts['FWD']} | "
                     f"{sum(r['low_minutes'] for r in rows)} |")
    lines += ["", "## Exceptions and limits", "",
              "Each `exception_note` in the manifest identifies a role fallback.",
              "Unknown position codes are excluded from the stratified sample.",
              "The source reference is incomplete relative to the unknown full player population,",
              "so this sample is representative only of the observed boards and cannot establish league coverage.",
              "Current team squads were rejected as historical evidence; transferred/multi-club cases remain unresolved."]
    exceptions = [r for r in sample if r["exception_note"]]
    lines += ["", f"Exception rows: {len(exceptions)}. Details are in `pilot_sample_manifest.csv`."]
    atomic_write(report_dir / "pilot_sampling_report.md", ("\n".join(lines) + "\n").encode("utf-8"))
    return len(sample)
