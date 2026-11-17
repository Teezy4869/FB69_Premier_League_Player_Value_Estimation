"""Holdout FotMob rebuild: the same code must reproduce release v3.1 for 2024/25 exactly."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.holdout import fotmob_tables as ft  # noqa: E402


class ReproduceRelease(unittest.TestCase):
    def test_2024_25_rebuild_matches_release_v3_1(self):
        r = ft.validate_2024_25()
        self.assertEqual(r["population_rebuilt"], r["population_release"])
        self.assertEqual(r["population_symmetric_difference"], 0)
        self.assertEqual(r["appearance_count_mismatch"], 0)
        self.assertEqual(r["position_mismatch"], 0)
        self.assertEqual(r["metric_cell_mismatch"], {})
        self.assertGreater(r["metric_cells_compared"], 29000)

    def test_position_map_is_a_function(self):
        m = ft.position_map()
        self.assertEqual(m[("usualPlayingPositionId", "1")], "DEF")


if __name__ == "__main__":
    unittest.main()
