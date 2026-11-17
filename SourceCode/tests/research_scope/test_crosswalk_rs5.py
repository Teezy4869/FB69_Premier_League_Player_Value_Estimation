"""G3: the rs5 crosswalk was rebuilt from in-scope evidence, keeps every identity, and keeps unresolved ones unresolved."""
from __future__ import annotations

import csv
import json
import unittest

import duckdb
import pyarrow.parquet as pq

from src.phase3.entity_resolution import MAPPED_STATUSES, validate_crosswalk
from src.phase3.tm_common import file_hash
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5
from src.research_scope.entity_resolution_rs5 import HISTORICAL_RUN, OUT, RUN_DIR, VALIDATION_OUT, scoped_load_inputs
from src.research_scope.scope import load_scope


class CrosswalkRs5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = pq.read_table(RUN_DIR / "player_crosswalk.parquet").to_pylist()
        cls.by_id = {r["fotmob_player_id"]: r for r in cls.rows}
        cls.manifest = json.loads((OUT / "crosswalk_rs5_manifest.json").read_text(encoding="utf-8"))
        cls.universe = set(pq.read_table(FOTMOB_RS5 / "normalized/confirmed_appeared_player_seasons.parquet", columns=["player_id"])["player_id"].to_pylist())

    def test_universe_is_exactly_the_rs5_population(self):
        self.assertEqual(set(self.by_id), self.universe)
        self.assertEqual(len(self.rows), 1228)

    def test_integrity_rules_hold(self):
        self.assertFalse(any(validate_crosswalk(self.rows).values()))

    def test_status_counts(self):
        counts = {}
        for r in self.rows:
            counts[r["match_status"]] = counts.get(r["match_status"], 0) + 1
        self.assertEqual(counts, {"AUTO_EXACT": 1190, "AUTO_ADJUDICATED": 36, "REVIEW_REQUIRED": 2})
        self.assertEqual(sum(r["player_season_rows"] for r in self.rows), 2747)
        self.assertFalse(any(r["match_status"] == "MANUAL_CONFIRMED" or r["reviewer"] for r in self.rows), "no human review exists")

    def test_unresolved_identities_stay_unresolved(self):
        unresolved = {r["fotmob_player_id"] for r in self.rows if r["match_status"] not in MAPPED_STATUSES}
        self.assertEqual(unresolved, {"982620", "1188035"})
        self.assertTrue(all(self.by_id[f]["transfermarkt_player_id"] is None for f in unresolved))

    def test_adjudications_are_automated_not_human(self):
        adjudicated = [r for r in self.rows if r["match_status"] == "AUTO_ADJUDICATED"]
        self.assertTrue(all(r["adjudicator"] and r["adjudicator"].startswith("automated") and not r["reviewer"] for r in adjudicated))

    def test_no_in_scope_mapping_changed(self):
        historical = {r["fotmob_player_id"]: r for r in pq.read_table(HISTORICAL_RUN / "player_crosswalk.parquet").to_pylist()}
        changed = [f for f in self.universe if (historical[f]["match_status"], historical[f]["transfermarkt_player_id"]) != (self.by_id[f]["match_status"], self.by_id[f]["transfermarkt_player_id"])]
        self.assertEqual(changed, [])
        self.assertEqual(self.manifest["comparison_with_matching_v2_1"]["mapping_changes"], [])

    def test_evidence_inputs_are_scoped(self):
        con = duckdb.connect()
        scoped_load_inputs(con)
        scope = load_scope()
        self.assertEqual({r[0] for r in con.execute("SELECT DISTINCT season FROM t_games").fetchall()}, set(scope.tm_start_years))
        self.assertEqual({r[0] for r in con.execute("SELECT DISTINCT season_start_year FROM t_pcs").fetchall()}, set(scope.tm_start_years))
        self.assertEqual(con.execute("SELECT count(*) FROM t_app ANTI JOIN t_games USING (game_id)").fetchone()[0], 0)
        self.assertEqual({r[0] for r in con.execute("SELECT DISTINCT season_label FROM f_conf").fetchall()}, set(scope.labels))
        self.assertTrue(all(label in scope.labels for label in self.manifest["run_summary"]["status_by_season"]))

    def test_validation_labels_cover_mapped_identities(self):
        with VALIDATION_OUT.open(encoding="utf-8-sig", newline="") as handle:
            labels = list(csv.DictReader(handle))
        self.assertEqual(len(labels), 1226)
        self.assertEqual({r["label"] for r in labels} - {"CONFIRMED_MATCH", "INCONCLUSIVE"}, set(), "no CONFIRMED_NON_MATCH among mapped identities")
        self.assertTrue(all(r["human_reviewed"] == "False" for r in labels))

    def test_manifest_hashes(self):
        for rel, sha in self.manifest["output_sha256"].items():
            if rel.startswith("matching_v2_1_rs5__reviews_none/") and rel.endswith(("run_manifest.json",)):
                continue
            self.assertEqual(file_hash(OUT / rel), sha, rel)


if __name__ == "__main__":
    unittest.main()
