import csv
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.release_manifest import build_manifest, physical_inventory, verify_manifest, write_manifest
from src.collection.statistics_semantics import compute_metric_eligibility_registry


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.release = Path(self.tmp.name)
        (self.release / "normalized").mkdir()
        (self.release / "metadata").mkdir()
        pq.write_table(pa.table({"id": ["a", "b"]}), self.release / "normalized/sample.parquet")
        (self.release / "README.md").write_text("sample", encoding="utf-8")

    def manifest(self):
        return write_manifest(self.release, version="test_v2", parent_version="test_v1",
                              seasons=["2024/2025"], quality_status="CONDITIONAL_GO",
                              known_limitations=[], reproduction_commands=["python -m test"],
                              created_at="2026-01-01T00:00:00+00:00")

    def test_physical_rows_and_file_inventory(self):
        m = self.manifest()
        self.assertEqual(m["total_files"], 3)
        self.assertEqual(m["parquet_tables"], 1)
        self.assertEqual(m["tables"][0]["rows"], 2)
        self.assertEqual({r["path"] for r in m["files"]}, {"README.md", "normalized/sample.parquet"})
        verify_manifest(self.release)

    def test_unlisted_and_stale_files_rejected(self):
        self.manifest()
        (self.release / "new.txt").write_text("unlisted", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "RELEASE_INVENTORY_MISMATCH"):
            verify_manifest(self.release)
        (self.release / "new.txt").unlink()
        (self.release / "README.md").unlink()
        with self.assertRaisesRegex(ValueError, "RELEASE_INVENTORY_MISMATCH"):
            verify_manifest(self.release)

    def test_checksum_and_row_count_rejected(self):
        self.manifest()
        (self.release / "README.md").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "RELEASE_CHECKSUM_MISMATCH"):
            verify_manifest(self.release)
        (self.release / "README.md").write_text("sample", encoding="utf-8")
        path = self.release / "metadata/release_manifest.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        m["tables"][0]["rows"] = 99
        path.write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "RELEASE_TABLE_MISMATCH"):
            verify_manifest(self.release)

    def test_manifest_idempotent_except_creation_timestamp(self):
        first = self.manifest()
        first_bytes = (self.release / "metadata/release_manifest.json").read_bytes()
        second = self.manifest()
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, (self.release / "metadata/release_manifest.json").read_bytes())
        self.assertEqual(physical_inventory(self.release), physical_inventory(self.release))


