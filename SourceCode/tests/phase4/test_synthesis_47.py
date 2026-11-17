"""Phase 4.7 final-acceptance tests: cross-phase consistency, integrity and notebook state. Read-only."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.phase4 import profiling as p  # noqa: E402
from src.phase4 import synthesis as syn  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_07/evidence"


class SynthesisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()

    def test_cross_phase_statistics_consistent(self):
        checks = syn.consistency_checks(self.df)
        self.assertTrue(checks["consistent"].all(), checks.loc[~checks["consistent"], "check"].tolist())

    def test_integrity(self):
        self.assertTrue(syn.scope_scan().empty)
        self.assertTrue(syn.predictor_integrity()["ok"].all())
        self.assertTrue(syn.eligibility_rebuild()["identical"])
        self.assertEqual(int(self.df["season"].isin(self.scope.excluded_labels).sum()), 0)

    def test_notebook_executed_cleanly(self):
        sections, summary = syn.notebook_audit()
        self.assertTrue(summary["executed_in_order"])
        self.assertEqual(summary["error_outputs"], [])
        self.assertEqual(summary["large_text_outputs"], [])
        self.assertEqual(sorted(sections["section"]), ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"])
        self.assertTrue(sections["markdown_before_first_code"].all())

    def test_recorded_evidence(self):
        summary = json.loads((EVIDENCE / "synthesis_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["consistency_all"] and summary["predictor_integrity_ok"])
        self.assertTrue(summary["eligibility_rebuild"]["identical"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
