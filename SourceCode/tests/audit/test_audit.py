import json
import tempfile
import unittest
from pathlib import Path

from src.audit.client import AuditClient, BudgetExceeded
from src.audit.validation import availability, deep_stats_facts, league_facts


class FakeResponse:
    url = "https://www.fotmob.com/api/data/leagues?id=47"
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def iter_content(self, chunk_size):
        yield b'{"details": {"id": 47}}'

    def close(self):
        pass


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


class AuditTests(unittest.TestCase):
    def test_numeric_season_id_and_substantive_records(self):
        payload = {"details": {"id": 47, "name": "Premier League", "selectedSeason": "2019/2020"},
                   "stats": {"seasonStatLinks": [{"Name": "2019/2020", "TournamentId": 14022}]},
                   "table": [{"data": {"table": {"all": [{"id": 1}]}}}],
                   "fixtures": {"allMatches": [{"id": 2}]}}
        facts = league_facts(payload, 47, "2019/2020")
        self.assertEqual(facts["season_id"], 14022)
        self.assertEqual(facts["fixture_count"], 1)
        self.assertEqual(availability(True, 1, 1, 0), "PARTIAL")
        self.assertFalse(league_facts(payload, 47, "2020/2021")["valid_league_season"])

    def test_empty_stats_are_not_available(self):
        self.assertEqual(deep_stats_facts({"statsData": []})["stats_data_count"], 0)
        self.assertEqual(availability(True, 20, 380, 0), "PARTIAL")

    def test_attempt_budget_and_logging(self):
        config = {"api_base_url": "https://www.fotmob.com/api/data", "max_retries": 0,
                  "request_budget": 1, "min_request_interval_seconds": 0,
                  "request_timeout_seconds": 1, "max_response_bytes": 1000,
                  "user_agent": "test", "backoff_seconds": 0}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requests.jsonl"
            client = AuditClient(config, path, session=FakeSession(), sleep=lambda _: None)
            self.assertEqual(client.get("leagues", {"id": 47})["payload"]["details"]["id"], 47)
            with self.assertRaises(BudgetExceeded):
                client.get("leagues", {"id": 47})
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["outcome"], "OK")


if __name__ == "__main__":
    unittest.main()
