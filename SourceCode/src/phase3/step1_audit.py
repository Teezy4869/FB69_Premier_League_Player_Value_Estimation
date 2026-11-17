"""Phase 3 Step 1 read-only feasibility audit.

Reads the frozen FotMob v3.1 release and a bounded local copy of Transfermarkt
evidence CSVs, then writes one JSON file of aggregate measurements.

Guarantees:
- Opens every input read-only and writes only to --out.
- Never joins FotMob players to Transfermarkt players (no matching).
- Keeps aggregates only: no player-level target or valuation table is written.

Usage:
    python -I src/phase3/step1_audit.py --root <FB69 root> --tm-evidence <dir> --out <json>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

RELEASE = "data/releases/fotmob_epl_2019_2025_v3_1"
TM_TABLES = ["player_valuations", "players", "transfers", "clubs", "competitions", "appearances"]
AGE_BINS = [("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("91-180", 91, 180), (">180", 181, 10**9)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm_name(value: str | None) -> str | None:
    """Comparison form used only for within-source collision counts."""
    if not value:
        return None
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip() or None


def rows(con, sql: str, *params):
    cursor = con.execute(sql, params) if params else con.execute(sql)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def one(con, sql: str):
    return rows(con, sql)[0]


def verify_manifest(release: Path) -> dict:
    manifest_path = release / "metadata/release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = {entry["path"]: entry for entry in manifest["files"]}
    on_disk = {p.relative_to(release).as_posix() for p in release.rglob("*") if p.is_file()}
    bad_hash, bad_bytes, bad_rows = [], [], []
    for rel, entry in listed.items():
        path = release / rel
        if not path.is_file():
            continue
        if path.stat().st_size != entry["bytes"]:
            bad_bytes.append(rel)
        if sha256(path) != entry["sha256"]:
            bad_hash.append(rel)
        if rel.endswith(".parquet") and entry.get("physical_rows") is not None:
            if pq.ParquetFile(path).metadata.num_rows != entry["physical_rows"]:
                bad_rows.append(rel)
    return {
        "manifest_sha256": sha256(manifest_path),
        "dataset_version": manifest["dataset_version"],
        "parent_release_version": manifest["parent_release_version"],
        "created_at_utc": manifest["created_at_utc"],
        "quality_status": manifest["quality_status"],
        "listed_files": len(listed),
        "files_on_disk": len(on_disk),
        "missing_from_disk": sorted(set(listed) - on_disk),
        "unlisted_on_disk": sorted(on_disk - set(listed)),
        "sha256_mismatches": bad_hash,
        "byte_mismatches": bad_bytes,
        "row_mismatches": bad_rows,
        "key_file_sha256": {r: listed[r]["sha256"] for r in listed if r.endswith(".parquet") and r.startswith(("curated/", "normalized/"))},
    }


def audit_fotmob(root: Path) -> tuple[dict, list[dict]]:
    release = root / RELEASE
    con = duckdb.connect(":memory:")
    tables = {
        "cur": "curated/confirmed_appeared_player_seasons", "wide": "curated/player_season_metrics_wide",
        "conf": "normalized/confirmed_appeared_player_seasons", "nonapp": "normalized/confirmed_non_appeared_player_seasons",
        "unv": "normalized/unverified_player_seasons", "cls": "normalized/complete_player_season_classification",
        "ps": "normalized/player_seasons", "pts": "normalized/player_team_seasons", "pl": "normalized/players",
        "se": "normalized/seasons", "te": "normalized/teams", "ma": "normalized/matches",
    }
    for alias, rel in tables.items():
        path = (release / f"{rel}.parquet").as_posix()
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path}')")

    out: dict = {"manifest_verification": verify_manifest(release)}
    out["table_row_counts"] = {a: one(con, f"SELECT count(*) n FROM {a}")["n"] for a in tables}
    out["population_by_season"] = rows(con, """
        SELECT c.season_label, count(*) FILTER (WHERE population_category='CONFIRMED_APPEARED') confirmed_appeared,
               count(*) FILTER (WHERE population_category NOT IN ('CONFIRMED_APPEARED','UNVERIFIED')) other,
               count(*) FILTER (WHERE population_category='UNVERIFIED') unverified, count(*) total
        FROM cls c GROUP BY 1 ORDER BY 1""")
    out["curated_by_season"] = rows(con, "SELECT season_label, count(*) n, count(DISTINCT player_id) players FROM cur GROUP BY 1 ORDER BY 1")
    out["status_encodings"] = {
        "curated.population_status": rows(con, "SELECT population_status v, count(*) n FROM cur GROUP BY 1 ORDER BY 2 DESC"),
        "wide.population_status": rows(con, "SELECT population_status v, count(*) n FROM wide GROUP BY 1 ORDER BY 2 DESC"),
        "classification.population_category": rows(con, "SELECT population_category v, count(*) n FROM cls GROUP BY 1 ORDER BY 2 DESC"),
        "player_seasons.evidence_status": rows(con, "SELECT evidence_status v, count(*) n FROM ps GROUP BY 1 ORDER BY 2 DESC"),
        "classification_reason": rows(con, "SELECT population_category c, classification_reason v, count(*) n FROM cls GROUP BY 1,2 ORDER BY 3 DESC"),
    }
    out["key_uniqueness"] = {a: one(con, f"SELECT count(*) n_rows, count(DISTINCT (season_id, player_id)) n_keys, count(*) FILTER (WHERE player_id IS NULL OR season_id IS NULL OR trim(player_id)='') null_keys, count(*) FILTER (WHERE NOT regexp_full_match(player_id,'[0-9]+')) non_numeric_player_ids FROM {a}") for a in ["cur", "conf", "unv", "cls", "ps", "wide"]}
    out["players_primary_key"] = one(con, "SELECT count(*) n_rows, count(DISTINCT player_id) n_keys FROM pl")
    out["population_set_reconciliation"] = {
        "curated_minus_confirmed": one(con, "SELECT count(*) n FROM (SELECT season_id,player_id FROM cur EXCEPT SELECT season_id,player_id FROM conf)")["n"],
        "confirmed_minus_curated": one(con, "SELECT count(*) n FROM (SELECT season_id,player_id FROM conf EXCEPT SELECT season_id,player_id FROM cur)")["n"],
        "confirmed_minus_classification_confirmed": one(con, "SELECT count(*) n FROM (SELECT season_id,player_id FROM conf EXCEPT SELECT season_id,player_id FROM cls WHERE population_category='CONFIRMED_APPEARED')")["n"],
        "confirmed_intersect_unverified": one(con, "SELECT count(*) n FROM (SELECT season_id,player_id FROM conf INTERSECT SELECT season_id,player_id FROM unv)")["n"],
        "wide_appeared_minus_curated": one(con, "SELECT count(*) n FROM (SELECT season_id,player_id FROM wide WHERE population_status='APPEARED' EXCEPT SELECT season_id,player_id FROM cur)")["n"],
        "confirmed_without_players_row": one(con, "SELECT count(*) n FROM conf c ANTI JOIN pl USING (player_id)")["n"],
        "confirmed_zero_appearance_rows": one(con, "SELECT count(*) n FROM conf WHERE confirmed_appearance_count<=0")["n"],
    }
    out["unique_confirmed_players"] = one(con, "SELECT count(DISTINCT player_id) n FROM conf")["n"]
    out["seasons_per_confirmed_player"] = rows(con, "SELECT seasons, count(*) players FROM (SELECT player_id, count(*) seasons FROM conf GROUP BY 1) GROUP BY 1 ORDER BY 1")
    out["multi_club"] = {
        "by_season": rows(con, "SELECT season_label, count(*) FILTER (WHERE is_multi_club) multi, count(*) FILTER (WHERE confirmed_team_count>=2) confirmed_team_count_ge2, max(confirmed_team_count) max_teams FROM conf GROUP BY 1 ORDER BY 1"),
        "status_values": rows(con, "SELECT multi_club_status v, count(*) n FROM conf GROUP BY 1 ORDER BY 2 DESC"),
        "pts_rows_for_confirmed_population": one(con, "SELECT count(*) n FROM pts JOIN conf USING (season_id, player_id)")["n"],
        "pts_confirmed_appeared_rows": one(con, "SELECT count(*) n FROM pts JOIN conf USING (season_id, player_id) WHERE pts.appeared_match_count>0")["n"],
        "pts_membership_status": rows(con, "SELECT membership_status v, validation_status w, count(*) n FROM pts JOIN conf USING (season_id, player_id) GROUP BY 1,2 ORDER BY 3 DESC"),
    }
    # Player identity fields, restricted to identities in the Confirmed population.
    identity = con.execute("""
        SELECT p.player_id, p.lineup_name, p.profile_name, p.birth_date, p.nationality_code, p.nationality_name,
               p.current_team_id, p.current_position, p.profile_status, p.profile_raw_path, p.profile_collected_at_utc
        FROM pl p SEMI JOIN conf USING (player_id)""").fetchall()
    names = ["player_id", "lineup_name", "profile_name", "birth_date", "nationality_code", "nationality_name",
             "current_team_id", "current_position", "profile_status", "profile_raw_path", "profile_collected_at_utc"]
    records = [dict(zip(names, r)) for r in identity]
    resolved = lambda r: r["profile_name"] or r["lineup_name"]  # noqa: E731
    collisions_nd = Counter((norm_name(resolved(r)), r["birth_date"]) for r in records if resolved(r) and r["birth_date"])
    collisions_n = Counter(norm_name(resolved(r)) for r in records if resolved(r))
    out["identity_confirmed"] = {
        "identities": len(records),
        "null_counts": {n: sum(1 for r in records if r[n] in (None, "")) for n in names},
        "birth_date_invalid": sum(1 for r in records if r["birth_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["birth_date"])),
        "birth_date_range": [min((r["birth_date"] for r in records if r["birth_date"]), default=None), max((r["birth_date"] for r in records if r["birth_date"]), default=None)],
        "profile_status": Counter(r["profile_status"] for r in records),
        "current_position_top": Counter(r["current_position"] for r in records).most_common(12),
        "profile_collected_range": [min(r["profile_collected_at_utc"] or "" for r in records), max(r["profile_collected_at_utc"] or "" for r in records)],
        "lineup_vs_profile_name_differs": sum(1 for r in records if r["lineup_name"] and r["profile_name"] and r["lineup_name"] != r["profile_name"]),
        "names_with_replacement_char": sum(1 for r in records if "�" in ((r["profile_name"] or "") + (r["lineup_name"] or ""))),
        "names_with_mojibake_marker": sum(1 for r in records if re.search("Ã.|Å.|â€", (r["profile_name"] or "") + (r["lineup_name"] or ""))),
        "names_non_ascii": sum(1 for r in records if not (resolved(r) or "").isascii()),
        "same_normalized_name_multiple_ids": sum(1 for c in collisions_n.values() if c > 1),
        "ids_in_name_collisions": sum(c for c in collisions_n.values() if c > 1),
        "same_name_and_dob_multiple_ids": sum(1 for c in collisions_nd.values() if c > 1),
        "profile_raw_files_missing": sum(1 for r in records if r["profile_raw_path"] and not (root / r["profile_raw_path"]).is_file()),
    }
    out["names_per_season_stability"] = one(con, "SELECT count(*) n_ids, count(*) FILTER (WHERE k>1) ids_with_multiple_names FROM (SELECT player_id, count(DISTINCT player_name) k FROM conf GROUP BY 1)")
    # Season boundaries from the frozen fixture table.
    out["season_match_dates"] = rows(con, """
        SELECT season_label, count(*) rows_in_table, count(*) FILTER (WHERE match_status='COMPLETED') completed,
               min(match_date_utc) FILTER (WHERE match_status='COMPLETED') first_match_utc,
               max(match_date_utc) FILTER (WHERE match_status='COMPLETED') last_match_utc,
               count(*) FILTER (WHERE match_status<>'COMPLETED') non_completed
        FROM ma GROUP BY 1 ORDER BY 1""")
    out["non_completed_matches"] = rows(con, "SELECT season_label, match_id, match_date_utc, status_reason, match_status FROM ma WHERE match_status<>'COMPLETED'")
    out["teams_distinct"] = one(con, "SELECT count(DISTINCT team_id) team_ids, count(DISTINCT team_name) team_names, count(*) team_seasons FROM te")
    # Feature inventory.
    cur_schema = pq.ParquetFile(release / f"{tables['cur']}.parquet").schema_arrow
    metric_cols = [f.name for f in cur_schema if f.name.startswith("m_")]
    status_cols = [f.name for f in cur_schema if f.name.startswith("s_")]
    out["features"] = {
        "total_columns": len(cur_schema), "metric_columns": len(metric_cols), "status_columns": len(status_cols),
        "metric_types": Counter(str(f.type) for f in cur_schema if f.name.startswith("m_")),
        "other_columns": [f.name for f in cur_schema if not f.name.startswith(("m_", "s_"))],
        "metric_names": metric_cols,
    }
    status_totals: Counter = Counter()
    for col in status_cols:
        for row in rows(con, f'SELECT "{col}" v, count(*) n FROM cur GROUP BY 1'):
            status_totals[row["v"]] += row["n"]
    out["features"]["status_vocabulary_cell_counts"] = status_totals
    per_metric = []
    for col in metric_cols:
        stat = col.replace("m_", "s_", 1)
        rec = {"metric": col}
        for row in rows(con, f'SELECT season_label s, count("{col}") nn FROM cur GROUP BY 1 ORDER BY 1'):
            rec[row["s"]] = row["nn"]
        rec["null_total"] = one(con, f'SELECT count(*)-count("{col}") n FROM cur')["n"]
        if stat in status_cols:
            rec["observed_total"] = one(con, f"SELECT count(*) FILTER (WHERE \"{stat}\"='OBSERVED') n FROM cur")["n"]
        per_metric.append(rec)
    out["features"]["zero_converted_check_minutes"] = one(con, "SELECT count(*) FILTER (WHERE m_minutes_played IS NULL) nulls, count(*) FILTER (WHERE m_minutes_played=0) zeros FROM cur")
    return out, per_metric


def audit_tm(evidence: Path, fotmob: dict) -> dict:
    con = duckdb.connect(":memory:")
    out: dict = {"files": {}}
    for table in TM_TABLES:
        path = evidence / f"{table}.csv.gz"
        with gzip.open(path, "rb") as handle:
            size, digest = 0, hashlib.sha256()
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                size += len(chunk)
                digest.update(chunk)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv('{path.as_posix()}', all_varchar=true, header=true, quote='\"')")
        columns = [r["name"] for r in rows(con, f"PRAGMA table_info({table})")]
        nulls = {c: one(con, f'SELECT count(*)-count("{c}") n FROM {table}')["n"] for c in columns}
        out["files"][table] = {
            "gz_bytes": path.stat().st_size, "gz_sha256": sha256(path), "decompressed_bytes": size,
            "decompressed_sha256": digest.hexdigest(), "rows": one(con, f"SELECT count(*) n FROM {table}")["n"],
            "columns": columns, "null_counts": nulls,
        }

    con.execute("""CREATE TABLE v AS SELECT player_id, date raw_date, try_cast(date AS DATE) d, market_value_in_eur raw_value,
                   try_cast(market_value_in_eur AS DOUBLE) val, current_club_name, current_club_id, player_club_domestic_competition_id FROM player_valuations""")
    con.execute("""CREATE TABLE p AS SELECT player_id, name, first_name, last_name, try_cast(date_of_birth AS TIMESTAMP)::DATE dob, date_of_birth raw_dob,
                   country_of_citizenship, country_of_birth, position, sub_position, current_club_id, last_season, url FROM players""")
    out["valuations"] = one(con, """
        SELECT count(*) n_rows, count(DISTINCT player_id) players, count(DISTINCT (player_id, raw_date)) keys,
               count(*) FILTER (WHERE d IS NULL) bad_dates, min(d)::VARCHAR min_date, max(d)::VARCHAR max_date,
               count(*) FILTER (WHERE val IS NULL) null_or_bad_values, count(*) FILTER (WHERE val<=0) nonpositive_values,
               count(*) FILTER (WHERE val<>floor(val)) non_integer_values, min(val) min_value, max(val) max_value,
               median(val) median_value, count(*) FILTER (WHERE player_id IS NULL OR NOT regexp_full_match(player_id,'[0-9]+')) bad_player_ids,
               count(*) FILTER (WHERE current_club_name='Unknown') club_name_unknown, count(*) FILTER (WHERE current_club_id IS NULL) club_id_null,
               count(*) FILTER (WHERE player_club_domestic_competition_id IS NULL) comp_null
        FROM v""")
    out["valuations"]["duplicate_key_groups"] = one(con, "SELECT count(*) n FROM (SELECT player_id, raw_date FROM v GROUP BY 1,2 HAVING count(*)>1)")["n"]
    out["valuations"]["conflicting_key_groups"] = one(con, "SELECT count(*) n FROM (SELECT player_id, raw_date FROM v GROUP BY 1,2 HAVING count(DISTINCT raw_value)>1)")["n"]
    out["valuations"]["future_dated_vs_snapshot"] = one(con, "SELECT count(*) n FROM v WHERE d>DATE '2026-09-05'")["n"]
    out["valuations"]["orphan_rows_no_player"] = one(con, "SELECT count(*) n FROM v ANTI JOIN p USING (player_id)")["n"]
    out["valuations"]["players_without_valuations"] = one(con, "SELECT count(*) n FROM p ANTI JOIN (SELECT DISTINCT player_id FROM v) USING (player_id)")["n"]
    out["valuations"]["rows_by_year"] = rows(con, "SELECT year(d) y, count(*) n, count(DISTINCT player_id) players, count(DISTINCT d) dates FROM v GROUP BY 1 ORDER BY 1")
    out["valuations"]["rows_by_month_2019_2025"] = rows(con, "SELECT strftime(d,'%Y-%m') ym, count(*) n, count(DISTINCT player_id) players FROM v WHERE d BETWEEN '2019-07-01' AND '2025-08-31' GROUP BY 1 ORDER BY 1")

    out["players"] = one(con, """SELECT count(*) n_rows, count(DISTINCT player_id) ids, count(*) FILTER (WHERE dob IS NULL) dob_missing,
        count(*) FILTER (WHERE raw_dob IS NOT NULL AND dob IS NULL) dob_unparseable, count(*) FILTER (WHERE name IS NULL) name_missing,
        count(*) FILTER (WHERE country_of_citizenship IS NULL) citizenship_missing, count(*) FILTER (WHERE position IS NULL OR position='Missing') position_missing,
        count(DISTINCT name) distinct_names, min(dob)::VARCHAR min_dob, max(dob)::VARCHAR max_dob FROM p""")
    out["players"]["positions"] = rows(con, "SELECT position v, count(*) n FROM p GROUP BY 1 ORDER BY 2 DESC")
    out["players"]["url_contains_player_id"] = one(con, "SELECT count(*) n FROM p WHERE url LIKE '%/spieler/' || player_id")["n"]

    # Within-TM identity collisions (no FotMob data involved).
    tm_people = con.execute("SELECT player_id, name, dob::VARCHAR FROM p").fetchall()
    name_only = Counter(norm_name(n) for _, n, _ in tm_people if n)
    name_dob = Counter((norm_name(n), d) for _, n, d in tm_people if n and d)
    out["players"]["normalized_name_groups_multi_id"] = sum(1 for c in name_only.values() if c > 1)
    out["players"]["ids_in_name_collisions"] = sum(c for c in name_only.values() if c > 1)
    out["players"]["name_dob_groups_multi_id"] = sum(1 for c in name_dob.values() if c > 1)
    out["players"]["ids_in_name_dob_collisions"] = sum(c for c in name_dob.values() if c > 1)

    out["competitions_gb"] = rows(con, "SELECT competition_id, competition_code, name, sub_type, type, country_name, domestic_league_code FROM competitions WHERE country_name='England' OR competition_id='GB1'")
    out["clubs_gb1"] = one(con, "SELECT count(*) n FROM clubs WHERE domestic_competition_id='GB1'")["n"]
    out["transfers"] = one(con, "SELECT count(*) n_rows, count(DISTINCT player_id) players, min(try_cast(transfer_date AS DATE))::VARCHAR min_d, max(try_cast(transfer_date AS DATE))::VARCHAR max_d, count(*) FILTER (WHERE try_cast(transfer_date AS DATE)>DATE '2026-09-05') future_dated FROM transfers")
    out["transfers"]["rows_in_research_window"] = one(con, "SELECT count(*) n FROM transfers WHERE try_cast(transfer_date AS DATE) BETWEEN '2019-07-01' AND '2025-08-31'")["n"]

    # EPL membership per season: TM appearances (GB1) inside the FotMob-derived season window.
    seasons = fotmob["season_match_dates"]
    conf = {r["season_label"]: r["n"] for r in fotmob["curated_by_season"]}
    epl, coverage = [], []
    for s in seasons:
        start, end = s["first_match_utc"][:10], s["last_match_utc"][:10]
        con.execute(f"""CREATE OR REPLACE TEMP TABLE a AS SELECT player_id, game_id, player_club_id, try_cast(minutes_played AS INT) mins, player_name
                        FROM appearances WHERE competition_id='GB1' AND try_cast(date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'""")
        stat = one(con, "SELECT count(*) appearance_rows, count(DISTINCT game_id) games, count(DISTINCT player_id) players, count(DISTINCT player_club_id) clubs, count(*) FILTER (WHERE mins IS NULL OR mins=0) zero_or_null_minutes FROM a")
        stat.update(season=s["season_label"], window=[start, end], fotmob_confirmed=conf[s["season_label"]],
                    players_not_in_players_table=one(con, "SELECT count(DISTINCT player_id) n FROM a ANTI JOIN p USING (player_id)")["n"],
                    players_multi_club=one(con, "SELECT count(*) n FROM (SELECT player_id FROM a GROUP BY 1 HAVING count(DISTINCT player_club_id)>1)")["n"])
        epl.append(stat)
        con.execute(f"""CREATE OR REPLACE TEMP TABLE c AS
            SELECT e.player_id, max(v.d) FILTER (WHERE v.d <= DATE '{end}') last_d,
                   count(v.d) FILTER (WHERE v.d <= DATE '{end}') n_on_or_before, count(v.d) FILTER (WHERE v.d > DATE '{end}') n_after,
                   count(v.d) n_total
            FROM (SELECT DISTINCT player_id FROM a) e LEFT JOIN v ON e.player_id=v.player_id GROUP BY 1""")
        cov = one(con, f"""SELECT count(*) tm_epl_players, count(*) FILTER (WHERE n_total=0) no_valuation_at_all,
              count(*) FILTER (WHERE n_on_or_before=0 AND n_total>0) only_after_cutoff, count(*) FILTER (WHERE n_on_or_before>0) has_on_or_before,
              median(date_diff('day', last_d, DATE '{end}')) median_age_days, quantile_cont(date_diff('day', last_d, DATE '{end}'),0.9) p90_age_days,
              max(date_diff('day', last_d, DATE '{end}')) max_age_days FROM c""")
        for label, low, high in AGE_BINS:
            cov[f"age_{label}"] = one(con, f"SELECT count(*) n FROM c WHERE date_diff('day', last_d, DATE '{end}') BETWEEN {low} AND {high}")["n"]
        cov.update(season=s["season_label"], cutoff=end,
                   valuations_all_players_in_season_window=one(con, f"SELECT count(*) n FROM v WHERE d BETWEEN DATE '{start}' AND DATE '{end}'")["n"],
                   same_date_conflicts_on_selected_date=one(con, "SELECT count(*) n FROM (SELECT c.player_id FROM c JOIN v ON c.player_id=v.player_id AND c.last_d=v.d GROUP BY 1 HAVING count(DISTINCT v.raw_value)>1)")["n"])
        coverage.append(cov)
    out["epl_appearance_population"] = epl
    out["valuation_coverage_tm_epl_population"] = coverage

    all_epl = "SELECT DISTINCT player_id FROM appearances WHERE competition_id='GB1' AND try_cast(date AS DATE) BETWEEN DATE '{}' AND DATE '{}'".format(seasons[0]["first_match_utc"][:10], seasons[-1]["last_match_utc"][:10])
    out["identity_tm_epl"] = one(con, f"""SELECT count(*) identities, count(*) FILTER (WHERE dob IS NULL) dob_missing, count(*) FILTER (WHERE country_of_citizenship IS NULL) citizenship_missing,
          count(*) FILTER (WHERE name IS NULL) name_missing, count(*) FILTER (WHERE position IS NULL OR position='Missing') position_missing,
          count(DISTINCT dob) distinct_dobs FROM p SEMI JOIN ({all_epl}) USING (player_id)""")
    rows_epl = con.execute(f"SELECT player_id, name, dob::VARCHAR FROM p SEMI JOIN ({all_epl}) USING (player_id)").fetchall()
    epl_nd = Counter((norm_name(n), d) for _, n, d in rows_epl if n and d)
    epl_n = Counter(norm_name(n) for _, n, _ in rows_epl if n)
    epl_d = Counter(d for _, _, d in rows_epl if d)
    out["identity_tm_epl"].update(
        name_dob_groups_multi_id=sum(1 for c in epl_nd.values() if c > 1),
        name_groups_multi_id=sum(1 for c in epl_n.values() if c > 1),
        dob_groups_multi_id=sum(1 for c in epl_d.values() if c > 1),
        ids_sharing_dob=sum(c for c in epl_d.values() if c > 1),
        max_ids_per_dob=max(epl_d.values(), default=0),
        appearance_player_name_missing=one(con, "SELECT count(*) n FROM appearances WHERE competition_id='GB1' AND player_name IS NULL")["n"],
    )
    # Derived club columns are not historical facts: measure how often they disagree with game-level evidence.
    out["valuation_club_vs_game_club_2019_2025"] = one(con, f"""
        WITH m AS (SELECT DISTINCT a.player_id, try_cast(a.date AS DATE) gd, a.player_club_id FROM appearances a
                   WHERE competition_id='GB1' AND try_cast(a.date AS DATE) BETWEEN DATE '2019-08-01' AND DATE '2025-05-31'),
             j AS (SELECT v.player_id, v.d, v.current_club_id, m.player_club_id, row_number() OVER (PARTITION BY v.player_id, v.d ORDER BY m.gd DESC) rn
                   FROM v JOIN m ON v.player_id=m.player_id AND m.gd BETWEEN v.d - INTERVAL 30 DAY AND v.d)
        SELECT count(*) compared_valuations, count(*) FILTER (WHERE current_club_id=player_club_id) club_agrees,
               count(*) FILTER (WHERE current_club_id IS DISTINCT FROM player_club_id) club_disagrees FROM j WHERE rn=1""")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--tm-evidence", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    fotmob, per_metric = audit_fotmob(args.root)
    tm = audit_tm(args.tm_evidence, fotmob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "duckdb_version": duckdb.__version__,
              "fotmob": fotmob, "fotmob_metric_coverage": per_metric, "transfermarkt": tm}
    args.out.write_text(json.dumps(result, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
