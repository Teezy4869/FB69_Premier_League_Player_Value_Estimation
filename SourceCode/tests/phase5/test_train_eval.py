"""Phase 5 step 03: metric definitions (synthetic) and invariants on the run outputs."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase5 import train_eval as te  # noqa: E402


class MetricTest(unittest.TestCase):
    def test_known_values(self):
        y = np.log(np.array([100.0, 100.0]))
        p = np.log(np.array([200.0, 50.0]))  # x2 over, x2 under
        m = te.metrics(y, p)
        self.assertAlmostEqual(m["mae_log"], np.log(2))
        self.assertAlmostEqual(m["rmse_log"], np.log(2))
        self.assertAlmostEqual(m["mdape_eur"], 75.0)  # |+100%|, |-50%| -> median 75%

    def test_perfect(self):
        y = np.log(np.array([1e6, 5e6]))
        self.assertEqual(te.metrics(y, y)["mae_log"], 0.0)


class RunOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (te.OUTPUT / "metrics.json").exists():
            raise unittest.SkipTest("run not built")
        cls.oof = pd.read_parquet(te.OUTPUT / "oof_predictions_primary.parquet")
        cls.fwd = pd.read_parquet(te.OUTPUT / "predictions_forward.parquet")
        cls.m = json.loads((te.OUTPUT / "metrics.json").read_text(encoding="utf-8"))

    def test_each_row_predicted_once_per_repeat(self):
        counts = self.oof.groupby(["repeat", "canonical_player_id", "season"]).size()
        self.assertEqual(counts.max(), 1)
        self.assertEqual(self.oof.groupby("repeat").size().unique().tolist(), [2491])

    def test_player_never_in_two_folds_of_a_repeat(self):
        self.assertEqual(self.oof.groupby(["repeat", "canonical_player_id"])["fold"].nunique().max(), 1)

    def test_forward_covers_test_seasons_only(self):
        self.assertNotIn("2020/2021", set(self.fwd["season"]))
        self.assertTrue((self.fwd["season"] == self.fwd["fold"]).all())

    def test_sensitivity_population(self):
        self.assertEqual(self.m["sensitivity_without_identity_rows"]["overall"]["n"], 2491 - 454)


if __name__ == "__main__":
    unittest.main()
