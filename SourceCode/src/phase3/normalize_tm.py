"""Normalize the approved Transfermarkt snapshot: Raw -> Staging -> Curated.

Rules:
- Staging keeps every source row and column, typed, with `<col>__raw` for each non-text column and
  file/row lineage. A value that fails a strict format check becomes null and is counted.
- Curated keeps every row for players, valuations, clubs, competitions and transfers. Problems are flagged.
- No row is deleted, no value is imputed, and no currency is converted.
- Output is built in a temporary folder. An existing different output is never overwritten.

Usage: python -I src/phase3/normalize_tm.py
"""
from __future__ import annotations

import csv
import gzip
import io
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402

from src.phase3.names import normalize_name  # noqa: E402
from src.phase3.tm_common import ROOT, file_hash, load_config, verify_fotmob_unchanged, write_json  # noqa: E402

RULE_VERSION = "tm_normalization_v1"
SNAPSHOT_DATE = "2026-09-05"
V, I, B, D, T, M, F = "VARCHAR", "INTEGER", "BIGINT", "DATE", "TIMESTAMP_AS_DATE", "DECIMAL(18,3)", "DOUBLE"

# Types were chosen after inspecting schema_snapshot.json. Identifiers stay text, as in the FotMob release.
CONTRACT = {
    "player_valuations": {"player_id": V, "date": D, "market_value_in_eur": B, "current_club_name": V, "current_club_id": V, "player_club_domestic_competition_id": V},
    "players": {"player_id": V, "first_name": V, "last_name": V, "name": V, "last_season": I, "current_club_id": V, "player_code": V, "country_of_birth": V, "city_of_birth": V, "country_of_citizenship": V, "date_of_birth": T, "sub_position": V, "position": V, "foot": V, "height_in_cm": I, "contract_expiration_date": T, "agent_name": V, "image_url": V, "international_caps": I, "international_goals": I, "current_national_team_id": V, "url": V, "current_club_domestic_competition_id": V, "current_club_name": V, "market_value_in_eur": B, "highest_market_value_in_eur": B},
    "transfers": {"player_id": V, "transfer_date": D, "transfer_season": V, "from_club_id": V, "to_club_id": V, "from_club_name": V, "to_club_name": V, "transfer_fee": M, "market_value_in_eur": M, "player_name": V},
    "clubs": {"club_id": V, "club_code": V, "name": V, "domestic_competition_id": V, "total_market_value": V, "squad_size": I, "average_age": F, "foreigners_number": I, "foreigners_percentage": F, "national_team_players": I, "stadium_name": V, "stadium_seats": I, "net_transfer_record": V, "coach_name": V, "last_season": I, "filename": V, "url": V},
    "competitions": {"competition_id": V, "competition_code": V, "name": V, "sub_type": V, "type": V, "country_id": V, "country_name": V, "domestic_league_code": V, "confederation": V, "total_clubs": I, "url": V},
    "appearances": {"appearance_id": V, "game_id": V, "player_id": V, "player_club_id": V, "player_current_club_id": V, "date": D, "player_name": V, "competition_id": V, "yellow_cards": I, "red_cards": I, "goals": I, "assists": I, "minutes_played": I},
    "games": {"game_id": V, "competition_id": V, "season": I, "round": V, "date": D, "home_club_id": V, "away_club_id": V, "home_club_goals": I, "away_club_goals": I, "home_club_position": I, "away_club_position": I, "home_club_manager_name": V, "away_club_manager_name": V, "stadium": V, "attendance": I, "referee": V, "url": V, "home_club_formation": V, "away_club_formation": V, "home_club_name": V, "away_club_name": V, "aggregate": V, "competition_type": V},
}

LINEAGE = ["_source_file", "_source_sha256", "_source_row_number"]

