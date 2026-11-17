"""Step 5: test each FotMob season metric against that player's EPL matches in raw files. Read-only.

Only metrics with a per-match field can be verified this way. Anything else is reported as not verified.

Usage: python -I src/phase3/feature_window_audit.py <evidence_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
FM = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
# Season metric -> per-match field. Sum-type metrics only; rates are handled separately.
SUM_FIELDS = {
    "minutes_played": "minutes_played", "goals": "goals", "assists": "assists", "expected_goals": "expected_goals", "expected_assists": "expected_assists", "non_penalty_xg": "expected_goals_non_penalty",
    "expected_goals_on_target": "expected_goals_on_target_variant", "accurate_passes": "accurate_passes", "accurate_long_passes": "long_balls_accurate", "aerials_won": "aerials_won", "blocked_shots": "shot_blocks", "chances_created": "chances_created",
    "big_chances_created": "big_chance_created_team_title", "clearances": "clearances", "dribbles_succeeded": "dribbles_succeeded", "duels_won": "duel_won", "fouls_committed": "fouls", "fouls_won": "was_fouled", "goals_conceded": "goals_conceded", "goals_prevented": "goals_prevented",
    "interceptions": "interceptions", "penalty_saves": "saved_penalties", "recoveries": "recoveries", "saves": "saves", "shots": "total_shots", "shots_on_target": "ShotsOnTarget", "successful_crosses": "accurate_crosses", "tackles": "matchstats.headers.tackles", "touches": "touches", "touches_opposition_box": "touches_opp_box",
}
FLOAT_METRICS = {"expected_goals", "expected_assists", "non_penalty_xg", "expected_goals_on_target", "goals_prevented"}
MIN_COMPARED = 20
# The per-match field only appears when the event happens, so low match coverage is expected.
RARE_EVENT_METRICS = {"penalty_saves"}
VERIFIED_SHARE = 0.98
FULL_MATCH_COVERAGE = 0.90


def values_of(player: dict) -> dict:
    found = {}
    for group in player.get("stats") or []:
        for obj in (group.get("stats") or {}).values():
            if isinstance(obj, dict) and obj.get("key"):
                value = (obj.get("stat") or {}).get("value")
                if obj["key"] not in found and isinstance(value, (int, float)) and not isinstance(value, bool):
                    found[obj["key"]] = float(value)
    return found


def main() -> None:
    evidence = Path(sys.argv[1])
    evidence.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    appearances = con.execute(f"""SELECT p.match_id, p.player_id, p.season_label, p.raw_path FROM read_parquet('{(FM / 'normalized/player_match_appearances.parquet').as_posix()}') p
        SEMI JOIN read_parquet('{(FM / 'normalized/confirmed_appeared_player_seasons.parquet').as_posix()}') c ON p.player_id=c.player_id AND p.season_label=c.season_label WHERE p.participation_status IN ('STARTED','SUBSTITUTED_ON') ORDER BY p.raw_path""").fetchall()
    by_path = defaultdict(list)
    for match_id, pid, season, path in appearances:
        by_path[path].append((match_id, pid, season))
    totals, ratings = defaultdict(lambda: defaultdict(float)), defaultdict(list)
    recorded, matches_with = defaultdict(set), defaultdict(set)
    seasons_matches = defaultdict(set)
    for path, items in by_path.items():
        stats = (json.loads((ROOT / path).read_text(encoding="utf-8")).get("content") or {}).get("playerStats") or {}
        for match_id, pid, season in items:
            seasons_matches[season].add(match_id)
            values = values_of(stats.get(pid) or {})
            if "rating_title" in values:
                ratings[(pid, season)].append(values["rating_title"])
            for field, value in values.items():
                totals[(pid, season)][field] += value
                recorded[(pid, season, field)].add(match_id)
                matches_with[(season, field)].add(match_id)
    schema = pq.read_schema(FM / "curated/confirmed_appeared_player_seasons.parquet")
    metrics = sorted(f.name[2:] for f in schema if f.name.startswith("m_"))
    current = pq.read_table(FM / "curated/confirmed_appeared_player_seasons.parquet", columns=["player_id", "season_label", *[f"m_{m}" for m in metrics]]).to_pylist()
    results = []
    for metric in metrics:
        for season in sorted(seasons_matches):
            rows = [r for r in current if r["season_label"] == season]
            non_null = sum(r[f"m_{metric}"] is not None for r in rows)
            result = {"metric": metric, "season": season, "rows": len(rows), "season_value_non_null": non_null, "per_match_field": SUM_FIELDS.get(metric), "compared": None, "agree": None, "agree_pct": None, "matches_with_field": None, "match_coverage_pct": None, "median_season_to_match_ratio": None, "window_status": "NOT_VERIFIABLE_FROM_MATCH_DATA"}
            if metric in SUM_FIELDS:
                field = SUM_FIELDS[metric]
                tolerance = 0.1 if metric in FLOAT_METRICS else 0.5
                pairs = [(r[f"m_{metric}"], totals[(r["player_id"], season)][field]) for r in rows if r[f"m_{metric}"] is not None and (r["player_id"], season, field) in recorded]
                agree = sum(abs(a - b) <= tolerance for a, b in pairs)
                coverage = len(matches_with[(season, field)]) / len(seasons_matches[season])
                result.update(compared=len(pairs), agree=agree, agree_pct=round(100 * agree / len(pairs), 2) if pairs else None, matches_with_field=len(matches_with[(season, field)]), match_coverage_pct=round(100 * coverage, 2))
                ratios = sorted(a / b for a, b in pairs if b)
                result["median_season_to_match_ratio"] = round(ratios[len(ratios) // 2], 3) if ratios else None
                if non_null == 0:
                    result["window_status"] = "NO_SEASON_VALUES"
                elif metric in RARE_EVENT_METRICS and pairs and agree / len(pairs) >= VERIFIED_SHARE:
                    result["window_status"] = "RARE_EVENT_CONSISTENT"
                elif coverage < FULL_MATCH_COVERAGE:
                    result["window_status"] = "PARTIAL_MATCH_COVERAGE"
                elif len(pairs) >= MIN_COMPARED and agree / len(pairs) >= VERIFIED_SHARE:
                    result["window_status"] = "FULL_EPL_SEASON_VERIFIED"
                else:
                    result["window_status"] = "DISAGREES_WITH_MATCH_SUM"
            elif metric == "appearances":
                pairs = [(r["m_appearances"], len(recorded.get((r["player_id"], season, "minutes_played"), ()))) for r in rows if r["m_appearances"] is not None]
                agree = sum(a == b for a, b in pairs)
                result.update(compared=len(pairs), agree=agree, agree_pct=round(100 * agree / len(pairs), 2) if pairs else None, per_match_field="count of appearance rows")
                result["window_status"] = "FULL_EPL_SEASON_VERIFIED" if pairs and agree / len(pairs) >= VERIFIED_SHARE else "DISAGREES_WITH_MATCH_SUM"
            elif metric == "rating":
                pairs = [(r["m_rating"], sum(ratings[(r["player_id"], season)]) / len(ratings[(r["player_id"], season)])) for r in rows if r["m_rating"] is not None and ratings.get((r["player_id"], season))]
                agree = sum(abs(a - b) <= 0.1 for a, b in pairs)
                result.update(compared=len(pairs), agree=agree, agree_pct=round(100 * agree / len(pairs), 2) if pairs else None, per_match_field="mean of rating_title")
                result["window_status"] = "FULL_EPL_SEASON_VERIFIED" if pairs and agree / len(pairs) >= VERIFIED_SHARE else "MEAN_DIFFERS_FROM_SEASON_VALUE"
            elif non_null == 0:
                result["window_status"] = "NO_SEASON_VALUES"
            results.append(result)
    with (evidence / "feature_window_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print({m: sorted({r["window_status"] for r in results if r["metric"] == m}) for m in metrics})
    for r in results:
        if r["window_status"] in ("PARTIAL_MATCH_COVERAGE", "DISAGREES_WITH_MATCH_SUM", "MEAN_DIFFERS_FROM_SEASON_VALUE"):
            print(r["metric"], r["season"], r["window_status"], r["compared"], r["agree_pct"], r["match_coverage_pct"], r["median_season_to_match_ratio"], r["per_match_field"])


if __name__ == "__main__":
    main()
