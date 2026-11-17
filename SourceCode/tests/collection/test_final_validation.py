"""Regression checks for pilot evidence, cache recovery and final review."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.audit.normalization import leaderboard_rows, player_stat_items, season_profile_entry
from src.collection.collection_config import load_config
from src.collection.final_validation import cross_season_rows, quality_rows, validate
from src.collection.foundation import PilotStore


class SequenceClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def get(self, endpoint, params):
        self.calls += 1
        payload = next(self.responses)
        return {"record": {"timestamp_utc": "2026-01-01T00:00:00Z", "http_status": 200 if payload else 503,
                           "content_type": "application/json", "source_url": "https://www.fotmob.com/api/data/teams",
                           "response_bytes": 2, "outcome": "OK" if payload else "FAILED"},
                "payload": payload, "raw_body": json.dumps(payload).encode() if payload else None}


class FinalValidationTests(unittest.TestCase):
    def test_cache_restoration_and_repeat_run_no_duplicate_raw(self):
        config = load_config()
        client = SequenceClient([{"details": {"id": 8650}}])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ("teams", {"id": 8650, "season": "2019/2020"}, "2019/2020", "season_team")
            self.assertEqual(PilotStore(config, client=client, root=root).fetch(*args)["details"]["id"], 8650)
            for _ in range(2):
                resumed = PilotStore(config, client=client, root=root)
                self.assertEqual(resumed.fetch(*args)["details"]["id"], 8650)
                self.assertEqual(resumed.events[0]["outcome"], "CACHE_HIT")
            self.assertEqual(client.calls, 1)
            raw_dir = root / config["raw_dir"]
            self.assertEqual(len(list(raw_dir.glob("*.json"))), 2)
            meta_path = next(raw_dir.glob("*.meta.json"))
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            payload_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            self.assertEqual(hashlib.sha256(payload_path.read_bytes()).hexdigest(), meta["sha256"])

    def test_partial_failure_is_not_cached_as_success(self):
        config = load_config()
        client = SequenceClient([None, {"details": {"id": 8650}}])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ("teams", {"id": 8650, "season": "2019/2020"}, "2019/2020", "season_team")
            self.assertIsNone(PilotStore(config, client=client, root=root).fetch(*args))
            self.assertEqual(len(list((root / config["raw_dir"]).glob("*.json"))), 0)
            self.assertIsNotNone(PilotStore(config, client=client, root=root).fetch(*args))
            self.assertEqual(client.calls, 2)

    def test_unexpected_source_shapes_do_not_create_stats(self):
        self.assertEqual(leaderboard_rows({"statsData": "unexpected"}), [])
        self.assertEqual(player_stat_items({"statsSection": "unexpected"}), {})
        self.assertIsNone(season_profile_entry({"statSeasons": []}, "2024/2025", 47))

    def test_independent_evidence_review_and_cross_source_conflict(self):
        result = validate()
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["raw"]["raw_pairs"], 265)
        self.assertEqual(result["raw"]["source_id_collisions"], {"team_roster_probe_liverpool": 2})
        self.assertEqual(sum(result["overlap"].values()), 183)
        self.assertEqual(len(result["disagreements"]), 1)
        self.assertEqual(result["disagreements"][0]["player_id"], "831489")
        dq = {row["finding_id"]: row for row in quality_rows(result)}
        self.assertEqual(dq["DQ02"]["status"], "UNKNOWN")
        self.assertEqual(dq["DQ12"]["affected_count"], 1)
        cross = {row["metric"]: row for row in cross_season_rows(result)}
        self.assertEqual(cross["key_passes"]["total_unsupported"], 120)
        self.assertEqual(cross["minutes_played"]["classification"], "OPTIONAL")


if __name__ == "__main__":
    unittest.main()
