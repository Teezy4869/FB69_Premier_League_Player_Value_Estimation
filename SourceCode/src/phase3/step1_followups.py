"""Phase 3 Step 1 follow-up measurements (read-only, aggregates only, no FotMob-to-TM player join)."""
import json, re, sys
from pathlib import Path
import duckdb
root, ev, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rel = root / "data/releases/fotmob_epl_2019_2025_v3_1"
c = duckdb.connect(":memory:")
for a, t in dict(cur="curated/confirmed_appeared_player_seasons", conf="normalized/confirmed_appeared_player_seasons", pl="normalized/players", pts="normalized/player_team_seasons", te="normalized/teams", pm="normalized/player_match_appearances").items():
    c.execute(f"CREATE VIEW {a} AS SELECT * FROM read_parquet('{(rel / (t + '.parquet')).as_posix()}')")
for t in ("appearances", "player_valuations"):
    c.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv('{(ev / (t + '.csv.gz')).as_posix()}', all_varchar=true, header=true)")
def q(s):
    x = c.execute(s); n = [d[0] for d in x.description]; return [dict(zip(n, r)) for r in x.fetchall()]
R = {}
paths = q("SELECT p.profile_raw_path v FROM pl p SEMI JOIN conf USING (player_id)")
hits = opta = 0; keys = {}
for r in paths:
    b = (root / r["v"]).read_bytes().decode("utf8", "replace").lower()
    hits += "transfermarkt" in b
    opta += '"opta' in b
    for m in re.findall(r'"([a-z_]*(?:external|tmid|transfermarkt|opta|wyscout|sofascore)[a-z_]*)"', b):
        keys[m] = keys.get(m, 0) + 1
R["id_bridge_scan"] = {"profiles_scanned": len(paths), "contain_transfermarkt_string": hits, "contains_opta_key_prefix": opta, "matching_key_names": keys}
R["confirmed_player_name"] = q("SELECT count(*) FILTER (WHERE player_name IS NULL) null_names, count(DISTINCT player_name) distinct_names FROM conf")[0]
R["minutes_null_vs_status"] = q("SELECT s_minutes_played st, count(*) n, count(m_minutes_played) nonnull FROM cur GROUP BY 1 ORDER BY 2 DESC")
R["minutes_null_vs_gk_metric"] = q("SELECT (m_minutes_played IS NULL) minutes_null, (m_saves IS NOT NULL OR m_goals_conceded IS NOT NULL) has_gk_metric, count(*) n FROM cur GROUP BY 1,2 ORDER BY 1,2")
R["minutes_null_vs_appearance_evidence"] = q("SELECT count(*) n, median(confirmed_appearance_count) median_apps, min(confirmed_appearance_count) min_apps, max(confirmed_appearance_count) max_apps FROM conf JOIN cur USING (season_id, player_id) WHERE m_minutes_played IS NULL")
R["multi_club_flag_vs_count"] = q("SELECT is_multi_club, confirmed_team_count, associated_team_count, count(*) n FROM conf GROUP BY 1,2,3 ORDER BY 1,2,3")
R["fotmob_appeared_player_matches"] = q("SELECT season_label, sum(started_match_count)+sum(sub_in_match_count) appeared_player_matches, sum(confirmed_appearance_count) confirmed_appearance_sum FROM conf GROUP BY 1 ORDER BY 1")
w = {"2019/2020": ("2019-08-09", "2020-07-26"), "2020/2021": ("2020-09-12", "2021-05-23"), "2021/2022": ("2021-08-13", "2022-05-22"), "2022/2023": ("2022-08-05", "2023-05-28"), "2023/2024": ("2023-08-11", "2024-05-19"), "2024/2025": ("2024-08-16", "2025-05-25")}
sh = []
for s, (a, b) in w.items():
    base = f"appearances WHERE competition_id='GB1' AND try_cast(date AS DATE) BETWEEN DATE '{a}' AND DATE '{b}'"
    per_game = q(f"SELECT min(k) min_rows_per_game, max(k) max_rows_per_game, median(k) med, count(*) FILTER (WHERE k<22) games_under_22 FROM (SELECT game_id, count(*) k FROM {base} GROUP BY 1)")[0]
    per_club = q(f"SELECT min(k) min_players_per_club, max(k) max_players_per_club FROM (SELECT player_club_id, count(DISTINCT player_id) k FROM {base} GROUP BY 1)")[0]
    last = q(f"""WITH e AS (SELECT DISTINCT player_id FROM {base}),
       l AS (SELECT e.player_id, max(try_cast(v.date AS DATE)) d FROM e JOIN player_valuations v USING (player_id) WHERE try_cast(v.date AS DATE)<=DATE '{b}' GROUP BY 1)
       SELECT mode(d)::VARCHAR modal_selected_date, count(*) FILTER (WHERE d=(SELECT mode(d) FROM l)) n_on_modal_date, count(*) FILTER (WHERE d<DATE '{b}') before_last_match, count(*) n FROM l""")[0]
    apps_after = q(f"""WITH g AS (SELECT DISTINCT game_id, try_cast(date AS DATE) d FROM {base}), l AS (SELECT mode(x.d) md FROM (SELECT e.player_id, max(try_cast(v.date AS DATE)) d FROM (SELECT DISTINCT player_id FROM {base}) e JOIN player_valuations v USING (player_id) WHERE try_cast(v.date AS DATE)<=DATE '{b}' GROUP BY 1) x)
       SELECT count(*) FILTER (WHERE g.d>l.md) games_after_modal_date, count(*) games FROM g, l""")[0]
    sh.append({"season": s, **per_game, **per_club, **last, **apps_after})
R["tm_epl_season_shape"] = sh
R["zero_valuation_rows"] = q("SELECT player_id, date, market_value_in_eur, current_club_name FROM player_valuations WHERE try_cast(market_value_in_eur AS DOUBLE)<=0")
R["fotmob_team_seasons_by_team_count"] = q("SELECT season_label, count(DISTINCT team_id) teams FROM te GROUP BY 1 ORDER BY 1")
out.write_text(json.dumps(R, indent=1, default=str), encoding="utf-8"); print(json.dumps(R, default=str))
