"""Step 4.1: independent audit of Step 4 targets. Read-only on all inputs; writes only to the audit folder.

Deliberately imports nothing from season_targets.py: selection is recomputed in SQL from the original CSV.

Usage: python -I src/phase3/step4_1_audit.py <evidence_dir>
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median, pstdev

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = ROOT / "data/phase_03/targets/target_v1__matching_v2_1"
TARGET = TARGET_DIR / "player_season_target.parquet"
CROSSWALK = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
FM = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
RAW_VALUATIONS = ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz"
TM_PLAYERS = ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_players.parquet"
SEASONS = ROOT / "configs/phase_03_seasons.yaml"
THRESHOLDS = (30, 60, 90, 180, None)
AGE_GROUPS = (("under 22", 0, 21.999), ("22-25", 22, 25.999), ("26-29", 26, 29.999), ("30+", 30, 99))
MATCH_METRICS = {"minutes_played": "m_minutes_played", "goals": "m_goals", "assists": "m_assists", "expected_goals": "m_expected_goals", "expected_assists": "m_expected_assists"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(con, sql):
    cursor = con.execute(sql)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, r)) for r in cursor.fetchall()]


def setup(con):
    con.execute("SET threads=1")
    con.execute(f"CREATE VIEW target AS SELECT * FROM read_parquet('{TARGET.as_posix()}')")
    con.execute(f"CREATE VIEW crosswalk AS SELECT * FROM read_parquet('{CROSSWALK.as_posix()}')")
    con.execute(f"CREATE VIEW conf AS SELECT * FROM read_parquet('{(FM / 'normalized/confirmed_appeared_player_seasons.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW cur AS SELECT * FROM read_parquet('{(FM / 'curated/confirmed_appeared_player_seasons.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW pm AS SELECT * FROM read_parquet('{(FM / 'normalized/player_match_appearances.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW matches AS SELECT * FROM read_parquet('{(FM / 'normalized/matches.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW players AS SELECT * FROM read_parquet('{(FM / 'normalized/players.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW pos AS SELECT * FROM read_parquet('{(FM / 'normalized/historical_position_observations.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW tm_players AS SELECT * FROM read_parquet('{TM_PLAYERS.as_posix()}')")
    con.execute(f"""CREATE TABLE raw_v AS SELECT row_number() OVER () AS rn, player_id, date raw_date, try_cast(date AS DATE) d, market_value_in_eur raw_value, try_cast(market_value_in_eur AS BIGINT) m, current_club_name, player_club_domestic_competition_id comp
                    FROM read_csv('{RAW_VALUATIONS.as_posix()}', all_varchar=true, header=true)""")


# ---------- Task 1 ----------

def reproduce(con, config) -> dict:
    manifest = json.loads((TARGET_DIR / "target_manifest.json").read_text(encoding="utf-8"))
    out: dict = {
        "input_hash_mismatches": [k for k, v in manifest["input_sha256"].items() if sha(ROOT / k) != v],
        "output_hash_mismatches": [k for k, v in manifest["output_sha256"].items() if sha(TARGET_DIR / k) != v],
        "code_hash_mismatches": [k for k, v in manifest["code_sha256"].items() if sha(ROOT / k) != v],
        "matching_versions_in_target": [r[0] for r in con.execute("SELECT DISTINCT matching_version FROM target").fetchall()],
        "rule_versions_in_target": [r[0] for r in con.execute("SELECT DISTINCT selection_rule_version FROM target").fetchall()],
    }
    cutoffs = {s["season"]: s["season_end_date"] for s in config["seasons"]}
    con.execute("CREATE TEMP TABLE cut(season VARCHAR, cutoff DATE)")
    con.executemany("INSERT INTO cut VALUES (?, ?)", list(cutoffs.items()))
    out["cutoff_checks"] = rows(con, """SELECT c.season, c.cutoff::VARCHAR cutoff, (SELECT substr(max(match_date_utc),1,10) FROM matches m WHERE m.season_label=c.season AND m.match_status='COMPLETED') last_fotmob_match,
        (SELECT min(season_end_date)::VARCHAR FROM target t WHERE t.season=c.season) target_min, (SELECT max(season_end_date)::VARCHAR FROM target t WHERE t.season=c.season) target_max FROM cut c ORDER BY 1""")
    out["grain"] = rows(con, "SELECT count(*) n_rows, count(DISTINCT (canonical_player_id, season)) keys, count(DISTINCT canonical_player_id) players FROM target")[0]
    out["population_diff"] = rows(con, """SELECT (SELECT count(*) FROM (SELECT player_id, season_label FROM conf EXCEPT SELECT fotmob_player_id, season FROM target)) missing_from_target,
        (SELECT count(*) FROM (SELECT fotmob_player_id, season FROM target EXCEPT SELECT player_id, season_label FROM conf)) extra_in_target""")[0]
    # Independent recomputation: population + crosswalk + cutoffs + raw CSV.
    con.execute("""CREATE TEMP TABLE recomputed AS
        WITH pop AS (SELECT c.player_id, c.season_label, k.cutoff, w.transfermarkt_player_id tid, w.match_status FROM conf c JOIN crosswalk w ON c.player_id=w.fotmob_player_id JOIN cut k ON k.season=c.season_label),
        eligible AS (SELECT p.player_id, p.season_label, v.d, v.m, v.rn, v.raw_date FROM pop p JOIN raw_v v ON v.player_id=p.tid AND v.d<=p.cutoff AND v.m>0),
        latest AS (SELECT player_id, season_label, max(d) d FROM eligible GROUP BY 1,2),
        chosen AS (SELECT e.player_id, e.season_label, e.d, e.m, e.rn, e.raw_date, count(*) OVER (PARTITION BY e.player_id, e.season_label) n_same_day FROM eligible e JOIN latest l USING (player_id, season_label, d))
        SELECT p.player_id, p.season_label, p.cutoff, p.tid, p.match_status, c.d, c.m, c.rn, c.n_same_day, date_diff('day', c.d, p.cutoff) age,
               (SELECT count(*) FROM raw_v v WHERE v.player_id=p.tid) n_history
        FROM pop p LEFT JOIN chosen c ON p.player_id=c.player_id AND p.season_label=c.season_label""")
    out["recomputation"] = rows(con, """SELECT count(*) compared,
        count(*) FILTER (WHERE r.d IS DISTINCT FROM t.selected_valuation_date) date_diffs, count(*) FILTER (WHERE r.m IS DISTINCT FROM t.market_value) value_diffs,
        count(*) FILTER (WHERE r.age IS DISTINCT FROM t.valuation_age_days) age_diffs, count(*) FILTER (WHERE r.rn IS DISTINCT FROM t.source_row_number) lineage_diffs,
        count(*) FILTER (WHERE r.tid IS DISTINCT FROM t.transfermarkt_player_id) id_diffs, count(*) FILTER (WHERE r.match_status IS DISTINCT FROM t.crosswalk_status) status_diffs,
        count(*) FILTER (WHERE r.n_same_day>1) same_day_multiple
        FROM recomputed r JOIN target t ON r.player_id=t.fotmob_player_id AND r.season_label=t.season""")[0]
    out["future_selected"] = con.execute("SELECT count(*) FROM target WHERE selected_valuation_date>season_end_date").fetchone()[0]
    out["status_counts"] = dict(con.execute("SELECT target_status, count(*) FROM target GROUP BY 1").fetchall())
    out["missing_reasons"] = dict(con.execute("SELECT target_missing_reason, count(*) FROM target WHERE target_missing_reason IS NOT NULL GROUP BY 1").fetchall())
    out["status_by_season"] = rows(con, """SELECT season, count(*) n, count(*) FILTER (WHERE target_status='VALID') valid, count(*) FILTER (WHERE target_status='STALE_TARGET') stale, count(*) FILTER (WHERE target_status='TARGET_MISSING') missing,
        count(*) FILTER (WHERE valuation_age_days BETWEEN 0 AND 30) b0, count(*) FILTER (WHERE valuation_age_days BETWEEN 31 AND 60) b31, count(*) FILTER (WHERE valuation_age_days BETWEEN 61 AND 90) b61, count(*) FILTER (WHERE valuation_age_days BETWEEN 91 AND 180) b91, count(*) FILTER (WHERE valuation_age_days>180) b181,
        median(valuation_age_days) med_age, max(valuation_age_days) max_age FROM target GROUP BY 1 ORDER BY 1""")
    out["usable_pct"] = con.execute("SELECT 100.0*count(*) FILTER (WHERE market_value IS NOT NULL)/count(*) FROM target").fetchone()[0]
    out["over_90_pct"] = con.execute("SELECT 100.0*count(*) FILTER (WHERE valuation_age_days>90)/count(*) FROM target WHERE market_value IS NOT NULL").fetchone()[0]
    out["manifest_summary_matches"] = {k: (manifest["summary"]["overall"][k], ) for k in ("usable", "VALID", "STALE_TARGET", "TARGET_MISSING", "pct_older_than_90_days", "pct_player_games_after_valuation", "mean_pct_league_games_after_valuation")}
    return out


# ---------- Task 2 ----------

def concentration(con) -> dict:
    out: dict = {"source_columns": [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_csv('{RAW_VALUATIONS.as_posix()}', all_varchar=true, header=true)").fetchall()]}
    out["top_dates_all_players"] = rows(con, "SELECT d::VARCHAR d, count(*) n, count(DISTINCT comp) competitions FROM raw_v GROUP BY 1 ORDER BY 2 DESC LIMIT 15")
    out["rows_around_2020_04_08"] = rows(con, "SELECT d::VARCHAR d, count(*) n FROM raw_v WHERE d BETWEEN '2020-03-25' AND '2020-04-25' GROUP BY 1 HAVING count(*)>=50 ORDER BY 1")
    out["share_2020_04_08_by_competition"] = rows(con, """SELECT coalesce(comp,'(none)') comp, count(*) n FROM raw_v WHERE d='2020-04-08' GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")
    out["distinct_competitions_on_2020_04_08"] = con.execute("SELECT count(DISTINCT comp) FROM raw_v WHERE d='2020-04-08'").fetchone()[0]
    # Selected-date concentration per season, with what happened to values on the most common date.
    con.execute("""CREATE TEMP TABLE changes AS SELECT player_id, d, m, lag(m) OVER w prev_m, lag(d) OVER w prev_d, lead(d) OVER w next_d, lead(m) OVER w next_m FROM raw_v WHERE m>0 WINDOW w AS (PARTITION BY player_id ORDER BY d)""")
    seasons = []
    for season, in con.execute("SELECT DISTINCT season FROM target ORDER BY 1").fetchall():
        tops = rows(con, f"SELECT selected_valuation_date::VARCHAR d, count(*) n FROM target WHERE season='{season}' AND market_value IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 3")
        usable = con.execute(f"SELECT count(*), count(DISTINCT selected_valuation_date) FROM target WHERE season='{season}' AND market_value IS NOT NULL").fetchone()
        mode = tops[0]["d"]
        effect = rows(con, f"""SELECT count(*) n, count(*) FILTER (WHERE c.m<c.prev_m) down, count(*) FILTER (WHERE c.m>c.prev_m) up, count(*) FILTER (WHERE c.m=c.prev_m) same, median(1.0*c.m/c.prev_m) median_ratio, median(date_diff('day', c.prev_d, c.d)) median_days_since_prev
            FROM target t JOIN changes c ON c.player_id=t.transfermarkt_player_id AND c.d=t.selected_valuation_date WHERE t.season='{season}' AND t.selected_valuation_date='{mode}' AND c.prev_m IS NOT NULL""")[0]
        whole = rows(con, f"SELECT count(*) rows_all_players, count(DISTINCT comp) competitions, median(CASE WHEN prev_m IS NOT NULL THEN 1.0*m/prev_m END) median_ratio_all FROM changes c LEFT JOIN (SELECT DISTINCT player_id, d, comp FROM raw_v) r USING (player_id, d) WHERE d='{mode}'")[0]
        seasons.append({"season": season, "usable": usable[0], "distinct_selected_dates": usable[1], "top_dates": tops, "top_date_share_pct": round(100 * tops[0]["n"] / usable[0], 2), "effect_on_top_date_epl": effect, "same_date_all_tm": whole})
    out["seasons"] = seasons
    # Test the externally reported rule against the data, using TM birth dates.
    con.execute("""CREATE TEMP TABLE april AS SELECT c.player_id, c.m, c.prev_m, 1.0*c.m/c.prev_m ratio, p.date_of_birth dob, year(p.date_of_birth)>=1998 born_1998_plus FROM changes c JOIN tm_players p ON p.tm_player_id=c.player_id WHERE c.d='2020-04-08' AND c.prev_m IS NOT NULL AND p.date_of_birth IS NOT NULL""")
    def cohort(where):
        return rows(con, f"""SELECT count(*) n, median(ratio) median_ratio, count(*) FILTER (WHERE ratio BETWEEN 0.75 AND 0.85) near_080, count(*) FILTER (WHERE ratio BETWEEN 0.85 AND 0.95) near_090, count(*) FILTER (WHERE ratio>=1) not_reduced, quantile_cont(ratio,0.1) p10, quantile_cont(ratio,0.9) p90 FROM april WHERE {where}""")[0]
    out["april_2020_all_tm"] = {"born_before_1998": cohort("NOT born_1998_plus"), "born_1998_or_later": cohort("born_1998_plus")}
    epl = "player_id IN (SELECT transfermarkt_player_id FROM target WHERE season='2019/2020' AND selected_valuation_date='2020-04-08')"
    out["april_2020_selected_targets"] = {"born_before_1998": cohort(f"NOT born_1998_plus AND {epl}"), "born_1998_or_later": cohort(f"born_1998_plus AND {epl}")}
    # Boundary check: compare neighbors of the 1998 birth-year line.
    out["april_2020_by_birth_year"] = rows(con, "SELECT year(dob) y, count(*) n, median(ratio) median_ratio FROM april WHERE year(dob) BETWEEN 1994 AND 2001 GROUP BY 1 ORDER BY 1")
    # Baseline: another large batch, to show the pattern is not generic.
    out["comparison_other_batches_all_tm"] = rows(con, """SELECT d::VARCHAR d, count(*) n, median(1.0*m/prev_m) median_ratio, 100.0*count(*) FILTER (WHERE m<prev_m)/count(*) pct_down FROM changes WHERE prev_m IS NOT NULL AND d IN (SELECT d FROM raw_v GROUP BY 1 ORDER BY count(*) DESC LIMIT 12) GROUP BY 1 ORDER BY 2 DESC""")
    out["next_valuation_gap_after_cutoff"] = rows(con, """SELECT t.season, count(*) n, median(date_diff('day', t.season_end_date, x.nd)) median_days FROM target t JOIN (SELECT r.player_id, r.season_label, min(v.d) nd FROM recomputed r JOIN raw_v v ON v.player_id=r.tid AND v.d>r.cutoff GROUP BY 1,2) x ON x.player_id=t.fotmob_player_id AND x.season_label=t.season WHERE t.market_value IS NOT NULL GROUP BY 1 ORDER BY 1""")
    # Values after the cut for 2019/20: did the next valuation reverse the cut?
    out["next_change_after_2020_04_08"] = rows(con, """SELECT count(*) n, median(1.0*c.next_m/c.m) median_next_ratio, median(date_diff('day', c.d, c.next_d)) median_days_to_next FROM changes c JOIN target t ON t.transfermarkt_player_id=c.player_id AND t.selected_valuation_date=c.d WHERE t.season='2019/2020' AND c.d='2020-04-08' AND c.next_m IS NOT NULL""")[0]
    return out


