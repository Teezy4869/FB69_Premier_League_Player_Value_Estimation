"""Data-quality audit of the normalized Transfermarkt tables. Read-only apart from quality_results.json.

The FotMob comparison uses per-date-and-score counts only. No player is compared or matched.

Usage: python -I src/phase3/tm_quality.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402

from src.phase3.normalize_tm import COLUMN_MAP, CONTRACT  # noqa: E402
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash, load_config, verify_fotmob_unchanged, write_json  # noqa: E402

RESEARCH_START, RESEARCH_END = "2019-08-09", "2025-05-25"
FORBIDDEN_CURATED_COLUMNS = {"market_value_in_eur", "highest_market_value_in_eur", "current_club_id", "player_current_club_id"}


def main() -> None:
    config = load_config()
    snapshot_id = config["snapshot_id"]
    base = ROOT / "data/transfermarkt"
    con = duckdb.connect(":memory:")
    for table in CONTRACT:
        con.execute(f"CREATE VIEW stg_{table} AS SELECT * FROM read_parquet('{(base / 'staging' / snapshot_id / f'stg_{table}.parquet').as_posix()}')")
    for table in COLUMN_MAP:
        con.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{(base / 'curated' / snapshot_id / f'{table}.parquet').as_posix()}')")
    for alias, rel in {"fm_matches": "matches", "fm_pm": "player_match_appearances"}.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{(FOTMOB_RELEASE / 'normalized' / f'{rel}.parquet').as_posix()}')")

    def rows(sql):
        cursor = con.execute(sql)
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, r)) for r in cursor.fetchall()]

    def one(sql):
        return rows(sql)[0]

    def count(sql):
        return con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]

    out: dict = {"snapshot_id": snapshot_id, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "fotmob_unchanged": verify_fotmob_unchanged()}

    manifest = json.loads((base / "metadata" / snapshot_id / "source_manifest.json").read_text(encoding="utf-8"))
    snapshot = base / "source" / snapshot_id
    out["raw_preservation"] = {
        "files": len(manifest["files"]),
        "sha256_mismatches": [f["file"] for f in manifest["files"] if file_hash(snapshot / f["file"]) != f["sha256"]],
        "writable_files": [f["file"] for f in manifest["files"] if os.access(snapshot / f["file"], os.W_OK)],
        "unexpected_files": sorted({p.name for p in snapshot.iterdir()} - {f["file"] for f in manifest["files"]}),
    }

    schema = json.loads((base / "metadata" / snapshot_id / "schema_snapshot.json").read_text(encoding="utf-8"))
    out["row_reconciliation"] = {
        table: {
            "source_csv_module": schema["tables"][table]["records_csv_module"],
            "source_duckdb": schema["tables"][table]["records_duckdb"],
            "staging": count(f"SELECT 1 FROM stg_{table}"),
            "row_numbers_contiguous": one(f"SELECT min(_source_row_number)=1 AND max(_source_row_number)=count(*) AND count(DISTINCT _source_row_number)=count(*) ok FROM stg_{table}")["ok"],
        } for table in CONTRACT
    }
    pairs = {"tm_players": "players", "tm_valuation_history": "player_valuations", "tm_clubs": "clubs", "tm_competitions": "competitions", "tm_transfers": "transfers"}
    out["curated_reconciliation"] = {c: {"staging": count(f"SELECT 1 FROM stg_{s}"), "curated": count(f"SELECT 1 FROM {c}")} for c, s in pairs.items()}
    out["curated_types"] = {t: {r["column_name"]: r["column_type"] for r in rows(f"DESCRIBE SELECT * FROM {t}")} for t in COLUMN_MAP}
    out["forbidden_columns_in_curated"] = {t: sorted(set(v) & FORBIDDEN_CURATED_COLUMNS) for t, v in out["curated_types"].items()}

    out["players"] = one("""SELECT count(*) n_rows, count(DISTINCT tm_player_id) distinct_ids, count(*) FILTER (WHERE tm_player_id IS NULL) missing_ids,
        count(*) FILTER (WHERE NOT is_valid_player_id) invalid_ids, count(*) FILTER (WHERE is_duplicate_player_id) duplicate_id_rows,
        count(*) FILTER (WHERE is_missing_date_of_birth) missing_dob, count(*) FILTER (WHERE is_missing_nationality) missing_nationality,
        count(*) FILTER (WHERE player_name_normalized IS NULL) empty_normalized_names, min(date_of_birth)::VARCHAR min_dob, max(date_of_birth)::VARCHAR max_dob,
        count(*) FILTER (WHERE is_name_dob_collision) name_dob_collision_rows FROM tm_players""")
    out["players"]["name_dob_collision_records"] = rows("SELECT tm_player_id, player_name_raw, date_of_birth::VARCHAR dob, nationality, position_profile, source_profile_url FROM tm_players WHERE is_name_dob_collision ORDER BY player_name_normalized, tm_player_id")
    out["players"]["normalized_name_groups_multi_id"] = count("SELECT player_name_normalized FROM tm_players GROUP BY 1 HAVING count(*)>1")

    out["valuations"] = one(f"""SELECT count(*) n_rows, count(DISTINCT tm_player_id) players, count(DISTINCT source_record_id) distinct_record_ids,
        count(*) FILTER (WHERE tm_player_id IS NULL) missing_ids, count(*) FILTER (WHERE valuation_date IS NULL) invalid_or_missing_dates,
        count(*) FILTER (WHERE market_value IS NULL) invalid_or_missing_values, count(*) FILTER (WHERE market_value<0) negative_values, count(*) FILTER (WHERE market_value=0) zero_values,
        count(*) FILTER (WHERE is_duplicate_key) duplicate_key_rows, count(*) FILTER (WHERE is_conflicting_key) conflicting_key_rows,
        count(*) FILTER (WHERE NOT reference_player_exists) orphan_rows, min(valuation_date)::VARCHAR min_date, max(valuation_date)::VARCHAR max_date,
        min(market_value) min_value, median(market_value) median_value, max(market_value) max_value,
        count(*) FILTER (WHERE valuation_date<DATE '{RESEARCH_START}') before_research_period, count(*) FILTER (WHERE valuation_date BETWEEN DATE '{RESEARCH_START}' AND DATE '{RESEARCH_END}') within_research_period,
        count(*) FILTER (WHERE valuation_date>DATE '{RESEARCH_END}') after_research_period,
        count(*) FILTER (WHERE source_current_club_name='Unknown') club_name_unknown, count(*) FILTER (WHERE source_club_domestic_competition_id IS NULL) club_competition_null
        FROM tm_valuation_history""")
    out["valuations"]["status_counts"] = rows("SELECT quality_status v, count(*) n FROM tm_valuation_history GROUP BY 1 ORDER BY 2 DESC")
    out["valuations"]["currency_counts"] = rows("SELECT currency v, currency_basis b, count(*) n FROM tm_valuation_history GROUP BY 1,2")
    out["valuations"]["raw_value_shapes"] = rows("SELECT regexp_full_match(market_value_raw,'[0-9]+') all_digits, count(*) n FROM tm_valuation_history GROUP BY 1")
    out["valuations"]["exceptions"] = rows("SELECT source_record_id, market_value_raw, quality_status, source_current_club_name FROM tm_valuation_history WHERE quality_status<>'VALID'")
    out["valuations"]["by_year"] = rows("SELECT year(valuation_date) y, count(*) n, count(DISTINCT tm_player_id) players FROM tm_valuation_history GROUP BY 1 ORDER BY 1")
    out["valuations"]["players_without_history"] = count("SELECT tm_player_id FROM tm_players ANTI JOIN tm_valuation_history USING (tm_player_id)")

    out["referential_integrity"] = {
        "valuations_to_players": count("SELECT tm_player_id FROM tm_valuation_history ANTI JOIN tm_players USING (tm_player_id)"),
        "transfers_to_players": count("SELECT tm_player_id FROM tm_transfers ANTI JOIN tm_players USING (tm_player_id)"),
        "appearances_to_players": count("SELECT player_id FROM stg_appearances ANTI JOIN stg_players USING (player_id)"),
        "appearances_to_games": count("SELECT game_id FROM stg_appearances ANTI JOIN stg_games USING (game_id)"),
        "appearances_club_to_clubs": count("SELECT a.player_club_id FROM stg_appearances a ANTI JOIN stg_clubs c ON a.player_club_id=c.club_id"),
        "gb1_appearances_to_players": count("SELECT player_id FROM stg_appearances a ANTI JOIN stg_players p USING (player_id) WHERE a.competition_id='GB1'"),
        "gb1_appearances_club_to_clubs": count("SELECT a.player_club_id FROM stg_appearances a ANTI JOIN stg_clubs c ON a.player_club_id=c.club_id WHERE a.competition_id='GB1'"),
        "games_to_competitions": count("SELECT g.competition_id FROM stg_games g ANTI JOIN stg_competitions c USING (competition_id)"),
        "clubs_to_competitions": count("SELECT latest_domestic_competition_id FROM tm_clubs c ANTI JOIN tm_competitions k ON c.latest_domestic_competition_id=k.competition_id"),
        "player_club_seasons_to_players": count("SELECT tm_player_id FROM tm_player_club_seasons ANTI JOIN tm_players USING (tm_player_id)"),
        "player_club_seasons_club_name_null": count("SELECT 1 FROM tm_player_club_seasons WHERE club_name IS NULL"),
    }
    out["keys"] = {
        "clubs_id_unique": count("SELECT tm_club_id FROM tm_clubs GROUP BY 1 HAVING count(*)>1") == 0,
        "competitions_id_unique": count("SELECT competition_id FROM tm_competitions GROUP BY 1 HAVING count(*)>1") == 0,
        "games_id_unique": count("SELECT game_id FROM stg_games GROUP BY 1 HAVING count(*)>1") == 0,
        "appearance_id_unique": count("SELECT appearance_id FROM stg_appearances GROUP BY 1 HAVING count(*)>1") == 0,
        "player_club_season_key_unique": count("SELECT 1 FROM tm_player_club_seasons GROUP BY tm_player_id, tm_club_id, season_start_year HAVING count(*)>1") == 0,
    }
    out["transfers"] = one("""SELECT count(*) n_rows, count(*) FILTER (WHERE is_after_snapshot) after_snapshot, count(*) FILTER (WHERE transfer_date IS NULL) null_dates,
        count(*) FILTER (WHERE NOT reference_player_exists) orphan_rows, min(transfer_date)::VARCHAR min_date, max(transfer_date)::VARCHAR max_date,
        count(*) FILTER (WHERE from_club_name='Unknown' OR to_club_name='Unknown') unknown_club_rows FROM tm_transfers""")
    out["transfers"]["exact_duplicate_rows_beyond_first"] = one("SELECT coalesce(sum(n-1),0) x FROM (SELECT count(*) n FROM tm_transfers GROUP BY tm_player_id, transfer_date, from_club_id, to_club_id HAVING count(*)>1)")["x"]
    out["appearances_quality"] = one("""SELECT count(*) FILTER (WHERE player_name IS NULL) null_player_name, count(*) FILTER (WHERE minutes_played<0) negative_minutes, count(*) FILTER (WHERE minutes_played>130) minutes_over_130,
        count(*) FILTER (WHERE competition_id='GB1' AND minutes_played>130) gb1_minutes_over_130, count(*) FILTER (WHERE date IS NULL) null_dates FROM stg_appearances""")

    # Season coverage. TM's own GB1 games define the windows; FotMob's fixture dates are a cross-check.
    seasons = []
    for row in rows(f"""SELECT season season_start_year, season||'/'||(season+1) season_label, count(*) games, min(date)::VARCHAR first_game, max(date)::VARCHAR last_game,
                        count(DISTINCT home_club_id) clubs FROM stg_games WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024 GROUP BY 1,2 ORDER BY 1"""):
        label = row["season_label"]
        fm = one(f"SELECT substr(min(match_date_utc),1,10) a, substr(max(match_date_utc),1,10) b, count(*) n FROM fm_matches WHERE season_label='{label}' AND match_status='COMPLETED'")
        row.update(fotmob_first=fm["a"], fotmob_last=fm["b"], fotmob_completed=fm["n"], windows_agree=(fm["a"] == row["first_game"] and fm["b"] == row["last_game"]))
        row.update(one(f"""SELECT count(*) valuation_rows, count(DISTINCT tm_player_id) valuation_players FROM tm_valuation_history
                           WHERE valuation_date BETWEEN DATE '{row['first_game']}' AND DATE '{row['last_game']}'"""))
        row.update(one(f"SELECT count(DISTINCT tm_player_id) epl_players, sum(game_count) epl_appearance_rows, count(DISTINCT tm_club_id) epl_clubs FROM tm_player_club_seasons WHERE season_start_year={row['season_start_year']}"))
        seasons.append(row)
    out["seasons"] = seasons

    # R3 diagnostic: where do TM's EPL appearance rows fall short? Compared by season, date and score only.
    con.execute("""CREATE TEMP TABLE fm_counts AS SELECT m.season_label, substr(m.match_date_utc,1,10) d, replace(m.score,' ','') score, count(DISTINCT m.match_id) games,
        count(p.player_id) rows_appeared FROM fm_matches m LEFT JOIN fm_pm p ON m.match_id=p.match_id AND p.participation_status IN ('STARTED','SUBSTITUTED_ON')
        WHERE m.match_status='COMPLETED' GROUP BY 1,2,3""")
    con.execute("""CREATE TEMP TABLE tm_counts AS SELECT g.season||'/'||(g.season+1) season_label, g.date::VARCHAR d, g.home_club_goals||'-'||g.away_club_goals score, count(DISTINCT g.game_id) games, count(a.player_id) rows_appeared
        FROM stg_games g LEFT JOIN stg_appearances a USING (game_id) WHERE g.competition_id='GB1' AND g.season BETWEEN 2019 AND 2024 GROUP BY 1,2,3""")
    out["participation_status_values"] = rows("SELECT participation_status v, count(*) n FROM fm_pm GROUP BY 1 ORDER BY 2 DESC")
    out["r3_game_level"] = rows("""SELECT coalesce(f.season_label,t.season_label) season, count(*) date_score_groups, count(*) FILTER (WHERE f.d IS NULL OR t.d IS NULL) unaligned_groups,
        count(*) FILTER (WHERE f.d IS NOT NULL AND t.d IS NOT NULL AND f.rows_appeared>t.rows_appeared) groups_tm_short, count(*) FILTER (WHERE f.d IS NOT NULL AND t.d IS NOT NULL AND f.rows_appeared<t.rows_appeared) groups_tm_over,
        coalesce(sum(f.rows_appeared),0) fotmob_rows, coalesce(sum(t.rows_appeared),0) tm_rows, max(f.rows_appeared-t.rows_appeared) max_group_shortfall
        FROM fm_counts f FULL JOIN tm_counts t ON f.season_label=t.season_label AND f.d=t.d AND f.score=t.score GROUP BY 1 ORDER BY 1""")
    out["r3_min_rows_per_game"] = rows("""SELECT g.season season_start_year, min(k) min_rows, median(k) median_rows, count(*) FILTER (WHERE k<22) games_under_22 FROM
        (SELECT game_id, count(*) k FROM stg_appearances WHERE competition_id='GB1' GROUP BY 1) x JOIN stg_games g USING (game_id) WHERE g.season BETWEEN 2019 AND 2024 GROUP BY 1 ORDER BY 1""")

    write_json(base / "metadata" / snapshot_id / "quality_results.json", out)
    print(json.dumps(out, default=str, ensure_ascii=True))


if __name__ == "__main__":
    main()
