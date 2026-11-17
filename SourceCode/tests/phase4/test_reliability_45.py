"""Phase 4.5 missingness, temporal and reliability tests. Read-only: official release and recorded evidence."""
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.phase4 import profiling as p  # noqa: E402
from src.phase4 import reliability as r  # noqa: E402

EVIDENCE = ROOT / "reports/phase_04/step_05/evidence"


class ReliabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.schema, cls.scope, cls.verification = p.load_verified()
        cls.original = cls.df.copy(deep=True)

    def test_status_semantics_preserved(self):
        sem = r.status_semantics(self.df).set_index("status")
        self.assertEqual(list(sem.index), r.STATUS_ORDER)  # eight statuses, none collapsed
        for st in ("MISSING", "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING"):
            self.assertEqual(sem.at[st, "stored_null"], sem.at[st, "cells"], st)  # unavailable -> null, never zero
        self.assertEqual(sem.at["OBSERVED_ZERO", "stored_zero"], sem.at["OBSERVED_ZERO", "cells"])
        self.assertEqual(int(sem["cells"].sum()), len(self.df) * len(r.status_cols(self.df)))

    def test_temporal_reference_values_recomputed(self):
        ref = r.temporal_reference(self.df)
        self.assertTrue(ref["matches_reference"].all(), ref)

    def test_identity_subset_kept_and_compared(self):
        comp = r.identity_comparison(self.df)
        self.assertEqual(comp.loc["P4-B01 subset", "rows"] + comp.loc["main without P4-B01 (sensitivity only)", "rows"],
                         comp.loc["main dataset", "rows"])
        self.assertEqual(comp.loc["main dataset", "rows"], len(self.df))
        self.assertEqual(comp.loc["P4-B01 subset", "rows"], 533)
        pd.testing.assert_frame_equal(self.df, self.original)

    def test_goalkeeper_checks(self):
        gk = r.goalkeeper_reliability(self.df, self.scope)
        checks = gk["gk_consistency_checks"].set_index("check")
        self.assertTrue((checks["agree_within_0_1pp"] == checks["rows_compared"]).all())
        self.assertEqual(int(gk["gk_coverage_by_season"]["gk_rows"].sum()), 206)

    def test_rd04_not_resolved_and_matches_window_audit(self):
        rd = r.rd04_assessment(self.df, self.scope)
        self.assertEqual(set(rd["metric"]), set(r.RD04))
        clear = rd[rd["metric"] == "m_clearances"].set_index("season")["values"]
        self.assertEqual(clear.tolist(), [0, 33, 0, 51, 447])
        rmap = r.reliability_map(self.df, *self._map_inputs())
        self.assertTrue(rmap.set_index("feature").loc[r.RD04, "reliability_class"].eq("pending owner decision (RD-04)").all())

    def _map_inputs(self):
        _, eligibility, reliability = p.load_metadata()
        from src.phase4 import univariate as u
        register = u.feature_register(eligibility, reliability)
        fm = r.feature_missingness(self.df, reliability, self.scope)
        window = pd.read_csv(r.WINDOW_AUDIT).rename(columns=lambda c: c.lstrip("﻿"))
        return register, fm, window

    def test_recorded_evidence_equals_recomputation(self):
        summary = json.loads((EVIDENCE / "reliability_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["sha256_verified"])
        self.assertTrue(summary["temporal_reference_all_match"])
        self.assertEqual(summary["dataset_sha256_after"], p.DATASET_SHA256)
        recorded = pd.read_csv(EVIDENCE / "status_matrix_all_rows.csv", index_col=0)
        pd.testing.assert_frame_equal(recorded, r.status_matrix(self.df), check_names=False)
        seasons = pd.read_csv(EVIDENCE / "temporal_by_season.csv")["season"].tolist()
        self.assertEqual(seasons, list(self.scope.labels))

    def test_dataset_unchanged_after_analysis(self):
        self.assertEqual(p.sha256_file(p.DATASET), p.DATASET_SHA256)


if __name__ == "__main__":
    unittest.main()
