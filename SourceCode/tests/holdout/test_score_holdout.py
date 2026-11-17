"""Scoring logic on SYNTHETIC data only. Never reads the holdout input or runs main()."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src.holdout import score_holdout as sh  # noqa: E402


class DecisionRule(unittest.TestCase):
    def test_three_level(self):
        self.assertEqual(sh.three_level(0.01, 0.2, 0.0, False), "PASS")
        self.assertEqual(sh.three_level(0.0, 0.2, 0.0, False), "INCONCLUSIVE")  # primary needs lower > 0
        self.assertEqual(sh.three_level(-0.3, -0.01, 0.0, False), "FAIL")
        self.assertEqual(sh.three_level(0.60, 0.7, 0.60, True), "PASS")       # secondary: lower >= 0.60
        self.assertEqual(sh.three_level(0.55, 0.65, 0.60, True), "INCONCLUSIVE")


class Statistics(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.y = rng.normal(15, 1, 300)
        self.g = np.array([f"p{i}" for i in range(300)])

    def test_better_model_passes(self):
        r = sh.paired_delta(self.y, self.y + 0.05, self.y + 0.5, self.g)
        self.assertAlmostEqual(r["delta_mae"], 0.45)
        self.assertEqual(r["verdict"], "PASS")

    def test_equally_good_predictions_inconclusive(self):
        rng = np.random.default_rng(2)
        noise = rng.normal(0, 0.3, 300)
        r = sh.paired_delta(self.y, self.y + noise, self.y - noise, self.g)  # same |error| per player
        self.assertLess(abs(r["delta_mae"]), 1e-12)
        self.assertEqual(r["verdict"], "INCONCLUSIVE")

    def test_noisy_tie_inconclusive(self):
        rng = np.random.default_rng(3)
        r = sh.paired_delta(self.y, self.y + rng.normal(0, 0.3, 300), self.y + rng.normal(0, 0.3, 300), self.g)
        self.assertEqual(r["verdict"], "INCONCLUSIVE")

    def test_band_counts_ratio(self):
        pred = self.y.copy()
        pred[:150] += np.log(1.5)  # half the rows 50% too high
        r = sh.within_band(self.y, pred, self.g)
        self.assertAlmostEqual(r["share_within_20pct"], 0.5)
        self.assertEqual(r["verdict"], "FAIL")

    def test_main_refuses_without_flag(self):
        argv, sys.argv = sys.argv, ["score_holdout.py"]
        try:
            with self.assertRaises(SystemExit):
                sh.main()
        finally:
            sys.argv = argv
        self.assertFalse(sh.LOCK.exists())


if __name__ == "__main__":
    unittest.main()