# normalized column -> original "table.column" or a description of how it is derived.
COLUMN_MAP = {
    "tm_players": {
        "tm_player_id": "players.player_id", "player_name_raw": "players.name", "first_name_raw": "players.first_name",
        "last_name_raw": "players.last_name", "player_name_normalized": "derived: normalize_name(players.name)",
        "player_code": "players.player_code", "date_of_birth": "players.date_of_birth (timestamp text to date)",
        "date_of_birth_raw": "players.date_of_birth", "nationality": "players.country_of_citizenship",
        "country_of_birth": "players.country_of_birth", "position_profile": "players.position (present-day profile)",
        "sub_position_profile": "players.sub_position (present-day profile)", "source_profile_url": "players.url",
        "is_valid_player_id": "derived: id is all digits", "is_duplicate_player_id": "derived: id repeats",
        "is_missing_date_of_birth": "derived", "is_missing_nationality": "derived",
        "is_name_dob_collision": "derived: same normalized name and birth date as another ID",
    },
    "tm_valuation_history": {
        "source_record_id": "derived: player_valuations:<player_id>:<date>; the source has no record ID",
        "tm_player_id": "player_valuations.player_id", "valuation_date": "player_valuations.date",
        "valuation_date_raw": "player_valuations.date", "market_value": "player_valuations.market_value_in_eur",
        "market_value_raw": "player_valuations.market_value_in_eur",
        "currency": "derived: literal EUR from the source column name; not converted",
        "currency_basis": "derived: states the evidence for the currency",
        "source_current_club_id": "player_valuations.current_club_id (not a historical fact; may fall back to present-day club)",
        "source_current_club_name": "player_valuations.current_club_name (not a historical fact)",
        "source_club_domestic_competition_id": "player_valuations.player_club_domestic_competition_id (derived upstream)",
        "reference_player_exists": "derived: player_id exists in players", "is_duplicate_key": "derived: (player_id, date) repeats",
        "is_conflicting_key": "derived: repeated key with different values", "quality_status": "derived; see normalization report",
    },
    "tm_clubs": {
        "tm_club_id": "clubs.club_id", "club_code": "clubs.club_code", "club_name": "clubs.name",
        "latest_domestic_competition_id": "clubs.domestic_competition_id (latest known league, not season membership)",
        "last_season": "clubs.last_season", "source_url": "clubs.url",
    },
    "tm_competitions": {
        "competition_id": "competitions.competition_id", "competition_code": "competitions.competition_code", "competition_name": "competitions.name",
        "competition_type": "competitions.type", "competition_sub_type": "competitions.sub_type", "country_name": "competitions.country_name",
        "domestic_league_code": "competitions.domestic_league_code", "confederation": "competitions.confederation", "source_url": "competitions.url",
    },
    "tm_transfers": {
        "source_record_id": "derived: transfers:<source row number>; the source has no record ID", "tm_player_id": "transfers.player_id",
        "player_name_raw": "transfers.player_name", "transfer_date": "transfers.transfer_date", "transfer_season": "transfers.transfer_season",
        "from_club_id": "transfers.from_club_id", "from_club_name": "transfers.from_club_name", "to_club_id": "transfers.to_club_id", "to_club_name": "transfers.to_club_name",
        "reference_player_exists": "derived: player_id exists in players", "is_after_snapshot": "derived: transfer_date after the snapshot date",
    },
    "tm_player_club_seasons": {
        "tm_player_id": "appearances.player_id", "tm_club_id": "appearances.player_club_id (club in that game)",
        "club_name": "clubs.name, else games home or away club name", "competition_id": "appearances.competition_id; only GB1 kept",
        "season_start_year": "games.season", "season_label": "derived from games.season, e.g. 2019/2020",
        "game_count": "derived: count of appearance rows", "minutes_played_sum": "derived: sum of appearances.minutes_played",
        "first_game_date": "derived: min of appearances.date", "last_game_date": "derived: max of appearances.date",
    },
}


def typed_expr(column: str, kind: str) -> str:
    """Strict cast. Any value that fails its format check becomes null and is counted."""
    q = f'"{column}"'
    if kind == V:
        return q
    if kind in (I, B):
        return f"CASE WHEN regexp_full_match({q}, '-?[0-9]+') THEN TRY_CAST({q} AS {kind}) END"
    if kind == D:
        return f"CASE WHEN regexp_full_match({q}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') THEN TRY_CAST({q} AS DATE) END"
    if kind == T:
        return f"CASE WHEN regexp_full_match({q}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}( [0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}})?') THEN TRY_CAST({q} AS TIMESTAMP)::DATE END"
    return f"CASE WHEN regexp_full_match({q}, '-?[0-9]+([.][0-9]+)?') THEN TRY_CAST({q} AS {kind}) END"


