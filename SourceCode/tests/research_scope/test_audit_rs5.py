"""G4: the audit evidence exists, matches the current rs5 dataset, and its key invariants hold."""
from __future__ import annotations

import csv
import json
import unittest

from src.phase3.tm_common import file_hash
from src.research_scope.audit_rs5 import DATASET
from src.research_scope.integrate_rs5 import column_role
from src.research_scope.scope import ROOT, load_scope

EVIDENCE = ROOT / "reports/research_scope_rs5/step_04/evidence"
CLASSES = {"PASS", "WARNING", "FAIL", "REQUIRES RESEARCH DECISION"}


def rows(name):
    with (EVIDENCE / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class AuditRs5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((EVIDENCE / "audit_summary.json").read_text(encoding="utf-8"))
        cls.temporal = json.loads((EVIDENCE / "temporal_audit.json").read_text(encoding="utf-8"))
        cls.quality = json.loads((EVIDENCE / "quality_audit.json").read_text(encoding="utf-8"))
        cls.scope = load_scope()

    def test_audit_is_of_the_current_dataset(self):
        self.assertEqual(self.summary["dataset_sha256"], file_hash(DATASET))

    def test_feature_windows_rechecked_on_five_seasons(self):
        self.assertTrue(self.summary["window_check"]["identical_to_historical_in_scope_rows"])
        self.assertEqual(set(self.summary["window_check"]["seasons"]), set(self.scope.labels))

    def test_temporal_indicators_recomputed_independently(self):
        overall = self.temporal["overall"]
        self.assertTrue(overall["temporal_columns_agree_with_recomputation"])
        self.assertEqual((overall["pct_targets_older_than_90_days"], overall["pct_appearances_after_valuation"]), (56.62, 44.10))
        self.assertEqual(overall["valuation_after_cutoff"], 0)
        self.assertEqual(self.temporal["appearances_after_cutoff"], 0)
        self.assertIn("denominator", self.temporal["definitions"]["pct_targets_older_than_90_days"])
        self.assertTrue(all(c["dataset_cutoff_matches_scope"] and c["last_match_equals_cutoff"] for c in self.temporal["season_cutoffs"].values()))

    def test_every_column_has_a_leakage_classification(self):
        leak = rows("leakage_audit.csv")
        import pyarrow.parquet as pq
        self.assertEqual({r["column"] for r in leak}, set(pq.read_schema(DATASET).names))
        self.assertTrue(all(r["classification"] in CLASSES and r["evidence"] for r in leak))

    def test_no_candidate_predictor_fails_and_every_target_derived_column_is_excluded(self):
        for r in rows("leakage_audit.csv"):
            if r["candidate_predictor"] == "True":
                self.assertNotEqual(r["classification"], "FAIL", r["column"])
            if r["column"].startswith(("target_", "temporal_")):
                self.assertEqual(r["classification"], "FAIL", r["column"])
                self.assertFalse(column_role(r["column"]).startswith("FEATURE"))

    def test_no_candidate_feature_encodes_the_target(self):
        for r in rows("leakage_audit.csv"):
            if r["candidate_predictor"] == "True" and r["spearman_with_log_target"]:
                self.assertLess(abs(float(r["spearman_with_log_target"])), 0.8, r["column"])

    def test_feature_reliability_covers_every_candidate(self):
        rel = {r["feature"] for r in rows("feature_reliability.csv")}
        candidates = {r["column"] for r in rows("leakage_audit.csv") if r["candidate_predictor"] == "True" and not r["column"].startswith("s_")}
        self.assertEqual(rel, candidates)

    def test_evidence_contains_only_official_seasons(self):
        for name in ("missingness_by_feature_season.csv", "metric_distribution_by_season.csv", "feature_window_audit_rs5.csv"):
            seasons = {r["season"] for r in rows(name)} - {"ALL"}
            self.assertEqual(seasons, set(self.scope.labels), name)

    def test_quality_invariants(self):
        s = self.quality["structural"]
        self.assertEqual(s["duplicate_keys"], 0)
        self.assertEqual(self.quality["reliability"]["unexpected_status_values"], [])
        self.assertEqual(self.quality["reliability"]["metric_value_status_inconsistencies"], {})
        self.assertEqual(s["invalid_values"]["target_not_positive"], 0)


if __name__ == "__main__":
    unittest.main()
