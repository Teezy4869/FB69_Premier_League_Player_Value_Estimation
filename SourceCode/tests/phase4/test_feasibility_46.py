"""Phase 4.6 feature assessment and feasibility tests. Read-only."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.phase4 import feasibility as fz  # noqa: E402
from src.phase4 import profiling as p  # noqa: E402
from src.phase4 import univariate as u  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_06/evidence"


class FeasibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.dictionary, cls.eligibility, cls.reliability = p.load_metadata()
        cls.register = u.feature_register(cls.eligibility, cls.reliability)
        cls.fa = fz.feature_assessment(cls.df, cls.register, fz.load_evidence()).set_index("feature")

    def test_every_feature_assessed_on_every_dimension(self):
        self.assertEqual(list(self.fa.index), u.FEATURES)
        dims = ["coverage", "reliability_class", "temporal", "position_relevance", "tail", "redundancy",
                "interpretability_judgment", "association", "beyond_playing_time", "identity_sensitivity",
                "usefulness_judgment", "phase5_recommendation"]
        self.assertFalse(self.fa[dims].isna().any().any())

    def test_owner_decisions_stay_pending_and_exclusions_respected(self):
        self.assertTrue(self.fa.loc[u.RD04, "phase5_recommendation"].eq("conditional: owner decision (RD-04)").all())
        for col in ("m_key_passes", "nationality_profile_present_day", "s_key_passes", "multi_club_class", u.TARGET):
            self.assertNotIn(col, self.fa.index)
        cond = self.fa[self.fa["eligibility_category"].eq("CONDITIONAL_PREDICTOR")]
        self.assertTrue(cond["phase5_recommendation"].str.startswith("conditional").all())
        review = fz.eligibility_review(self.eligibility, self.fa.reset_index())
        self.assertEqual(int(review["columns"].sum()), 175)
        self.assertEqual(review.at["CANDIDATE_PREDICTOR", "columns"], 41)
        self.assertEqual(review.at["EXCLUDED_PREDICTOR", "columns"], 3)

    def test_eligibility_file_unchanged(self):
        # Rebuild the register with its Phase 4.0 script and compare byte for byte (corrected in Phase 4.7:
        # the first version compared the file with itself).
        from src.phase4 import synthesis
        rebuilt = synthesis.eligibility_rebuild()
        self.assertTrue(rebuilt["identical"], rebuilt)
        self.assertEqual(rebuilt["category_counts"]["CANDIDATE_PREDICTOR"], 41)

    def test_split_feasibility_is_analytic_only(self):
        leak = fz.random_split_leakage(self.df)
        self.assertGreater(leak["expected_test_rows_with_player_in_train_pct"], 70)
        th = fz.temporal_holdout(self.df, self.scope)
        self.assertEqual(th["test_season"].tolist(), list(self.scope.labels)[1:])
        self.assertTrue((th["train_rows"] + th["test_rows"]).le(int(self.df["target_usable"].sum())).all())
        structure = fz.player_structure(self.df)
        self.assertEqual(int(structure["rows"].sum()), int(self.df["target_usable"].sum()))

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "feasibility_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["sha256_verified"])
        self.assertTrue(summary["no_model_trained"] and summary["no_feature_engineered"] and summary["no_split_executed"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)
        recorded = pd.read_csv(EVIDENCE / "feature_assessment_matrix.csv").set_index("feature")
        self.assertTrue((recorded["phase5_recommendation"] == self.fa["phase5_recommendation"]).all())

    def test_dataset_unchanged(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