def read_header(path: Path) -> list[str]:
    with gzip.open(path, "rb") as handle:
        return next(csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline="")))


def stage_table(con, source_dir: Path, table: str) -> dict:
    path = source_dir / f"{table}.csv.gz"
    contract = CONTRACT[table]
    header = read_header(path)
    if header != list(contract):
        raise RuntimeError(f"{table}: header differs from contract. Actual: {header}")
    columns = ", ".join(f"'{c}': 'VARCHAR'" for c in contract)
    con.execute(f"""CREATE TEMP TABLE raw_{table} AS
        SELECT *, row_number() OVER () AS _source_row_number
        FROM read_csv('{path.as_posix()}', header=true, delim=',', quote='"', escape='"', auto_detect=false, columns={{{columns}}})""")
    select = []
    for column, kind in contract.items():
        select.append(f'{typed_expr(column, kind)} AS "{column}"')
        if kind != V:
            select.append(f'"{column}" AS "{column}__raw"')
    sha = file_hash(path)
    con.execute(f"""CREATE TABLE stg_{table} AS SELECT {', '.join(select)}, '{path.name}' AS _source_file, '{sha}' AS _source_sha256,
        _source_row_number FROM raw_{table} ORDER BY _source_row_number""")
    failures = {}
    for column, kind in contract.items():
        if kind != V:
            failed = con.execute(f'SELECT count(*) FROM stg_{table} WHERE "{column}__raw" IS NOT NULL AND "{column}" IS NULL').fetchone()[0]
            if failed:
                failures[column] = failed
    rows = con.execute(f"SELECT count(*) FROM raw_{table}").fetchone()[0]
    return {"source_rows": rows, "staging_rows": con.execute(f"SELECT count(*) FROM stg_{table}").fetchone()[0], "cast_failures": failures, "sha256": sha}


