"""Unit and regression tests for Phase 2B.1-R Steps 03 & 04.

Validates:
  - Step 03: Confirmed appearance from starting lineup, confirmed substitution-on,
    unused substitute handling, unobserved bench evidence (unverified), season-level
    nonappearance inference, conflicting appearance detection, multi-club summing
    and deduplication, historical scope mismatch rejection, partition completeness.
  - Step 04: Legacy quality gate migration to SUPERSEDED, metadata validation,
    missing gate replacement detection, DAG dependency validation, manifest migration idempotency.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.full_manifest import Manifest, STATES, SATISFIED
from src.collection.remediation_population import (
    segment_player_seasons,
    execute_step03_remediation
)
from src.collection.remediation_manifest import (
    migrate_collection_manifest,
    execute_step04_remediation
)


class RemediationSteps0304Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = ROOT / "data/phase_02b1/remediation"
        cls.report_dir = ROOT / "reports/phase_02b1_remediation"
        cls.manifest_path = ROOT / "data/phase_02b1/manifests/collection_manifest_v2b1r.sqlite"
        
        # Load tables
        cls.complete_pq = cls.data_dir / "complete_player_season_classification.parquet"
        cls.appeared_pq = cls.data_dir / "confirmed_appeared_player_seasons.parquet"
        cls.unverified_pq = cls.data_dir / "unverified_player_seasons.parquet"
        cls.non_appeared_pq = cls.data_dir / "non_appeared_player_seasons.parquet"

        cls.complete_rows = pq.read_table(cls.complete_pq).to_pylist() if cls.complete_pq.exists() else []

    def test_01_confirmed_appearance_from_starting_lineup(self):
        """Verified starting lineup listing must yield CONFIRMED_APPEARED with started_match_count >= 1."""
        starters = [r for r in self.complete_rows if r["started_match_count"] > 0]
        self.assertGreater(len(starters), 0)
        for r in starters[:50]:
            self.assertEqual(r["population_category"], "CONFIRMED_APPEARED")
            self.assertGreaterEqual(r["confirmed_appearance_count"], r["started_match_count"])

    def test_02_confirmed_substitution_on(self):
        """Verified substitution-on listing must yield CONFIRMED_APPEARED."""
        sub_ins = [r for r in self.complete_rows if r["sub_in_match_count"] > 0]
        self.assertGreater(len(sub_ins), 0)
        for r in sub_ins[:50]:
            self.assertEqual(r["population_category"], "CONFIRMED_APPEARED")
            self.assertGreaterEqual(r["confirmed_appearance_count"], 1)

    def test_03_unused_substitute_handling(self):
        """Unused substitutes must be counted in unused_substitute_count and not silently dropped."""
        with_unused = [r for r in self.complete_rows if r["unused_substitute_count"] > 0]
        self.assertGreater(len(with_unused), 0)
        # Players with only unused substitutes and 0 starts/subs/unresolved must be CONFIRMED_NON_APPEARED
        only_unused = [r for r in with_unused if r["confirmed_appearance_count"] == 0 and r["unresolved_substitute_count"] == 0]
        self.assertEqual(len(only_unused), 204)
        for r in only_unused:
            self.assertEqual(r["population_category"], "CONFIRMED_NON_APPEARED")

    def test_04_incomplete_match_evidence_unverified(self):
        """Unobserved bench listings with 0 appearances must yield UNVERIFIED, not non-appeared."""
        unverified = [r for r in self.complete_rows if r["population_category"] == "UNVERIFIED"]
        self.assertEqual(len(unverified), 586)
        for r in unverified:
            self.assertEqual(r["confirmed_appearance_count"], 0)
            self.assertGreaterEqual(r["unresolved_substitute_count"], 1)
            self.assertIn("nonparticipation cannot be conclusively established", r["classification_reason"])

    def test_05_season_level_nonappearance_inference(self):
        """Player with 0 appearances and complete negative evidence must be CONFIRMED_NON_APPEARED."""
        non_appeared = [r for r in self.complete_rows if r["population_category"] == "CONFIRMED_NON_APPEARED"]
        self.assertEqual(len(non_appeared), 204)
        for r in non_appeared:
            self.assertEqual(r["confirmed_appearance_count"], 0)
            self.assertEqual(r["unresolved_substitute_count"], 0)
            self.assertGreaterEqual(r["unused_substitute_count"], 1)
            self.assertIn("UNUSED_SUBSTITUTE", r["classification_reason"])

    def test_06_conflicting_appearance_evidence(self):
        """Discrepancies between base summary status and matchday evidence must be flagged CONFLICTING."""
        # Verify that in release v2 there are zero conflicting records
        conflicting = [r for r in self.complete_rows if r["population_category"] == "CONFLICTING"]
        self.assertEqual(len(conflicting), 0)

    def test_07_multi_club_players_grain_and_summing(self):
        """Multi-club players must maintain single Player-Season grain with summed appearances."""
        mc_rows = [r for r in self.complete_rows if r["is_multi_club"]]
        self.assertEqual(len(mc_rows), 83)
        
        # Confirmed multi-club players (played for >1 club in a season)
        mc_played = [r for r in mc_rows if r["confirmed_team_count"] > 1]
        self.assertEqual(len(mc_played), 61)

        # Check a specific multi-club player (Jesse Lingard in 2020/21: player_id 299215)
        lingard = next((r for r in self.complete_rows if r["player_id"] == "299215" and r["season_label"] == "2020/2021"), None)
        self.assertIsNotNone(lingard)
        self.assertTrue(lingard["is_multi_club"])
        self.assertEqual(lingard["confirmed_appearance_count"], 16)
        self.assertIn("8654", lingard["team_ids"])  # West Ham
        self.assertIn("10260", lingard["team_ids"])  # Man Utd

    def test_08_duplicate_player_season_rejection(self):
        """Player-Season primary key (season_id, player_id) must be strictly unique."""
        keys = [(r["season_id"], r["player_id"]) for r in self.complete_rows]
        self.assertEqual(len(keys), len(set(keys)), "Duplicate (season_id, player_id) detected in classification!")

    def test_09_historical_scope_mismatch_rejection(self):
        """Appearances from abandoned or ineligible fixtures must not inflate appearance counts."""
        # Match 4193691 (Bournemouth vs Luton, abandoned) must not be counted as a completed fixture
        pma = pq.read_table(ROOT / "data/releases/fotmob_epl_2019_2025_v2/normalized/player_match_appearances.parquet").to_pylist()
        abandoned_in_pma = [r for r in pma if r["match_id"] == "4193691"]
        self.assertEqual(len(abandoned_in_pma), 0, "Abandoned fixture 4193691 must not exist in player_match_appearances")

    def test_10_population_partition_completeness(self):
        """Exhaustive mutual exclusivity: sum of 4 partitions must exactly equal 4,052."""
        appeared = pq.read_table(self.appeared_pq).num_rows
        unverified = pq.read_table(self.unverified_pq).num_rows
        non_appeared = pq.read_table(self.non_appeared_pq).num_rows
        complete = pq.read_table(self.complete_pq).num_rows

        self.assertEqual(appeared, 3262)
        self.assertEqual(unverified, 586)
        self.assertEqual(non_appeared, 204)
        self.assertEqual(complete, 4052)
        self.assertEqual(appeared + unverified + non_appeared, 4052)

    def test_11_superseded_gate_migration_and_fields(self):
        """All 12 legacy gates must be SUPERSEDED with full replacement metadata."""
        conn = sqlite3.connect(self.manifest_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE execution_state = 'PLANNED'")
        planned_cnt = cursor.fetchone()[0]
        self.assertEqual(planned_cnt, 0, "No tasks should remain in PLANNED state in v2b1r manifest")

        cursor.execute("""
            SELECT task_id, season_label, resource_type, execution_state, validation_result, context_json
            FROM tasks
            WHERE execution_state = 'SUPERSEDED'
        """)
        superseded_rows = cursor.fetchall()
        self.assertEqual(len(superseded_rows), 12)

        for row in superseded_rows:
            tid, season, rtype, state, val, ctx_str = row
            self.assertEqual(state, "SUPERSEDED")
            self.assertEqual(val, "SUPERSEDED_BY_EXECUTION05_ACCEPTANCE")
            ctx = json.loads(ctx_str)
            self.assertEqual(ctx.get("superseded_status"), "SUPERSEDED")
            self.assertIn("replacement_mechanism", ctx)
            self.assertIn("replacement_checkpoint", ctx)
            self.assertIn("migration_timestamp_utc", ctx)

        conn.close()

    def test_12_missing_gate_replacement_detection(self):
        """Gate replacement must reference existing execution05 evidence files."""
        checkpoint = ROOT / "reports/phase_02b1/execution05_checkpoint.json"
        self.assertTrue(checkpoint.is_file(), "Execution 05 checkpoint file must exist")
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertIn("season_acceptance", data)
        for season in ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025"):
            self.assertEqual(data["season_acceptance"].get(season), "CONDITIONAL_PASS")

    def test_13_gate_dependency_validation(self):
        """Predecessors of NORMALIZATION_GATE must be VALIDATED; SEASON_ACCEPTANCE_GATE has 0 dependents."""
        conn = sqlite3.connect(self.manifest_path)
        cursor = conn.cursor()

        # Check NORMALIZATION_GATE predecessors
        cursor.execute("SELECT task_id FROM tasks WHERE resource_type = 'NORMALIZATION_GATE'")
        norm_tids = [r[0] for r in cursor.fetchall()]
        for ntid in norm_tids:
            cursor.execute("SELECT depends_on FROM dependencies WHERE task_id = ?", (ntid,))
            parent_ids = [r[0] for r in cursor.fetchall()]
            self.assertEqual(len(parent_ids), 4)
            for pid in parent_ids:
                cursor.execute("SELECT execution_state FROM tasks WHERE task_id = ?", (pid,))
                p_state = cursor.fetchone()[0]
                self.assertIn(p_state, ("VALIDATED", "NORMALIZED", "ACCEPTED", "SUPERSEDED"))

        # Check SEASON_ACCEPTANCE_GATE dependents
        cursor.execute("SELECT task_id FROM tasks WHERE resource_type = 'SEASON_ACCEPTANCE_GATE'")
        acc_tids = [r[0] for r in cursor.fetchall()]
        for atid in acc_tids:
            cursor.execute("SELECT task_id FROM dependencies WHERE depends_on = ?", (atid,))
            children = cursor.fetchall()
            self.assertEqual(len(children), 0, "SEASON_ACCEPTANCE_GATE must have 0 downstream dependents")

        conn.close()

    def test_14_manifest_migration_idempotency(self):
        """Running manifest migration repeatedly must be safe and idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_manifest.sqlite"
            import shutil
            shutil.copy2(self.manifest_path, temp_db)

            # Re-run migration on already-migrated database
            res = migrate_collection_manifest(temp_db, [temp_db], Path(tmpdir))
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["tasks_migrated"], 0)
            self.assertEqual(res["total_superseded_in_registry"], 12)


if __name__ == "__main__":
    unittest.main()

