"""Phase 4.3 bivariate tests. Read-only: they load the official release and the recorded evidence."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase4 import bivariate as b  # noqa: E402
from src.phase4 import profiling as p  # noqa: E402
from src.phase4 import univariate as u  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_03/evidence"
NEVER_ANALYSED = ("target_", "temporal_", "s_", "identity_", "crosswalk_")


class BivariateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.original = cls.df.copy(deep=True)
        cls.dictionary, cls.eligibility, cls.reliability = p.load_metadata()
        cls.register = u.feature_register(cls.eligibility, cls.reliability)
        boot = pd.read_csv(EVIDENCE / "feature_target_association.csv").set_index("feature")[
            ["spearman_ci_low", "spearman_ci_high"]]
        cls.assoc = b.feature_target_association(cls.df, cls.register, boot).set_index("feature")

    def test_only_eligible_features_analysed(self):
        self.assertEqual(list(self.assoc.index), u.FEATURES)
        roles = self.dictionary.set_index("column").loc[u.FEATURES, "role"]
        self.assertNotIn("CLUB_CONTEXT", set(roles))
        for f in u.FEATURES:
            self.assertFalse(f.startswith(NEVER_ANALYSED), f)
        for col in ("nationality_profile_present_day", "m_key_passes", "canonical_player_id", "season", "season_id",
                    "multi_club_class", "is_multi_club", u.TARGET):
            self.assertNotIn(col, u.FEATURES)
            self.assertNotIn(col, b.OUTFIELD_FEATURES)
        rd04 = self.assoc.loc[u.RD04, "flags"]
        self.assertTrue(rd04.str.contains("RD-04 pending").all())

    def test_correlations_match_reference_and_use_pairwise_complete_rows(self):
        for f in ("m_goals", "age_at_season_end_years", "m_saves", "m_clearances"):
            app = u.applicable_rows(self.df, f, self.register) & self.df["target_usable"]
            sub = self.df.loc[app, [f, u.TARGET]].dropna()
            self.assertEqual(self.assoc.at[f, "n_pairs"], len(sub), f)
            self.assertAlmostEqual(self.assoc.at[f, "spearman"], sub.corr(method="spearman").iat[0, 1], places=10)
            self.assertAlmostEqual(self.assoc.at[f, "pearson_raw"], sub.corr().iat[0, 1], places=10)
            self.assertEqual(self.assoc.at[f, "null_rows_with_target"], int(self.df.loc[app, f].isna().sum()))
        pd.testing.assert_frame_equal(self.df, self.original)  # nothing filled, dropped or transformed

    def test_goalkeeper_metrics_only_on_goalkeeper_rows(self):
        for f in u.FEATURE_GROUPS["8 Goalkeeping"]:
            self.assertLessEqual(self.assoc.at[f, "n_pairs"], 206)
            self.assertNotIn(f, b.OUTFIELD_FEATURES)

    def test_identity_rows_kept_in_main_analysis(self):
        self.assertEqual(int(b.identity_sensitivity_mask(self.df).sum()), 533)
        self.assertEqual(self.assoc.at["age_at_season_end_years", "n_pairs"], 2697)
        sens = b.identity_sensitivity(self.df, self.register).set_index("feature")
        self.assertEqual(sens.at["age_at_season_end_years", "n_all"] - sens.at["age_at_season_end_years", "n_without_p4b01"],
                         int((b.identity_sensitivity_mask(self.df) & self.df["target_usable"]).sum()))

    def test_correlation_matrix_well_formed(self):
        rows = self.df[u.POSITION].isin(b.OUTFIELD)
        corr, n = b.correlation_matrix(self.df, b.OUTFIELD_FEATURES, rows)
        self.assertEqual(list(corr.columns), b.OUTFIELD_FEATURES)
        self.assertTrue(np.allclose(corr.to_numpy(), corr.to_numpy().T, equal_nan=True))
        self.assertTrue(np.allclose(np.diag(corr), 1.0))
        self.assertTrue(corr.to_numpy()[n.to_numpy() < b.MIN_N].size == 0 or np.isnan(corr.to_numpy()[n.to_numpy() < b.MIN_N]).all())
        recorded = pd.read_csv(EVIDENCE / "correlation_matrix_spearman_outfield.csv", index_col=0)
        self.assertTrue(np.allclose(recorded.to_numpy(), corr.to_numpy(), atol=1e-5, equal_nan=True))

    def test_redundancy_clusters_describe_without_removing(self):
        clusters = pd.read_csv(EVIDENCE / "redundancy_clusters_outfield.csv")
        corr = pd.read_csv(EVIDENCE / "correlation_matrix_spearman_outfield.csv", index_col=0)
        self.assertEqual(list(corr.columns), b.OUTFIELD_FEATURES)  # every feature still present
        for members in clusters["members"].str.split(", "):
            for m in members:
                linked = corr.loc[m, [x for x in members if x != m]].abs().max()
                self.assertGreaterEqual(linked, b.REDUNDANT - 1e-6, m)

    def test_statistics_helpers(self):
        h = b.epsilon_squared(pd.Series([1.0, 2, 3, 4]), pd.Series(list("aabb")))
        self.assertAlmostEqual(h["kruskal_h"], 2.4)
        self.assertAlmostEqual(h["epsilon_squared"], 0.8)
        self.assertAlmostEqual(b.partial(0.5, 0.0, 0.0), 0.5)
        self.assertTrue(np.isnan(b.partial(0.5, 1.0, 0.5)))
        self.assertTrue(np.isnan(b.spearman(np.ones(10), np.arange(10.0))))

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "bivariate_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["sha256_verified"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)
        self.assertEqual(summary["identity_sensitivity_rows"], 533)
        recorded = pd.read_csv(EVIDENCE / "feature_target_association.csv").set_index("feature")
        for col in ("n_pairs", "null_rows_with_target"):
            self.assertTrue((recorded[col] == self.assoc[col]).all(), col)
        for col in ("spearman", "pearson_raw", "pearson_log10", "partial_spearman_given_minutes"):
            self.assertTrue(np.allclose(recorded[col], self.assoc[col], atol=1e-5, equal_nan=True), col)
        ci = recorded[["spearman_ci_low", "spearman", "spearman_ci_high"]].dropna()
        self.assertTrue(((ci["spearman_ci_low"] <= ci["spearman"]) & (ci["spearman"] <= ci["spearman_ci_high"])).all())
        seasons = pd.read_csv(EVIDENCE / "target_by_season_43.csv")["season"].tolist()
        self.assertEqual(seasons, list(self.scope.labels))

    def test_dataset_unchanged_after_analysis(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