# ---------- Task 3 ----------

def stat_values(player: dict) -> dict:
    found = {}
    for group in player.get("stats") or []:
        for obj in (group.get("stats") or {}).values():
            if isinstance(obj, dict) and obj.get("key"):
                value = (obj.get("stat") or {}).get("value")
                if obj["key"] not in found and isinstance(value, (int, float)) and not isinstance(value, bool):
                    found[obj["key"]] = float(value)
    return found


def parse_matches(con) -> tuple[dict, dict]:
    appearances = rows(con, """SELECT p.match_id, p.player_id, p.season_label, substr(p.match_date_utc,1,10) d, p.raw_path FROM pm p SEMI JOIN conf c ON p.player_id=c.player_id AND p.season_label=c.season_label WHERE p.participation_status IN ('STARTED','SUBSTITUTED_ON')""")
    by_match = defaultdict(list)
    for row in appearances:
        by_match[row["raw_path"]].append(row)
    per_game, keys_by_season, match_stats = {}, defaultdict(Counter), defaultdict(lambda: {"matches": 0, "with_any_xg": 0, "first_xg": None, "last_xg": None, "with_playerstats": 0})
    for raw_path, items in sorted(by_match.items()):
        content = (json.loads((ROOT / raw_path).read_text(encoding="utf-8")).get("content") or {})
        stats = content.get("playerStats") or {}
        season = items[0]["season_label"]
        day = items[0]["d"]
        tally = match_stats[season]
        tally["matches"] += 1
        tally["with_playerstats"] += bool(stats)
        any_xg = False
        for row in items:
            values = stat_values(stats.get(row["player_id"]) or {})
            keys_by_season[season].update(values.keys())
            per_game[(row["player_id"], row["season_label"], row["match_id"])] = {"d": row["d"], **{k: values.get(k) for k in MATCH_METRICS}}
            any_xg = any_xg or values.get("expected_goals") is not None
        if any_xg:
            tally["with_any_xg"] += 1
            tally["first_xg"] = min(tally["first_xg"] or day, day)
            tally["last_xg"] = max(tally["last_xg"] or day, day)
    return per_game, {"match_level": dict(match_stats), "stat_keys_by_season": {s: dict(c.most_common(70)) for s, c in keys_by_season.items()}}


