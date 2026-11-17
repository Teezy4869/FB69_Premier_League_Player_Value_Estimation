"""Phase 5 step 01: season-start previous value. Synthetic rule tests plus invariants on the built output."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pyarrow.parquet as pq  # noqa: E402

from src.phase5 import season_start_prev_value as sp  # noqa: E402

START = date(2023, 8, 11)


def obs(day, value, status="VALID", rid=None):
    """Synthetic valuation observation (test fixture, not research data)."""
    return {"valuation_date": day, "market_value": value, "quality_status": status, "source_record_id": rid or f"syn:{day}:{value}"}


class RuleTest(unittest.TestCase):
    def test_valuation_on_first_match_day_is_not_eligible(self):
        d = sp.decide([obs(date(2023, 6, 1), 5), obs(START, 9)], START)
        self.assertEqual((d["prev_valuation_date"], d["prev_market_value"], d["prev_age_days_at_first_match"]), (date(2023, 6, 1), 5, 71))

    def test_only_later_valuations_is_missing_not_imputed(self):
        d = sp.decide([obs(date(2023, 12, 1), 5)], START)
        self.assertEqual((d["prev_status"], d["prev_market_value"]), ("TARGET_MISSING", None))

    def test_same_date_conflict_is_flagged(self):
        d = sp.decide([obs(date(2023, 6, 1), 5, rid="a"), obs(date(2023, 6, 1), 7, rid="b")], START)
        self.assertEqual((d["prev_status"], d["prev_market_value"]), ("AMBIGUOUS_VALUATION", None))

    def test_invalid_status_skipped(self):
        d = sp.decide([obs(date(2023, 5, 1), 4), obs(date(2023, 6, 1), 0)], START)
        self.assertEqual(d["prev_market_value"], 4)


class OutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = sp.OUTPUT / "season_start_prev_value.parquet"
        if not path.exists():
            raise unittest.SkipTest("output not built")
        cls.rows = pq.read_table(path).to_pylist()

    def test_one_row_per_release_player_season(self):
        self.assertEqual(len(self.rows), 2747)
        self.assertEqual(len({(r["canonical_player_id"], r["season"]) for r in self.rows}), 2747)

    def test_invariants(self):
        sp.check(self.rows)

    def test_every_value_predates_season_start(self):
        self.assertTrue(all(r["prev_valuation_date"] < r["first_match_date"] for r in self.rows if r["prev_valuation_date"]))


if __name__ == "__main__":
    unittest.main()
