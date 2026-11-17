import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.audit.normalization import leaderboard_rows, player_stat_items, season_profile_entry
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.normalize_pilot import METRICS, career_team_candidates, fixture_state, parse_number, write_parquet
from src.collection.phase_02a_03_06 import cache_by_source, match_plan, sample_rows, stats_plan


class Phase2ACollectionTests(unittest.TestCase):
    def test_numeric_parser_and_distinct_units(self):
        self.assertEqual(parse_number("1,234"), 1234.0)
        self.assertEqual(parse_number("-2.25"), -2.25)
        self.assertIsNone(parse_number("1/3"))
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number(None))
        self.assertEqual(METRICS["saves"][1:3], ("count", "total"))
        self.assertEqual(METRICS["passing_accuracy"][2], "percentage")
        self.assertEqual(METRICS["key_passes"][0], ())

    def test_empty_response_and_verified_profile_season(self):
        self.assertEqual(leaderboard_rows({"statsData": []}), [])
        self.assertEqual(player_stat_items({}), {})
        store = PilotStore(load_config())
        profile = cache_by_source(store, "playerData")["profile_108038"][1]
        self.assertEqual(str(profile["id"]), "108038")
        self.assertEqual(season_profile_entry(profile, "2019/2020", 47)["entryId"], "7-0")
        self.assertIsNone(season_profile_entry(profile, "2019/2020", 48))

    def test_stats_plan_uses_only_verified_season_entry(self):
        rows = [{"fotmob_player_id": "10", "season_label": "2019/2020"}]
        profiles = {"profile_10": ({}, {"id": 10, "statSeasons": []})}
        plan, skipped = stats_plan(rows, profiles)
        self.assertEqual(plan, [])
        self.assertEqual(skipped[0]["reason"], "NO_VERIFIED_SEASON_ENTRY")

    def test_current_profile_is_not_historical_team(self):
        with (ROOT / "reports/phase_02a/historical_identity_audit.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        vardy_or_sample = next(r for r in rows if r["current_vs_historical_team"] == "DIFFERENT")
        self.assertNotEqual(vardy_or_sample["current_team_id"], vardy_or_sample["historical_team_id"])
        self.assertEqual(vardy_or_sample["historical_team_status"], "HISTORICAL_VERIFIED")
        with (ROOT / "reports/phase_02a/pilot_player_profiles.csv").open(encoding="utf-8") as handle:
            profiles = list(csv.DictReader(handle))
        self.assertTrue(all(r["current_team_status"] in ("CURRENT_ONLY", "UNKNOWN") for r in profiles))

    def test_multi_club_candidate_does_not_invent_relationship(self):
        profile = {"careerHistory": {"careerItems": {"senior": {"teamEntries": [
            {"teamId": 1, "startDate": "2024-07-01", "endDate": "2025-01-15"},
            {"teamId": 2, "startDate": "2025-01-16", "endDate": None},
        ]}}}}
        self.assertEqual(career_team_candidates(profile, "2024/2025", {"1", "2"},
                                                ("2024-08-01", "2025-05-30")), ["1", "2"])
        self.assertEqual(career_team_candidates(profile, "2024/2025", {"2"},
                                                ("2024-08-01", "2025-05-30")), ["2"])

    def test_canceled_replayed_fixture_evidence(self):
        self.assertEqual(fixture_state({"cancelled": True, "finished": True}), "CANCELLED_OR_ABANDONED")
        store = PilotStore(load_config())
        league = cache_by_source(store, "leagues")["league_2023_2024"][1]
        fixtures = {str(x["id"]): x for x in league["fixtures"]["allMatches"]}
        self.assertEqual(fixture_state(fixtures["4193691"]["status"]), "CANCELLED_OR_ABANDONED")
        self.assertEqual(fixture_state(fixtures["4421797"]["status"]), "FINISHED")
        self.assertNotEqual(fixtures["4193691"]["id"], fixtures["4421797"]["id"])

    def test_player_match_links_have_selected_lineup_evidence(self):
        store = PilotStore(load_config())
        planned = match_plan(sample_rows(load_config()), cache_by_source(store, "leagues"))
        self.assertEqual(len(planned), 10)
        links = pq.read_table(ROOT / "data/pilot/normalized/player_match_links.parquet").to_pylist()
        self.assertGreater(len(links), 0)
        details = cache_by_source(store, "matchDetails")
        for link in links:
            source = details[link["source_id"]][1]
            lineup = source["content"]["lineup"]
            players = [str(p["id"]) for side in ("homeTeam", "awayTeam")
                       for role in ("starters", "subs") for p in (lineup.get(side) or {}).get(role) or []]
            self.assertIn(link["player_id"], players)
            self.assertEqual(link["link_status"], "HISTORICAL_VERIFIED_LINEUP")

    def test_parquet_idempotency_and_primary_keys(self):
        schema = pa.schema([("id", pa.string()), ("value", pa.float64())])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.parquet"
            rows = [{"id": "1", "value": 1.5}]
            write_parquet(path, schema, rows)
            first_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            write_parquet(path, schema, rows)
            self.assertEqual(first_hash, hashlib.sha256(path.read_bytes()).hexdigest())
        schema_def = json.loads((ROOT / "reports/phase_02a/schema_definition.json").read_text(encoding="utf-8"))
        for name in ("players", "teams", "player_seasons", "player_team_seasons", "matches", "player_match_links"):
            table = pq.read_table(ROOT / "data/pilot/normalized" / f"{name}.parquet")
            self.assertEqual(table.num_rows, schema_def[name]["rows"])
            keys = schema_def[name]["primary_key"]
            records = table.to_pylist()
            self.assertEqual(len(records), len({tuple(r[k] for k in keys) for r in records}))


if __name__ == "__main__":
    unittest.main()
