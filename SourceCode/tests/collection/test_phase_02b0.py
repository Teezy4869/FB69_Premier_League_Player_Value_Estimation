"""Phase 2B.0 request identity, immutable capture and appearance regressions."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.historical_lineup_validator import (
    build_population_rows, lineup_members, read_csv, select_matches, verify_detail,
)
from src.collection.provenance_validator import audit_captures, validate_lineage, legacy_lineup_link_status
from src.collection.source_registry import (
    SourceRegistry, load_hardening_config, request_key, validate_scope,
)
from src.collection.historical_lineup_validator import fixture_lookup


def fake_result(payload):
    raw = json.dumps(payload, sort_keys=True).encode()
    return {"record": {"timestamp_utc": "2026-11-02T08:00:00Z", "http_status": 200,
                       "content_type": "application/json", "source_url": "https://www.fotmob.com/api/data/teams",
                       "outcome": "OK"}, "payload": payload, "raw_body": raw}


class Phase2B0Tests(unittest.TestCase):
    def setUp(self):
        self.config = load_hardening_config()

    def test_request_key_is_canonical_and_season_sensitive(self):
        a = request_key("teams", {"season": "2019/2020", "id": 8650})
        b = request_key("teams", {"id": "8650", "season": "2019/2020"})
        c = request_key("teams", {"id": 8650, "season": "2024/2025"})
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_distinct_capture_ids_and_identical_content_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = SourceRegistry(self.config, root=Path(directory))
            payload = {"details": {"id": 8650, "latestSeason": "2026/2027"}, "squad": {"squad": []}}
            first, _ = registry.capture("teams", {"id": 8650, "season": "2019/2020"},
                                        "2019/2020", fake_result(payload))
            second, _ = registry.capture("teams", {"id": 8650, "season": "2024/2025"},
                                         "2024/2025", fake_result(payload))
            self.assertNotEqual(first["request_key"], second["request_key"])
            self.assertNotEqual(first["capture_id"], second["capture_id"])
            self.assertEqual(first["content_sha256"], second["content_sha256"])
            with self.assertRaises(FileExistsError):
                registry.capture("teams", {"id": 8650, "season": "2019/2020"},
                                 "2019/2020", fake_result({"details": {"id": 999}}))
            self.assertEqual(len(list(registry.captures())), 2)
            self.assertIsNone(registry.lookup("teams", {"id": 8650, "season": "2023/2024"}, "2023/2024"))

    def test_wrong_season_cache_lookup_even_with_same_match_id(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = SourceRegistry(self.config, root=Path(directory))
            registry.capture("matchDetails", {"matchId": 123}, "2019/2020",
                             fake_result({"general": {"matchId": 123, "leagueId": 47}}))
            self.assertIsNotNone(registry.lookup("matchDetails", {"matchId": 123}, "2019/2020"))
            self.assertIsNone(registry.lookup("matchDetails", {"matchId": 123}, "2020/2021"))

    def test_scope_states(self):
        self.assertEqual(validate_scope("leagues", {"season": "2019/2020"}, "2019/2020", 14022,
                                        {"details": {}})[0], "UNVERIFIED")
        self.assertEqual(validate_scope("leagues", {"season": "2019/2020"}, "2019/2020", 14022,
                                        {"details": {"selectedSeason": "2024/2025"}})[0],
                         "HISTORICAL_SCOPE_MISMATCH")
        self.assertEqual(validate_scope("teams", {"id": 8650}, "2019/2020", 14022,
                                        {"details": {"id": 8650, "latestSeason": "2026/2027"}})[0],
                         "UNVERIFIED")

    def test_live_fetch_requires_bounded_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = SourceRegistry(self.config, root=Path(directory))
            with self.assertRaisesRegex(ValueError, "limited to a bounded matchDetails"):
                registry.fetch("teams", {"id": 8650, "season": "2019/2020"}, "2019/2020")
            with self.assertRaisesRegex(ValueError, "fixture expectation"):
                registry.fetch("matchDetails", {"matchId": 123}, "2019/2020")
            self.assertEqual(len(list(registry.captures())), 0)

    def test_failed_response_is_not_registered_as_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = SourceRegistry(self.config, root=Path(directory))
            failed = {"record": {"timestamp_utc": "2026-11-02T08:00:00Z", "http_status": 503,
                                 "content_type": "application/json", "source_url": "https://example.test/matchDetails",
                                 "outcome": "FAILED"}, "payload": None}
            self.assertIsNone(registry.capture("matchDetails", {"matchId": 123}, "2019/2020", failed))
            self.assertEqual(len(list(registry.captures())), 0)
            self.assertIsNotNone(registry.capture("matchDetails", {"matchId": 123}, "2019/2020",
                                                  fake_result({"general": {"matchId": 123, "leagueId": 47}})))
            self.assertEqual(len(list(registry.captures())), 1)

    def test_interrupted_write_does_not_touch_committed_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = SourceRegistry(self.config, root=Path(directory))
            first, _ = registry.capture("teams", {"id": 1, "season": "2019/2020"},
                                        "2019/2020", fake_result({"details": {"id": 1}}))
            committed = Path(directory) / first["raw_path"]
            original = committed.read_bytes()
            with patch("src.collection.source_registry.os.rename", side_effect=OSError("simulated interruption")):
                with self.assertRaisesRegex(OSError, "simulated interruption"):
                    registry.capture("teams", {"id": 2, "season": "2020/2021"},
                                     "2020/2021", fake_result({"details": {"id": 2}}))
            self.assertEqual(committed.read_bytes(), original)
            self.assertEqual(len(list(registry.captures())), 1)
            self.assertIsNone(registry.lookup("teams", {"id": 2, "season": "2020/2021"}, "2020/2021"))
            committed.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                registry.lookup("teams", {"id": 1, "season": "2019/2020"}, "2019/2020")

    def test_starter_and_entered_sub_only(self):
        fixture = {"season_label": "2019/2020", "season_id": "14022", "match_id": "1",
                   "match_date_utc": "2019-09-01T12:00:00Z", "home_team_id": "10", "away_team_id": "20"}
        capture = {"raw_path": "example.json", "capture_id": "cap1", "request_key": "req1",
                   "collected_at_utc": "2026-11-02T00:00:00Z"}
        detail = {"content": {"lineup": {"lineupType": "standard",
            "homeTeam": {"id": 10, "starters": [{"id": 1, "name": "Starter"}],
                         "subs": [{"id": 2, "name": "Entered", "performance": {"substitutionEvents": [{"type": "subIn"}]}},
                                  {"id": 3, "name": "Unused", "performance": {"substitutionEvents": []}}]},
            "awayTeam": {"id": 20, "starters": [], "subs": []}}}}
        candidates = {("2019/2020", "1"): [{"fotmob_team_id": "10"}]}
        rows = lineup_members(detail, fixture, capture, candidates)
        self.assertEqual([r["appearance_status"] for r in rows],
                         ["APPEARED", "APPEARED", "UNUSED_SUBSTITUTE"])
        population = build_population_rows([], rows, {})
        self.assertEqual({r["player_id"] for r in population}, {"1", "2"})

    def test_real_sample_and_lineage_evidence(self):
        pilot = PilotStore(load_config())
        plan = select_matches(pilot, self.config)
        self.assertEqual(len(plan), 18)
        self.assertEqual({r["window"] for r in plan}, {"EARLY", "MID", "LATE"})
        self.assertEqual(len({r["season_label"] for r in plan}), 6)
        sample = read_csv(ROOT / "reports/phase_02b0/historical_match_sample.csv")
        self.assertTrue(all(r["detail_scope_status"] == "ACCEPTED" for r in sample))
        population = read_csv(ROOT / "reports/phase_02b0/historical_population_validation.csv")
        self.assertEqual(sum(r["verification_status"] == "VERIFIED_APPEARANCE_OTHER_TEAM" for r in population), 2)
        self.assertEqual(sum(r["missing_from_candidate_population"] == "True" for r in population), 0)
        minutes = {(r["season_label"], r["fotmob_player_id"]): float(r["minutes_played"])
                   for r in read_csv(ROOT / "reports/phase_02a/player_reference_index.csv") if r["minutes_played"]}
        lineups = read_csv(ROOT / "reports/phase_02b0/historical_lineup_comparison.csv")
        self.assertEqual(sum(r["appearance_status"] == "APPEARED" and r["lineup_role"] == "SUBSTITUTE" and
                             minutes.get((r["season_label"], r["player_id"]), float("inf")) < 90 for r in lineups), 5)
        integrity, aliases, problems = audit_captures(SourceRegistry(self.config), fixture_lookup(pilot))
        self.assertEqual(problems, [])
        self.assertEqual(len(integrity), 277)
        self.assertEqual(len(aliases), 2)
        self.assertEqual(legacy_lineup_link_status()["UNUSED_SUBSTITUTE"], 6)
        checked, problems = validate_lineage(integrity)
        self.assertGreater(checked, 10000)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
