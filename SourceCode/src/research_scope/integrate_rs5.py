"""Prompt 03 Task C: integrate the rs5 FotMob population, rs5 crosswalk and rs5 target (one row per player-season).

Business rules come from the approved Phase 3 integration (src/phase3/integrate.py): start from the Confirmed
population, every join is `integrate.checked_join` (unique right keys, unchanged row count, stop on failure), FotMob
features are copied unchanged, multi-club players stay one row, nothing is imputed or dropped.

Differences from v1, all forced by the scope (D9):
  * dropped: D7 columns (sensitivity_season_2019_20, xg_xa_unavailable_for_comparison, feature_quality_status) and the
    2020-04-08 batch columns (target_on_2020_04_08_batch, target_audit_last_non_batch_valuation_date,
    target_audit_age_days_from_last_non_batch, temporal_player_games_after_last_non_batch). In scope the batch flag is
    false on every row and the "non-batch" values equal the plain ones (tested in Step 2).
  * added: identity_rs5_validation_label (rule_v2 on in-scope evidence) and research_scope_id.
Expected counts are read from the rs5 FotMob release, not hard-coded.

Usage: python -I src/research_scope/integrate_rs5.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.phase3.integrate import COLUMN_ROLES as V1_ROLES, IntegrationError, checked_join  # noqa: E402
from src.phase3.tm_common import file_hash, verify_fotmob_unchanged, write_json  # noqa: E402
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.build_targets_rs5 import verify_rs5_release  # noqa: E402
from src.research_scope.entity_resolution_rs5 import RUN_DIR, VALIDATION_OUT  # noqa: E402
from src.research_scope.scope import ROOT, check_table, load_scope  # noqa: E402

DATASET_VERSION = "player_season_integrated_rs5_v1"
RELEASE = ROOT / "data/releases/fb69_player_season_integrated_rs5_v1"
CROSSWALK = RUN_DIR / "player_crosswalk.parquet"
TARGET_DIR = ROOT / "data/research_rs5/targets/target_rs5_v1__matching_v2_1_rs5"
TARGET = TARGET_DIR / "player_season_target.parquet"
TEMPORAL = TARGET_DIR / "temporal_alignment_by_player_season.parquet"
PREVIOUS = TARGET_DIR / "target_previous_valuation_audit.parquet"
DROPPED_V1_COLUMNS = {
    "sensitivity_season_2019_20": "D7 flag; D9 excludes 2019/20", "xg_xa_unavailable_for_comparison": "D7 flag; D9 excludes 2019/20", "feature_quality_status": "D7 status (2019/20 xG coverage); constant in scope",
    "target_on_2020_04_08_batch": "2019/20 batch flag; false on every in-scope row", "target_audit_last_non_batch_valuation_date": "Equals target_valuation_date on every in-scope row",
    "target_audit_age_days_from_last_non_batch": "Equals target_valuation_age_days on every in-scope row", "temporal_player_games_after_last_non_batch": "Equals temporal_player_games_after_valuation on every in-scope row",
}
ADDED_COLUMNS = {"identity_rs5_validation_label": "IDENTITY_QUALITY", "research_scope_id": "PROVENANCE"}


def column_roles() -> dict[str, tuple[str, ...]]:
    roles = {role: tuple(c for c in cols if c not in DROPPED_V1_COLUMNS) for role, cols in V1_ROLES.items()}
    for col, role in ADDED_COLUMNS.items():
        roles[role] = (*roles[role], col)
    return roles


ROLES = column_roles()


def column_role(name: str) -> str:
    if name.startswith("m_"):
        return "FEATURE_FOTMOB_METRIC"
    if name.startswith("s_"):
        return "FEATURE_STATUS_FOTMOB"
    for role, names in ROLES.items():
        if name in names:
            return role
    raise IntegrationError(f"Column has no role: {name}")


def build(out_dir: Path) -> dict:
    scope = load_scope()
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    con.execute("SET preserve_insertion_order=true")
    fm = FOTMOB_RS5
    con.execute(f"CREATE TABLE s_val AS SELECT fotmob_player_id, label FROM read_csv('{VALIDATION_OUT.as_posix()}', all_varchar=true, header=true)")
    sources = {"s_cur": fm / "curated/confirmed_appeared_player_seasons.parquet", "s_conf": fm / "normalized/confirmed_appeared_player_seasons.parquet", "s_players": fm / "normalized/players.parquet",
               "s_pos": fm / "normalized/historical_position_observations.parquet", "s_pts": fm / "normalized/player_team_seasons.parquet", "s_teams": fm / "normalized/teams.parquet",
               "s_cw": CROSSWALK, "s_target": TARGET, "s_prev": PREVIOUS, "s_temporal": TEMPORAL}
    for alias, path in sources.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    expected_rows = con.execute("SELECT count(*) FROM s_conf").fetchone()[0]
    expected_players = con.execute("SELECT count(DISTINCT player_id) FROM s_conf").fetchone()[0]
    check_table(con, "s_cur", scope, where="FotMob rs5 curated")
    log: list = []
    source_rows = con.execute("SELECT count(*) FROM s_cur").fetchone()[0]
    source_keys = con.execute("SELECT count(DISTINCT (season_id, player_id)) FROM s_cur").fetchone()[0]
    statuses = [r[0] for r in con.execute("SELECT DISTINCT population_status FROM s_cur").fetchall()]
    if source_rows != expected_rows or source_keys != expected_rows or statuses != ["APPEARED"]:
        raise IntegrationError(f"Unexpected population: {source_rows} rows, {source_keys} keys, statuses {statuses}")
    columns = [r[0] for r in con.execute("DESCRIBE s_cur").fetchall()]
    metric_cols = [c for c in columns if c.startswith("m_")]
    status_cols = [c for c in columns if c.startswith("s_")]
    con.execute("CREATE TABLE j0 AS SELECT * FROM s_cur ORDER BY season_label, player_id")
    checked_join(con, log, "population attributes (FotMob rs5 normalized)", "j0", "s_conf", (("season_id", "season_id"), ("player_id", "player_id")),
                 "r.player_name, r.population_category, r.confirmed_appearance_count, r.started_match_count, r.sub_in_match_count, r.unresolved_substitute_count, r.is_multi_club, r.multi_club_status, r.associated_team_count, r.team_ids, r.team_names, r.classification_reason, r.profile_status", "j1")
    checked_join(con, log, "player identity (FotMob players)", "j1", "s_players", (("player_id", "player_id"),), "r.profile_name, r.birth_date, r.nationality_name AS nationality_profile_present_day", "j2")
    con.execute("""CREATE TEMP TABLE modal AS SELECT player_id, season_id, mapped_group FROM (SELECT player_id, season_id, mapped_group, row_number() OVER (PARTITION BY player_id, season_id ORDER BY count(*) DESC, mapped_group) rk
                   FROM s_pos WHERE mapped_group<>'UNKNOWN' GROUP BY 1,2,3) WHERE rk=1""")
    checked_join(con, log, "historical season position (FotMob lineups)", "j2", "modal", (("season_id", "season_id"), ("player_id", "player_id")), "r.mapped_group AS position_group_season", "j3", require_all=False)
    checked_join(con, log, "identity crosswalk (rs5)", "j3", "s_cw", (("player_id", "fotmob_player_id"),),
                 "r.canonical_player_id, r.transfermarkt_player_id, r.match_status AS crosswalk_status, r.match_method AS crosswalk_method, r.review_status AS identity_review_status, r.adjudicator AS identity_adjudicator, r.adjudication_confidence AS identity_adjudication_confidence, r.adjudication_basis AS identity_adjudication_basis, r.matching_version", "j4")
    checked_join(con, log, "identity validation label (rule_v2, in-scope evidence)", "j4", "s_val", (("player_id", "fotmob_player_id"),), "r.label AS identity_rs5_validation_label", "j4b", require_all=False)
    checked_join(con, log, "season-end target (rs5)", "j4b", "s_target", (("player_id", "fotmob_player_id"), ("season_label", "season")),
                 """r.canonical_player_id AS _target_canonical, r.transfermarkt_player_id AS _target_tm, r.matching_version AS _target_matching, r.market_value AS target_market_value, r.currency AS target_currency, r.selected_valuation_date AS target_valuation_date, r.season_end_date AS target_season_end_date, r.valuation_age_days AS target_valuation_age_days, r.staleness_bucket AS target_staleness_bucket,
                    r.target_status, r.target_missing_reason, r.identity_evidence_tier, r.source_record_reference AS target_source_record_reference, r.source_file_sha256 AS target_source_file_sha256, r.source_row_number AS target_source_row_number, r.selection_rule_version AS target_selection_rule_version,
                    r.player_games_in_season AS temporal_player_games_in_season, r.player_games_after_valuation AS temporal_player_games_after_valuation, r.league_games_in_season AS temporal_league_games_in_season, r.league_games_after_valuation AS temporal_league_games_after_valuation""", "j5")
    mismatch = con.execute("SELECT count(*) FROM j5 WHERE canonical_player_id<>_target_canonical OR transfermarkt_player_id IS DISTINCT FROM _target_tm OR matching_version<>_target_matching").fetchone()[0]
    ineligible = con.execute("SELECT count(*) FROM j5 WHERE _target_tm IS NULL AND transfermarkt_player_id IS NOT NULL").fetchone()[0]
    if mismatch or ineligible:
        raise IntegrationError(f"Crosswalk and target disagree on {mismatch} rows ({ineligible} ineligible)")
    checked_join(con, log, "previous valuation audit (rs5)", "j5", "s_prev", (("player_id", "fotmob_player_id"), ("season_label", "season")),
                 "r.previous_value AS target_audit_previous_value, r.previous_valuation_date AS target_audit_previous_valuation_date, r.ratio_to_previous_value AS target_audit_ratio_to_previous_value", "j6")
    checked_join(con, log, "temporal alignment (rs5)", "j6", "s_temporal", (("player_id", "fotmob_player_id"), ("season_label", "season")),
                 "r.games_on_valuation_date AS temporal_player_games_on_valuation_date, r.minutes_played_before AS temporal_minutes_before_or_on_valuation, r.minutes_played_after AS temporal_minutes_after_valuation", "j7")
    metric_null_sum = " + ".join(f'CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END' for c in metric_cols)
    con.execute(f"""CREATE TABLE final AS SELECT
        canonical_player_id, season_label AS season, season_id, player_id AS fotmob_player_id, transfermarkt_player_id,
        player_name AS fotmob_player_name, profile_name AS fotmob_profile_name, birth_date AS fotmob_birth_date, nationality_profile_present_day,
        population_status, population_category, classification_reason, profile_status, confirmed_appearance_count, started_match_count, sub_in_match_count, unresolved_substitute_count,
        confirmed_team_ids, confirmed_team_count, associated_team_count, team_ids AS associated_team_ids, team_names AS associated_team_names, is_multi_club, multi_club_status,
        CASE WHEN confirmed_team_count>=2 THEN 'MULTI_CLUB_CONFIRMED_APPEARANCES' WHEN is_multi_club THEN 'MULTI_CLUB_SQUAD_ONLY' ELSE 'SINGLE_CLUB' END AS multi_club_class,
        round(date_diff('day', birth_date::DATE, target_season_end_date)/365.25, 2) AS age_at_season_end_years, coalesce(position_group_season, 'UNKNOWN') AS position_group_season,
        target_market_value, target_currency, target_status, target_missing_reason, target_valuation_date, target_season_end_date, target_valuation_age_days, target_staleness_bucket, target_market_value IS NOT NULL AS target_usable,
        target_source_record_reference, target_source_file_sha256, target_source_row_number, target_selection_rule_version,
        target_audit_previous_value, target_audit_previous_valuation_date, target_audit_ratio_to_previous_value,
        crosswalk_status, crosswalk_method, identity_evidence_tier, identity_rs5_validation_label, identity_review_status, identity_review_status='REVIEWED' AS identity_human_reviewed, identity_adjudicator, identity_adjudication_confidence, identity_adjudication_basis, matching_version,
        CASE WHEN transfermarkt_player_id IS NULL THEN 'UNRESOLVED_NO_MAPPING' ELSE 'MAPPED' END AS identity_match_status,
        temporal_player_games_in_season, temporal_player_games_on_valuation_date, temporal_player_games_after_valuation, temporal_league_games_in_season, temporal_league_games_after_valuation, temporal_minutes_before_or_on_valuation, temporal_minutes_after_valuation,
        CASE WHEN target_valuation_date IS NULL THEN 'NO_VALUATION_SELECTED' WHEN temporal_player_games_after_valuation=0 THEN 'ALL_GAMES_ON_OR_BEFORE_VALUATION' WHEN temporal_player_games_after_valuation=temporal_player_games_in_season THEN 'ALL_GAMES_AFTER_VALUATION' ELSE 'MIXED' END AS temporal_alignment_class,
        ({metric_null_sum}) AS missing_feature_count,
        '{DATASET_VERSION}' AS dataset_version, '{scope.scope_id}' AS research_scope_id, '{FOTMOB_RS5.name}' AS fotmob_source_version, 'tm_r2_20260905' AS transfermarkt_source_version, profile_raw_path AS provenance_profile_raw_path, stats_raw_path AS provenance_stats_raw_path,
        {', '.join(f'"{c}"' for c in metric_cols)}, {', '.join(f'"{c}"' for c in status_cols)}
        FROM j7 ORDER BY season_label, canonical_player_id""")
    final_rows = con.execute("SELECT count(*) FROM final").fetchone()[0]
    final_keys = con.execute("SELECT count(DISTINCT (canonical_player_id, season)) FROM final").fetchone()[0]
    players = con.execute("SELECT count(DISTINCT canonical_player_id) FROM final").fetchone()[0]
    if final_rows != expected_rows or final_keys != expected_rows or players != expected_players:
        raise IntegrationError(f"Final grain wrong: {final_rows} rows, {final_keys} keys, {players} players")
    check_table(con, "final", scope, "season", "season_id", where="integrated rs5")
    con.execute("""CREATE TABLE club_evidence AS SELECT c.canonical_player_id, t.season_label AS season, t.player_id AS fotmob_player_id, t.team_id, n.team_name, t.membership_status, t.validation_status, t.appeared_match_count, t.evidence_raw_paths
        FROM s_pts t JOIN final c ON c.fotmob_player_id=t.player_id AND c.season_id=t.season_id LEFT JOIN s_teams n ON n.team_id=t.team_id AND n.season_id=t.season_id ORDER BY season, canonical_player_id, team_id""")
    check_table(con, "club_evidence", scope, "season", None, where="club evidence rs5")
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path, evidence_path = out_dir / f"{DATASET_VERSION}.parquet", out_dir / "player_team_season_evidence.parquet"
    con.execute(f"COPY final TO '{target_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute(f"COPY club_evidence TO '{evidence_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return {"source_rows": source_rows, "source_unique_keys": source_keys, "expected_rows_from_fotmob_rs5": expected_rows, "expected_players_from_fotmob_rs5": expected_players, "joins": log,
            "final_rows": final_rows, "final_unique_keys": final_keys, "distinct_players": players, "club_evidence_rows": con.execute("SELECT count(*) FROM club_evidence").fetchone()[0],
            "rows_by_season": dict(con.execute("SELECT season, count(*) FROM final GROUP BY 1 ORDER BY 1").fetchall()),
            "metric_columns": len(metric_cols), "status_columns": len(status_cols), "output_sha256": {target_path.name: file_hash(target_path), evidence_path.name: file_hash(evidence_path)}}


NOTES = {"nationality_profile_present_day": "Present-day profile value (collected 2026-11); not a historical feature", "age_at_season_end_years": "(season end - FotMob birth date) / 365.25",
         "position_group_season": "Modal known lineup position group that season", "target_market_value": "Season-end target, EUR; null when not usable", "identity_rs5_validation_label": "rule_v2 identity validator on in-scope evidence; null for unvalidated statuses",
         "missing_feature_count": "Number of null m_* metrics in the row", "research_scope_id": "rs5_v1 (D9)"}


def write_data_dictionary(out_dir: Path) -> int:
    schema = pq.read_schema(out_dir / f"{DATASET_VERSION}.parquet")
    with (out_dir / "data_dictionary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["column", "role", "type", "candidate_predictor", "note"])
        for field in schema:
            role = column_role(field.name)
            writer.writerow([field.name, role, str(field.type), role.startswith("FEATURE") or role == "CONTEXT_FEATURE", NOTES.get(field.name, "")])
    return len(schema)


def main() -> int:
    fotmob = verify_fotmob_unchanged()
    rs5 = verify_rs5_release()
    scope = load_scope()
    temp = RELEASE.parent / f"_build_{uuid.uuid4().hex}"
    try:
        record = build(temp)
        columns = write_data_dictionary(temp)
        record["output_sha256"]["data_dictionary.csv"] = file_hash(temp / "data_dictionary.csv")
        if RELEASE.exists():
            existing = {name: file_hash(RELEASE / name) for name in record["output_sha256"]}
            if existing != record["output_sha256"]:
                print(f"STOP: {RELEASE} exists with different content; not overwritten.")
                return 2
            print("Existing release has identical content; manifest kept.")
            return 0
        shutil.move(str(temp), str(RELEASE))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    inputs = [ROOT / "configs/research_scope.yaml", FOTMOB_RS5 / "metadata/release_manifest.json", CROSSWALK, VALIDATION_OUT, TARGET, PREVIOUS, TEMPORAL, TARGET_DIR / "target_manifest.json",
              ROOT / "data/research_rs5/entity_resolution/crosswalk_rs5_manifest.json", ROOT / "configs/phase_03_seasons.yaml", ROOT / "configs/phase_03_matching.yaml", ROOT / "configs/phase_03_tm_source.yaml"]
    code = [ROOT / "src/research_scope" / n for n in ("integrate_rs5.py", "scope.py", "build_fotmob_rs5.py", "build_targets_rs5.py", "entity_resolution_rs5.py")] + [ROOT / "src/phase3/integrate.py"]
    write_json(RELEASE / "integration_manifest.json", {
        "dataset_version": DATASET_VERSION, "scope_id": scope.scope_id, "seasons": list(scope.labels), "excluded_seasons": list(scope.excluded_labels), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_objective": "A: end-of-season estimation (D6)", "owner_decisions": {"D6": "A", "D9": "Five seasons 2020/21-2024/25; 2019/20 excluded; supersedes D7"},
        "code_version": None, "code_version_note": "No git (D5); script hashes recorded instead.", "fotmob_v3_1_preflight": fotmob, "fotmob_rs5_preflight": rs5,
        "dropped_v1_columns": DROPPED_V1_COLUMNS, "added_columns": ADDED_COLUMNS, "column_count": columns,
        "input_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in inputs}, "code_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in code},
        "environment": {"python": sys.version.split()[0], "duckdb": duckdb.__version__, "pyarrow": pa.__version__}, **record,
    })
    print(json.dumps({k: record[k] for k in ("source_rows", "final_rows", "final_unique_keys", "distinct_players", "club_evidence_rows", "rows_by_season", "joins", "output_sha256")}, indent=0, default=str))
    print("columns", columns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
