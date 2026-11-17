"""Deterministic failure injection for the bounded Step 05 client and cache."""
import json
import tempfile
import unittest
from pathlib import Path

import requests

from src.audit.client import AuditClient, retry_after_seconds
from src.collection.historical_lineup_validator import build_population_rows
from src.collection.reliability_runner import schema_state, profile_entry
from src.collection.source_registry import SourceRegistry, load_hardening_config, request_key


class Response:
    def __init__(self, status, body=b"{}", headers=None):
        self.status_code = status
        self.body = body
        self.headers = headers or {"Content-Type": "application/json"}
        self.url = "https://example.test/api/data/leagues"
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class Session:
    def __init__(self, events):
        self.events = iter(events)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        event = next(self.events)
        if isinstance(event, Exception):
            raise event
        return event


class ReliabilityFailureTests(unittest.TestCase):
    def client(self, events, temp, waits, retries=1):
        cfg = {"api_base_url": "https://example.test/api/data", "max_retries": retries,
               "request_budget": 4, "min_request_interval_seconds": 0,
               "backoff_seconds": 2, "max_retry_after_seconds": 10,
               "request_timeout_seconds": 1, "user_agent": "test", "max_response_bytes": 1000}
        session = Session(events)
        return AuditClient(cfg, Path(temp) / "requests.jsonl", session=session,
                           sleep=waits.append, clock=lambda: 0), session

    def test_parameter_error_and_access_denial_stop_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            waits = []
            client, session = self.client([Response(400, b'{"error":"bad parameters"}')], temp, waits)
            result = client.get("leagues", {"id": 47})
            self.assertIsNone(result["payload"])
            self.assertEqual(result["raw_body"], b'{"error":"bad parameters"}')
            self.assertEqual(result["record"]["response_error"], "bad parameters")
            self.assertEqual(session.calls, 1)
            client, session = self.client([Response(403, b'{"error":"denied"}')], temp, waits)
            self.assertEqual(client.get("leagues")["record"]["http_status"], 403)
            self.assertEqual(session.calls, 1)

    def test_rate_limit_waits_for_retry_after_and_has_bounded_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            waits = []
            client, session = self.client([Response(429, headers={"Content-Type": "application/json", "Retry-After": "5"}),
                                           Response(200, b'{"ok":true}')], temp, waits)
            self.assertEqual(client.get("leagues")["payload"], {"ok": True})
            self.assertEqual(session.calls, 2)
            self.assertIn(5.0, waits)
            client, session = self.client([Response(429, headers={"Content-Type": "application/json", "Retry-After": "3600"})], temp, [])
            result = client.get("leagues")
            self.assertEqual(result["record"]["error"], "Retry-After exceeds bounded wait")
            self.assertEqual(session.calls, 1)
            self.assertEqual(retry_after_seconds("nonsense"), None)

    def test_server_errors_timeout_and_reset_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            for events in ([Response(500), Response(503)],
                           [requests.Timeout("timeout"), requests.ConnectionError("reset")]):
                client, session = self.client(events, temp, [])
                result = client.get("leagues")
                self.assertIsNone(result["payload"])
                self.assertEqual(session.calls, 2)
                self.assertEqual(client.attempts, 2)

    def test_invalid_json_empty_data_and_unexpected_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            client, _ = self.client([Response(200, b"{bad json")], temp, [], retries=0)
            result = client.get("leagues")
            self.assertFalse(result["record"]["json_parse_success"])
            self.assertEqual(result["raw_body"], b"{bad json")
        self.assertEqual(schema_state("leagues", {}, {"id": 47})[0], "SCHEMA_ERROR")
        self.assertEqual(schema_state("leagueseasondeepstats", {"currentSeasonId": 1,
                         "currentStatName": "mins_played", "statsData": []}, {})[0], "EMPTY_DATA")
        self.assertIsNone(profile_entry({"statSeasons": [{"seasonName": "2024/2025",
                          "tournaments": [{"tournamentId": 55, "entryId": "1-0"}]}]}, "2024/2025"))

    def test_wrong_season_capture_is_preserved_but_not_cache_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = load_hardening_config()
            registry = SourceRegistry(cfg, root=Path(temp))
            payload = {"details": {"selectedSeason": "2024/2025"}}
            result = {"record": {"timestamp_utc": "2026-11-02T00:00:00Z", "http_status": 200,
                                  "content_type": "application/json", "source_url": "https://example.test/leagues"},
                      "payload": payload, "raw_body": json.dumps(payload).encode()}
            with self.assertRaisesRegex(ValueError, "Historical scope mismatch preserved"):
                registry.capture("leagues", {"id": 47, "season": "2019/2020"}, "2019/2020", result)
            self.assertEqual(len(list(registry.captures())), 1)
            with self.assertRaisesRegex(ValueError, "invalid historical scope"):
                registry.lookup("leagues", {"id": 47, "season": "2019/2020"}, "2019/2020")

    def test_missing_player_id_is_detected_without_zero_imputation(self):
        candidate = {"fotmob_season_id": "14022", "season_label": "2019/2020",
                     "fotmob_player_id": "1", "fotmob_team_id": "10",
                     "reference_source": "leagueseasondeepstats", "evidence_source_ids": "board1",
                     "reference_timestamp": "2026-11-02T00:00:00Z", "observed_metrics": "mins_played"}
        lineup = {"season_id": "14022", "season_label": "2019/2020", "player_id": "2",
                  "team_id": "10", "appearance_status": "APPEARED", "match_id": "100",
                  "evidence_reference": "match.json", "collection_timestamp": "2026-11-02T00:00:00Z"}
        rows = build_population_rows([candidate], [lineup], {"board1": "board.json"})
        missing = next(r for r in rows if r["player_id"] == "2")
        self.assertEqual(missing["verification_status"], "VERIFIED_APPEARANCE_MISSING_CANDIDATE")
        self.assertTrue(missing["missing_from_candidate_population"])
        self.assertEqual(missing["observed_metrics"], "")
        self.assertNotEqual(request_key("leagues", {"id": 47, "season": "2019/2020"}),
                            request_key("leagues", {"id": 47, "season": "2024/2025"}))


if __name__ == "__main__":
    unittest.main()
