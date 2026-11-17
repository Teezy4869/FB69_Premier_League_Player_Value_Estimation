"""Unit tests for Phase 2B.1-R Steps 08 & 09: Release v3 Validation and Verification."""

import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
import pyarrow.parquet as pq
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_V3 = ROOT / "data" / "releases" / "fotmob_epl_2019_2025_v3"


class ReleaseV3AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v3_root = RELEASE_V3
        cls.normalized_dir = cls.v3_root / "normalized"
        cls.curated_dir = cls.v3_root / "curated"
        cls.manifests_dir = cls.v3_root / "manifests"
        cls.metadata_dir = cls.v3_root / "metadata"
        cls.quality_dir = cls.v3_root / "quality_reports"

    def test_01_release_structure_and_manifest_existence(self):
        """Release v3 directory must exist and contain required subdirectories and files."""
        self.assertTrue(self.v3_root.is_dir(), "Release v3 directory missing")
        self.assertTrue(self.normalized_dir.is_dir(), "normalized directory missing")
        self.assertTrue(self.curated_dir.is_dir(), "curated directory missing")
        self.assertTrue(self.manifests_dir.is_dir(), "manifests directory missing")
        self.assertTrue(self.metadata_dir.is_dir(), "metadata directory missing")
        self.assertTrue(self.quality_dir.is_dir(), "quality_reports directory missing")
        self.assertTrue((self.metadata_dir / "release_manifest.json").is_file(), "release_manifest.json missing")
        self.assertTrue((self.manifests_dir / "collection_manifest.sqlite").is_file(), "collection_manifest.sqlite missing")

    def test_02_sha256_checksum_verification(self):
        """All files registered in release_manifest.json must match their cryptographic SHA-256."""
        manifest_path = self.metadata_dir / "release_manifest.json"
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        for rel_path, file_meta in manifest.get("files", {}).items():
            full_path = self.v3_root / rel_path
            self.assertTrue(full_path.is_file(), f"Manifest file missing on disk: {rel_path}")
            hasher = hashlib.sha256()
            with full_path.open("rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha = hasher.hexdigest()
            self.assertEqual(
                actual_sha,
                file_meta["sha256"],
                f"SHA256 mismatch for {rel_path}: expected {file_meta['sha256']}, got {actual_sha}",
            )

    def test_03_normalized_table_exact_counts(self):
        """Normalized tables must meet strict exact row counts for Level 2+ dataset."""
        expected_counts = {
            "players.parquet": 1757,
            "teams.parquet": 120,
            "seasons.parquet": 6,
            "matches.parquet": 2281,
            "player_seasons.parquet": 4052,
            "player_team_seasons.parquet": 4135,
            "player_match_appearances.parquet": 89392,
            "metric_observations.parquet": 207043,
            "historical_position_observations.parquet": 151475,
        }
        for fname, exp_count in expected_counts.items():
            tbl_path = self.normalized_dir / fname
            tbl = pq.read_table(tbl_path)
            self.assertEqual(
                tbl.num_rows, exp_count, f"{fname} row count mismatch: expected {exp_count}, got {tbl.num_rows}"
            )

    def test_04_curated_table_exact_counts_and_dimensions(self):
        """Curated wide tables must have exact expected dimensions and non-empty columns."""
        conf_path = self.curated_dir / "confirmed_appeared_player_seasons.parquet"
        wide_path = self.curated_dir / "player_season_metrics_wide.parquet"

        t_conf = pq.read_table(conf_path)
        t_wide = pq.read_table(wide_path)

        self.assertEqual(t_conf.num_rows, 3262, f"confirmed_appeared rows mismatch: {t_conf.num_rows}")
        self.assertEqual(t_conf.num_columns, 114, f"confirmed_appeared cols mismatch: {t_conf.num_columns}")

        self.assertEqual(t_wide.num_rows, 4052, f"player_season_metrics_wide rows mismatch: {t_wide.num_rows}")
        self.assertEqual(t_wide.num_columns, 114, f"player_season_metrics_wide cols mismatch: {t_wide.num_columns}")

    def test_05_zero_unknown_appearances(self):
        """Zero UNKNOWN substitution/appearance records permitted in Release v3."""
        pma = pq.read_table(self.normalized_dir / "player_match_appearances.parquet")
        part_status = pma.column("participation_status").to_pylist()

        self.assertEqual(part_status.count("UNKNOWN"), 0, "Found UNKNOWN participation_status in PMA")

        # Starter: 50,160; Subbed-on: 15,628; Unused: 23,604
        self.assertEqual(part_status.count("STARTED"), 50160)
        self.assertEqual(part_status.count("SUBSTITUTED_ON"), 15628)
        self.assertEqual(part_status.count("UNUSED_SUBSTITUTE"), 23604)

    def test_06_zero_unverified_player_seasons(self):
        """Zero UNVERIFIED player-season records permitted in Release v3."""
        ps = pq.read_table(self.normalized_dir / "player_seasons.parquet")
        pop_status = ps.column("evidence_status").to_pylist()

        self.assertEqual(pop_status.count("UNVERIFIED"), 0, "Found UNVERIFIED in player_seasons")
        self.assertEqual(pop_status.count("UNKNOWN_PARTICIPATION"), 0, "Found UNKNOWN_PARTICIPATION in player_seasons")
        self.assertEqual(pop_status.count("APPEARED"), 3262)
        self.assertEqual(pop_status.count("UNUSED_SUBSTITUTE_ONLY"), 790)

    def test_07_coverage_anomalies_completely_resolved(self):
        """Cross-season feature coverage must have 318 cells, 0 anomalies, max coverage <= 100%."""
        cov_path = self.quality_dir / "cross_season_feature_coverage.csv"
        df_cov = pd.read_csv(cov_path)
        self.assertEqual(len(df_cov), 318, f"Coverage cells count mismatch: expected 318, got {len(df_cov)}")

        for _, row in df_cov.iterrows():
            metric = row["metric_name"]
            season = row["season_label"]
            valid_cnt = row["valid_values"]
            elig_cnt = row["eligible_players"]
            cov_ratio = row["coverage_fraction"]
            self.assertLessEqual(
                valid_cnt,
                elig_cnt,
                f"Coverage numerator > denominator for {metric} in {season}: {valid_cnt} > {elig_cnt}",
            )
            self.assertLessEqual(
                cov_ratio,
                1.000001,
                f"Coverage ratio > 100% for {metric} in {season}: {cov_ratio}",
            )

    def test_08_metric_reconciliation_verdict(self):
        """Step 05 reconciliation must reconcile 539 conflicts and preserve exactly 36 genuine conflicts as null."""
        recon_path = self.quality_dir / "metric_reconciliation_report.csv"
        df_recon = pd.read_csv(recon_path)
        self.assertEqual(len(df_recon), 575, f"Expected 575 conflicts inventoried, got {len(df_recon)}")

        genuine_conflicts = df_recon[df_recon["resolution_action"] == "PRESERVED_UNRESOLVED_NULL"]
        self.assertEqual(len(genuine_conflicts), 36, f"Expected 36 genuine conflicts, got {len(genuine_conflicts)}")

        resolved_conflicts = df_recon[df_recon["resolution_action"] != "PRESERVED_UNRESOLVED_NULL"]
        self.assertEqual(len(resolved_conflicts), 539, f"Expected 539 resolved conflicts, got {len(resolved_conflicts)}")

    def test_09_all_six_seasons_acceptance_pass(self):
        """All six seasonal acceptance reports must exist and indicate PASS status."""
        seasons = ["2019_2020", "2020_2021", "2021_2022", "2022_2023", "2023_2024", "2024_2025"]
        for s in seasons:
            rep_path = self.quality_dir / f"season_{s}_acceptance.md"
            self.assertTrue(rep_path.is_file(), f"Seasonal report missing: season_{s}_acceptance.md")
            content = rep_path.read_text(encoding="utf-8")
            self.assertIn("- **Acceptance Verdict:** **PASS**", content, f"Verdict not PASS in {rep_path.name}")

    def test_10_foreign_key_referential_integrity(self):
        """All foreign keys in Release v3 tables must resolve to valid primary keys."""
        p_ids = set(pq.read_table(self.normalized_dir / "players.parquet").column("player_id").to_pylist())
        t_ids = set(pq.read_table(self.normalized_dir / "teams.parquet").column("team_id").to_pylist())
        s_ids = set(pq.read_table(self.normalized_dir / "seasons.parquet").column("season_id").to_pylist())
        m_ids = set(pq.read_table(self.normalized_dir / "matches.parquet").column("match_id").to_pylist())

        # Check player_seasons
        ps = pq.read_table(self.normalized_dir / "player_seasons.parquet")
        for pid in ps.column("player_id").to_pylist():
            self.assertIn(pid, p_ids)
        for sid in ps.column("season_id").to_pylist():
            self.assertIn(sid, s_ids)

        # Check player_match_appearances
        pma = pq.read_table(self.normalized_dir / "player_match_appearances.parquet")
        for pid in pma.column("player_id").to_pylist():
            self.assertIn(pid, p_ids)
        for mid in pma.column("match_id").to_pylist():
            self.assertIn(mid, m_ids)
        for tid in pma.column("team_id").to_pylist():
            self.assertIn(tid, t_ids)

    def test_11_abandoned_fixture_quarantine_integrity(self):
        """Fixture 4193691 (Bournemouth vs Luton abandoned) must produce zero active appearances."""
        pma = pq.read_table(self.normalized_dir / "player_match_appearances.parquet")
        pma_df = pma.to_pandas()
        ab_apps = pma_df[pma_df["match_id"] == 4193691]
        self.assertEqual(len(ab_apps), 0, "Abandoned fixture 4193691 has active appearances in PMA")

    def test_12_historical_xa_recovery_counts(self):
        """Season 2019/20 xA must have exactly 96 recovered observations and 419 missing without zero filling."""
        wide_path = self.curated_dir / "confirmed_appeared_player_seasons.parquet"
        df_wide = pq.read_table(wide_path).to_pandas()
        s19 = df_wide[df_wide["season_label"] == "2019/2020"]
        self.assertEqual(len(s19), 515)

        # Check m_expected_assists valid values
        valid_xa = s19["m_expected_assists"].dropna()
        self.assertEqual(len(valid_xa), 96, f"Expected 96 valid xA in 2019/20, got {len(valid_xa)}")
        missing_xa = s19["m_expected_assists"].isna().sum()
        self.assertEqual(missing_xa, 419, f"Expected 419 missing xA in 2019/20, got {missing_xa}")


if __name__ == "__main__":
    unittest.main()