def build_curated(con) -> None:
    people = con.execute("SELECT _source_row_number, name FROM stg_players ORDER BY 1").fetchall()
    con.register("normalized_names", pa.table({
        "_source_row_number": pa.array([r[0] for r in people], pa.int64()),
        "player_name_normalized": pa.array([normalize_name(r[1]) for r in people], pa.string()),
    }))
    lineage = ", ".join(f"s.{c}" for c in LINEAGE)
    con.execute(f"""CREATE TABLE tm_players AS
        WITH base AS (SELECT s.*, n.player_name_normalized FROM stg_players s JOIN normalized_names n USING (_source_row_number)),
        collisions AS (SELECT player_name_normalized, date_of_birth FROM base WHERE player_name_normalized IS NOT NULL AND date_of_birth IS NOT NULL
                       GROUP BY 1, 2 HAVING count(DISTINCT player_id) > 1)
        SELECT s.player_id AS tm_player_id, s.name AS player_name_raw, s.first_name AS first_name_raw, s.last_name AS last_name_raw,
               s.player_name_normalized, s.player_code, s.date_of_birth, s.date_of_birth__raw AS date_of_birth_raw,
               s.country_of_citizenship AS nationality, s.country_of_birth, s.position AS position_profile, s.sub_position AS sub_position_profile,
               s.url AS source_profile_url,
               coalesce(regexp_full_match(s.player_id, '[0-9]+'), false) AS is_valid_player_id,
               count(*) OVER (PARTITION BY s.player_id) > 1 AS is_duplicate_player_id,
               s.date_of_birth IS NULL AS is_missing_date_of_birth, s.country_of_citizenship IS NULL AS is_missing_nationality,
               c.date_of_birth IS NOT NULL AS is_name_dob_collision, {lineage}
        FROM base s LEFT JOIN collisions c ON s.player_name_normalized = c.player_name_normalized AND s.date_of_birth = c.date_of_birth
        ORDER BY s._source_row_number""")
    con.execute(f"""CREATE TABLE tm_valuation_history AS
        WITH keyed AS (SELECT player_id, date__raw, count(*) n, count(DISTINCT market_value_in_eur__raw) k FROM stg_player_valuations GROUP BY 1, 2),
        known AS (SELECT DISTINCT player_id FROM stg_players),
        j AS (SELECT s.*, coalesce(y.n, 1) > 1 AS is_duplicate_key, coalesce(y.k, 1) > 1 AS is_conflicting_key, k.player_id IS NOT NULL AS reference_player_exists
              FROM stg_player_valuations s
              LEFT JOIN keyed y ON s.player_id = y.player_id AND s.date__raw = y.date__raw
              LEFT JOIN known k ON s.player_id = k.player_id)
        SELECT 'player_valuations:' || coalesce(s.player_id, '') || ':' || coalesce(s.date__raw, '') AS source_record_id,
               s.player_id AS tm_player_id, s.date AS valuation_date, s.date__raw AS valuation_date_raw,
               s.market_value_in_eur AS market_value, s.market_value_in_eur__raw AS market_value_raw, 'EUR' AS currency,
               'SOURCE_COLUMN_NAME_AND_DOCUMENTATION' AS currency_basis,
               s.current_club_id AS source_current_club_id, s.current_club_name AS source_current_club_name,
               s.player_club_domestic_competition_id AS source_club_domestic_competition_id,
               s.reference_player_exists, s.is_duplicate_key, s.is_conflicting_key,
               CASE WHEN s.player_id IS NULL OR NOT regexp_full_match(s.player_id, '[0-9]+') THEN 'INVALID_PLAYER_ID'
                    WHEN s.date IS NULL THEN 'INVALID_DATE'
                    WHEN s.date > DATE '{SNAPSHOT_DATE}' THEN 'INVALID_DATE_AFTER_SNAPSHOT'
                    WHEN s.market_value_in_eur IS NULL THEN 'INVALID_VALUE_MISSING_OR_UNPARSEABLE'
                    WHEN s.market_value_in_eur <= 0 THEN 'INVALID_VALUE_NONPOSITIVE'
                    WHEN s.is_conflicting_key THEN 'CONFLICT_SAME_DATE'
                    WHEN s.is_duplicate_key THEN 'DUPLICATE_EXACT'
                    WHEN NOT s.reference_player_exists THEN 'ORPHAN_PLAYER'
                    ELSE 'VALID' END AS quality_status, {lineage}
        FROM j s ORDER BY s._source_row_number""")
    con.execute(f"""CREATE TABLE tm_clubs AS SELECT club_id AS tm_club_id, club_code, name AS club_name, domestic_competition_id AS latest_domestic_competition_id,
        last_season, url AS source_url, {', '.join(LINEAGE)} FROM stg_clubs ORDER BY _source_row_number""")
    con.execute(f"""CREATE TABLE tm_competitions AS SELECT competition_id, competition_code, name AS competition_name, type AS competition_type, sub_type AS competition_sub_type,
        country_name, domestic_league_code, confederation, url AS source_url, {', '.join(LINEAGE)} FROM stg_competitions ORDER BY _source_row_number""")
    con.execute(f"""CREATE TABLE tm_transfers AS SELECT 'transfers:' || s._source_row_number AS source_record_id, s.player_id AS tm_player_id, s.player_name AS player_name_raw,
        s.transfer_date, s.transfer_season, s.from_club_id, s.from_club_name, s.to_club_id, s.to_club_name,
        s.player_id IN (SELECT player_id FROM stg_players) AS reference_player_exists, s.transfer_date > DATE '{SNAPSHOT_DATE}' AS is_after_snapshot, {lineage}
        FROM stg_transfers s ORDER BY s._source_row_number""")
    con.execute("""CREATE TABLE tm_player_club_seasons AS
        WITH names AS (SELECT home_club_id AS club_id, any_value(home_club_name) AS n FROM stg_games WHERE home_club_name IS NOT NULL GROUP BY 1
                       UNION ALL SELECT away_club_id, any_value(away_club_name) FROM stg_games WHERE away_club_name IS NOT NULL GROUP BY 1),
        fallback AS (SELECT club_id, min(n) AS n FROM names GROUP BY 1)
        SELECT a.player_id AS tm_player_id, a.player_club_id AS tm_club_id, coalesce(c.name, f.n) AS club_name, a.competition_id,
               g.season AS season_start_year, g.season || '/' || (g.season + 1) AS season_label,
               count(*) AS game_count, sum(a.minutes_played)::BIGINT AS minutes_played_sum, min(a.date) AS first_game_date, max(a.date) AS last_game_date,
               any_value(a._source_file) AS _source_file, any_value(a._source_sha256) AS _source_sha256
        FROM stg_appearances a JOIN stg_games g USING (game_id)
        LEFT JOIN stg_clubs c ON a.player_club_id = c.club_id LEFT JOIN fallback f ON a.player_club_id = f.club_id
        WHERE a.competition_id = 'GB1'
        GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY season_start_year, tm_club_id, tm_player_id""")