def temporal(con, per_game: dict, match_info: dict, evidence: Path) -> dict:
    target = rows(con, "SELECT fotmob_player_id f, season, selected_valuation_date v, market_value mv, season_end_date cut, player_games_in_season g, player_games_after_valuation ga, target_status st FROM target")
    metric_cols = ", ".join(sorted(set(MATCH_METRICS.values())))
    season_values = {(r["player_id"], r["season_label"]): r for r in rows(con, f"SELECT player_id, season_label, m_appearances, {metric_cols} FROM cur")}
    games_by_key = defaultdict(list)
    for (fid, season, _), game in per_game.items():
        games_by_key[(fid, season)].append(game)
    window = []
    for row in target:
        key = (row["f"], row["season"])
        games = games_by_key[key]
        chosen = row["v"]
        record = {"fotmob_player_id": row["f"], "season": row["season"], "selected_valuation_date": chosen, "games_total": len(games)}
        for metric in MATCH_METRICS:
            values = [g[metric] for g in games if g[metric] is not None]
            record[f"{metric}_total"] = sum(values) if values else None
            record[f"{metric}_games_recorded"] = len(values)
            if chosen is not None:
                before = [g[metric] for g in games if g[metric] is not None and date.fromisoformat(g["d"]) <= chosen]
                after = [g[metric] for g in games if g[metric] is not None and date.fromisoformat(g["d"]) > chosen]
                record[f"{metric}_before"] = sum(before) if before else 0.0 if values else None
                record[f"{metric}_after"] = sum(after) if after else 0.0 if values else None
            else:
                record[f"{metric}_before"] = record[f"{metric}_after"] = None
        if chosen is not None:
            record["games_before_or_on"] = sum(date.fromisoformat(g["d"]) <= chosen for g in games)
            record["games_after"] = sum(date.fromisoformat(g["d"]) > chosen for g in games)
            record["games_on_valuation_date"] = sum(date.fromisoformat(g["d"]) == chosen for g in games)
        else:
            record["games_before_or_on"] = record["games_after"] = record["games_on_valuation_date"] = None
        window.append(record)
    types = {"fotmob_player_id": pa.string(), "season": pa.string(), "selected_valuation_date": pa.date32()}
    columns = list(window[0])
    table = pa.table({c: pa.array([r[c] for r in window], types.get(c, pa.float64())) for c in columns})
    pq.write_table(table, evidence / "temporal_alignment_by_player_season.parquet", compression="zstd")
    out: dict = {"match_level": match_info["match_level"], "per_match_stat_keys_2023_24": sorted(match_info["stat_keys_by_season"].get("2023/2024", {})), "rows": len(window)}
    # Does the season metric equal the sum of EPL matches? This is direct evidence of its observation window.
    agreement = {}
    for metric, column in MATCH_METRICS.items():
        by_season = {}
        for season in sorted({r["season"] for r in window}):
            pairs = []
            null_metric_with_match_value = no_match_value_with_metric = 0
            for record in (r for r in window if r["season"] == season):
                total = record[f"{metric}_total"]
                value = season_values[(record["fotmob_player_id"], season)][column]
                if total is not None and value is not None:
                    pairs.append((total, value))
                elif total is not None and value is None and total != 0:
                    null_metric_with_match_value += 1
                elif total is None and value is not None:
                    no_match_value_with_metric += 1
            tolerance = 0.5 if metric in ("expected_goals", "expected_assists") else 0.5
            close = sum(abs(a - b) <= tolerance for a, b in pairs)
            by_season[season] = {"both_present": len(pairs), "within_tolerance": close, "pct": round(100 * close / len(pairs), 2) if pairs else None, "median_season_value": median(b for _, b in pairs) if pairs else None,
                                 "season_null_but_match_nonzero": null_metric_with_match_value, "match_absent_but_season_present": no_match_value_with_metric, "sum_match": round(sum(a for a, _ in pairs), 2), "sum_season": round(sum(b for _, b in pairs), 2)}
        agreement[metric] = by_season
    out["season_metric_vs_match_sum"] = agreement
    out["appearances_vs_games"] = {s: {"compared": n, "equal": e} for s, n, e in con.execute("""SELECT c.season_label, count(c.m_appearances), count(*) FILTER (WHERE c.m_appearances=n.confirmed_appearance_count) FROM cur c JOIN conf n ON c.player_id=n.player_id AND c.season_id=n.season_id GROUP BY 1 ORDER BY 1""").fetchall()}
    # Before and after split, for usable targets.
    usable = [r for r in window if r["selected_valuation_date"] is not None]
    def split(items):
        games_after = sum(r["games_after"] for r in items)
        games_total = sum(r["games_total"] for r in items)
        result = {"player_seasons": len(items), "games_total": games_total, "games_after": games_after, "pct_games_after": round(100 * games_after / games_total, 2) if games_total else None,
                  "player_seasons_all_games_before": sum(r["games_after"] == 0 for r in items), "player_seasons_all_games_after": sum(r["games_before_or_on"] == 0 for r in items), "player_seasons_majority_after": sum(r["games_after"] * 2 > r["games_total"] for r in items),
                  "games_on_valuation_date": sum(r["games_on_valuation_date"] for r in items)}
        for metric in MATCH_METRICS:
            before = sum(r[f"{metric}_before"] or 0 for r in items)
            after = sum(r[f"{metric}_after"] or 0 for r in items)
            result[f"{metric}_pct_after"] = round(100 * after / (before + after), 2) if before + after else None
            result[f"{metric}_recorded_share_pct"] = round(100 * sum(r[f"{metric}_games_recorded"] for r in items) / games_total, 2) if games_total else None
        return result
    out["split_overall"] = split(usable)
    out["split_by_season"] = {s: split([r for r in usable if r["season"] == s]) for s in sorted({r["season"] for r in usable})}
    bins = Counter()
    for r in usable:
        share = r["games_after"] / r["games_total"] if r["games_total"] else 0
        bins["0%" if share == 0 else "1-25%" if share <= .25 else "26-50%" if share <= .5 else "51-75%" if share <= .75 else "76-99%" if share < 1 else "100%"] += 1
    out["share_of_games_after_valuation_distribution"] = dict(bins)
    # Which season metrics can even be split by date with the raw match data?
    metric_names = {f.name[2:] for f in pq.read_schema(FM / "curated/confirmed_appeared_player_seasons.parquet") if f.name.startswith("m_")}
    per_match = set(match_info["stat_keys_by_season"].get("2023/2024", {}))
    out["curated_metric_count"] = len(metric_names)
    out["curated_metrics_with_same_named_match_key"] = sorted(metric_names & per_match)
    out["curated_metrics_without_same_named_match_key"] = sorted(metric_names - per_match)
    out["collection_dates"] = rows(con, f"""SELECT min(collected_at_utc) first_collected, max(collected_at_utc) last_collected FROM read_parquet('{(FM / 'normalized/metric_observations.parquet').as_posix()}')""")[0]
    out["source_revised_cells"] = sum(con.execute(f'SELECT count(*) FROM cur WHERE "{c}"=\'OBSERVED_SOURCE_REVISED\'').fetchone()[0] for c in [f.name for f in pq.read_schema(FM / "curated/confirmed_appeared_player_seasons.parquet") if f.name.startswith("s_")])
    return out


