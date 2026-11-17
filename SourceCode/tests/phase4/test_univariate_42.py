"""Phase 4.2 target and univariate tests. Read-only: they load the official release and the recorded evidence."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase4 import profiling as p  # noqa: E402
from src.phase4 import univariate as u  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_02/evidence"
NEVER_ANALYSED = ("target_", "temporal_", "s_")


class UnivariateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.original = cls.df.copy(deep=True)
        cls.dictionary, cls.eligibility, cls.reliability = p.load_metadata()
        cls.register = u.feature_register(cls.eligibility, cls.reliability)
        cls.summary = u.feature_summary(cls.df, cls.register)

    def test_feature_set_follows_eligibility_register(self):
        metrics = set(p.metric_columns(self.df)) - {"m_key_passes"}
        self.assertEqual(len(u.FEATURES), len(set(u.FEATURES)))
        self.assertEqual(set(u.FEATURES), metrics | {"age_at_season_end_years"})
        self.assertTrue(set(self.register["eligibility_category"]) <= u.PREDICTOR_CATEGORIES)
        roles = self.dictionary.set_index("column").loc[u.FEATURES, "role"]
        self.assertNotIn("CLUB_CONTEXT", set(roles))

    def test_excluded_columns_never_analysed(self):
        for f in u.FEATURES:
            self.assertFalse(f.startswith(NEVER_ANALYSED), f)
        for col in ("nationality_profile_present_day", "m_key_passes", "s_key_passes", "canonical_player_id",
                    "fotmob_player_name", "season", "season_id", u.TARGET):
            self.assertNotIn(col, u.FEATURES)
        excluded = u.excluded_from_analysis(self.df, self.eligibility)
        self.assertEqual(len(excluded) + len(u.FEATURES), self.df.shape[1])

    def test_rd04_flagged_not_resolved(self):
        flagged = set(self.register.loc[self.register["pending_owner_decision"] == "RD-04", "feature"])
        self.assertEqual(flagged, set(u.RD04))
        self.assertTrue((self.register.set_index("feature").loc[u.RD04, "eligibility_category"] == "CONDITIONAL_PREDICTOR").all())

    def test_target_statistics_on_raw_values(self):
        t = self.df.loc[self.df["target_usable"], u.TARGET].astype(float)
        s = u.target_summary(self.df)["raw_eur"]
        self.assertEqual(s["n"], 2697)
        self.assertEqual((s["p50"], s["min"], s["max"]), (13_000_000, 100_000, 200_000_000))
        self.assertAlmostEqual(s["mean"], t.mean())
        self.assertAlmostEqual(s["skew"], t.skew())
        self.assertGreater(s["skew"], 1)
        self.assertEqual(s["upper_3iqr"], int((t > t.quantile(.75) + 3 * (t.quantile(.75) - t.quantile(.25))).sum()))

    def test_stored_data_unchanged_and_tails_kept(self):
        u.target_summary(self.df), u.target_tail(self.df), u.zero_recording(self.df, self.register)
        pd.testing.assert_frame_equal(self.df, self.original)
        s = self.summary.set_index("feature")
        for f in u.FEATURES:
            app = u.applicable_rows(self.df, f, self.register)
            self.assertEqual(s.at[f, "n"] + s.at[f, "null_applicable"], app.sum(), f)
            self.assertEqual(s.at[f, "max"], self.df.loc[app, f].max(), f)

    def test_goalkeeper_metrics_on_goalkeeper_rows(self):
        s = self.summary.set_index("feature")
        for f in u.FEATURE_GROUPS["8 Goalkeeping"]:
            self.assertEqual(s.at[f, "applicable_rows"], 206)
            self.assertEqual(s.at[f, "values_on_non_applicable_rows"], 0)

    def test_per90_bands_cover_rows_with_minutes(self):
        bands = u.per90_by_minutes(self.df)
        for f in u.per90_columns():
            expected = self.df[[f, "m_minutes_played"]].dropna().shape[0]
            self.assertEqual(bands.loc[bands["feature"] == f, "n"].sum(), expected, f)
        self.assertEqual(u.per90_tail_share(self.df).set_index("feature").at["m_tackles_per90", "rows_under_90_minutes_with_value"], 31)

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "univariate_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["sha256_verified"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)
        self.assertEqual(summary["target"]["p50"], 13_000_000)
        recorded = pd.read_csv(EVIDENCE / "feature_summary.csv").set_index("feature")
        fresh = self.summary.set_index("feature")
        for col in ("n", "null_applicable", "upper_3iqr"):
            self.assertTrue((recorded[col] == fresh[col]).all(), col)
        self.assertTrue(np.allclose(recorded["p50"], fresh["p50"], rtol=1e-5, equal_nan=True))
        seasons = pd.read_csv(EVIDENCE / "target_by_season.csv")["season"].tolist()
        self.assertEqual(seasons, list(self.scope.labels))

    def test_dataset_unchanged_after_analysis(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