def export(con, table: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY (SELECT * FROM {table}) TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return file_hash(path)


def build(source_dir: Path, out_dir: Path) -> dict:
    """Build all staging and curated Parquet files into out_dir and return the row and hash record."""
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    con.execute("SET preserve_insertion_order=true")
    stats = {table: stage_table(con, source_dir, table) for table in CONTRACT}
    build_curated(con)
    hashes = {}
    for table in CONTRACT:
        hashes[f"staging/stg_{table}.parquet"] = export(con, f"stg_{table}", out_dir / "staging" / f"stg_{table}.parquet")
    curated_rows = {}
    for table in COLUMN_MAP:
        hashes[f"curated/{table}.parquet"] = export(con, table, out_dir / "curated" / f"{table}.parquet")
        curated_rows[table] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    exceptions = out_dir / "curated" / "tm_valuation_exceptions.csv"
    con.execute(f"COPY (SELECT * FROM tm_valuation_history WHERE quality_status <> 'VALID' ORDER BY _source_row_number) TO '{exceptions.as_posix()}' (HEADER, DELIMITER ',')")
    filters = {
        "tm_player_club_seasons": {
            "source_appearance_rows": stats["appearances"]["source_rows"],
            "rows_competition_gb1": con.execute("SELECT count(*) FROM stg_appearances WHERE competition_id='GB1'").fetchone()[0],
            "rows_gb1_without_game": con.execute("SELECT count(*) FROM stg_appearances a ANTI JOIN stg_games g USING (game_id) WHERE a.competition_id='GB1'").fetchone()[0],
            "grouped_rows": curated_rows["tm_player_club_seasons"],
        }
    }
    return {"tables": stats, "curated_rows": curated_rows, "output_sha256": hashes, "filters": filters}


def main() -> int:
    config = load_config()
    snapshot_id = config["snapshot_id"]
    base = ROOT / "data/transfermarkt"
    fotmob = verify_fotmob_unchanged()
    temp = base / f"_build_{uuid.uuid4().hex}"
    try:
        record = build(base / "source" / snapshot_id, temp)
        for layer in ("staging", "curated"):
            target = base / layer / snapshot_id
            if target.exists():
                existing = {f"{layer}/{p.name}": file_hash(p) for p in target.glob("*.parquet")}
                new = {k: v for k, v in record["output_sha256"].items() if k.startswith(layer)}
                if existing != new:
                    print(f"STOP: {target} exists with different content; not overwritten.")
                    return 2
                print(f"{layer}: identical output already present")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp / layer), str(target))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    con = duckdb.connect(":memory:")
    types = {}
    for table in COLUMN_MAP:
        path = (base / "curated" / snapshot_id / f"{table}.parquet").as_posix()
        types[table] = {r[0]: r[1] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()}
    write_json(base / "metadata" / snapshot_id / "normalization_manifest.json", {
        "snapshot_id": snapshot_id, "rule_version": RULE_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_version": None, "code_version_note": "Project is not a git repository; git initialization was not approved (D5).",
        "duckdb_version": duckdb.__version__, "pyarrow_version": pa.__version__, "fotmob_preflight": fotmob,
        "rights": config["rights"], "column_map": COLUMN_MAP, "curated_column_types": types, "staging_contract": CONTRACT, **record,
    })
    print({k: (v["source_rows"], v["staging_rows"], v["cast_failures"]) for k, v in record["tables"].items()})
    print(record["curated_rows"], record["filters"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
