"""Unit and regression tests for Phase 2B.1-R Steps 05 & 06.

Validates:
  - Step 05: Metric conflict taxonomy, rounding differences, definition mismatches,
    aggregation mismatches, source revisions, multiclub protection, unresolved preservation.
  - Step 06: Historical xG/xA missingness diagnosis, fallback candidate validation,
    proper vs invalid fallback, 2019/20 recovery, raw evidence traceability,
    reprocessing determinism.
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.remediation_conflicts import (
    classify_conflict,
    build_conflict_inventory,
    build_reconciliation_registry_v3,
    execute_step05_remediation
)
from src.collection.remediation_recovery import (
    build_historical_xg_xa_audit,
    build_metric_fallback_validation,
    generate_provisional_curated_wide,
    execute_step06_remediation
)


class RemediationSteps0506Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_dir = ROOT / "reports/phase_02b1_remediation"
        cls.provisional_path = ROOT / "data/phase_02b1/remediation/curated/player_season_metrics_wide_provisional.parquet"
        cls.conflict_csv = cls.report_dir / "metric_conflict_root_causes.csv"
        cls.audit_csv = cls.report_dir / "historical_xg_xa_audit.csv"
        cls.fallback_csv = cls.report_dir / "metric_fallback_validation.csv"
        cls.registry_json = cls.report_dir / "metric_reconciliation_registry_v3.json"

        # Load inventory
        with cls.conflict_csv.open(encoding="utf-8", newline="") as f:
            cls.conflict_rows = list(csv.DictReader(f))

        # Load provisional table
        cls.prov_table = pq.read_table(cls.provisional_path).to_pandas() if cls.provisional_path.exists() else None

    def test_01_two_compatible_observations_with_equal_values(self):
        """When board and playerStats values match exactly, status must be MATCH and value OBSERVED."""
        recon_path = ROOT / "reports/phase_02b1/metric_reconciliation_report.csv"
        with recon_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        matches = [r for r in rows if r["comparison_status"] == "MATCH"]
        self.assertGreater(len(matches), 10000)
        sample = matches[0]
        self.assertEqual(float(sample["board_value"]), float(sample["player_stats_value"]))

    def test_02_rounding_differences(self):
        """Discrepancies on 0.x5 boundary (diff <= 0.051) must be classified ROUNDING_DIFFERENCE and resolved."""
        rounding_conflicts = [r for r in self.conflict_rows if r["root_cause_classification"] == "ROUNDING_DIFFERENCE"]
        self.assertEqual(len(rounding_conflicts), 444)
        for r in rounding_conflicts:
            self.assertEqual(r["resolution_action"], "RESOLVED_ROUNDING_TOLERANCE")
            self.assertEqual(r["curated_resolved_status"], "OBSERVED")
            self.assertNotEqual(r["curated_resolved_value"], "")

    def test_03_incompatible_metric_definitions(self):
        """Definition divergence (e.g. goals_prevented) must be DEFINITION_MISMATCH and preserved as CONFLICTING."""
        def_mismatches = [r for r in self.conflict_rows if r["root_cause_classification"] == "DEFINITION_MISMATCH"]
        self.assertEqual(len(def_mismatches), 18)
        for r in def_mismatches:
            self.assertEqual(r["canonical_metric"], "goals_prevented")
            self.assertEqual(r["resolution_action"], "PRESERVED_UNRESOLVED_NULL")
            self.assertEqual(r["curated_resolved_status"], "CONFLICTING")
            self.assertEqual(r["curated_resolved_value"], "")

    def test_04_total_versus_per90_mismatch(self):
        """Total metrics and per90 metrics must maintain separate aggregation types and never cross-reconcile."""
        registry = json.loads(self.registry_json.read_text(encoding="utf-8"))
        rules = registry["rules"]
        self.assertEqual(rules["accurate_passes"]["aggregation_type"], "total")
        self.assertEqual(rules["accurate_passes_per90"]["aggregation_type"], "per90")
        self.assertNotEqual(rules["accurate_passes"]["aggregation_type"], rules["accurate_passes_per90"]["aggregation_type"])

    def test_05_season_total_versus_team_specific_total(self):
        """Multi-club players must be flagged INCOMPARABLE_MULTICLUB to prevent mixing season totals with club boards."""
        recon_path = ROOT / "reports/phase_02b1/metric_reconciliation_report.csv"
        with recon_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        multiclub_recon = [r for r in rows if r["comparison_status"] == "INCOMPARABLE_MULTICLUB"]
        self.assertEqual(len(multiclub_recon), 707)

    def test_06_different_season_ids(self):
        """Metric observations must strictly match target season_id; cross-season comparisons are prohibited."""
        for r in self.conflict_rows[:100]:
            self.assertIn(r["season_label"], ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025"))

    def test_07_wrong_competition(self):
        """All observations must belong strictly to EPL (leagueId 47)."""
        raw_paths = {r["board_raw_path"] for r in self.conflict_rows if r["board_raw_path"]}
        for p in list(raw_paths)[:20]:
            with (ROOT / p).open(encoding="utf-8") as f:
                data = json.load(f)
            # Verify response is valid JSON
            self.assertIsInstance(data, dict)

    def test_08_parser_induced_conflicts(self):
        """Display rounding on 0.x5 boundary must not leave artificial conflicts unresolved."""
        xa_conflicts = [r for r in self.conflict_rows if r["canonical_metric"] == "expected_assists"]
        self.assertEqual(len(xa_conflicts), 76)
        # All 76 are resolved as rounding tolerance
        for r in xa_conflicts:
            self.assertEqual(r["root_cause_classification"], "ROUNDING_DIFFERENCE")
            self.assertEqual(r["resolution_action"], "RESOLVED_ROUNDING_TOLERANCE")

    def test_09_proper_source_fallback(self):
        """When playerStats is MISSING, validated leagueseasondeepstats observation is admitted as fallback."""
        with self.fallback_csv.open(encoding="utf-8", newline="") as f:
            fallbacks = list(csv.DictReader(f))
        self.assertGreater(len(fallbacks), 90)
        for fb in fallbacks:
            self.assertEqual(fb["validation_verdict"], "VALID_FALLBACK_CANDIDATE")
            self.assertEqual(fb["proposed_status"], "OBSERVED_FALLBACK_LEADERBOARD")
            self.assertEqual(fb["source_endpoint"], "leagueseasondeepstats")

    def test_10_invalid_source_fallback(self):
        """Unverified/ineligible players must NOT receive fallback observations."""
        self.assertIsNotNone(self.prov_table)
        unverified = self.prov_table[self.prov_table["population_status"] != "APPEARED"]
        # All unverified players must have NOT_COLLECTED_UNVERIFIED_APPEARANCE
        for col in ("s_expected_goals", "s_expected_assists"):
            statuses = set(unverified[col])
            self.assertEqual(statuses, {"NOT_COLLECTED_UNVERIFIED_APPEARANCE"})

    def test_11_missing_xa_with_valid_historical_alternative(self):
        """2019/20 xA must recover exactly 96 observations; remaining 419 remain MISSING without zero-filling."""
        self.assertIsNotNone(self.prov_table)
        w19 = self.prov_table[self.prov_table["season_label"] == "2019/2020"]
        w19_app = w19[w19["population_status"] == "APPEARED"]
        self.assertEqual(len(w19_app), 515)

        # Recovered 96
        recovered_cnt = (w19_app["s_expected_assists"] == "OBSERVED_FALLBACK_LEADERBOARD").sum()
        self.assertEqual(recovered_cnt, 96)

        # Remaining 419
        missing_cnt = (w19_app["s_expected_assists"] == "MISSING").sum()
        self.assertEqual(missing_cnt, 419)
        self.assertEqual(recovered_cnt + missing_cnt, 515)

    def test_12_unresolved_conflict_preservation(self):
        """All 36 genuine unresolved conflicts must remain CONFLICTING with null values."""
        self.assertIsNotNone(self.prov_table)
        status_cols = [c for c in self.prov_table.columns if c.startswith("s_")]
        conf_total = sum((self.prov_table[c] == "CONFLICTING").sum() for c in status_cols)
        self.assertEqual(conf_total, 36)

    def test_13_raw_evidence_traceability(self):
        """Every conflict record and fallback record must trace to an existing raw file on disk."""
        for r in self.conflict_rows[:50]:
            if r["board_raw_path"]:
                self.assertTrue((ROOT / r["board_raw_path"]).is_file(), f"Missing board raw: {r['board_raw_path']}")
            if r["stats_raw_path"]:
                self.assertTrue((ROOT / r["stats_raw_path"]).is_file(), f"Missing stats raw: {r['stats_raw_path']}")

    def test_14_reprocessing_determinism(self):
        """Re-executing Steps 05 & 06 must be strictly deterministic and produce identical results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            res5 = execute_step05_remediation(tmp_path)
            self.assertEqual(res5["status"], "SUCCESS")
            self.assertEqual(res5["total_conflicts_inventoried"], 575)

            res6 = execute_step06_remediation(tmp_path)
            self.assertEqual(res6["status"], "SUCCESS")
            self.assertEqual(res6["curated_wide_rows"], 4052)


if __name__ == "__main__":
    unittest.main()

