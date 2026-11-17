"""Execution 03 scope and cross-season profile-cache regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.collection.batch_quality import batch_decision, inspect_capture
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import cached, registries
from src.collection.reliability_runner import classify_empty_stats_payload, profile_entry
from src.collection.reliability_runner import schema_state
from src.collection.statistics_catalog import board_spec
from src.collection.statistics_report import reconcile
from src.collection.statistics_semantics import (collapse_stat_occurrences, leaderboard_coverage,
                                                 metric_denominator, validate_board_filter, value_status)


class StatisticsExecution03Tests(unittest.TestCase):
    def test_consecutive_null_stats_trip_quality_gate(self):
        cfg = load_full_config()
        null = {"decision": "QUARANTINED", "error_classification": "NO_STATS_PAYLOAD",
                "missing_value_count": 0}
        valid = {"decision": "VALIDATED", "error_classification": "", "missing_value_count": 0}
        self.assertEqual(batch_decision([null, null, null], cfg)["decision"], "STOP")
        self.assertEqual(batch_decision([null, valid, null], cfg)["decision"], "REVIEW")

    def test_json_null_player_stats_is_source_absence_and_other_bad_json_is_error(self):
        record = {"http_status": 200, "json_parse_success": True}
        self.assertEqual(classify_empty_stats_payload("playerStats", record, b"null"), "NO_STATS_PAYLOAD")
        self.assertEqual(classify_empty_stats_payload("playerStats", record, b"{}"), "SCHEMA_ERROR")
        self.assertEqual(classify_empty_stats_payload("leagues", record, b"null"), "SCHEMA_ERROR")

    def test_sparse_top_card_is_retained_but_malformed_response_is_rejected(self):
        payload = {"topStatCard": {"items": [{"localizedTitleId": "goals", "statValue": "0"}]}}
        self.assertEqual(schema_state("playerStats", payload, {} )[0], "SPARSE_DATA")
        self.assertEqual(schema_state("playerStats", {"topStatCard": {"items": []}}, {} )[0], "SCHEMA_ERROR")

    def test_reconciliation_respects_display_rounding_and_multiclub_scope(self):
        shared = {"season_label": "2019/2020", "player_id": "1", "metric_name": "shots_per90",
                  "unit": "count", "aggregation_type": "per90", "team_id": "9", "team_count": 1,
                  "capture_id": "cap1"}
        board = dict(shared, source_endpoint="leagueseasondeepstats", value=2.2, raw_value="2.2")
        stats = dict(shared, source_endpoint="playerStats", value=2.208, raw_value="2.208")
        self.assertEqual(reconcile([board, stats])[0]["comparison_status"], "MATCH_ROUNDED")
        board["team_count"] = 2
        self.assertEqual(reconcile([board, stats])[0]["comparison_status"], "INCOMPARABLE_MULTICLUB")
        board["team_count"] = 1
        board["value"], board["raw_value"] = 3, "3"
        self.assertEqual(reconcile([board, stats])[0]["comparison_status"], "CONFLICTING")

    def test_leaderboard_subset_and_explicit_pagination(self):
        payload = {"statsData": [{"id": 1}, {"id": 2}]}
        self.assertEqual(leaderboard_coverage(payload, {"1", "2", "3"})["status"],
                         "PARTIAL_RANKED_OR_FILTERED")
        payload["pagination"] = {"total": 5, "page": 1}
        self.assertEqual(leaderboard_coverage(payload, {"1", "2", "3"})["status"],
                         "PAGINATED_OR_TRUNCATED")
        payload["statsData"].append({"id": 1})
        self.assertEqual(leaderboard_coverage(payload, {"1", "2", "3"})["status"],
                         "DUPLICATE_PLAYER_ID")

    def test_team_filter_and_wrong_season_remain_unverified_or_rejected(self):
        payload = {"currentSeasonId": 14022, "currentStatName": "goals", "statsData": []}
        params = {"season": 14022, "stat": "goals", "teamId": 8650}
        self.assertEqual(validate_board_filter(payload, params), "UNVERIFIED_TEAM_FILTER")
        self.assertEqual(validate_board_filter(dict(payload, teamId=999), params), "TEAM_FILTER_MISMATCH")
        self.assertEqual(validate_board_filter(dict(payload, teamId=8650), params), "VERIFIED_TEAM_FILTER")
        self.assertEqual(validate_board_filter(dict(payload, currentSeasonId=15382), params),
                         "HISTORICAL_SCOPE_MISMATCH")

    def test_missing_zero_and_total_per90_are_distinct(self):
        self.assertEqual(value_status(None), ("MISSING", None))
        self.assertEqual(value_status("0"), ("OBSERVED_ZERO", 0.0))
        self.assertEqual(value_status("not a number"), ("UNVERIFIED", None))
        self.assertEqual(board_spec("total_scoring_att")["aggregation"], "per90")
        self.assertEqual(board_spec("goals")["aggregation"], "total")

    def test_conflicting_duplicate_source_fields_are_preserved_for_review(self):
        payload = {"topStatCard": {"localizedTitleId": "goals", "statValue": "3"},
                   "statsSection": {"localizedTitleId": "goals", "statValue": "4"}}
        items, conflicts = collapse_stat_occurrences(payload)
        self.assertEqual(items["goals"]["raw_value"], "4")
        self.assertEqual(conflicts[0]["raw_values"], ["3", "4"])
        self.assertEqual(collapse_stat_occurrences({"statsSection": {}}), ({}, []))

    def test_position_specific_denominator_uses_confirmed_keeper_ids_only(self):
        appeared = {"1", "2", "3"}
        self.assertEqual(metric_denominator(appeared, {"2", "4"}, True), {"2"})
        self.assertEqual(metric_denominator(appeared, {"2", "4"}, False), appeared)

    def test_saved_profile_can_support_another_checked_season(self):
        cfg = load_full_config()
        current, old = registries(cfg)
        with tempfile.TemporaryDirectory() as temp:
            manifest = Manifest(Path(temp) / "manifest.sqlite")
            try:
                ident = manifest.add("2020/2021", 15382, "D", "PLAYER_PROFILE", "playerData",
                                     {"id": 108038}, {"identity": "profile_108038"})
                task = manifest.task(ident)
                meta, payload = cached(task, current, old)
                self.assertEqual(meta["season_label"], "2019/2020")
                self.assertIsNotNone(profile_entry(payload, "2020/2021"))
                quality = inspect_capture(task, meta, payload)
                self.assertEqual(quality["decision"], "VALIDATED")
                self.assertIn("reused capture", quality["note"])
            finally:
                manifest.close()


if __name__ == "__main__":
    unittest.main()
