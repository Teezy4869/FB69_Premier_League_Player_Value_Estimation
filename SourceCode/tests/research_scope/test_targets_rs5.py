"""G2: the rs5 target follows the approved rule, stays in scope, and matches the historical in-scope rows."""
from __future__ import annotations

import json
import unittest
from datetime import date

import duckdb
import pyarrow.parquet as pq

from src.phase3 import season_targets
from src.phase3.tm_common import file_hash
from src.research_scope.build_targets_rs5 import HISTORICAL_TARGET, HISTORICAL_TEMPORAL, IDENTITY_COLUMNS, OUT_ROOT, TARGET_VERSION, validate
from src.research_scope.scope import check_parquet, load_scope

class TargetRs5Test(unittest.TestCase):
    """Step 2 version: historical player-level mapping restricted to the rs5 universe."""

    FOLDER = OUT_ROOT / f"{TARGET_VERSION}__matching_v2_1"
    # Columns allowed to differ from the historical in-scope rows.
    ALLOWED_DIFF: tuple[str, ...] = ()

    @classmethod
    def setUpClass(cls):
        global FOLDER, TARGET
        FOLDER, TARGET = cls.FOLDER, cls.FOLDER / "player_season_target.parquet"
        cls.TARGET = TARGET
        cls.scope = load_scope()
        cls.manifest = json.loads((FOLDER / "target_manifest.json").read_text(encoding="utf-8"))
        cls.con = duckdb.connect()
        cls.con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{TARGET.as_posix()}')")

    def setUp(self):
        global FOLDER, TARGET
        FOLDER, TARGET = self.FOLDER, self.TARGET

    def one(self, sql):
        return self.con.execute(sql).fetchone()[0]

    def test_outputs_match_manifest(self):
        for name, sha in self.manifest["output_sha256"].items():
            self.assertEqual(file_hash(FOLDER / name), sha, name)

    def test_scope_and_cutoffs(self):
        check_parquet(TARGET, self.scope, "season", "season_id")
        for season, cut in self.con.execute("SELECT DISTINCT season, season_end_date FROM t").fetchall():
            self.assertEqual(cut, self.scope.by_label(season).season_end_date)
        check_parquet(FOLDER / "temporal_alignment_by_player_season.parquet", self.scope, "season", None)
        check_parquet(FOLDER / "target_previous_valuation_audit.parquet", self.scope, "season", None)

    def test_schema_is_the_approved_target_schema(self):
        self.assertEqual(pq.read_schema(TARGET).remove_metadata(), season_targets.SCHEMA)

    def test_all_validation_checks_pass(self):
        failed = [c for c in validate([], TARGET) if c["status"] != "PASS"]
        self.assertEqual(failed, [])

    def test_counts(self):
        self.assertEqual(self.one("SELECT count(*) FROM t"), 2747)
        self.assertEqual(self.one("SELECT count(*) FROM t WHERE target_status IN ('VALID','STALE_TARGET')"), 2697)
        self.assertEqual(dict(self.con.execute("SELECT target_missing_reason, count(*) FROM t WHERE market_value IS NULL GROUP BY 1").fetchall()),
                         {"ONLY_VALUATIONS_AFTER_CUTOFF": 37, "NO_VALUATION_HISTORY": 11, "NO_ELIGIBLE_IDENTITY_MATCH": 2})
        self.assertEqual(self.one("SELECT count(*) FROM t WHERE target_status IN ('INVALID_VALUATION','AMBIGUOUS_VALUATION')"), 0)

    def test_rows_equal_historical_in_scope_rows(self):
        for fresh, old in ((TARGET, HISTORICAL_TARGET), (FOLDER / "temporal_alignment_by_player_season.parquet", HISTORICAL_TEMPORAL)):
            cols = ", ".join(f.name for f in pq.read_schema(fresh) if f.name not in self.ALLOWED_DIFF)
            a, b = f"(SELECT {cols} FROM read_parquet('{fresh.as_posix()}'))", f"(SELECT {cols} FROM read_parquet('{old.as_posix()}') WHERE season IN ({self.scope.sql_labels()}))"
            self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})"), 0, fresh.name)
            self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT * FROM {b} EXCEPT ALL SELECT * FROM {a})"), 0, fresh.name)

    def test_staleness_is_a_label_not_an_exclusion(self):
        self.assertGreater(self.one("SELECT count(*) FROM t WHERE target_status='STALE_TARGET' AND market_value IS NOT NULL"), 0)
        self.assertEqual(self.one(f"SELECT count(*) FROM t WHERE (valuation_age_days > {self.scope.stale_label_days}) <> (target_status='STALE_TARGET') AND market_value IS NOT NULL"), 0)

    def test_select_target_never_uses_future_valuations(self):
        """Synthetic observations, not research data."""
        cut = date(2021, 5, 23)
        obs = [{"valuation_date": date(2021, 5, 30), "market_value": 9, "quality_status": "VALID", "source_record_id": "b"},
               {"valuation_date": date(2021, 3, 1), "market_value": 5, "quality_status": "VALID", "source_record_id": "a"}]
        self.assertEqual(season_targets.select_target(obs, cut, 90)["market_value"], 5)
        self.assertEqual(season_targets.select_target(obs[:1], cut, 90)["target_missing_reason"], "ONLY_VALUATIONS_AFTER_CUTOFF")

    def test_statistics_definitions_are_recorded(self):
        stats = self.manifest["statistics"]
        self.assertIn("pct_targets_older_than_90_days", stats["definitions"])
        self.assertEqual(set(stats["by_season"]), set(self.scope.labels))



class TargetRs5RevalidatedIdentityTest(TargetRs5Test):
    """Step 3 version used by integration: rs5 crosswalk and in-scope validation labels. Only identity columns may differ."""

    FOLDER = OUT_ROOT / f"{TARGET_VERSION}__matching_v2_1_rs5"
    ALLOWED_DIFF = IDENTITY_COLUMNS

    def test_only_identity_columns_differ_from_step_2(self):
        step2 = (OUT_ROOT / f"{TARGET_VERSION}__matching_v2_1" / "player_season_target.parquet").as_posix()
        cols = ", ".join(f.name for f in pq.read_schema(TARGET) if f.name not in IDENTITY_COLUMNS)
        self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT {cols} FROM t EXCEPT ALL SELECT {cols} FROM read_parquet('{step2}'))"), 0)
        self.assertEqual(self.one("SELECT count(DISTINCT matching_version) FROM t"), 1)
        self.assertEqual(self.one("SELECT any_value(matching_version) FROM t"), "matching_v2_1_rs5")


if __name__ == "__main__":
    unittest.main()