# ---------- Task 4 ----------

def smd(a: list[float], b: list[float]):
    if len(a) < 2 or len(b) < 2:
        return None
    spread = math.sqrt((pstdev(a) ** 2 + pstdev(b) ** 2) / 2)
    return round((mean(a) - mean(b)) / spread, 3) if spread else None


def sensitivity(con, evidence: Path) -> dict:
    con.execute("""CREATE TEMP TABLE modal AS SELECT player_id, season_id, mapped_group FROM (SELECT player_id, season_id, mapped_group, count(*) n, row_number() OVER (PARTITION BY player_id, season_id ORDER BY count(*) DESC, mapped_group) rk FROM pos WHERE mapped_group<>'UNKNOWN' GROUP BY 1,2,3) WHERE rk=1""")
    base = rows(con, """SELECT t.season, t.season_id, t.fotmob_player_id f, t.market_value mv, t.valuation_age_days age_days, t.season_end_date cut, t.player_games_in_season g, t.identity_evidence_tier tier, t.crosswalk_status cw, coalesce(m.mapped_group,'UNKNOWN') pos, p.birth_date, n.is_multi_club multi
        FROM target t LEFT JOIN modal m ON m.player_id=t.fotmob_player_id AND m.season_id=t.season_id JOIN players p ON p.player_id=t.fotmob_player_id JOIN conf n ON n.player_id=t.fotmob_player_id AND n.season_id=t.season_id""")
    for r in base:
        r["player_age"] = (r["cut"] - date.fromisoformat(r["birth_date"])).days / 365.25 if r["birth_date"] else None
        r["age_group"] = next((name for name, low, high in AGE_GROUPS if r["player_age"] is not None and low <= r["player_age"] <= high), "UNKNOWN")
        r["log_mv"] = math.log(r["mv"]) if r["mv"] else None
    usable = [r for r in base if r["mv"] is not None]
    seasons = sorted({r["season"] for r in base})
    out: dict = {"population": len(base), "usable": len(usable), "scenarios": {}}
    long_rows = []
    for threshold in THRESHOLDS:
        label = f"<={threshold}" if threshold else "all_available"
        kept = [r for r in usable if threshold is None or r["age_days"] <= threshold]
        excluded = [r for r in usable if threshold is not None and r["age_days"] > threshold]
        scenario = {"eligible": len(kept), "pct_of_population": round(100 * len(kept) / len(base), 2), "pct_of_usable": round(100 * len(kept) / len(usable), 2), "distinct_players": len({r["f"] for r in kept}),
                    "median_market_value": median(r["mv"] for r in kept) if kept else None, "median_player_age": round(median(r["player_age"] for r in kept), 2) if kept else None, "median_games": median(r["g"] for r in kept) if kept else None,
                    "smd_kept_vs_excluded": {"log_market_value": smd([r["log_mv"] for r in kept], [r["log_mv"] for r in excluded]), "player_age": smd([r["player_age"] for r in kept], [r["player_age"] for r in excluded]), "games": smd([r["g"] for r in kept], [r["g"] for r in excluded])}}
        for dimension in ("season", "pos", "age_group", "tier"):
            groups = sorted({r[dimension] for r in base})
            scenario[f"by_{dimension}"] = {}
            for group in groups:
                population = sum(r[dimension] == group for r in base)
                count = sum(r[dimension] == group for r in kept)
                scenario[f"by_{dimension}"][group] = {"eligible": count, "coverage_pct": round(100 * count / population, 2) if population else None, "share_of_kept_pct": round(100 * count / len(kept), 2) if kept else None, "population": population}
                long_rows.append({"threshold": label, "dimension": dimension, "group": group, "eligible": count, "population": population, "coverage_pct": scenario[f"by_{dimension}"][group]["coverage_pct"], "share_of_kept_pct": scenario[f"by_{dimension}"][group]["share_of_kept_pct"]})
        # Within-season differences isolate player selection from league-wide batch timing.
        within = {}
        for season in seasons:
            k = [r for r in kept if r["season"] == season]
            e = [r for r in excluded if r["season"] == season]
            within[season] = {"kept": len(k), "excluded": len(e), "log_mv_smd": smd([r["log_mv"] for r in k], [r["log_mv"] for r in e]), "age_smd": smd([r["player_age"] for r in k], [r["player_age"] for r in e]), "games_smd": smd([r["g"] for r in k], [r["g"] for r in e])}
        scenario["within_season_smd"] = within
        out["scenarios"][label] = scenario
    with (evidence / "staleness_sensitivity_long.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(long_rows[0]))
        writer.writeheader()
        writer.writerows(long_rows)
    out["age_days_by_status_of_batch"] = rows(con, """SELECT season, count(*) FILTER (WHERE valuation_age_days<=90) le90, count(*) n, min(selected_valuation_date)::VARCHAR first_date, max(selected_valuation_date)::VARCHAR last_date FROM target WHERE market_value IS NOT NULL GROUP BY 1 ORDER BY 1""")
    return out


# ---------- Task 5 ----------

def identity(con) -> dict:
    out = {
        "by_crosswalk_status": rows(con, """SELECT crosswalk_status, identity_evidence_tier tier, count(*) player_seasons, count(DISTINCT canonical_player_id) players, count(market_value) usable, count(*) FILTER (WHERE target_status='VALID') valid, count(*) FILTER (WHERE target_status='STALE_TARGET') stale, count(*) FILTER (WHERE target_status='TARGET_MISSING') missing FROM target GROUP BY 1,2 ORDER BY 1,2"""),
        "crosswalk_status_counts": dict(con.execute("SELECT match_status, count(*) FROM crosswalk GROUP BY 1").fetchall()),
        "review_status_counts": dict(con.execute("SELECT review_status, count(*) FROM crosswalk GROUP BY 1").fetchall()),
        "target_vs_crosswalk_mismatch": con.execute("""SELECT count(*) FROM target t JOIN crosswalk c ON c.fotmob_player_id=t.fotmob_player_id WHERE t.crosswalk_status<>c.match_status OR t.transfermarkt_player_id IS DISTINCT FROM c.transfermarkt_player_id OR t.canonical_player_id<>c.canonical_player_id""").fetchone()[0],
        "unresolved_with_value": con.execute("SELECT count(*) FROM target WHERE crosswalk_status NOT IN ('AUTO_EXACT','AUTO_ADJUDICATED','MANUAL_CONFIRMED') AND (market_value IS NOT NULL OR transfermarkt_player_id IS NOT NULL OR selected_valuation_date IS NOT NULL)").fetchone()[0],
        "unresolved_rows": rows(con, "SELECT t.season, t.fotmob_player_id, c.fotmob_names_raw names, t.crosswalk_status, t.target_status, t.target_missing_reason FROM target t JOIN crosswalk c USING (fotmob_player_id) WHERE t.crosswalk_status NOT IN ('AUTO_EXACT','AUTO_ADJUDICATED','MANUAL_CONFIRMED') ORDER BY 2"),
        "human_review_fields_filled": con.execute("SELECT count(*) FROM crosswalk WHERE reviewer IS NOT NULL OR review_date IS NOT NULL").fetchone()[0],
        "adjudicated_labelled_human": con.execute("SELECT count(*) FROM crosswalk WHERE match_status='AUTO_ADJUDICATED' AND (review_status<>'AUTOMATED_ADJUDICATION_NOT_HUMAN' OR adjudicator IS NULL)").fetchone()[0],
        "ledger_exists": (ROOT / "data/phase_03/review/review_decisions_ledger.csv").exists(),
        "duplicate_tm_ids": con.execute("SELECT count(*) FROM (SELECT transfermarkt_player_id FROM crosswalk WHERE transfermarkt_player_id IS NOT NULL GROUP BY 1 HAVING count(*)>1)").fetchone()[0],
        "by_season_tier": rows(con, "SELECT season, identity_evidence_tier tier, count(*) n, count(market_value) usable FROM target GROUP BY 1,2 ORDER BY 1,2"),
        "stale_by_tier": rows(con, "SELECT identity_evidence_tier tier, count(market_value) usable, count(*) FILTER (WHERE valuation_age_days>90) over_90, median(valuation_age_days) median_age, median(market_value) median_mv, median(player_games_in_season) median_games FROM target GROUP BY 1 ORDER BY 1"),
    }
    return out


def main() -> None:
    evidence = Path(sys.argv[1])
    evidence.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(SEASONS.read_text(encoding="utf-8"))
    con = duckdb.connect(":memory:")
    setup(con)
    results = {"reproduction": reproduce(con, config)}
    results["concentration"] = concentration(con)
    per_game, match_info = parse_matches(con)
    results["temporal"] = temporal(con, per_game, match_info, evidence)
    results["sensitivity"] = sensitivity(con, evidence)
    results["identity"] = identity(con)
    (evidence / "step_04_1_audit_results.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    print("done", len(per_game))


if __name__ == "__main__":
    main()
