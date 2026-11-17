"""Curated metric and raw-integrity regression checks."""
import csv
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.execution05_acceptance import OUT, REPORT


class Execution05AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = pq.read_table(OUT / "player_season_metrics_wide.parquet").to_pylist()

    def test_wide_unique_grain(self):
        self.assertEqual(len(self.rows), len({(r["season_id"], r["player_id"]) for r in self.rows}))

    def test_conflict_is_null_and_traced(self):
        conflict = next(r for r in self.rows if r["s_rating"] == "CONFLICTING")
        self.assertIsNone(conflict["m_rating"])
        self.assertTrue(conflict["stats_raw_path"])

    def test_missing_not_zero(self):
        row = next(r for r in self.rows if r["s_key_passes"] == "UNSUPPORTED")
        self.assertIsNone(row["m_key_passes"])

    def test_unconfirmed_population_not_stat_filled(self):
        row = next(r for r in self.rows if r["population_status"] != "APPEARED")
        self.assertEqual(row["s_appearances"], "NOT_COLLECTED_UNVERIFIED_APPEARANCE")
        self.assertIsNone(row["m_appearances"])

    def test_raw_audit_rejected_attempts_not_promoted(self):
        with (REPORT / "raw_integrity_report.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(any(r["semantic_status"] == "REJECTED" for r in rows))
        self.assertTrue(all(r["integrity_status"] == "VERIFIED" for r in rows))
