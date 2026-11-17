"""Evidence and regression tests for historical identity, roles, metrics and matches."""
import csv
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.historical_identity import build_identity_rows, read_csv
from src.collection.match_index_validator import fixture_facts, probe_player_matches, probe_records
from src.collection.metric_reconciler import classify_metric, dictionary_rows, reconciliation_rows
from src.collection.phase_02b0_03_04 import validate_outputs
from src.collection.position_mapper import build as build_positions, exact_code_mapping


class Steps0304Tests(unittest.TestCase):
    def test_historical_multi_club_keeps_verified_and_inferred_distinct(self):
        rows, facts = build_identity_rows()
        self.assertEqual(facts["lineup_added_relations"], 2)
        self.assertEqual(facts["inferred_added_relations"], 3)
        self.assertEqual(facts["multi_club_player_seasons"], 5)
        self.assertEqual(facts["multi_club_all_verified"], 2)
        self.assertEqual(set(facts["id_name_review_counts"].values()), {0})
        archer = [r for r in rows if r["season_label"] == "2023/2024" and r["fotmob_player_id"] == "1086647"]
        self.assertEqual({r["historical_validation_status"] for r in archer},
                         {"HISTORICAL_VERIFIED", "HISTORICAL_INFERRED"})
        self.assertTrue(all(r["statistic_scope"] != "TEAM_SPECIFIC_TOTAL" for r in archer))
        minamino = [r for r in rows if r["season_label"] == "2020/2021" and r["fotmob_player_id"] == "408943"]
        self.assertEqual({r["fotmob_team_id"] for r in minamino}, {"8466", "8650"})
        self.assertTrue(all(r["historical_validation_status"] == "HISTORICAL_VERIFIED" for r in minamino))

    def test_current_profile_does_not_create_history_or_double_count_totals(self):
        rows, facts = build_identity_rows()
        self.assertEqual(facts["current_historical_team_mismatches"], 84)
        self.assertEqual(facts["duplicate_player_season"], 0)
        self.assertEqual(facts["duplicate_player_team_season"], 0)
        self.assertFalse(any(r["relationship_origin"] == "CURRENT_PROFILE" or
                             r["current_team_is_historical"] == "True" for r in rows))
        table = pq.read_table(ROOT / load_config()["normalized_dir"] / "player_team_seasons.parquet").to_pylist()
        self.assertTrue(all(r["team_stat_allocation_status"] == "UNVERIFIED_TEAM_SPLIT" for r in table))

    def test_exact_code_mapping_unknown_invalid_and_goalkeeper(self):
        self.assertEqual(exact_code_mapping("999", [], "positionId")["mapping_status"], "UNKNOWN")
        self.assertEqual(exact_code_mapping("11", [
            {"usual_id": "0", "raw_path": "a"}, {"usual_id": "0", "raw_path": "b"}],
            "positionId")["broader_position_group"], "GK")
        self.assertEqual(exact_code_mapping("72", [
            {"usual_id": "2", "raw_path": "a"}, {"usual_id": "3", "raw_path": "b"}],
            "positionId")["broader_position_group"], "UNKNOWN")

    def test_wijnaldum_and_changing_match_positions(self):
        registry, report, facts = build_positions()
        wijnaldum = next(r for r in report if r["season_label"] == "2019/2020" and r["player_id"] == "108038")
        self.assertEqual(wijnaldum["leaderboard_position_code"], "104")
        self.assertEqual(wijnaldum["pilot_code_band_group"], "FWD")
        self.assertEqual(wijnaldum["historical_group_inferred"], "MID")
        self.assertEqual(wijnaldum["historical_lineup_position_codes"], "64|77")
        self.assertTrue(wijnaldum["pilot_group_conflict"])
        self.assertEqual(facts["pilot_group_conflicts"], 3)
        self.assertTrue(any(r["mapping_status"] == "UNKNOWN" for r in registry["mappings"]))
        self.assertTrue(any(r["source_field"] == "usualPlayingPositionId" for r in registry["mappings"]))

    def test_metric_registry_and_minutes_conflict(self):
        dictionary = {r["normalized_field"]: r for r in dictionary_rows()}
        self.assertEqual(len(dictionary), 24)
        self.assertEqual(dictionary["key_passes"]["validation_status"], "UNVERIFIED")
        self.assertEqual(dictionary["rating"]["validation_status"], "EXCLUDED_FOR_NOW")
        self.assertEqual(dictionary["saves"]["validation_status"], "POSITION_SPECIFIC")
        self.assertEqual(dictionary["minutes_played"]["source_preference"], "NONE_UNRESOLVED")
        comparisons = reconciliation_rows()
        self.assertEqual(len(comparisons), 183)
        conflicts = [r for r in comparisons if r["comparison_status"] == "UNRESOLVED"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((conflicts[0]["player_id"], conflicts[0]["leaderboard_raw_value"],
                          conflicts[0]["player_stats_raw_value"]), ("831489", 2607, "2606"))
        self.assertEqual(conflicts[0]["source_preference"], "NONE")
        self.assertTrue(all((ROOT / r["leaderboard_evidence_path"]).is_file() and
                            (ROOT / r["player_stats_evidence_path"]).is_file() for r in conflicts))

    def test_match_status_replay_and_fallback(self):
        facts = fixture_facts()
        self.assertEqual(facts["fixture_records"], 2281)
        self.assertEqual(facts["finished"], 2280)
        self.assertEqual(facts["abandoned_or_cancelled"], 1)
        self.assertEqual(facts["by_season"]["2023/2024"]["fixture_records"], 381)
        self.assertEqual(facts["sampled_verified_participation_entries"], 513)
        self.assertEqual(facts["sampled_matches"], 18)

    def test_player_matches_errors_preserved_and_cache_only_rerun(self):
        before = probe_records()
        self.assertEqual(len(before), 2)
        self.assertEqual({r["http_status"] for r in before}, {400})
        self.assertTrue(all(r["response_error"] == "Invalid or missing query parameters" for r in before))
        for meta in before:
            body = (ROOT / meta["raw_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), meta["content_sha256"])
            self.assertEqual(json.loads(body)["error"], meta["response_error"])
        log = ROOT / "logs/phase_02b0_player_matches_requests.jsonl"
        count = len(log.read_text(encoding="utf-8").splitlines())
        self.assertEqual(probe_player_matches(True)["new_http_attempts"], 0)
        self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), count)

    def test_versioned_output_lineage_and_constraints(self):
        result = validate_outputs()
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["identity_rows"], 3267)
        self.assertEqual(result["mapping_entries"], 88)
        self.assertEqual(result["metric_conflicts"], 1)


if __name__ == "__main__":
    unittest.main()
