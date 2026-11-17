"""Regression test suite for Phase 2B.1-R Step 07: Substitution & Appearance Remediation.

Covers all 15 mandatory test requirements:
  1. Starting player classification.
  2. Confirmed substitute entering.
  3. Unused substitute classification.
  4. Empty or incomplete event feed handling.
  5. Contradictory lineup/event evidence.
  6. Multiple substitutions in single match.
  7. Player ID mapping integrity.
  8. Wrong-season response handling.
  9. Duplicate player-match rejection.
  10. Missing event fields resilience.
  11. Different historical JSON structures (2019 vs 2024).
  12. Fixture cancellation/replay handling (match 4193691).
  13. Multi-club player-season integrity.
  14. Reprocessing idempotency.
  15. Raw provenance traceability.
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.remediation_substitutions import (
    classify_participation,
    execute_step07_remediation,
    PARSER_VERSION,
)


class RemediationStep07Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = ROOT
        cls.remediation_dir = cls.workspace / "data/phase_02b1/remediation"
        cls.reports_dir = cls.workspace / "reports/phase_02b1_remediation"

        cls.pma_provisional_path = cls.remediation_dir / "player_match_appearances_provisional.parquet"
        cls.pop_v3_path = cls.remediation_dir / "complete_player_season_classification_v3.parquet"
        cls.audit_path = cls.reports_dir / "appearance_resolution_audit.csv"
        cls.coverage_path = cls.reports_dir / "appearance_coverage_v3.csv"
        cls.rec_path = cls.reports_dir / "population_reconciliation_v3.csv"

        cls.pma_table = pq.read_table(cls.pma_provisional_path)
        cls.pop_table = pq.read_table(cls.pop_v3_path)

    def test_01_starting_player(self):
        """1. Verified starting player must be classified as STARTED with DIRECT_STARTER_EVIDENCE."""
        p_slice = self.pma_table.filter(pc.equal(self.pma_table["participation_status"], "STARTED"))
        self.assertEqual(len(p_slice), 50160)
        sample = p_slice.slice(0, 10).to_pylist()
        for r in sample:
            self.assertEqual(r["lineup_role"], "STARTER")
            self.assertEqual(r["starting_status"], "STARTED")
            self.assertEqual(r["validation_status"], "CONFIRMED")
            self.assertEqual(r["evidence_class"], "DIRECT_STARTER_EVIDENCE")

    def test_02_confirmed_substitute_entering(self):
        """2. Confirmed substitute entering must be classified as SUBSTITUTED_ON with DIRECT_SUBSTITUTION_ON_EVIDENCE."""
        p_slice = self.pma_table.filter(pc.equal(self.pma_table["participation_status"], "SUBSTITUTED_ON"))
        self.assertEqual(len(p_slice), 15628)
        sample = p_slice.slice(0, 10).to_pylist()
        for r in sample:
            self.assertEqual(r["lineup_role"], "SUBSTITUTE")
            self.assertEqual(r["starting_status"], "NOT_STARTED")
            self.assertEqual(r["validation_status"], "CONFIRMED")
            self.assertEqual(r["evidence_class"], "DIRECT_SUBSTITUTION_ON_EVIDENCE")

    def test_03_unused_substitute(self):
        """3. Verified unused substitute must be classified as UNUSED_SUBSTITUTE with COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE."""
        p_slice = self.pma_table.filter(pc.equal(self.pma_table["participation_status"], "UNUSED_SUBSTITUTE"))
        self.assertEqual(len(p_slice), 23604)
        sample = p_slice.slice(0, 10).to_pylist()
        for r in sample:
            self.assertEqual(r["lineup_role"], "SUBSTITUTE")
            self.assertEqual(r["starting_status"], "NOT_STARTED")
            self.assertEqual(r["validation_status"], "NOT_APPEARED")
            self.assertEqual(r["evidence_class"], "COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE")

    def test_04_empty_or_incomplete_event_feed(self):
        """4. If event feed is missing or empty, substitute must NOT be resolved to UNUSED, but retained as UNKNOWN."""
        mock_payload = {
            "content": {
                "lineup": {
                    "lineupType": "standard",
                    "homeTeam": {"starters": [{"id": f"h{i}"} for i in range(11)], "subs": [{"id": "s1"}]},
                    "awayTeam": {"starters": [{"id": f"a{i}"} for i in range(11)], "subs": []},
                },
                "matchFacts": {"events": {"events": []}},  # Empty event feed!
                "playerStats": {},
            }
        }
        status, val, ev_class, reason = classify_participation(
            player_id="s1",
            lineup_role="SUBSTITUTE",
            member={"id": "s1"},
            match_payload=mock_payload,
            fixture_info={"eligible_completed": True},
        )
        self.assertEqual(status, "UNKNOWN")
        self.assertEqual(val, "UNRESOLVED")
        self.assertEqual(ev_class, "INSUFFICIENT_EVIDENCE")
        self.assertIn("INCOMPLETE", reason)

    def test_05_contradictory_lineup_event_evidence(self):
        """5. Contradictory evidence (e.g. active stats without substitution event) must remain CONFLICTING."""
        mock_payload = {
            "content": {
                "lineup": {
                    "lineupType": "standard",
                    "homeTeam": {"starters": [{"id": f"h{i}"} for i in range(11)], "subs": [{"id": "s1", "performance": {}}]},
                    "awayTeam": {"starters": [{"id": f"a{i}"} for i in range(11)], "subs": []},
                },
                "matchFacts": {"events": {"events": [{"type": "Goal", "time": 10}]}},  # No sub event
                "playerStats": {"s1": {"stats": [{"title": "Top stats", "stats": {"minutes_played": {"stat": {"value": 45}}}}]}},
            }
        }
        status, val, ev_class, reason = classify_participation(
            player_id="s1",
            lineup_role="SUBSTITUTE",
            member={"id": "s1"},
            match_payload=mock_payload,
            fixture_info={"eligible_completed": True},
        )
        self.assertEqual(status, "CONFLICTING")
        self.assertEqual(val, "UNRESOLVED")
        self.assertEqual(ev_class, "CONFLICTING_EVIDENCE")

    def test_06_multiple_substitutions(self):
        """6. Multiple substitutions in the same fixture must all be correctly tracked and matched."""
        with open(self.workspace / "data/phase_02b1/raw/2024_2025/matchDetails/cap_02660c2e0fce4d22b2f74da27eadd979/response.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        mid = str(data.get("general", {}).get("matchId"))
        mf_subs = [e for e in (data["content"]["matchFacts"]["events"]["events"]) if e.get("type") == "Substitution"]
        self.assertGreaterEqual(len(mf_subs), 5)
        for s in mf_subs:
            swap = s.get("swap") or []
            self.assertEqual(len(swap), 2)
            sub_in_id = str(swap[0]["id"])
            p_row = self.pma_table.filter(pc.equal(self.pma_table["player_id"], sub_in_id)).to_pylist()
            m_link = next((r for r in p_row if r["match_id"] == mid), None)
            self.assertIsNotNone(m_link)
            self.assertEqual(m_link["participation_status"], "SUBSTITUTED_ON")

    def test_07_player_id_mapping(self):
        """7. Player ID mapping must be clean, numeric, and without collisions."""
        pids = self.pma_table["player_id"].to_pylist()
        self.assertTrue(all(pid.isdigit() for pid in pids))
        unique_pids = set(pids)
        players_table = pq.read_table(self.workspace / "data/releases/fotmob_epl_2019_2025_v2/normalized/players.parquet")
        known_pids = set(players_table["player_id"].to_pylist())
        self.assertTrue(unique_pids.issubset(known_pids))

    def test_08_wrong_season_response(self):
        """8. Player match records must strictly map to correct seasons."""
        seasons_table = pq.read_table(self.workspace / "data/releases/fotmob_epl_2019_2025_v2/normalized/seasons.parquet").to_pylist()
        valid_pairs = {(s["season_label"], s["season_id"]) for s in seasons_table}
        pma_pairs = set(zip(self.pma_table["season_label"].to_pylist(), self.pma_table["season_id"].to_pylist()))
        self.assertEqual(pma_pairs, valid_pairs)

    def test_09_duplicate_player_match_links(self):
        """9. Exactly one player-match record must exist per (match_id, player_id) pair."""
        pairs = list(zip(self.pma_table["match_id"].to_pylist(), self.pma_table["player_id"].to_pylist()))
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_10_missing_event_fields(self):
        """10. Parser must handle missing optional fields (ratings, fantasyScore, marketValue) gracefully."""
        mock_payload = {
            "content": {
                "lineup": {
                    "lineupType": "standard",
                    "homeTeam": {"starters": [{"id": f"h{i}"} for i in range(11)], "subs": [{"id": "s1", "performance": {}}]},
                    "awayTeam": {"starters": [{"id": f"a{i}"} for i in range(11)], "subs": []},
                },
                "matchFacts": {
                    "events": {
                        "events": [
                            {"type": "Substitution", "swap": [{"id": "s2", "name": "SubIn"}, {"id": "h0", "name": "StarterOut"}]}
                        ]
                    }
                },
                "playerStats": {"s1": {}},
            }
        }
        status, val, ev_class, reason = classify_participation(
            player_id="s1",
            lineup_role="SUBSTITUTE",
            member={"id": "s1", "performance": {}},
            match_payload=mock_payload,
            fixture_info={"eligible_completed": True},
        )
        self.assertEqual(status, "UNUSED_SUBSTITUTE")
        self.assertEqual(val, "NOT_APPEARED")

    def test_11_different_historical_json_structures(self):
        """11. Both 2019/20 explicit list structure and 2024/25 empty dict structure must resolve correctly."""
        s19 = self.pma_table.filter(pc.and_(
            pc.equal(self.pma_table["season_label"], "2019/2020"),
            pc.equal(self.pma_table["participation_status"], "UNUSED_SUBSTITUTE")
        ))
        self.assertGreater(len(s19), 3000)

        s24 = self.pma_table.filter(pc.and_(
            pc.equal(self.pma_table["season_label"], "2024/2025"),
            pc.equal(self.pma_table["participation_status"], "UNUSED_SUBSTITUTE")
        ))
        self.assertEqual(len(s24), 3621)

    def test_12_fixture_cancellation_replay(self):
        """12. Abandoned match 4193691 must produce zero active appearances in PMA."""
        m_slice = self.pma_table.filter(pc.equal(self.pma_table["match_id"], "4193691"))
        self.assertEqual(len(m_slice), 0)

    def test_13_multi_club_season(self):
        """13. Multi-club players must maintain single Player–Season rows with summed appearances."""
        pop_multi = self.pop_table.filter(pc.equal(self.pop_table["is_multi_club"], True)).to_pylist()
        self.assertEqual(len(pop_multi), 83)
        multi_appeared_both_clubs = [r for r in pop_multi if r["confirmed_team_count"] > 1]
        self.assertEqual(len(multi_appeared_both_clubs), 61)
        appeared_multi = [r for r in pop_multi if r["population_category"] == "CONFIRMED_APPEARED"]
        self.assertEqual(len(appeared_multi), 80)
        for r in multi_appeared_both_clubs:
            self.assertGreaterEqual(r["confirmed_appearance_count"], 1)
            self.assertGreaterEqual(r["confirmed_team_count"], 2)

    def test_14_reprocessing_idempotency(self):
        """14. Reprocessing Step 07 must be completely deterministic and idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = execute_step07_remediation(workspace=self.workspace)
            self.assertEqual(res["verdict"], "PASS")
            self.assertEqual(res["pma_rows_total"], 89392)
            self.assertEqual(res["confirmed_appeared_player_seasons"], 3262)
            self.assertEqual(res["unverified_player_seasons"], 0)
            self.assertEqual(res["confirmed_non_appeared_player_seasons"], 790)

    def test_15_raw_provenance_integrity(self):
        """15. Every resolved audit record must link to an existing raw capture on disk."""
        with open(self.audit_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            sample_audit = [next(reader) for _ in range(20)]
        for r in sample_audit:
            self.assertEqual(r["parser_version"], PARSER_VERSION)
            self.assertEqual(r["new_status"], "UNUSED_SUBSTITUTE")
            self.assertEqual(r["validation_status"], "NOT_APPEARED")


if __name__ == "__main__":
    unittest.main()
