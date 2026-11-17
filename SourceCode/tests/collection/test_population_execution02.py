"""Participation rules anchored to a saved FotMob match and season fixtures."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.collection.batch_quality import batch_decision, inspect_capture
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore
from src.collection.full_manifest import load_full_config
from src.collection.historical_lineup_validator import fixture_lookup
from src.collection.population_execution02 import participation_rows, reconcile_sets
from src.collection.source_registry import SourceRegistry, load_hardening_config


class PopulationExecution02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SourceRegistry(load_hardening_config())
        cls.meta, cls.detail = next((m, p) for m, p in registry.captures()
                                    if m["endpoint"] == "matchDetails" and m["season_label"] == "2019/2020")
        fixtures = fixture_lookup(PilotStore(load_config()))
        cls.fixture = next(row for row in fixtures["2019/2020"]
                           if row["match_id"] == str(cls.detail["general"]["matchId"]))

    def test_saved_match_distinguishes_entered_from_unused_substitute(self):
        rows, issues = participation_rows(self.detail, self.fixture, self.meta)
        self.assertFalse(issues)
        self.assertTrue(any(r["lineup_role"] == "STARTER" and r["participation_status"] == "APPEARED"
                            for r in rows))
        self.assertTrue(any(r["lineup_role"] == "SUBSTITUTE" and r["participation_status"] == "APPEARED"
                            for r in rows))
        self.assertTrue(any(r["lineup_role"] == "SUBSTITUTE" and r["participation_status"] == "UNUSED_SUBSTITUTE"
                            for r in rows))

    def test_missing_substitution_evidence_is_unknown(self):
        payload = copy.deepcopy(self.detail)
        substitute = next(member for member in payload["content"]["lineup"]["homeTeam"]["subs"]
                          if not (member.get("performance") or {}).get("substitutionEvents"))
        substitute["performance"].pop("substitutionEvents", None)
        rows, issues = participation_rows(payload, self.fixture, self.meta)
        self.assertFalse(issues)
        self.assertEqual(next(r["participation_status"] for r in rows
                              if r["player_id"] == str(substitute["id"])), "UNKNOWN")

    def test_invalid_and_duplicate_player_id_are_reported(self):
        payload = copy.deepcopy(self.detail)
        starters = payload["content"]["lineup"]["homeTeam"]["starters"]
        starters[0].pop("id")
        _, issues = participation_rows(payload, self.fixture, self.meta)
        self.assertTrue(any(issue.startswith("MISSING_PLAYER_ID") for issue in issues))
        payload = copy.deepcopy(self.detail)
        starters = payload["content"]["lineup"]["homeTeam"]["starters"]
        starters[1]["id"] = starters[0]["id"]
        _, issues = participation_rows(payload, self.fixture, self.meta)
        self.assertTrue(any(issue.startswith("DUPLICATE_MATCH_PLAYER") for issue in issues))

    def test_missing_lineup_list_is_reported(self):
        payload = copy.deepcopy(self.detail)
        payload["content"]["lineup"]["awayTeam"].pop("subs")
        _, issues = participation_rows(payload, self.fixture, self.meta)
        self.assertTrue(any(issue.startswith("MISSING_LINEUP_LIST") for issue in issues))
        payload = copy.deepcopy(self.detail)
        payload["content"]["lineup"]["homeTeam"]["starters"].pop()
        _, issues = participation_rows(payload, self.fixture, self.meta)
        self.assertTrue(any(issue.startswith("INCOMPLETE_STARTERS") for issue in issues))

    def test_duplicate_lineup_stops_batch_quality_gate(self):
        payload = copy.deepcopy(self.detail)
        starters = payload["content"]["lineup"]["homeTeam"]["starters"]
        starters[1]["id"] = starters[0]["id"]
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase_02b1") as temp:
            raw = Path(temp) / "response.json"
            body = json.dumps(payload).encode("utf-8")
            raw.write_bytes(body)
            meta = dict(self.meta, raw_path=raw.relative_to(ROOT).as_posix(),
                        content_sha256=hashlib.sha256(body).hexdigest())
            task = {"task_id": "test_detail", "request_key": meta["request_key"],
                    "season_label": "2019/2020", "season_id": 14022, "stage": "E",
                    "resource_type": "MATCH_DETAIL", "endpoint": "matchDetails",
                    "params": {"matchId": int(self.fixture["match_id"])},
                    "context": {"fixture": self.fixture}}
            result = inspect_capture(task, meta, payload)
            self.assertEqual(result["error_classification"], "DUPLICATE_OR_MISSING_ID")
            self.assertEqual(batch_decision([result], load_full_config())["decision"], "STOP")

    def test_wrong_fixture_context_is_rejected(self):
        fixture = dict(self.fixture, season_label="2020/2021", match_id="999999")
        rows, issues = participation_rows(self.detail, fixture, self.meta)
        self.assertEqual(rows, [])
        self.assertTrue(issues[0].startswith("WRONG_SEASON_OR_FIXTURE"))

    def test_abandoned_match_and_replay(self):
        _, payload = next((m, p) for m, p in PilotStore(load_config()).cached_payloads("leagues")
                          if m["season_label"] == "2023/2024")
        matches = {str(item["id"]): item for item in payload["fixtures"]["allMatches"]}
        self.assertTrue(matches["4193691"]["status"]["cancelled"])
        self.assertFalse(matches["4421797"]["status"]["cancelled"])
        ids = {row["match_id"] for row in fixture_lookup(PilotStore(load_config()))["2023/2024"]}
        self.assertNotIn("4193691", ids)
        self.assertIn("4421797", ids)

    def test_multiclub_and_missing_leaderboard_candidate(self):
        result = reconcile_sets({"10", "30"}, {("10", "100"), ("10", "200"), ("20", "300")})
        self.assertEqual(result["appeared_ids"], {"10", "20"})
        self.assertEqual(result["missing_candidates"], {"20"})
        self.assertEqual(result["candidate_unconfirmed"], {"30"})
        self.assertEqual(result["multi_club_ids"], {"10"})


if __name__ == "__main__":
    unittest.main()
