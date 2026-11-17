import json
import unittest
from pathlib import Path

from src.audit.normalization import (coverage_facts, leaderboard_rows, player_stat_items,
                                     season_profile_entry, stat_catalog)
from src.audit.player_coverage import coverage_row
from src.audit.profile_match_audit import profile_row


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((Path(__file__).parent / "fixtures/phase2_shapes.json").read_text(encoding="utf-8"))


class Phase2Tests(unittest.TestCase):
    def test_list_and_dict_stats_shapes_and_empty(self):
        self.assertEqual(len(leaderboard_rows(FIXTURE["leaderboard_list"])), 3)
        self.assertEqual(len(leaderboard_rows(FIXTURE["leaderboard_dict"])), 1)
        self.assertEqual(leaderboard_rows({"statsData": []}), [])
        self.assertEqual(leaderboard_rows({"statsData": {}}), [])
        self.assertIn("goals", stat_catalog(FIXTURE["leaderboard_list"]))

    def test_duplicates_and_multiple_teams_are_sample_only(self):
        facts = coverage_facts({"goals": leaderboard_rows(FIXTURE["leaderboard_list"]),
                                "mins_played": [], "saves": leaderboard_rows(FIXTURE["leaderboard_dict"])})
        self.assertEqual(facts["by_metric"]["goals"]["duplicate_player_rows"], 1)
        self.assertEqual(facts["sample_multi_team_player_count"], 1)
        self.assertEqual(facts["sample_unique_player_count"], 3)
        self.assertEqual(facts["unique_ids"], {"10", "20", "30"})
        self.assertEqual(facts["sample_missing_fields"]["id"], 0)
        row = coverage_row("2019/2020", 20,
                           {"goals": FIXTURE["leaderboard_list"], "mins_played": {}, "saves": FIXTURE["leaderboard_dict"]},
                           {}, False)
        self.assertEqual(row["denominator_status"], "UNKNOWN_DENOMINATOR")
        self.assertEqual(row["reference_player_count"], "")
        self.assertIn("10", row["sample_player_id_list"])

    def test_season_mapping_from_previous_saved_sample(self):
        sample = json.loads((ROOT / "data/audit/raw_samples/league_2019_2020.json").read_text(encoding="utf-8"))
        self.assertEqual(sample["season_id_evidence"]["TournamentId"], 14022)
        self.assertEqual(sample["selected_season_evidence"], "2019/2020")

    def test_current_profile_is_not_historical_team(self):
        entry = season_profile_entry(FIXTURE["profile"], "2019/2020", 47)
        self.assertEqual(entry["entryId"], "7-0")
        self.assertIsNone(season_profile_entry(FIXTURE["profile"], "2020/2021", 47))
        row = profile_row("2019/2020", "outfield_top_goals", {"id": 10, "teamId": 1},
                          FIXTURE["profile"], FIXTURE["player_stats"], {}, {})
        self.assertEqual(row["current_vs_historical_team_id"], "DIFFERENT")
        self.assertEqual(row["historical_leaderboard_team_id"], 1)
        self.assertEqual(row["current_team_id"], 99)

    def test_nested_player_stats_fields(self):
        fields = player_stat_items(FIXTURE["player_stats"])
        self.assertEqual(fields["matches_uppercase"]["statValue"], "30")
        self.assertEqual(fields["successful_passes_accuracy"]["statFormat"], "percent")


if __name__ == "__main__":
    unittest.main()
