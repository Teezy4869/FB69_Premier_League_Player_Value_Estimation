"""Controlled integration of FotMob features and Transfermarkt targets (Phase 3, Step 5).

Starts from the frozen Confirmed population. Every join is a checked one-to-one or many-to-one LEFT JOIN: right keys
must be unique, and the row count must not change. Any failure stops the build. Nothing is imputed, and no row is dropped.

Usage: python -I src/phase3/integrate.py
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
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash, verify_fotmob_unchanged, write_json  # noqa: E402

DATASET_VERSION = "player_season_integrated_v1"
RELEASE = ROOT / "data/releases/fb69_player_season_integrated_v1"
CROSSWALK = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
TARGET = ROOT / "data/phase_03/targets/target_v1__matching_v2_1/player_season_target.parquet"
AUDIT = ROOT / "reports/phase_03/step_04/audit_4_1/evidence"
FLAGS = AUDIT / "target_quality_flags.parquet"
TEMPORAL = AUDIT / "temporal_alignment_by_player_season.parquet"
SEASONS = ROOT / "configs/phase_03_seasons.yaml"
EXPECTED_ROWS = 3262
EXPECTED_PLAYERS = 1343
# D7: 2019/20 values are kept, and flagged as unavailable for comparison. Same-family metrics share the 4-of-380 coverage.
XG_XA_FAMILY = ("m_expected_goals", "m_expected_assists", "m_non_penalty_xg", "m_expected_goals_on_target")


class IntegrationError(RuntimeError):
    pass


def checked_join(con, log: list, name: str, left: str, right: str, keys: tuple[tuple[str, str], ...], columns: str, output: str, require_all: bool = True) -> None:
    """Create `output` as left LEFT JOIN right, and stop unless right keys are unique and row count is unchanged."""
    right_keys = ", ".join(r for _, r in keys)
    before = con.execute(f"SELECT count(*) FROM {left}").fetchone()[0]
    right_rows = con.execute(f"SELECT count(*) FROM {right}").fetchone()[0]
    right_unique = con.execute(f"SELECT count(*) FROM (SELECT DISTINCT {right_keys} FROM {right})").fetchone()[0]
    right_null = con.execute(f"SELECT count(*) FROM {right} WHERE " + " OR ".join(f"{r} IS NULL" for _, r in keys)).fetchone()[0]
    if right_unique != right_rows or right_null:
        raise IntegrationError(f"{name}: right key not unique or null ({right_rows} rows, {right_unique} keys, {right_null} null)")
    condition = " AND ".join(f"l.{a}=r.{b}" for a, b in keys)
    con.execute(f"CREATE TABLE {output} AS SELECT l.*, {columns} FROM {left} l LEFT JOIN {right} r ON {condition}")
    after = con.execute(f"SELECT count(*) FROM {output}").fetchone()[0]
    unmatched = con.execute(f"SELECT count(*) FROM {left} l ANTI JOIN {right} r ON {condition}").fetchone()[0]
    if after != before:
        raise IntegrationError(f"{name}: row count changed from {before} to {after}")
    if require_all and unmatched:
        raise IntegrationError(f"{name}: {unmatched} left rows have no match")
    log.append({"join": name, "rows_before": before, "right_rows": right_rows, "right_unique_keys": right_unique, "rows_after": after, "left_rows_without_match": unmatched, "cardinality": "at most one right row per left row (right key unique)"})


def build(out_dir: Path) -> dict:
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    con.execute("SET preserve_insertion_order=true")
    fm = FOTMOB_RELEASE
    sources = {"s_cur": fm / "curated/confirmed_appeared_player_seasons.parquet", "s_conf": fm / "normalized/confirmed_appeared_player_seasons.parquet", "s_players": fm / "normalized/players.parquet", "s_pos": fm / "normalized/historical_position_observations.parquet",
               "s_pts": fm / "normalized/player_team_seasons.parquet", "s_teams": fm / "normalized/teams.parquet", "s_cw": CROSSWALK, "s_target": TARGET, "s_flags": FLAGS, "s_temporal": TEMPORAL}
    for alias, path in sources.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    log: list = []
    source_rows = con.execute("SELECT count(*) FROM s_cur").fetchone()[0]
    source_keys = con.execute("SELECT count(DISTINCT (season_id, player_id)) FROM s_cur").fetchone()[0]
    statuses = [r[0] for r in con.execute("SELECT DISTINCT population_status FROM s_cur").fetchall()]
    if source_rows != EXPECTED_ROWS or source_keys != EXPECTED_ROWS or statuses != ["APPEARED"]:
        raise IntegrationError(f"Unexpected population: {source_rows} rows, {source_keys} keys, statuses {statuses}")
    columns = [r[0] for r in con.execute("DESCRIBE s_cur").fetchall()]
    metric_cols = [c for c in columns if c.startswith("m_")]
    status_cols = [c for c in columns if c.startswith("s_")]
    con.execute("CREATE TABLE j0 AS SELECT * FROM s_cur ORDER BY season_label, player_id")
    checked_join(con, log, "population attributes (FotMob normalized)", "j0", "s_conf", (("season_id", "season_id"), ("player_id", "player_id")),
                 "r.player_name, r.population_category, r.confirmed_appearance_count, r.started_match_count, r.sub_in_match_count, r.unresolved_substitute_count, r.is_multi_club, r.multi_club_status, r.associated_team_count, r.team_ids, r.team_names, r.classification_reason, r.profile_status", "j1")
    checked_join(con, log, "player identity (FotMob players)", "j1", "s_players", (("player_id", "player_id"),), "r.profile_name, r.birth_date, r.nationality_name AS nationality_profile_present_day", "j2")
    con.execute("""CREATE TEMP TABLE modal AS SELECT player_id, season_id, mapped_group FROM (SELECT player_id, season_id, mapped_group, row_number() OVER (PARTITION BY player_id, season_id ORDER BY count(*) DESC, mapped_group) rk
                   FROM s_pos WHERE mapped_group<>'UNKNOWN' GROUP BY 1,2,3) WHERE rk=1""")
    checked_join(con, log, "historical season position (FotMob lineups)", "j2", "modal", (("season_id", "season_id"), ("player_id", "player_id")), "r.mapped_group AS position_group_season", "j3", require_all=False)
    checked_join(con, log, "identity crosswalk", "j3", "s_cw", (("player_id", "fotmob_player_id"),),
                 "r.canonical_player_id, r.transfermarkt_player_id, r.match_status AS crosswalk_status, r.match_method AS crosswalk_method, r.review_status AS identity_review_status, r.adjudicator AS identity_adjudicator, r.adjudication_confidence AS identity_adjudication_confidence, r.adjudication_basis AS identity_adjudication_basis, r.matching_version", "j4")
    checked_join(con, log, "season-end target", "j4", "s_target", (("player_id", "fotmob_player_id"), ("season_label", "season")),
                 """r.canonical_player_id AS _target_canonical, r.transfermarkt_player_id AS _target_tm, r.market_value AS target_market_value, r.currency AS target_currency, r.selected_valuation_date AS target_valuation_date, r.season_end_date AS target_season_end_date, r.valuation_age_days AS target_valuation_age_days, r.staleness_bucket AS target_staleness_bucket,
                    r.target_status, r.target_missing_reason, r.identity_evidence_tier, r.source_record_reference AS target_source_record_reference, r.source_file_sha256 AS target_source_file_sha256, r.source_row_number AS target_source_row_number, r.selection_rule_version AS target_selection_rule_version,
                    r.player_games_in_season AS temporal_player_games_in_season, r.player_games_after_valuation AS temporal_player_games_after_valuation, r.league_games_in_season AS temporal_league_games_in_season, r.league_games_after_valuation AS temporal_league_games_after_valuation""", "j5")
    mismatch = con.execute("SELECT count(*) FROM j5 WHERE canonical_player_id<>_target_canonical OR transfermarkt_player_id IS DISTINCT FROM _target_tm").fetchone()[0]
    ineligible = con.execute("SELECT count(*) FROM j5 WHERE _target_tm IS NULL AND transfermarkt_player_id IS NOT NULL").fetchone()[0]
    if mismatch or ineligible:
        raise IntegrationError(f"Crosswalk and target disagree on {mismatch} rows")
    checked_join(con, log, "target quality flags (Step 4.1)", "j5", "s_flags", (("player_id", "fotmob_player_id"), ("season_label", "season")),
                 """r.on_2020_04_08_batch AS target_on_2020_04_08_batch, r.previous_value AS target_audit_previous_value, r.previous_valuation_date AS target_audit_previous_valuation_date, r.ratio_to_previous_value AS target_audit_ratio_to_previous_value,
                    r.last_valuation_before_2020_04_08_batch AS target_audit_last_non_batch_valuation_date, r.age_days_from_last_non_batch_valuation AS target_audit_age_days_from_last_non_batch, r.player_games_after_last_non_batch_valuation AS temporal_player_games_after_last_non_batch""", "j6")
    checked_join(con, log, "temporal alignment (Step 4.1)", "j6", "s_temporal", (("player_id", "fotmob_player_id"), ("season_label", "season")), "r.games_on_valuation_date AS temporal_player_games_on_valuation_date, r.minutes_played_before AS temporal_minutes_before_or_on_valuation, r.minutes_played_after AS temporal_minutes_after_valuation", "j7")
    metric_null_sum = " + ".join(f'CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END' for c in metric_cols)
    xg_list = ", ".join(f"'{c}'" for c in XG_XA_FAMILY)
    con.execute(f"""CREATE TABLE final AS SELECT
        canonical_player_id, season_label AS season, season_id, player_id AS fotmob_player_id, transfermarkt_player_id,
        player_name AS fotmob_player_name, profile_name AS fotmob_profile_name, birth_date AS fotmob_birth_date, nationality_profile_present_day,
        population_status, population_category, classification_reason, profile_status, confirmed_appearance_count, started_match_count, sub_in_match_count, unresolved_substitute_count,
        confirmed_team_ids, confirmed_team_count, associated_team_count, team_ids AS associated_team_ids, team_names AS associated_team_names, is_multi_club, multi_club_status,
        CASE WHEN confirmed_team_count>=2 THEN 'MULTI_CLUB_CONFIRMED_APPEARANCES' WHEN is_multi_club THEN 'MULTI_CLUB_SQUAD_ONLY' ELSE 'SINGLE_CLUB' END AS multi_club_class,
        round(date_diff('day', birth_date::DATE, target_season_end_date)/365.25, 2) AS age_at_season_end_years, coalesce(position_group_season, 'UNKNOWN') AS position_group_season,
        target_market_value, target_currency, target_status, target_missing_reason, target_valuation_date, target_season_end_date, target_valuation_age_days, target_staleness_bucket, target_market_value IS NOT NULL AS target_usable,
        target_source_record_reference, target_source_file_sha256, target_source_row_number, target_selection_rule_version,
        target_on_2020_04_08_batch, target_audit_previous_value, target_audit_previous_valuation_date, target_audit_ratio_to_previous_value, target_audit_last_non_batch_valuation_date, target_audit_age_days_from_last_non_batch,
        crosswalk_status, crosswalk_method, identity_evidence_tier, identity_review_status, identity_review_status='REVIEWED' AS identity_human_reviewed, identity_adjudicator, identity_adjudication_confidence, identity_adjudication_basis, matching_version,
        CASE WHEN transfermarkt_player_id IS NULL THEN 'UNRESOLVED_NO_MAPPING' ELSE 'MAPPED' END AS identity_match_status,
        temporal_player_games_in_season, temporal_player_games_on_valuation_date, temporal_player_games_after_valuation, temporal_player_games_after_last_non_batch, temporal_league_games_in_season, temporal_league_games_after_valuation, temporal_minutes_before_or_on_valuation, temporal_minutes_after_valuation,
        CASE WHEN target_valuation_date IS NULL THEN 'NO_VALUATION_SELECTED' WHEN temporal_player_games_after_valuation=0 THEN 'ALL_GAMES_ON_OR_BEFORE_VALUATION' WHEN temporal_player_games_after_valuation=temporal_player_games_in_season THEN 'ALL_GAMES_AFTER_VALUATION' ELSE 'MIXED' END AS temporal_alignment_class,
        season_label='2019/2020' AS sensitivity_season_2019_20, season_label='2019/2020' AS xg_xa_unavailable_for_comparison,
        CASE WHEN season_label='2019/2020' THEN 'XG_XA_PARTIAL_4_OF_380_MATCHES' ELSE 'STANDARD' END AS feature_quality_status, ({metric_null_sum}) AS missing_feature_count,
        '{DATASET_VERSION}' AS dataset_version, 'fotmob_epl_2019_2025_v3_1' AS fotmob_source_version, 'tm_r2_20260905' AS transfermarkt_source_version, profile_raw_path AS provenance_profile_raw_path, stats_raw_path AS provenance_stats_raw_path,
        {', '.join(f'"{c}"' for c in metric_cols)}, {', '.join(f'"{c}"' for c in status_cols)}
        FROM j7 ORDER BY season_label, canonical_player_id""")
    final_rows = con.execute("SELECT count(*) FROM final").fetchone()[0]
    final_keys = con.execute("SELECT count(DISTINCT (canonical_player_id, season)) FROM final").fetchone()[0]
    players = con.execute("SELECT count(DISTINCT canonical_player_id) FROM final").fetchone()[0]
    if final_rows != EXPECTED_ROWS or final_keys != EXPECTED_ROWS or players != EXPECTED_PLAYERS:
        raise IntegrationError(f"Final grain wrong: {final_rows} rows, {final_keys} keys, {players} players")
    con.execute("""CREATE TABLE club_evidence AS SELECT c.canonical_player_id, t.season_label AS season, t.player_id AS fotmob_player_id, t.team_id, n.team_name, t.membership_status, t.validation_status, t.appeared_match_count, t.evidence_raw_paths
        FROM s_pts t JOIN final c ON c.fotmob_player_id=t.player_id AND c.season_id=t.season_id LEFT JOIN s_teams n ON n.team_id=t.team_id AND n.season_id=t.season_id ORDER BY season, canonical_player_id, team_id""")
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path, evidence_path = out_dir / f"{DATASET_VERSION}.parquet", out_dir / "player_team_season_evidence.parquet"
    con.execute(f"COPY final TO '{target_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute(f"COPY club_evidence TO '{evidence_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return {"source_rows": source_rows, "source_unique_keys": source_keys, "joins": log, "final_rows": final_rows, "final_unique_keys": final_keys, "distinct_players": players, "club_evidence_rows": con.execute("SELECT count(*) FROM club_evidence").fetchone()[0],
            "metric_columns": metric_cols, "status_columns": status_cols, "output_sha256": {target_path.name: file_hash(target_path), evidence_path.name: file_hash(evidence_path)}}


COLUMN_ROLES = {
    "KEY": ("canonical_player_id", "season", "season_id", "fotmob_player_id"),
    "IDENTITY_LINK": ("transfermarkt_player_id",),
    "IDENTITY_CONTEXT": ("fotmob_player_name", "fotmob_profile_name", "fotmob_birth_date", "nationality_profile_present_day"),
    "POPULATION_EVIDENCE": ("population_status", "population_category", "classification_reason", "profile_status", "confirmed_appearance_count", "started_match_count", "sub_in_match_count", "unresolved_substitute_count"),
    "CLUB_CONTEXT": ("confirmed_team_ids", "confirmed_team_count", "associated_team_count", "associated_team_ids", "associated_team_names", "is_multi_club", "multi_club_status", "multi_club_class"),
    "CONTEXT_FEATURE": ("age_at_season_end_years", "position_group_season"),
    "TARGET": ("target_market_value", "target_currency"),
    "TARGET_METADATA": ("target_status", "target_missing_reason", "target_valuation_date", "target_season_end_date", "target_valuation_age_days", "target_staleness_bucket", "target_usable", "target_source_record_reference", "target_source_file_sha256", "target_source_row_number", "target_selection_rule_version"),
    "TARGET_AUDIT_NOT_A_PREDICTOR": ("target_on_2020_04_08_batch", "target_audit_previous_value", "target_audit_previous_valuation_date", "target_audit_ratio_to_previous_value", "target_audit_last_non_batch_valuation_date", "target_audit_age_days_from_last_non_batch"),
    "IDENTITY_QUALITY": ("crosswalk_status", "crosswalk_method", "identity_evidence_tier", "identity_review_status", "identity_human_reviewed", "identity_adjudicator", "identity_adjudication_confidence", "identity_adjudication_basis", "matching_version", "identity_match_status"),
    "TEMPORAL_ALIGNMENT_NOT_A_PREDICTOR": ("temporal_player_games_in_season", "temporal_player_games_on_valuation_date", "temporal_player_games_after_valuation", "temporal_player_games_after_last_non_batch", "temporal_league_games_in_season", "temporal_league_games_after_valuation", "temporal_minutes_before_or_on_valuation", "temporal_minutes_after_valuation", "temporal_alignment_class"),
    "QUALITY_FLAG": ("sensitivity_season_2019_20", "xg_xa_unavailable_for_comparison", "feature_quality_status", "missing_feature_count"),
    "PROVENANCE": ("dataset_version", "fotmob_source_version", "transfermarkt_source_version", "provenance_profile_raw_path", "provenance_stats_raw_path"),
}


def column_role(name: str) -> str:
    if name.startswith("m_"):
        return "FEATURE_FOTMOB_METRIC"
    if name.startswith("s_"):
        return "FEATURE_STATUS_FOTMOB"
    for role, names in COLUMN_ROLES.items():
        if name in names:
            return role
    raise IntegrationError(f"Column has no role: {name}")


def write_data_dictionary(out_dir: Path) -> int:
    schema = pq.read_schema(out_dir / f"{DATASET_VERSION}.parquet")
    with (out_dir / "data_dictionary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["column", "role", "type"])
        for field in schema:
            writer.writerow([field.name, column_role(field.name), str(field.type)])
    return len(schema)


def main() -> int:
    fotmob = verify_fotmob_unchanged()
    temp = RELEASE.parent / f"_build_{uuid.uuid4().hex}"
    try:
        record = build(temp)
        columns = write_data_dictionary(temp)
        if RELEASE.exists():
            existing = {name: file_hash(RELEASE / name) for name in record["output_sha256"]}
            if existing != record["output_sha256"]:
                print(f"STOP: {RELEASE} exists with different content; not overwritten.")
                return 2
        else:
            shutil.move(str(temp), str(RELEASE))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    inputs = [FOTMOB_RELEASE / "metadata/release_manifest.json", *[FOTMOB_RELEASE / f"normalized/{n}.parquet" for n in ("confirmed_appeared_player_seasons", "players", "historical_position_observations", "player_team_seasons", "teams", "matches", "player_match_appearances")],
              FOTMOB_RELEASE / "curated/confirmed_appeared_player_seasons.parquet", CROSSWALK, TARGET, FLAGS, TEMPORAL, SEASONS, ROOT / "configs/phase_03_matching.yaml", ROOT / "configs/phase_03_tm_source.yaml"]
    scripts = sorted((ROOT / "src/phase3").glob("*.py"))
    config = yaml.safe_load((ROOT / "configs/phase_03_tm_source.yaml").read_text(encoding="utf-8"))
    write_json(RELEASE / "integration_manifest.json", {
        "dataset_version": DATASET_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "code_version": None, "code_version_note": "No git (owner decision D5); script hashes recorded instead.",
        "research_objective": "A: end-of-season estimation (owner decision D6)", "owner_decisions": {"D6": "A", "D7": "Keep all 2019/20 rows and original values; flag; treat 2019/20 xG and xA as unavailable for comparison; require sensitivity with and without 2019/20", "D8": "Start Step 5"},
        "gate_inputs": {"G3": "CONDITIONAL_PASS", "G4": "PASS"}, "fotmob_preflight": fotmob, "rights": config["rights"],
        "xg_xa_family_flagged_for_2019_20": list(XG_XA_FAMILY), "column_count": columns, "input_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in inputs}, "code_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in scripts}, **record,
    })
    print(json.dumps({k: record[k] for k in ("source_rows", "final_rows", "final_unique_keys", "distinct_players", "club_evidence_rows", "joins", "output_sha256")}, indent=0, default=str))
    print("columns", columns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
