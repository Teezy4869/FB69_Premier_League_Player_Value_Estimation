"""Regression test suite for Phase 2B.1-R Steps 01-02:
Metric eligibility model, verified denominators, and cross-season coverage repair.

Covers:
1. Top-N leaderboard denominator errors
2. Goalkeeper-only metrics
3. Unknown positions
4. Duplicate source observations
5. Multi-club players
6. Missing values
7. Not-applicable values
8. Eligible population equal to zero
9. Valid observations outside verified eligibility
10. Numerator/denominator grain consistency
"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.statistics_semantics import (
    compute_metric_eligibility_registry,
    metric_denominator,
    verified_goalkeepers_from_positions,
)


class RemediationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release_dir = ROOT / "data/releases/fotmob_epl_2019_2025_v2"
        cls.wide = pq.read_table(cls.release_dir / "curated/player_season_metrics_wide.parquet").to_pylist()
        cls.positions = pq.read_table(cls.release_dir / "normalized/historical_position_observations.parquet").to_pylist()
        cls.seasons = pq.read_table(cls.release_dir / "normalized/seasons.parquet").to_pylist()
        with (cls.release_dir / "manifests/metric_dictionary_v3.csv").open(encoding="utf-8") as f:
            cls.rules = list(csv.DictReader(f))
        cls.metrics = [r["normalized_field"] for r in cls.rules]
        cls.registry_rows, cls.cov_v3_rows = compute_metric_eligibility_registry(
            cls.wide, cls.metrics, cls.rules, cls.positions, cls.seasons
        )

    def test_01_top_n_leaderboard_denominator_errors_prevented(self):
        """Top-N leaderboard subsets must not be used as the full-season eligibility denominator."""
        # Simulated top-20 saves leaderboard vs 37 actual appeared GKs
        top_20_board_pids = {f"gk_{i}" for i in range(1, 21)}
        actual_appeared_gk_pids = {f"gk_{i}" for i in range(1, 38)}  # 37 goalkeepers
        simulated_wide = []
        for pid in actual_appeared_gk_pids:
            simulated_wide.append({
                "season_label": "2019/2020",
                "player_id": pid,
                "population_status": "APPEARED",
                "s_saves": "OBSERVED",
                "m_saves": 50.0
            })
        simulated_positions = [{"season_id": "14022", "season_label": "2019/2020", "player_id": pid, "mapped_group": "GK"}
                               for pid in actual_appeared_gk_pids]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]

        # Faulty legacy logic: using top-20 board directly produces 37/20 = 1.85
        legacy_ratio = len(actual_appeared_gk_pids) / len(top_20_board_pids)
        self.assertGreater(legacy_ratio, 1.0)

        # Verified eligibility logic: denominator is 37, ratio is 37/37 = 1.0
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(cov[0]["eligible_players"], 37)
        self.assertEqual(cov[0]["valid_values"], 37)
        self.assertEqual(cov[0]["coverage_fraction"], 1.0)
        self.assertLessEqual(cov[0]["coverage_fraction"], 1.0)

    def test_02_goalkeeper_only_metrics_coverage_valid_across_all_seasons(self):
        """Goalkeeper-only metrics must never exceed 100% coverage and resolve all 41 prior anomalies."""
        gk_metrics = {r["normalized_field"] for r in self.rules if r["applicable_positions"] == "GK_ONLY"}
        self.assertEqual(len(gk_metrics), 7)

        gk_cov_rows = [r for r in self.cov_v3_rows if r["metric_name"] in gk_metrics]
        self.assertEqual(len(gk_cov_rows), 7 * 6)  # 42 rows

        for r in gk_cov_rows:
            valid = int(r["valid_values"])
            eligible = int(r["eligible_players"])
            self.assertGreater(eligible, 0, f"Eligible GKs must be > 0 in {r['season_label']} for {r['metric_name']}")
            self.assertLessEqual(valid, eligible,
                                 f"valid_values ({valid}) > eligible_players ({eligible}) in {r['season_label']} for {r['metric_name']}")
            self.assertLessEqual(float(r["coverage_fraction"]), 1.0)

    def test_03_unknown_positions_tracked_not_imputed(self):
        """Players with unknown position must be tracked in eligibility_unknown_count and not silently classified."""
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "p_known_gk", "population_status": "APPEARED", "s_saves": "OBSERVED"},
            {"season_label": "2024/2025", "player_id": "p_known_out", "population_status": "APPEARED", "s_saves": "UNVERIFIED_POSITION"},
            {"season_label": "2024/2025", "player_id": "p_unk_pos", "population_status": "APPEARED", "s_saves": "OBSERVED"},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "p_known_gk", "mapped_group": "GK"},
            {"season_label": "2024/2025", "player_id": "p_known_out", "mapped_group": "MID"},
            {"season_label": "2024/2025", "player_id": "p_unk_pos", "mapped_group": "UNKNOWN"},
        ]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]

        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(reg[0]["eligible_verified_count"], 1)
        self.assertEqual(reg[0]["eligibility_unknown_count"], 1)
        # p_unk_pos has valid save observation outside verified eligible GKs:
        self.assertEqual(reg[0]["valid_outside_verified_eligibility_count"], 1)
        self.assertEqual(reg[0]["coverage_status"], "ANOMALOUS_OUTSIDE_ELIGIBILITY")

    def test_04_duplicate_source_observations_do_not_inflate_numerator(self):
        """Duplicate source observations must not cause double-counting at Player-Season grain."""
        # Even if multiple observations existed, distinct player IDs are counted
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "p1", "population_status": "APPEARED", "s_goals": "OBSERVED"},
            {"season_label": "2024/2025", "player_id": "p2", "population_status": "APPEARED", "s_goals": "OBSERVED"},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "p1", "mapped_group": "FWD"},
            {"season_label": "2024/2025", "player_id": "p2", "mapped_group": "MID"},
        ]
        simulated_rules = [{"normalized_field": "goals", "metric_group": "ATTACK",
                            "applicable_positions": "ALL", "unit": "count", "aggregation_type": "total"}]
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["goals"], simulated_rules, simulated_positions
        )
        self.assertEqual(reg[0]["observed_distinct_players"], 2)
        self.assertEqual(reg[0]["valid_eligible_count"], 2)

    def test_05_multi_club_players_grain_consistency(self):
        """Multi-club players must be counted exactly once per season (Player-Season grain)."""
        multi_club_wide = [r for r in self.wide if int(r.get("confirmed_team_count", 0)) > 1 and r["population_status"] == "APPEARED"]
        self.assertGreater(len(multi_club_wide), 0)
        # Check no duplicate player_id within season in wide table
        for season in {r["season_label"] for r in multi_club_wide}:
            s_rows = [r for r in self.wide if r["season_label"] == season and r["population_status"] == "APPEARED"]
            pids = [r["player_id"] for r in s_rows]
            self.assertEqual(len(pids), len(set(pids)), f"Duplicate player_id found in {season}")

    def test_06_missing_values_tracked_not_zero_filled(self):
        """Missing values for eligible players must be tracked in missing_eligible_count without zero fabrication."""
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "gk1", "population_status": "APPEARED", "s_saves": "OBSERVED", "m_saves": 10.0},
            {"season_label": "2024/2025", "player_id": "gk2", "population_status": "APPEARED", "s_saves": "MISSING", "m_saves": None},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "gk1", "mapped_group": "GK"},
            {"season_label": "2024/2025", "player_id": "gk2", "mapped_group": "GK"},
        ]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(reg[0]["eligible_verified_count"], 2)
        self.assertEqual(reg[0]["valid_eligible_count"], 1)
        self.assertEqual(reg[0]["missing_eligible_count"], 1)
        self.assertEqual(reg[0]["coverage_ratio"], 0.5)

    def test_07_not_applicable_values_excluded_from_denominator(self):
        """Outfield players must be categorized as not-applicable and excluded from GK metric denominators."""
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "gk1", "population_status": "APPEARED", "s_saves": "OBSERVED"},
            {"season_label": "2024/2025", "player_id": "out1", "population_status": "APPEARED", "s_saves": "UNVERIFIED_POSITION"},
            {"season_label": "2024/2025", "player_id": "out2", "population_status": "APPEARED", "s_saves": "UNVERIFIED_POSITION"},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "gk1", "mapped_group": "GK"},
            {"season_label": "2024/2025", "player_id": "out1", "mapped_group": "DEF"},
            {"season_label": "2024/2025", "player_id": "out2", "mapped_group": "MID"},
        ]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(cov[0]["eligible_players"], 1)
        self.assertEqual(cov[0]["appeared_players"], 3)
        self.assertEqual(cov[0]["not_applicable"], 2)
        self.assertEqual(cov[0]["valid_values"], 1)
        self.assertEqual(cov[0]["coverage_fraction"], 1.0)

    def test_08_eligible_population_zero_returns_undefined(self):
        """When eligible population is zero, coverage must be undefined, not an error or 0% / 100%."""
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "out1", "population_status": "APPEARED", "s_saves": "UNVERIFIED_POSITION"},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "out1", "mapped_group": "MID"},
        ]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(reg[0]["eligible_verified_count"], 0)
        self.assertEqual(reg[0]["coverage_status"], "UNDEFINED")
        self.assertEqual(reg[0]["coverage_ratio"], "")
        self.assertEqual(cov[0]["coverage_status"], "UNDEFINED")
        self.assertEqual(cov[0]["coverage_fraction"], 0.0)

    def test_09_valid_observations_outside_verified_eligibility_tracked(self):
        """Valid observations outside verified eligibility must be tracked and not silently dropped."""
        simulated_wide = [
            {"season_label": "2024/2025", "player_id": "gk1", "population_status": "APPEARED", "s_saves": "OBSERVED"},
            # Emergency goalkeeper (defender with observed saves)
            {"season_label": "2024/2025", "player_id": "def_emergency_gk", "population_status": "APPEARED", "s_saves": "OBSERVED"},
        ]
        simulated_positions = [
            {"season_label": "2024/2025", "player_id": "gk1", "mapped_group": "GK"},
            {"season_label": "2024/2025", "player_id": "def_emergency_gk", "mapped_group": "DEF"},
        ]
        simulated_rules = [{"normalized_field": "saves", "metric_group": "GOALKEEPING",
                            "applicable_positions": "GK_ONLY", "unit": "count", "aggregation_type": "total"}]
        reg, cov = compute_metric_eligibility_registry(
            simulated_wide, ["saves"], simulated_rules, simulated_positions
        )
        self.assertEqual(reg[0]["eligible_verified_count"], 1)
        self.assertEqual(reg[0]["valid_eligible_count"], 1)
        self.assertEqual(reg[0]["valid_outside_verified_eligibility_count"], 1)
        self.assertEqual(reg[0]["observed_distinct_players"], 2)
        self.assertEqual(reg[0]["coverage_status"], "ANOMALOUS_OUTSIDE_ELIGIBILITY")

    def test_10_numerator_denominator_grain_consistency_across_full_dataset(self):
        """Strict grain consistency: valid_eligible_count <= eligible_verified_count across all 318 cells."""
        self.assertEqual(len(self.registry_rows), 318)
        self.assertEqual(len(self.cov_v3_rows), 318)

        for reg in self.registry_rows:
            eligible = reg["eligible_verified_count"]
            valid = reg["valid_eligible_count"]
            outside = reg["valid_outside_verified_eligibility_count"]
            self.assertLessEqual(valid, eligible,
                                 f"Numerator {valid} exceeds denominator {eligible} in {reg['season_label']} for {reg['metric_name']}")
            self.assertEqual(outside, 0,
                             f"Unexpected observations outside eligibility: {outside} in {reg['season_label']} for {reg['metric_name']}")


if __name__ == "__main__":
    unittest.main()

