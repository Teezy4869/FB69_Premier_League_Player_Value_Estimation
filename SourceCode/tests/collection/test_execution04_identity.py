"""Execution 04 regression checks against the saved historical evidence."""
import unittest
import json
import sqlite3
from collections import Counter, defaultdict

from src.collection.execution04_identity import OUT, appearance_status, identity_fields
from src.collection.collection_config import ROOT
import pyarrow.parquet as pq


class Execution04IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = {name: pq.read_table(OUT / f"{name}.parquet").to_pylist() for name in (
            "players", "player_seasons", "player_team_seasons", "matches",
            "player_match_appearances", "historical_position_observations")}

    def test_01_deduplicated_profiles(self):
        rows = self.tables["players"]
        self.assertEqual(len(rows), len({r["player_id"] for r in rows}))

    def test_02_current_historical_separation(self):
        self.assertNotIn("current_team_id", self.tables["player_team_seasons"][0])
        self.assertIsNone(identity_fields({"id": 1, "primaryTeam": None})["current_team_id"])

    def test_03_multi_club_relationships(self):
        groups = Counter((r["season_id"], r["player_id"]) for r in self.tables["player_team_seasons"] if r["validation_status"] == "CONFIRMED")
        self.assertGreater(sum(n > 1 for n in groups.values()), 0)

    def test_04_no_double_counted_player_season(self):
        rows = self.tables["player_seasons"]
        self.assertEqual(len(rows), len({(r["season_id"], r["player_id"]) for r in rows}))

    def test_05_unknown_position_preserved(self):
        rows = self.tables["historical_position_observations"]
        self.assertTrue(any(r["mapping_status"] == "UNKNOWN" for r in rows))

    def test_06_exact_code_position_registry(self):
        rows = self.tables["historical_position_observations"]
        self.assertTrue(all(r["mapping_version"] == "2.0" and r["original_code"] for r in rows))

    def test_07_started_vs_unused_sub(self):
        self.assertEqual(appearance_status({"lineup_role": "STARTER", "participation_status": "APPEARED", "substitution_events": None}), "STARTED")
        self.assertEqual(appearance_status({"lineup_role": "SUBSTITUTE", "participation_status": "UNUSED_SUBSTITUTE", "substitution_events": None}), "UNUSED_SUBSTITUTE")
        self.assertEqual(appearance_status({"lineup_role": "SUBSTITUTE", "participation_status": "UNKNOWN", "substitution_events": None}), "UNKNOWN")

    def test_08_abandoned_replay(self):
        by_id = {r["match_id"]: r for r in self.tables["matches"]}
        self.assertEqual((by_id["4193691"]["eligible_completed"], by_id["4421797"]["eligible_completed"]), ("False", "True"))

    def test_09_missing_lineup_not_invented(self):
        links = self.tables["player_match_appearances"]
        self.assertTrue(all(r["raw_path"] for r in links))
        self.assertTrue(all(r["validation_status"] == "UNRESOLVED" for r in links if r["participation_status"] == "UNKNOWN"))

    def test_10_unique_player_match(self):
        links = self.tables["player_match_appearances"]
        self.assertEqual(len(links), len({(r["match_id"], r["player_id"]) for r in links}))

    def test_11_wrong_season_rejected(self):
        seasons = {r["match_id"]: r["season_id"] for r in self.tables["matches"]}
        self.assertTrue(all(r["season_id"] == seasons[r["match_id"]] for r in self.tables["player_match_appearances"]))

    def test_12_idempotent_keys(self):
        self.assertEqual(len(self.tables["matches"]), len({r["match_id"] for r in self.tables["matches"]}))
        self.assertEqual(len(self.tables["player_team_seasons"]), len({(r["season_id"], r["player_id"], r["team_id"]) for r in self.tables["player_team_seasons"]}))

    def test_13_cache_resume_lineage(self):
        rows = self.tables["players"]
        self.assertTrue(all(r["profile_raw_path"] for r in rows if r["profile_status"] == "VERIFIED_ID"))
        self.assertTrue(all(r["profile_collected_at_utc"] for r in rows if r["profile_status"] == "VERIFIED_ID"))
        with sqlite3.connect(ROOT / "data/phase_02b1/collection_manifest.sqlite") as db:
            ids = [json.loads(r[0])["id"] for r in db.execute(
                "SELECT params_json FROM tasks WHERE resource_type='PLAYER_IDENTITY_PROFILE'")]
        self.assertEqual(len(ids), len(set(ids)))
