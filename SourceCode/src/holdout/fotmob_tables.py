"""Holdout (D10): rebuild the FotMob player-season tables for one season from raw responses.

Reuses the frozen Phase 2 parsing and decision functions unchanged:
  participation  final_acceptance_fix.evaluate_match + remediation_substitutions.classify_participation_verified
  population     final_acceptance_fix.population_status (CONFIRMED_APPEARED = at least one start or sub-on)
  metrics        statistics_semantics.collapse_stat_occurrences + statistics_report.player_metric (dictionary v3)
  board checks   statistics_report reconcile rule + remediation_conflicts.classify_conflict, xG/xA board fallback
  positions      the exact (source_field, code) -> group map used in release v3.1
  profiles       normalize_pilot.iso_utc / nationality
`validate_2024_25()` rebuilds 2024/25 from its saved raw files and compares the result with release v3.1.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb
import yaml

from src.audit.normalization import leaderboard_rows
from src.collection.final_acceptance_fix import evaluate_match, population_status
from src.collection.normalize_pilot import iso_utc, nationality, parse_number
from src.collection.remediation_conflicts import classify_conflict
from src.collection.remediation_substitutions import classify_participation_verified
from src.collection.statistics_report import player_metric
from src.collection.statistics_semantics import collapse_stat_occurrences, value_status

ROOT = Path(__file__).resolve().parents[2]
V31 = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
DICTIONARY = ROOT / "reports/phase_02b1/metric_dictionary_v3.csv"
SPECS = yaml.safe_load((ROOT / "configs/statistics_collection.yaml").read_text(encoding="utf-8"))["leaderboard_specs"]


def metric_rules() -> list[dict]:
    with DICTIONARY.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def position_map() -> dict[tuple[str, str], str]:
    rows = duckdb.sql(f"SELECT DISTINCT source_field, original_code, mapped_group FROM '{(V31 / 'normalized/historical_position_observations.parquet').as_posix()}'").fetchall()
    out = {(f, c): g for f, c, g in rows}
    assert len(out) == len(rows), "position map is not a function"
    return out


def match_rows(detail: dict, fixture: dict, pos_map: dict) -> tuple[list[dict], list[dict], dict]:
    """Player-match participation and position observations for one match."""
    ev = evaluate_match(detail, fixture)
    if ev["completeness"] == "CONFLICTING":
        raise ValueError(f"CRITICAL_MATCH_EVIDENCE_CONFLICT:{fixture['match_id']}")
    lineup = (detail.get("content") or {}).get("lineup") or {}
    pma, pos = [], []
    for side_key, team in (("homeTeam", fixture["home_team_id"]), ("awayTeam", fixture["away_team_id"])):
        side = lineup.get(side_key) or {}
        for role, members in (("STARTER", side.get("starters") or []), ("SUBSTITUTE", side.get("subs") or [])):
            for m in members:
                if not isinstance(m, dict) or m.get("id") is None:
                    continue
                pid = str(m["id"])
                status, *_ = classify_participation_verified(pid, role, ev["starter_ids"], ev["lineup_in"], ev["fact_in"], ev["completeness"])
                pma.append({"match_id": str(fixture["match_id"]), "team_id": str(team), "player_id": pid, "player_name": m.get("name"),
                            "lineup_role": role, "participation_status": status, "match_date_utc": fixture["match_date_utc"]})
                fields = [("usualPlayingPositionId", m.get("usualPlayingPositionId"))] + ([("positionId", m.get("positionId"))] if role == "STARTER" or m.get("positionId") is not None else [])
                for field, code in fields:
                    if code is None:
                        continue
                    pos.append({"match_id": str(fixture["match_id"]), "player_id": pid, "team_id": str(team), "source_field": field,
                                "original_code": str(code), "mapped_group": pos_map.get((field, str(code)), "UNMAPPED_NEW_CODE")})
    return pma, pos, ev


def season_population(pma: list[dict]) -> dict[str, dict]:
    by_player = defaultdict(list)
    for r in pma:
        by_player[r["player_id"]].append(r)
    out = {}
    for pid, rows in by_player.items():
        if population_status(rows) != "CONFIRMED_APPEARED":
            continue
        teams = sorted({r["team_id"] for r in rows if r["participation_status"] in ("STARTED", "SUBSTITUTED_ON")}, key=int)
        out[pid] = {"player_id": pid, "player_name": Counter(r["player_name"] for r in rows).most_common(1)[0][0], "confirmed_team_ids": teams,
                    "confirmed_appearance_count": sum(r["participation_status"] in ("STARTED", "SUBSTITUTED_ON") for r in rows),
                    "started_match_count": sum(r["participation_status"] == "STARTED" for r in rows)}
    return out


def modal_position(pos: list[dict]) -> dict[str, str]:
    counts = defaultdict(Counter)
    for r in pos:
        if r["mapped_group"] not in ("UNKNOWN", "UNMAPPED_NEW_CODE"):
            counts[r["player_id"]][r["mapped_group"]] += 1
    return {pid: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for pid, c in counts.items()}


def board_values(boards: dict[str, dict]) -> dict[str, dict[str, tuple]]:
    """{metric: {player_id: (raw, value, team_id)}} from leaderboard payloads keyed by stat."""
    out = {}
    for spec in SPECS:
        payload = boards.get(spec["stat"])
        if payload is None:
            continue
        key = "substatValue" if spec["source_field"].startswith("substat") else "statValue"
        if key == "substatValue" and payload.get("substatTitle") != spec.get("required_substat_title"):
            continue
        rows = {}
        for r in leaderboard_rows(payload):
            node = r.get(key)
            raw = node.get("value") if isinstance(node, dict) else None
            if raw is not None:
                rows[str(r["id"])] = (str(raw), parse_number(raw), str(r.get("teamId")))
        out[spec["metric"]] = rows
    return out


def player_metrics(stats: dict | None, team_count: int, boards: dict, pid: str, rules: list[dict]) -> dict:
    items = collapse_stat_occurrences(stats)[0] if stats else {}
    row = {}
    for rule in rules:
        metric = rule["normalized_field"]
        raw, *_ = player_metric(items, rule)
        status, value = value_status(raw) if stats else ("MISSING", None)
        board = boards.get(metric, {}).get(pid)
        if value is not None and board is not None and board[1] is not None and team_count == 1:
            decimals = len(board[0].split(".", 1)[1]) if "." in board[0] and "e" not in board[0].lower() else 0
            shown = float(Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))
            if abs(board[1] - value) >= 1e-9 and shown != board[1]:
                _, _, action, resolved, resolved_status = classify_conflict({"metric_name": metric, "board_value": board[1], "player_stats_value": value})
                if action in ("RESOLVED_ROUNDING_TOLERANCE", "RECONCILED_PREFERRED_SOURCE"):
                    status, value = resolved_status, resolved
                else:
                    status, value = "CONFLICTING", None
        elif value is None and metric in ("expected_goals", "expected_assists") and board is not None and board[1] is not None:
            status, value = "OBSERVED_FALLBACK_LEADERBOARD", board[1]
        elif value is None and status in ("OBSERVED", "OBSERVED_ZERO"):
            status = "MISSING"
        row["m_" + metric], row["s_" + metric] = value, status
    return row


def profile_fields(profile: dict | None) -> dict:
    if not profile:
        return {"birth_date": None, "nationality_name": None, "profile_name": None, "current_position": None}
    birth = iso_utc((profile.get("birthDate") or {}).get("utcTime"))
    return {"birth_date": birth[:10] if birth else None, "nationality_name": nationality(profile), "profile_name": profile.get("name"),
            "current_position": ((profile.get("positionDescription") or {}).get("primaryPosition") or {}).get("label")}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_2024_25() -> dict:
    """Rebuild 2024/25 from the exact raw files release v3.1 used, and compare."""
    con = duckdb.connect()
    n = (V31 / "normalized").as_posix()
    fixtures = {r[0]: dict(zip(("match_id", "match_date_utc", "home_team_id", "away_team_id", "competition_id", "season_id", "season_label"), r))
                for r in con.execute(f"SELECT match_id, match_date_utc, home_team_id, away_team_id, competition_id, season_id, season_label FROM '{n}/matches.parquet' WHERE season_label='2024/2025' AND match_status='COMPLETED'").fetchall()}
    paths = dict(con.execute(f"SELECT DISTINCT match_id, raw_path FROM '{n}/player_match_appearances.parquet' WHERE season_label='2024/2025'").fetchall())
    pos_map, pma, pos = position_map(), [], []
    for mid, fixture in fixtures.items():
        p = ROOT / paths[mid]
        a, b, _ = match_rows(load_json(p / "response.json" if p.is_dir() else p), fixture, pos_map)
        pma += a
        pos += b
    population = season_population(pma)
    ref = {r[0]: r for r in con.execute(f"SELECT player_id, confirmed_appearance_count, started_match_count FROM '{n}/confirmed_appeared_player_seasons.parquet' WHERE season_label='2024/2025'").fetchall()}
    modal = modal_position(pos)
    ref_pos = dict(con.execute(f"""SELECT player_id, mapped_group FROM (SELECT player_id, mapped_group, row_number() OVER (PARTITION BY player_id ORDER BY count(*) DESC, mapped_group) rk
                                    FROM '{n}/historical_position_observations.parquet' WHERE season_id='23685' AND mapped_group<>'UNKNOWN' GROUP BY 1,2) WHERE rk=1""").fetchall())
    boards = {}
    for p in sorted((ROOT / "data/phase_02b1/raw/2024_2025/leagueseasondeepstats").glob("cap_*/metadata.json")):
        meta = load_json(p)
        boards.setdefault(meta["params"]["stat"], load_json(p.with_name("response.json")))
    bv, rules = board_values(boards), metric_rules()
    cur = con.execute(f"SELECT * FROM '{(V31 / 'curated/confirmed_appeared_player_seasons.parquet').as_posix()}' WHERE season_label='2024/2025'").df()
    diffs, cells = Counter(), Counter()
    for r in cur.to_dict("records"):
        sp = r["stats_raw_path"]
        stats = load_json(ROOT / sp) if isinstance(sp, str) and sp and "playerStats" in sp else None
        mine = player_metrics(stats, int(r["confirmed_team_count"]), bv, r["player_id"], rules)
        for k, v in mine.items():
            if not k.startswith("m_"):
                continue
            a = r[k]
            a = None if a is None or (isinstance(a, float) and a != a) else float(a)
            cells[k] += 1
            if not ((a is None and v is None) or (a is not None and v is not None and abs(a - v) < 1e-6)):
                diffs[k] += 1
    return {"population_rebuilt": len(population), "population_release": len(ref), "population_symmetric_difference": len(set(population) ^ set(ref)),
            "appearance_count_mismatch": sum(population[p]["confirmed_appearance_count"] != ref[p][1] for p in set(population) & set(ref)),
            "position_mismatch": sum(modal.get(p) != ref_pos.get(p) for p in ref), "players_compared": len(cur),
            "metric_cells_compared": sum(cells.values()), "metric_cell_mismatch": dict(diffs)}


if __name__ == "__main__":
    print(json.dumps(validate_2024_25(), indent=1))
