"""Step 4.1 follow-ups: tighter feature-window checks, effective age of April 2020 values, and quality flags.

Writes only to the audit folder. The target dataset is not changed; flags are a separate table for later joining.

Usage: python -I src/phase3/step4_1_followups.py <evidence_dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
FM = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
TARGET = ROOT / "data/phase_03/targets/target_v1__matching_v2_1/player_season_target.parquet"
RAW = ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz"
ADJUSTMENT_DATE = date(2020, 4, 8)


def main() -> None:
    evidence = Path(sys.argv[1])
    con = duckdb.connect(":memory:")
    window = pq.read_table(evidence / "temporal_alignment_by_player_season.parquet").to_pylist()
    current = {(r["player_id"], r["season_label"]): r for r in pq.read_table(FM / "curated/confirmed_appeared_player_seasons.parquet", columns=["player_id", "season_label", "m_expected_goals", "m_expected_assists", "m_minutes_played", "s_expected_goals", "s_expected_assists"]).to_pylist()}
    out: dict = {}
    # Tight comparison of xG and xA: season value against the sum of EPL matches.
    tight = {}
    for metric, column in (("expected_goals", "m_expected_goals"), ("expected_assists", "m_expected_assists")):
        tight[metric] = {}
        for season in sorted({r["season"] for r in window}):
            gaps, absent_values, absent_status = [], [], Counter()
            for r in (x for x in window if x["season"] == season):
                value = current[(r["fotmob_player_id"], season)][column]
                total = r[f"{metric}_total"]
                if value is not None and total is not None:
                    gaps.append(abs(value - total))
                elif value is not None and total is None:
                    absent_values.append(value)
            tight[metric][season] = {"compared": len(gaps), "within_0.02": sum(g <= 0.02 for g in gaps), "within_0.05": sum(g <= 0.05 for g in gaps), "within_0.10": sum(g <= 0.10 for g in gaps), "max_gap": round(max(gaps), 3) if gaps else None,
                                     "median_gap": round(median(gaps), 4) if gaps else None, "season_value_without_match_value": len(absent_values), "nonzero_among_those": sum(v != 0 for v in absent_values), "median_of_those": median(absent_values) if absent_values else None}
    out["xg_xa_tight"] = tight
    # 2019/20 xG: how much of each player's season can the season value represent?
    rows = [r for r in window if r["season"] == "2019/2020"]
    with_season_xg = [r for r in rows if current[(r["fotmob_player_id"], "2019/2020")]["m_expected_goals"] is not None]
    out["xg_2019_20"] = {"confirmed_rows": len(rows), "rows_with_season_xg": len(with_season_xg), "median_games_with_match_xg_among_them": median(r["expected_goals_games_recorded"] for r in with_season_xg), "median_games_played_among_them": median(r["games_total"] for r in with_season_xg), "total_games_recorded": sum(r["expected_goals_games_recorded"] for r in rows), "total_games": sum(r["games_total"] for r in rows)}
    pm = (FM / "normalized/player_match_appearances.parquet").as_posix()
    paths = con.execute(f"SELECT DISTINCT match_id, substr(match_date_utc,1,10) d, raw_path FROM read_parquet('{pm}') WHERE season_label='2019/2020' ORDER BY 2").fetchall()
    xg_matches = []
    for match_id, day, path in paths:
        body = json.loads((ROOT / path).read_text(encoding="utf-8"))
        stats = (body.get("content") or {}).get("playerStats") or {}
        count = 0
        for player in stats.values():
            for group in player.get("stats") or []:
                obj = (group.get("stats") or {})
                count += any(isinstance(v, dict) and v.get("key") == "expected_goals" and (v.get("stat") or {}).get("value") is not None for v in obj.values())
        if count:
            header = (body.get("general") or {})
            xg_matches.append({"match_id": match_id, "date": day, "players_with_xg": count, "home": (header.get("homeTeam") or {}).get("name"), "away": (header.get("awayTeam") or {}).get("name")})
    out["xg_2019_20_matches"] = xg_matches
    # The few minutes outliers.
    outliers = []
    for r in window:
        value = current[(r["fotmob_player_id"], r["season"])]["m_minutes_played"]
        if value is not None and r["minutes_played_total"] is not None and abs(value - r["minutes_played_total"]) > 0.5:
            outliers.append({"fotmob_player_id": r["fotmob_player_id"], "season": r["season"], "season_minutes": value, "match_sum": r["minutes_played_total"], "games": r["games_total"]})
    out["minutes_outliers"] = outliers
    # Abandoned fixture: does the source include it in season minutes?
    con.execute(f"CREATE VIEW target AS SELECT * FROM read_parquet('{TARGET.as_posix()}')")
    con.execute(f"""CREATE TABLE raw_v AS SELECT row_number() OVER () rn, player_id, try_cast(date AS DATE) d, try_cast(market_value_in_eur AS BIGINT) m FROM read_csv('{RAW.as_posix()}', all_varchar=true, header=true)""")
    con.execute("CREATE TEMP TABLE chain AS SELECT player_id, d, m, lag(m) OVER w prev_m, lag(d) OVER w prev_d, lead(d) OVER w next_d, lead(m) OVER w next_m FROM raw_v WHERE m>0 WINDOW w AS (PARTITION BY player_id ORDER BY d)")
    target_rows = con.execute("""SELECT t.canonical_player_id, t.fotmob_player_id, t.season, t.season_end_date, t.selected_valuation_date, t.market_value, t.valuation_age_days, c.prev_m, c.prev_d, c.next_d, c.next_m, t.player_games_in_season, t.player_games_after_valuation
        FROM target t LEFT JOIN chain c ON c.player_id=t.transfermarkt_player_id AND c.d=t.selected_valuation_date ORDER BY t.season, t.canonical_player_id""").fetchall()
    names = ["canonical_player_id", "fotmob_player_id", "season", "season_end_date", "selected_valuation_date", "market_value", "valuation_age_days", "previous_value", "previous_valuation_date", "next_valuation_date", "next_value", "player_games_in_season", "player_games_after_valuation"]
    games_by_key = defaultdict(list)
    for fid, season, day in con.execute(f"SELECT player_id, season_label, substr(match_date_utc,1,10) FROM read_parquet('{pm}') WHERE participation_status IN ('STARTED','SUBSTITUTED_ON')").fetchall():
        games_by_key[(fid, season)].append(date.fromisoformat(day))
    flags = []
    for row in target_rows:
        record = dict(zip(names, row))
        chosen = record["selected_valuation_date"]
        adjusted = chosen == ADJUSTMENT_DATE
        record["on_2020_04_08_batch"] = adjusted
        record["ratio_to_previous_value"] = round(record["market_value"] / record["previous_value"], 4) if record["market_value"] and record["previous_value"] else None
        record["last_valuation_before_2020_04_08_batch"] = record["previous_valuation_date"] if adjusted else chosen
        effective = record["last_valuation_before_2020_04_08_batch"]
        record["age_days_from_last_non_batch_valuation"] = (record["season_end_date"] - effective).days if effective else None
        games = games_by_key[(record["fotmob_player_id"], record["season"])]
        record["player_games_after_last_non_batch_valuation"] = sum(d > effective for d in games) if effective else None
        flags.append(record)
    schema = pa.schema([("canonical_player_id", pa.string()), ("fotmob_player_id", pa.string()), ("season", pa.string()), ("season_end_date", pa.date32()), ("selected_valuation_date", pa.date32()), ("market_value", pa.int64()), ("valuation_age_days", pa.int32()), ("previous_value", pa.int64()), ("previous_valuation_date", pa.date32()), ("next_valuation_date", pa.date32()), ("next_value", pa.int64()), ("player_games_in_season", pa.int32()), ("player_games_after_valuation", pa.int32()), ("on_2020_04_08_batch", pa.bool_()), ("ratio_to_previous_value", pa.float64()), ("last_valuation_before_2020_04_08_batch", pa.date32()), ("age_days_from_last_non_batch_valuation", pa.int32()), ("player_games_after_last_non_batch_valuation", pa.int32())])
    pq.write_table(pa.table({f.name: pa.array([r[f.name] for r in flags], f.type) for f in schema}), evidence / "target_quality_flags.parquet", compression="zstd")
    adjusted = [r for r in flags if r["on_2020_04_08_batch"]]
    out["batch_2020_04_08"] = {
        "rows_by_season": dict(Counter(r["season"] for r in adjusted)), "with_previous_value": sum(r["previous_value"] is not None for r in adjusted),
        "median_previous_valuation_date": str(sorted(r["previous_valuation_date"] for r in adjusted if r["previous_valuation_date"])[sum(r["previous_valuation_date"] is not None for r in adjusted) // 2]),
        "top_previous_dates": Counter(str(r["previous_valuation_date"]) for r in adjusted).most_common(5),
        "median_age_reported": median(r["valuation_age_days"] for r in adjusted), "median_age_from_previous_valuation": median(r["age_days_from_last_non_batch_valuation"] for r in adjusted if r["age_days_from_last_non_batch_valuation"] is not None),
        "pct_games_after_batch": round(100 * sum(r["player_games_after_valuation"] for r in adjusted) / sum(r["player_games_in_season"] for r in adjusted), 2),
        "pct_games_after_previous_valuation": round(100 * sum(r["player_games_after_last_non_batch_valuation"] or 0 for r in adjusted) / sum(r["player_games_in_season"] for r in adjusted), 2),
    }
    usable = [r for r in flags if r["market_value"] is not None]
    out["overall_with_previous_valuation_substituted_for_timing_only"] = {
        "pct_over_90_days": round(100 * sum(r["age_days_from_last_non_batch_valuation"] > 90 for r in usable) / len(usable), 2),
        "pct_games_after": round(100 * sum(r["player_games_after_last_non_batch_valuation"] for r in usable) / sum(r["player_games_in_season"] for r in usable), 2),
        "note": "Descriptive only. No date or value was replaced in the target dataset.",
    }
    (evidence / "step_04_1_followups.json").write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
