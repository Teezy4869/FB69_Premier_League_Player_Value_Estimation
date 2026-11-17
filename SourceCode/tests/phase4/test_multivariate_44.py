"""Phase 4.4 multivariate and group tests. Read-only: they load the official release and the recorded evidence."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase4 import multivariate as mv  # noqa: E402
from src.phase4 import profiling as p  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_04/evidence"


class MultivariateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.original = cls.df.copy(deep=True)
        cls.g = mv.groups(cls.df)

    def test_groups_cover_every_row_without_filling(self):
        self.assertEqual(len(self.g), len(self.df))
        self.assertEqual(int(self.g["starts_group"].eq("starts missing").sum()), int(self.df["m_starts"].isna().sum()))
        self.assertEqual(int(self.g["minutes_band"].eq("minutes missing").sum()), int(self.df["m_minutes_played"].isna().sum()))
        zero = self.df["m_starts"].eq(0)
        self.assertTrue(self.g.loc[zero, "starts_group"].eq("0 starts").all())
        self.assertTrue(self.g.loc[self.df["m_starts"].between(19, 28), "starts_group"].eq("19-28 starts").all())
        self.assertEqual(int(self.g["p4b01"].sum()), 533)
        pd.testing.assert_frame_equal(self.df, self.original)

    def test_profiles_reconcile_with_dataset(self):
        prof_pos = mv.profile(self.df, mv.POSITION)
        self.assertEqual(int(prof_pos["rows"].sum()), len(self.df))
        self.assertEqual(int(prof_pos["usable_targets"].sum()), int(self.df["target_usable"].sum()))
        self.assertEqual(prof_pos.at["GK", "target_median_eur"], 6_000_000)
        bounds = mv.group_boundaries(self.df)
        for grouping, b in bounds.groupby("grouping"):
            self.assertEqual(int(b["total"].sum()), len(self.df), grouping)

    def test_small_cells_left_empty(self):
        med, n = mv.median_grid(self.df, mv.POSITION, "starts_group", mv.POSITION_ORDER, mv.STARTS_LABELS)
        self.assertTrue(med[n < mv.MIN_N].isna().all().all())
        self.assertTrue(med[n >= mv.MIN_N].notna().sum().sum() == (n >= mv.MIN_N).sum().sum())

    def test_goalkeeper_metrics_described_on_goalkeeper_rows_only(self):
        gk = pd.read_csv(EVIDENCE / "position_goalkeeper_metrics.csv")
        self.assertEqual(int(gk.groupby("metric")["rows"].sum().iloc[0]), 206)
        out = pd.read_csv(EVIDENCE / "position_outfield_metrics.csv")
        self.assertNotIn("GK", set(out[mv.POSITION]))
        self.assertFalse(set(out["metric"]) & (set(mv.GK_METRICS) - {"m_rating"}))

    def test_season_tables_follow_scope(self):
        pop = pd.read_csv(EVIDENCE / "season_population.csv")
        self.assertEqual(pop["season"].tolist(), list(self.scope.labels))
        self.assertEqual(int(pop["rows"].sum()), len(self.df))
        timing = pd.read_csv(EVIDENCE / "season_timing.csv")
        self.assertEqual(int(timing["usable_targets"].sum()), int(self.df["target_usable"].sum()))

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "multivariate_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["sha256_verified"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)
        recorded = pd.read_csv(EVIDENCE / "season_stratified_medians_two_roles.csv")
        fresh = mv.season_stratified_medians(self.df, self.scope, coarse=True)
        self.assertTrue(np.allclose(recorded["last_to_first_ratio"], fresh["last_to_first_ratio"], equal_nan=True))

    def test_dataset_unchanged_after_analysis(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
