import unittest
from pathlib import Path

import pandas as pd

from src.audit.final_review import (AuditEvidenceError, classify_feature,
                                    read_evidence, validate_final_outputs,
                                    validate_prior_outputs)


ROOT = Path(__file__).resolve().parents[2]


class FinalReviewTests(unittest.TestCase):
    def test_saved_season_and_metric_evidence(self):
        validated = validate_prior_outputs(ROOT)
        self.assertTrue(validated["catalog_stable"])
        self.assertEqual(validated["goal_agreements"], 6)
        self.assertEqual(len(validated["retained_board_rows"]), 90)

    def test_classification_requires_direct_or_scoped_evidence(self):
        direct = pd.DataFrame({"status": ["AVAILABLE"] * 6})
        partial = pd.DataFrame({"status": ["PARTIAL"] * 6})
        unknown = pd.DataFrame({"status": ["UNVERIFIED"] * 6})
        self.assertEqual(classify_feature("Goals", direct, True)[0], "CORE")
        self.assertEqual(classify_feature("Goals", direct, False)[0], "UNVERIFIED")
        self.assertEqual(classify_feature("Assists", partial, True)[0], "OPTIONAL")
        self.assertEqual(classify_feature("Saves", direct, True)[0], "POSITION_SPECIFIC")
        self.assertEqual(classify_feature("Long passes", partial, True)[0], "EXCLUDED_FOR_NOW")
        self.assertEqual(classify_feature("Key passes", unknown, True)[0], "UNVERIFIED")

    def test_abandoned_and_replayed_fixture_are_distinct(self):
        data = read_evidence(ROOT, "data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json")
        self.assertEqual(data["record_count"], 381)
        self.assertEqual(data["ordered_pair_count"], 380)
        matches = data["duplicate_ordered_pair_entries"]
        self.assertEqual({str(x["id"]) for x in matches}, {"4193691", "4421797"})
        self.assertEqual(sum(bool(x["status"].get("cancelled")) for x in matches), 1)

    def test_saves_unit_label_is_explicit(self):
        data = read_evidence(ROOT, "data/audit/raw_samples/final_review/saves_2019_2020_units.json")
        self.assertEqual(data["payload"]["substatTitle"], "Total saves")
        self.assertEqual(data["payload"]["statsData_first"]["statValue"]["value"], 4)
        self.assertEqual(data["payload"]["statsData_first"]["substatValue"]["value"], 81)

    def test_missing_or_escaping_evidence_is_rejected(self):
        with self.assertRaises(AuditEvidenceError):
            read_evidence(ROOT, "data/audit/raw_samples/does_not_exist.json")
        with self.assertRaises(AuditEvidenceError):
            read_evidence(ROOT, "../outside.json")

    def test_final_report_links_and_sections(self):
        validate_final_outputs(ROOT)


if __name__ == "__main__":
    unittest.main()
