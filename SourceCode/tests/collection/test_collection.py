import json
import tempfile
import unittest
from pathlib import Path

from src.collection.collection_config import EXPECTED_SEASONS, load_config
from src.collection.foundation import PilotStore
from src.collection.player_reference import build_reference
from src.collection.pilot_sampler import choose_light, position_group


class FakeClient:
    def __init__(self):
        self.calls = 0

    def get(self, endpoint, params):
        self.calls += 1
        return {"record": {"timestamp_utc": "2020-01-01T00:00:00+00:00", "http_status": 200,
                           "content_type": "application/json", "source_url": "https://example.test/teams",
                           "response_bytes": 12, "outcome": "OK"}, "payload": {"details": {"id": 47}}}


class FakeStore:
    config = {"seasons": {s: n for s, n in zip(EXPECTED_SEASONS,
              (14022, 15382, 16390, 17664, 20720, 23685))},
              "reference_metrics": ["mins_played", "goals", "saves"]}

    def cached_payloads(self):
        season = "2019/2020"
        league = {"details": {"selectedSeason": season}, "table": [{"data": {"table": {
            "all": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}}}]}
        yield {"endpoint": "leagues", "season_label": season, "params": {"season": season}}, league
        for metric in self.config["reference_metrics"]:
            rows = [{"id": 10, "teamId": 1, "name": "Player", "position": 36,
                     "statValue": {"value": 100}}]
            if metric == "goals":
                rows.append({"id": 10, "teamId": 2, "name": "Player", "position": 36,
                             "statValue": {"value": 1}})
            yield {"endpoint": "leagueseasondeepstats", "season_label": season,
                   "params": {"stat": metric}, "source_id": metric,
                   "collected_at_utc": "2020-01-01T00:00:00+00:00"}, {
                       "currentSeasonId": 14022, "currentStatName": metric, "statsData": rows}


class CollectionTests(unittest.TestCase):
    def test_config_scope(self):
        config = load_config()
        self.assertEqual(tuple(config["seasons"]), EXPECTED_SEASONS)
        self.assertLessEqual(config["request_budget"], 40)

    def test_cache_resume_and_integrity(self):
        config = load_config()
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory:
            store = PilotStore(config, client=client, root=Path(directory))
            first = store.fetch("teams", {"id": 8650, "season": "2019/2020"},
                                "2019/2020", "test_team")
            self.assertEqual(first, store.fetch("teams", {"id": 8650, "season": "2019/2020"},
                                                "2019/2020", "test_team"))
            self.assertEqual(client.calls, 1)
            with self.assertRaisesRegex(ValueError, "Unexpected request parameters"):
                store.fetch("teams", {"id": 8650, "season": "2019/2020", "token": "secret"},
                            "2019/2020", "test_team")
            self.assertEqual(client.calls, 1)
            meta_path = next((Path(directory) / config["raw_dir"]).glob("*.meta.json"))
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["season_label"], "2019/2020")
            self.assertEqual(metadata["http_status"], 200)
            payload_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            payload_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                store.fetch("teams", {"id": 8650, "season": "2019/2020"},
                            "2019/2020", "test_team")

    def test_multi_club_relationship_and_unknown_denominator(self):
        rows, coverage = build_reference(FakeStore())
        first = [r for r in rows if r["season_label"] == "2019/2020"]
        self.assertEqual({r["fotmob_team_id"] for r in first}, {"1", "2"})
        self.assertEqual(coverage[0]["unique_player_count"], 1)
        self.assertEqual(coverage[0]["player_team_season_count"], 2)
        self.assertEqual(coverage[0]["multi_team_player_count"], 1)
        self.assertEqual(coverage[0]["population_denominator"], "UNKNOWN")
        self.assertEqual(coverage[0]["population_coverage_percent"], "")

    def test_duplicate_player_team_metric_row_is_rejected(self):
        class DuplicateStore(FakeStore):
            def cached_payloads(self):
                for meta, payload in super().cached_payloads():
                    if meta["endpoint"] == "leagueseasondeepstats" and meta["params"]["stat"] == "goals":
                        payload["statsData"].append(dict(payload["statsData"][0]))
                    yield meta, payload
        with self.assertRaisesRegex(ValueError, "Duplicate player/team row"):
            build_reference(DuplicateStore())

    def test_light_sample_balances_roles_and_low_minutes(self):
        rows = [{"fotmob_player_id": str(i), "fotmob_team_id": "1", "position": str(code),
                 "minutes_played": str(value)} for i, code, value in
                [(1, 11, 2000), (2, 36, 1800), (3, 66, 1000), (4, 115, 900), (5, 66, 20)]]
        import random
        pick = choose_light(rows, ("FWD", "LOW"), random.Random(6902))
        self.assertEqual([position_group(r["position"]) for r, _, _ in pick], ["FWD", "MID"])
        self.assertEqual(pick[1][0]["minutes_played"], "20")


if __name__ == "__main__":
    unittest.main()
