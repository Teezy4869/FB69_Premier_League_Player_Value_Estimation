"""Phase 5 step 02: model input table and config. Synthetic per-90 tests plus invariants on the built output."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase4 import profiling  # noqa: E402
from src.phase5 import features as fx  # noqa: E402


class Per90Test(unittest.TestCase):
    def test_zero_or_null_minutes_give_null_never_zero(self):
        r = fx.per90(pd.Series([10, 10, None, 0]), pd.Series([900, 0, 900, None]))
        self.assertEqual(r.iloc[0], 1.0)
        self.assertTrue(r.iloc[1:].isna().all())

    def test_matches_source_per90_convention(self):
        df = profiling.load_verified()[0]
        d = (fx.per90(df["m_accurate_passes"], df["m_minutes_played"]) - df["m_accurate_passes_per90"]).abs().dropna()
        self.assertGreater(len(d), 2000)
        self.assertLess(d.max(), 1e-6)


class ConfigTest(unittest.TestCase):
    def test_baseline_has_19_features_and_no_excluded_groups(self):
        cfg = fx.load_config()
        feats = fx.feature_columns(cfg)
        self.assertEqual(len(feats), 19)
        for banned in ("m_tackles", "m_recoveries", "m_duels_won", "m_yellow_cards", "m_clearances", "season", "m_shots", "m_expected_goals", "m_chances_created"):
            self.assertNotIn(banned, feats)
        self.assertNotIn("GK", cfg["population"]["positions"])


class OutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = fx.OUTPUT / "model_input.parquet"
        if not path.exists():
            raise unittest.SkipTest("output not built")
        cls.cfg = fx.load_config()
        cls.out = pd.read_parquet(path)

    def test_population_counts(self):
        self.assertEqual(len(self.out), 2491)
        self.assertEqual(self.out["canonical_player_id"].nunique(), 1101)
        self.assertEqual(int((~self.out["has_prev_value"]).sum()), 107)
        self.assertEqual(int(self.out["target_before_season_start"].sum()), 15)

    def test_invariants(self):
        fx.check(self.out, self.cfg)

    def test_log_target_matches_target(self):
        np.testing.assert_allclose(np.exp(self.out["log_target"]), self.out["target_market_value"], rtol=1e-9)


if __name__ == "__main__":
    unittest.main()
