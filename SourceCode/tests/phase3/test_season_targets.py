"""Temporal validation tests for season-end targets.

FixtureTests use SYNTHETIC observations. RealTargetTests read the real output and fail if it is missing,
and recompute selection independently in SQL from the original source CSV.

Run: .venv/Scripts/python.exe -I -m unittest discover -s tests/phase3 -t . -v
"""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta

import duckdb
import pyarrow.parquet as pq
import yaml

import src.phase3.season_targets as module
from src.phase3.season_targets import ELIGIBLE_CROSSWALK, OUTPUT, SEASONS_PATH, TARGET_STATUSES, select_target, staleness_bucket
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT

CUTOFF = date(2024, 5, 19)


def obs(day, value=1000, status="VALID", record=None):
    return {"valuation_date": day, "market_value": value, "quality_status": status, "source_record_id": record or f"r:{day}:{value}", "_source_sha256": "synthetic", "_source_row_number": 1}


class SelectionFixtureTests(unittest.TestCase):
    def test_selects_latest_on_or_before_cutoff(self):
        result = select_target([obs(date(2023, 1, 1), 1), obs(date(2024, 1, 1), 2), obs(date(2024, 6, 1), 3)], CUTOFF, 90)
        self.assertEqual((result["selected_valuation_date"], result["market_value"]), (date(2024, 1, 1), 2))

    def test_valuation_on_the_cutoff_is_eligible_with_zero_age(self):
        result = select_target([obs(CUTOFF, 5)], CUTOFF, 90)
        self.assertEqual((result["market_value"], result["valuation_age_days"], result["staleness_bucket"], result["target_status"]), (5, 0, "0-30", "VALID"))

    def test_one_day_after_cutoff_is_never_selected(self):
        result = select_target([obs(CUTOFF + timedelta(days=1), 5)], CUTOFF, 90)
        self.assertIsNone(result["market_value"])
        self.assertEqual((result["target_status"], result["target_missing_reason"]), ("TARGET_MISSING", "ONLY_VALUATIONS_AFTER_CUTOFF"))

    def test_future_valuation_is_not_a_fallback_even_when_closer(self):
        result = select_target([obs(date(2015, 1, 1), 1), obs(CUTOFF + timedelta(days=1), 99)], CUTOFF, 90)
        self.assertEqual(result["market_value"], 1)

    def test_no_history_stays_missing_not_zero(self):
        result = select_target([], CUTOFF, 90)
        self.assertIsNone(result["market_value"])
        self.assertEqual(result["target_missing_reason"], "NO_VALUATION_HISTORY")

    def test_stale_is_labeled_and_kept(self):
        at_90 = select_target([obs(CUTOFF - timedelta(days=90), 7)], CUTOFF, 90)
        at_91 = select_target([obs(CUTOFF - timedelta(days=91), 7)], CUTOFF, 90)
        self.assertEqual(at_90["target_status"], "VALID")
        self.assertEqual((at_91["target_status"], at_91["market_value"], at_91["valuation_age_days"]), ("STALE_TARGET", 7, 91))

    def test_same_date_conflict_is_flagged_without_a_value(self):
        day = date(2024, 1, 1)
        result = select_target([obs(day, 1, "CONFLICT_SAME_DATE", "a"), obs(day, 2, "CONFLICT_SAME_DATE", "b"), obs(date(2023, 1, 1), 9)], CUTOFF, 90)
        self.assertEqual(result["target_status"], "AMBIGUOUS_VALUATION")
        self.assertIsNone(result["market_value"])
        self.assertEqual(result["conflicting_record_references"], "a|b")

    def test_exact_duplicate_is_not_a_conflict(self):
        day = date(2024, 1, 1)
        result = select_target([obs(day, 5, "DUPLICATE_EXACT", "b"), obs(day, 5, "DUPLICATE_EXACT", "a")], CUTOFF, 90)
        self.assertEqual((result["market_value"], result["source_record_reference"]), (5, "a"))

    def test_invalid_values_are_skipped_for_the_latest_valid_one(self):
        result = select_target([obs(date(2024, 2, 1), 0, "INVALID_VALUE_NONPOSITIVE"), obs(date(2023, 1, 1), 8)], CUTOFF, 90)
        self.assertEqual(result["market_value"], 8)

    def test_only_invalid_values_give_invalid_status(self):
        result = select_target([obs(date(2024, 2, 1), 0, "INVALID_VALUE_NONPOSITIVE")], CUTOFF, 90)
        self.assertEqual(result["target_status"], "INVALID_VALUATION")
        self.assertIsNone(result["market_value"])

    def test_buckets_use_the_exact_reporting_boundaries(self):
        cases = {0: "0-30", 30: "0-30", 31: "31-60", 60: "31-60", 61: "61-90", 90: "61-90", 91: "91-180", 180: "91-180", 181: ">180"}
        for age, label in cases.items():
            self.assertEqual(staleness_bucket(age), label)
        self.assertIsNone(staleness_bucket(None))
        with self.assertRaises(ValueError):
            staleness_bucket(-1)

    def test_module_never_reads_profile_market_values(self):
        source = inspect.getsource(module)
        self.assertNotIn("highest_market_value", source)
        self.assertNotIn("market_value_in_eur", source)
        self.assertNotIn("stg_players", source)


class RealTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = OUTPUT / "player_season_target.parquet"
        cls.rows = pq.read_table(cls.path).to_pylist()
        cls.config = yaml.safe_load(SEASONS_PATH.read_text(encoding="utf-8"))
        cls.con = duckdb.connect()

    def test_grain_is_one_row_per_canonical_player_season(self):
        keys = {(r["canonical_player_id"], r["season"]) for r in self.rows}
        self.assertEqual(len(keys), len(self.rows))
        self.assertEqual(len(self.rows), 3262)

    def test_population_is_exactly_the_confirmed_population(self):
        confirmed = set(self.con.execute(f"SELECT player_id, season_label FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/confirmed_appeared_player_seasons.parquet').as_posix()}')").fetchall())
        self.assertEqual({(r["fotmob_player_id"], r["season"]) for r in self.rows}, confirmed)

    def test_no_selected_valuation_is_after_its_cutoff(self):
        self.assertEqual(sum(r["selected_valuation_date"] is not None and r["selected_valuation_date"] > r["season_end_date"] for r in self.rows), 0)

    def test_cutoffs_match_the_verified_config_and_fixtures(self):
        cutoffs = {s["season"]: s["season_end_date"] for s in self.config["seasons"]}
        self.assertTrue(all(s["verification_status"] == "VERIFIED" for s in self.config["seasons"]))
        self.assertEqual(len(cutoffs), 6)
        for row in self.rows:
            self.assertEqual(row["season_end_date"].isoformat(), cutoffs[row["season"]])
        for season, day in self.con.execute(f"SELECT season_label, substr(max(match_date_utc),1,10) FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/matches.parquet').as_posix()}') WHERE match_status='COMPLETED' GROUP BY 1").fetchall():
            self.assertEqual(day, cutoffs[season])
        for season, day in self.con.execute(f"SELECT season||'/'||(season+1), max(date)::VARCHAR FROM read_parquet('{(ROOT / 'data/transfermarkt/staging/tm_r2_20260905/stg_games.parquet').as_posix()}') WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024 GROUP BY 1").fetchall():
            self.assertEqual(day, cutoffs[season])

    def test_age_and_bucket_are_correct(self):
        for row in self.rows:
            if row["selected_valuation_date"] is not None:
                self.assertEqual(row["valuation_age_days"], (row["season_end_date"] - row["selected_valuation_date"]).days)
                self.assertEqual(row["staleness_bucket"], staleness_bucket(row["valuation_age_days"]))
                self.assertGreaterEqual(row["valuation_age_days"], 0)

    def test_status_matches_age_and_value(self):
        stale = self.config["stale_label_days"]
        for row in self.rows:
            self.assertIn(row["target_status"], TARGET_STATUSES)
            if row["target_status"] == "VALID":
                self.assertLessEqual(row["valuation_age_days"], stale)
            if row["target_status"] == "STALE_TARGET":
                self.assertGreater(row["valuation_age_days"], stale)
            if row["target_status"] in ("VALID", "STALE_TARGET"):
                self.assertGreater(row["market_value"], 0)
                self.assertEqual(row["currency"], "EUR")
            else:
                self.assertIsNone(row["market_value"])

    def test_missing_targets_have_a_reason_and_no_imputed_zero(self):
        self.assertEqual(sum(r["market_value"] == 0 for r in self.rows), 0)
        for row in self.rows:
            if row["market_value"] is None:
                self.assertTrue(row["target_missing_reason"])

    def test_only_eligible_identities_get_targets(self):
        for row in self.rows:
            if row["crosswalk_status"] not in ELIGIBLE_CROSSWALK:
                self.assertIsNone(row["transfermarkt_player_id"])
                self.assertIsNone(row["market_value"])

    def test_every_target_traces_to_the_exact_source_row(self):
        source = ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz"
        self.con.execute("SET threads=1")
        raw = self.con.execute(f"SELECT row_number() OVER () rn, player_id, date, market_value_in_eur FROM read_csv('{source.as_posix()}', all_varchar=true, header=true)").fetchall()
        lookup = {r[0]: r for r in raw}
        checked = 0
        for row in self.rows:
            if row["market_value"] is not None:
                rn, player, day, value = lookup[row["source_row_number"]]
                self.assertEqual((player, day, int(value)), (row["transfermarkt_player_id"], row["selected_valuation_date"].isoformat(), row["market_value"]))
                self.assertEqual(row["source_record_reference"], f"player_valuations:{player}:{day}")
                self.assertTrue(row["source_file_sha256"])
                checked += 1
        self.assertGreater(checked, 3000)

    def test_independent_sql_recomputes_every_selected_valuation(self):
        """A second implementation, from the original CSV, must select the same date and value."""
        source = ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz"
        recomputed = self.con.execute(f"""
            WITH v AS (SELECT player_id, date::DATE d, market_value_in_eur::BIGINT m FROM read_csv('{source.as_posix()}', all_varchar=true, header=true) WHERE market_value_in_eur::BIGINT > 0),
                 t AS (SELECT * FROM read_parquet('{self.path.as_posix()}') WHERE transfermarkt_player_id IS NOT NULL)
            SELECT t.canonical_player_id, t.season, arg_max(v.m, v.d), max(v.d) FROM t LEFT JOIN v ON v.player_id=t.transfermarkt_player_id AND v.d<=t.season_end_date GROUP BY 1, 2""").fetchall()
        expected = {(r["canonical_player_id"], r["season"]): (r["market_value"], r["selected_valuation_date"]) for r in self.rows if r["transfermarkt_player_id"] is not None}
        self.assertEqual(len(recomputed), len(expected))
        for player, season, value, day in recomputed:
            self.assertEqual((value, day), expected[(player, season)], (player, season))

    def test_no_later_eligible_valuation_was_skipped(self):
        history = (ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_valuation_history.parquet").as_posix()
        skipped = self.con.execute(f"""SELECT count(*) FROM read_parquet('{self.path.as_posix()}') t JOIN read_parquet('{history}') h ON h.tm_player_id=t.transfermarkt_player_id
            WHERE t.selected_valuation_date IS NOT NULL AND h.quality_status='VALID' AND h.valuation_date>t.selected_valuation_date AND h.valuation_date<=t.season_end_date""").fetchone()[0]
        self.assertEqual(skipped, 0)

    def test_match_timing_fields_are_consistent(self):
        for row in self.rows:
            self.assertGreater(row["player_games_in_season"], 0)
            self.assertEqual(row["league_games_in_season"], 380)
            if row["selected_valuation_date"] is not None:
                self.assertLessEqual(row["player_games_after_valuation"], row["player_games_in_season"])
                self.assertLessEqual(row["league_games_after_valuation"], 380)


if __name__ == "__main__":
    unittest.main()
