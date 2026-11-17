"""Tests for the integrated dataset.

CheckedJoinTests use SYNTHETIC tables in memory. All other tests read the real release and frozen sources,
and fail if they are missing.

Run the whole suite only with: .venv/Scripts/python.exe -I src/phase3/step3_qa_run_full_tests.py <output_dir>
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from src.phase3.integrate import RELEASE, IntegrationError, build, checked_join, column_role
from src.phase3.season_targets import staleness_bucket
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash

DATASET = RELEASE / "player_season_integrated_v1.parquet"
EVIDENCE = ROOT / "reports/phase_03/step_05/evidence"


class CheckedJoinTests(unittest.TestCase):
    """All records here are synthetic."""

    def setUp(self):
        self.con = duckdb.connect(":memory:")
        self.con.execute("CREATE TABLE l AS SELECT * FROM (VALUES ('a', 1), ('b', 2)) t(k, v)")
        self.log = []

    def test_one_to_one_join_passes_and_logs(self):
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10), ('b', 20)) t(k, w)")
        checked_join(self.con, self.log, "x", "l", "r", (("k", "k"),), "r.w", "out")
        self.assertEqual(self.log[0]["rows_before"], self.log[0]["rows_after"])
        self.assertEqual(self.con.execute("SELECT count(*) FROM out").fetchone()[0], 2)

    def test_duplicate_right_key_stops_the_build(self):
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10), ('a', 11), ('b', 20)) t(k, w)")
        with self.assertRaises(IntegrationError):
            checked_join(self.con, self.log, "x", "l", "r", (("k", "k"),), "r.w", "out")

    def test_many_to_many_stops_the_build(self):
        self.con.execute("CREATE TABLE l2 AS SELECT * FROM (VALUES ('a'), ('a')) t(k)")
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10), ('a', 11)) t(k, w)")
        with self.assertRaises(IntegrationError):
            checked_join(self.con, self.log, "x", "l2", "r", (("k", "k"),), "r.w", "out")

    def test_null_right_key_stops_the_build(self):
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10), (NULL, 11)) t(k, w)")
        with self.assertRaises(IntegrationError):
            checked_join(self.con, self.log, "x", "l", "r", (("k", "k"),), "r.w", "out")

    def test_lost_match_stops_a_required_join(self):
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10)) t(k, w)")
        with self.assertRaises(IntegrationError):
            checked_join(self.con, self.log, "x", "l", "r", (("k", "k"),), "r.w", "out")

    def test_optional_join_keeps_unmatched_rows_as_null(self):
        self.con.execute("CREATE TABLE r AS SELECT * FROM (VALUES ('a', 10)) t(k, w)")
        checked_join(self.con, self.log, "x", "l", "r", (("k", "k"),), "r.w", "out", require_all=False)
        self.assertEqual(self.con.execute("SELECT w FROM out WHERE k='b'").fetchone()[0], None)
        self.assertEqual(self.log[0]["left_rows_without_match"], 1)

    def test_a_new_column_without_a_role_is_rejected(self):
        with self.assertRaises(IntegrationError):
            column_role("surprise")


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = duckdb.connect(":memory:")
        cls.con.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet('{DATASET.as_posix()}')")
        cls.con.execute(f"CREATE VIEW conf AS SELECT * FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/confirmed_appeared_player_seasons.parquet').as_posix()}')")
        cls.con.execute(f"CREATE VIEW unv AS SELECT * FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/unverified_player_seasons.parquet').as_posix()}')")
        cls.con.execute(f"CREATE VIEW cur AS SELECT * FROM read_parquet('{(FOTMOB_RELEASE / 'curated/confirmed_appeared_player_seasons.parquet').as_posix()}')")
        cls.manifest = json.loads((RELEASE / "integration_manifest.json").read_text(encoding="utf-8"))

    def one(self, sql):
        return self.con.execute(sql).fetchone()[0]

    # Population
    def test_row_count_matches_frozen_source(self):
        self.assertEqual(self.one("SELECT count(*) FROM d"), self.one("SELECT count(*) FROM conf"))
        self.assertEqual(self.one("SELECT count(*) FROM d"), 3262)

    def test_confirmed_only(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE population_category<>'CONFIRMED_APPEARED' OR population_status<>'APPEARED'"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d SEMI JOIN unv ON d.fotmob_player_id=unv.player_id AND d.season_id=unv.season_id"), 0)

    def test_no_row_lost_or_added(self):
        self.assertEqual(self.one("SELECT count(*) FROM (SELECT player_id, season_label FROM conf EXCEPT SELECT fotmob_player_id, season FROM d)"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM (SELECT fotmob_player_id, season FROM d EXCEPT SELECT player_id, season_label FROM conf)"), 0)

    # Keys and cardinality
    def test_one_row_per_canonical_player_season(self):
        self.assertEqual(self.one("SELECT count(*)-count(DISTINCT (canonical_player_id, season)) FROM d"), 0)
        self.assertEqual(self.one("SELECT count(DISTINCT canonical_player_id) FROM d"), 1343)

    def test_every_join_kept_the_row_count(self):
        self.assertEqual(len(self.manifest["joins"]), 7)
        for join in self.manifest["joins"]:
            self.assertEqual(join["rows_before"], 3262, join["join"])
            self.assertEqual(join["rows_after"], 3262, join["join"])
            self.assertEqual(join["right_rows"], join["right_unique_keys"], join["join"])

    def test_multi_club_players_are_one_row(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE confirmed_team_count>=2"), 61)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE is_multi_club"), 80)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE multi_club_class='MULTI_CLUB_SQUAD_ONLY'"), 19)
        self.assertEqual(self.one("SELECT count(*) FROM (SELECT canonical_player_id, season FROM d WHERE is_multi_club GROUP BY 1,2 HAVING count(*)>1)"), 0)

    def test_multi_club_appearances_are_season_totals(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE confirmed_team_count>=2 AND m_appearances<>confirmed_appearance_count"), 0)

    def test_club_evidence_is_kept_separately(self):
        table = pq.read_table(RELEASE / "player_team_season_evidence.parquet", columns=["canonical_player_id", "season", "team_id"]).to_pylist()
        self.assertEqual(len(table), 3342)
        self.assertEqual(len({(r["canonical_player_id"], r["season"], r["team_id"]) for r in table}), 3342)

    # Temporal
    def test_no_valuation_after_cutoff(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_valuation_date>target_season_end_date"), 0)

    def test_staleness_is_correct(self):
        rows = self.con.execute("SELECT target_valuation_age_days, target_valuation_date, target_season_end_date, target_staleness_bucket FROM d WHERE target_valuation_date IS NOT NULL").fetchall()
        self.assertEqual(len(rows), 3195)
        for age, day, end, bucket in rows:
            self.assertEqual(age, (end - day).days)
            self.assertEqual(bucket, staleness_bucket(age))

    def test_no_future_information_columns(self):
        columns = [r[0] for r in self.con.execute("DESCRIBE d").fetchall()]
        for forbidden in ("next_valuation", "next_value", "highest_market", "market_value_in_eur", "current_position", "current_team", "contract"):
            self.assertFalse([c for c in columns if forbidden in c], forbidden)

    def test_original_dates_and_values_are_kept_for_the_april_2020_batch(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_on_2020_04_08_batch"), 491)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_on_2020_04_08_batch AND target_valuation_date<>DATE '2020-04-08'"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_on_2020_04_08_batch AND target_valuation_age_days<>109"), 0)

    # Missingness
    def test_missing_targets_stay_missing(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_market_value IS NULL"), 67)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_market_value=0"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_market_value IS NULL AND target_missing_reason IS NULL"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE target_usable<>(target_market_value IS NOT NULL)"), 0)

    def test_features_are_unchanged_and_nulls_are_not_zero(self):
        metrics = [r[0] for r in self.con.execute("DESCRIBE cur").fetchall() if r[0].startswith(("m_", "s_"))]
        self.assertEqual(len(metrics), 106)
        for column in metrics:
            self.assertEqual(self.one(f'SELECT count(*) FROM d JOIN cur c ON d.fotmob_player_id=c.player_id AND d.season_id=c.season_id WHERE d."{column}" IS DISTINCT FROM c."{column}"'), 0, column)

    def test_all_2019_20_rows_are_kept_with_xg_values_and_flagged(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE season='2019/2020'"), 515)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE xg_xa_unavailable_for_comparison"), 515)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE sensitivity_season_2019_20 AND season<>'2019/2020'"), 0)
        self.assertEqual(self.one("SELECT count(m_expected_goals) FROM d WHERE season='2019/2020'"), 69)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE season<>'2019/2020' AND feature_quality_status<>'STANDARD'"), 0)

    def test_unresolved_identities_remain_auditable(self):
        rows = self.con.execute("SELECT fotmob_player_name, crosswalk_status, transfermarkt_player_id, target_market_value, target_missing_reason, identity_match_status FROM d WHERE crosswalk_status='REVIEW_REQUIRED' ORDER BY 1").fetchall()
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row[1:], ("REVIEW_REQUIRED", None, None, "NO_ELIGIBLE_IDENTITY_MATCH", "UNRESOLVED_NO_MAPPING"))

    def test_no_automated_match_is_labeled_human(self):
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE identity_human_reviewed"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE crosswalk_status='MANUAL_CONFIRMED'"), 0)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE crosswalk_status='AUTO_ADJUDICATED'"), 98)
        self.assertEqual(self.one("SELECT count(*) FROM d WHERE crosswalk_status='AUTO_ADJUDICATED' AND identity_review_status<>'AUTOMATED_ADJUDICATION_NOT_HUMAN'"), 0)

    # Target separation
    def test_target_and_audit_columns_are_never_predictors(self):
        with (RELEASE / "data_dictionary.csv").open(encoding="utf-8-sig", newline="") as handle:
            roles = {r["column"]: r["role"] for r in csv.DictReader(handle)}
        self.assertEqual(len(roles), len(self.con.execute("DESCRIBE d").fetchall()))
        predictors = [c for c, r in roles.items() if r in ("FEATURE_FOTMOB_METRIC", "FEATURE_STATUS_FOTMOB", "CONTEXT_FEATURE")]
        self.assertEqual(len(predictors), 108)
        self.assertFalse([c for c in predictors if c.startswith(("target_", "temporal_", "identity_", "crosswalk"))])
        self.assertEqual(roles["target_market_value"], "TARGET")
        self.assertEqual(roles["target_audit_previous_value"], "TARGET_AUDIT_NOT_A_PREDICTOR")

    # Reproducibility
    def test_manifest_matches_outputs(self):
        for name, sha in self.manifest["output_sha256"].items():
            self.assertEqual(file_hash(RELEASE / name), sha, name)
        for name, sha in self.manifest["input_sha256"].items():
            self.assertEqual(file_hash(ROOT / name), sha, name)
        self.assertEqual(self.manifest["final_rows"], 3262)
        self.assertEqual(self.manifest["gate_inputs"]["G3"], "CONDITIONAL_PASS")

    def test_integration_rebuilds_byte_identically(self):
        with tempfile.TemporaryDirectory() as folder:
            record = build(Path(folder) / "out")
        self.assertEqual(record["output_sha256"], self.manifest["output_sha256"])

    def test_validation_summary_has_no_failures(self):
        summary = json.loads((EVIDENCE / "validation_summary.json").read_text(encoding="utf-8"))
        self.assertGreater(summary["checks"], 25)
        self.assertEqual(summary["failed"], 0)

    def test_full_chain_reproduction_passed(self):
        result = json.loads((EVIDENCE / "phase3_reproduction.json").read_text(encoding="utf-8"))
        self.assertTrue(result["all_identical"])
        self.assertGreaterEqual(result["stages_checked"], 11)


if __name__ == "__main__":
    unittest.main()