class CorrectedEvidenceTests(unittest.TestCase):
    def test_fallback_and_revised_are_valid_coverage(self):
        wide = [{"season_label": "2024/2025", "season_id": "s", "player_id": "1", "population_status": "APPEARED",
                 "s_expected_assists": "OBSERVED_FALLBACK_LEADERBOARD", "m_expected_assists": 0.4,
                 "s_expected_goals": "OBSERVED_SOURCE_REVISED", "m_expected_goals": 1.0}]
        rules = [{"normalized_field": m, "applicable_positions": "ALL", "unit": "goals", "aggregation_type": "total"}
                 for m in ("expected_assists", "expected_goals")]
        registry, coverage = compute_metric_eligibility_registry(wide, [r["normalized_field"] for r in rules], rules, [], [{"season_id": "s", "season_label": "2024/2025"}])
        self.assertEqual([r["valid_values"] for r in coverage], [1, 1])
        self.assertTrue(all(r["coverage_fraction"] == 1.0 for r in coverage))

    def test_part1_population_partition_and_parent_hashes(self):
        report = ROOT / "reports/final_acceptance_fix"
        snap = json.loads((report / "release_preservation_snapshot.json").read_text(encoding="utf-8"))
        from src.collection.release_manifest import sha256
        self.assertTrue(all(sha256(ROOT / rel) == h for group in snap.values() for rel, h in group.items()))
        with (report / "corrected_population_reconciliation.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(sum(int(row["population_" + k]) for k in ("confirmed_appeared", "confirmed_non_appeared", "unverified", "conflicting")), int(row["player_seasons_total"]))

    def test_full_test_report_is_log_derived(self):
        report = ROOT / "reports/final_acceptance_fix"
        info = json.loads((report / "test_environment_report.json").read_text(encoding="utf-8"))
        log = (report / "full_test_execution.log").read_text(encoding="utf-8")
        self.assertIn(f"Ran {info['executed_tests']} tests", log)
        self.assertEqual(info["passed"] + info["failed"] + info["errored"] + info["skipped"], info["executed_tests"])

    def test_promoted_release_integrity_if_present(self):
        release = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
        if not release.exists():
            self.skipTest("release not promoted yet")
        manifest = verify_manifest(release)
        pop = pq.read_table(release / "normalized/complete_player_season_classification.parquet").to_pylist()
        appeared = pq.read_table(release / "normalized/confirmed_appeared_player_seasons.parquet").to_pylist()
        unknown = pq.read_table(release / "normalized/unverified_player_seasons.parquet").to_pylist()
        self.assertEqual(len(pop), len(appeared) + len(unknown))
        self.assertEqual(manifest["parent_release_version"], "fotmob_epl_2019_2025_v3")

    def test_season_reports_match_canonical_population(self):
        release = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
        if not release.exists():
            self.skipTest("release not promoted yet")
        summary = json.loads((release / "metadata/canonical_summary.json").read_text(encoding="utf-8"))
        for row in summary["population_by_season"]:
            path = release / "quality_reports" / f"season_{row['season_label'].replace('/', '_')}_acceptance.md"
            body = path.read_text(encoding="utf-8")
            self.assertIn(f"Confirmed appeared: {row['confirmed_appeared']}; confirmed non-appeared: {row['confirmed_non_appeared']}; unverified: {row['unverified']}.", body)
        self.assertEqual(sum(r["confirmed_appeared"] for r in summary["population_by_season"]),
                         pq.read_metadata(release / "normalized/confirmed_appeared_player_seasons.parquet").num_rows)

    def test_coverage_bounds_and_historical_window_metadata(self):
        release = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
        if not release.exists():
            self.skipTest("release not promoted yet")
        with (release / "quality_reports/cross_season_feature_coverage.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            eligible = int(row["eligible_players"])
            valid = int(row["valid_values"])
            self.assertLessEqual(valid, eligible)
            if eligible == 0:
                self.assertEqual(row["coverage_status"], "UNDEFINED")
                self.assertEqual(row["coverage_fraction"], "")
            else:
                self.assertLessEqual(float(row["coverage_fraction"]), 1.0)
        with (release / "quality_reports/historical_xg_xa_coverage_quality.csv").open(encoding="utf-8", newline="") as f:
            quality = list(csv.DictReader(f))
        self.assertEqual(len(quality), 12)
        self.assertTrue(all(r["coverage_window_status"] == "UNKNOWN_COVERAGE_WINDOW" for r in quality))
        self.assertTrue(all(not r["verified_window_start_utc"] and not r["verified_window_end_utc"] for r in quality))
        xa_quality = next(r for r in quality if r["season_label"] == "2019/2020" and r["metric_name"] == "expected_assists")
        xa_coverage = next(r for r in rows if r["season_label"] == "2019/2020" and r["metric_name"] == "expected_assists")
        self.assertEqual(xa_quality["observed_players"], xa_coverage["valid_values"])

    def test_confirmed_table_excludes_unverified(self):
        release = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
        if not release.exists():
            self.skipTest("release not promoted yet")
        confirmed = pq.read_table(release / "normalized/confirmed_appeared_player_seasons.parquet", columns=["population_category"]).to_pylist()
        self.assertTrue(all(r["population_category"] == "CONFIRMED_APPEARED" for r in confirmed))
        non = pq.read_table(release / "normalized/confirmed_non_appeared_player_seasons.parquet")
        self.assertEqual(len(non), 0)


if __name__ == "__main__":
    unittest.main()
