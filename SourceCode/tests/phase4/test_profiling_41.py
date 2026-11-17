"""Phase 4.1 profiling tests. Read-only: they load the official release and the recorded evidence; they write nothing."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.phase4 import profiling as p  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_01/evidence"


class ProfilingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.dictionary, cls.eligibility, cls.reliability = p.load_metadata()

    def test_hash_mismatch_stops_before_loading(self):
        with self.assertRaises(RuntimeError):
            p.load_verified(expected="0" * 64)

    def test_overview_matches_official_release(self):
        o = p.overview(self.df, self.scope)
        self.assertEqual((o["rows"], o["columns"], o["unique_players"], o["usable_targets"], o["missing_targets"]), (2747, 175, 1228, 2697, 50))
        self.assertEqual(o["target_coverage_pct"], 98.18)
        self.assertEqual((o["duplicated_full_rows"], o["duplicated_primary_keys"], o["null_primary_keys"]), (0, 0, 0))
        self.assertTrue(o["seasons_equal_scope"])

    def test_only_official_seasons(self):
        self.assertEqual(sorted(self.df["season"].unique()), sorted(self.scope.labels))
        self.assertFalse(set(self.df["season"]) & set(self.scope.excluded_labels))
        self.assertEqual(p.season_distribution(self.df, self.scope)["rows"].tolist(), [524, 537, 554, 570, 562])

    def test_schema_profile_covers_every_column_once(self):
        profile = p.schema_profile(self.df, self.schema, self.dictionary, self.eligibility)
        self.assertEqual(profile["column"].tolist(), self.df.columns.tolist())
        self.assertFalse(profile["eligibility_category"].isna().any())
        self.assertEqual(p.type_checks(self.schema, self.dictionary), [])

    def test_known_anomaly_preserved_not_corrected(self):
        rows = p.starts_gt_appearances(self.df)
        self.assertEqual(len(rows), 6)
        self.assertEqual(set(rows["season"]), {"2020/2021"})
        self.assertTrue((rows["m_starts"] - rows["m_appearances"] == 1).all())

    def test_status_and_value_agree(self):
        consistency = p.metric_status_consistency(self.df).set_index("metric")
        self.assertEqual(int(consistency.to_numpy().sum()), 0)

    def test_no_unexpected_categories(self):
        domains = p.categorical_domains(self.df, self.scope)
        self.assertTrue((domains["unexpected_values"].str.len() == 0).all())

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "profiling_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["sha256"], p.DATASET_SHA256)
        self.assertEqual(summary["overview"], json.loads(json.dumps(p.overview(self.df, self.scope))))
        self.assertEqual(summary["missingness"], p.missingness_overview(self.df))
        recorded = pd.read_csv(EVIDENCE / "logical_checks.csv", index_col=0)["rows"]
        self.assertEqual(recorded.to_dict(), p.logical_checks(self.df)["rows"].to_dict())
        recorded_profile = pd.read_csv(EVIDENCE / "schema_profile.csv")
        fresh = p.schema_profile(self.df, self.schema, self.dictionary, self.eligibility)
        self.assertEqual(recorded_profile["null"].tolist(), fresh["null"].tolist())
        self.assertEqual(recorded_profile["unique"].tolist(), fresh["unique"].tolist())

    def test_dataset_unchanged_after_profiling(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
