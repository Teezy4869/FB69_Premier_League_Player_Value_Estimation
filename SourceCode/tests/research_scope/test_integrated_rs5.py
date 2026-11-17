"""G3: the rs5 integrated dataset passes every integration check and keeps the approved business rules."""
from __future__ import annotations

import json
import unittest

from src.phase3.tm_common import file_hash
from src.research_scope.integrate_rs5 import DROPPED_V1_COLUMNS, RELEASE
from src.research_scope.validate_rs5 import connect, integration_checks, integration_statistics


class IntegratedRs5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = connect()
        cls.checks = integration_checks(cls.con)
        cls.stats = integration_statistics(cls.con)
        cls.manifest = json.loads((RELEASE / "integration_manifest.json").read_text(encoding="utf-8"))

    def test_all_integration_checks_pass(self):
        self.assertEqual([c["check"] for c in self.checks if c["status"] != "PASS"], [])
        self.assertGreaterEqual(len(self.checks), 27)

    def test_counts(self):
        s = self.stats
        self.assertEqual((s["rows"], s["unique_players"], s["usable_targets"], s["missing_targets"], s["unmapped_rows"], s["duplicate_player_season_rows"]), (2747, 1228, 2697, 50, 2, 0))
        self.assertEqual(s["rows_by_season"], {"2020/2021": 524, "2021/2022": 537, "2022/2023": 554, "2023/2024": 570, "2024/2025": 562})

    def test_every_join_kept_row_count(self):
        self.assertTrue(all(j["rows_before"] == j["rows_after"] == 2747 for j in self.manifest["joins"]))
        self.assertTrue(all(j["right_rows"] == j["right_unique_keys"] for j in self.manifest["joins"]))

    def test_dropped_columns_are_absent(self):
        cols = {r[0] for r in self.con.execute("DESCRIBE d").fetchall()}
        self.assertFalse(set(DROPPED_V1_COLUMNS) & cols)

    def test_outputs_match_manifest(self):
        for name, sha in self.manifest["output_sha256"].items():
            self.assertEqual(file_hash(RELEASE / name), sha, name)

    def test_nothing_imputed_or_zero_filled(self):
        self.assertEqual(self.con.execute("SELECT count(*) FROM d WHERE NOT target_usable AND target_market_value IS NOT NULL").fetchone()[0], 0)
        self.assertGreater(self.stats["null_metric_cells"], 0)


if __name__ == "__main__":
    unittest.main()
