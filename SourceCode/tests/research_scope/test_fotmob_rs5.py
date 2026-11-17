"""G2: the rs5 FotMob research release is in scope, unchanged per row, complete, and traceable."""
from __future__ import annotations

import csv
import json
import unittest

import duckdb
import pyarrow.parquet as pq

from src.phase3.tm_common import FOTMOB_RELEASE, file_hash, verify_fotmob_unchanged
from src.research_scope.build_fotmob_rs5 import KEYS, RELEASE
from src.research_scope.scope import check_parquet, load_scope

EXPECTED_CONFIRMED = {"2020/2021": 524, "2021/2022": 537, "2022/2023": 554, "2023/2024": 570, "2024/2025": 562}


class FotmobRs5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = load_scope()
        cls.manifest = json.loads((RELEASE / "metadata/release_manifest.json").read_text(encoding="utf-8"))
        cls.con = duckdb.connect()

    def rel(self, name: str) -> str:
        return f"read_parquet('{(RELEASE / (name + '.parquet')).as_posix()}')"

    def one(self, sql: str):
        return self.con.execute(sql).fetchone()[0]

    def test_manifest_hashes_and_inventory(self):
        on_disk = {p.relative_to(RELEASE).as_posix() for p in RELEASE.rglob("*") if p.is_file() and p.name != "release_manifest.json"}
        self.assertEqual(on_disk, {f["path"] for f in self.manifest["files"]})
        for entry in self.manifest["files"]:
            self.assertEqual(file_hash(RELEASE / entry["path"]), entry["sha256"], entry["path"])
        self.assertEqual(self.manifest["seasons"], list(self.scope.labels))
        self.assertEqual(self.manifest["source"]["release_manifest_sha256"], file_hash(FOTMOB_RELEASE / "metadata/release_manifest.json"))

    def test_historical_release_unchanged(self):
        self.assertEqual(verify_fotmob_unchanged()["mismatches"], 0)

    def test_every_table_is_in_scope(self):
        for rel in KEYS:
            if rel == "normalized/players":
                continue
            cols = pq.read_schema(RELEASE / f"{rel}.parquet").names
            check_parquet(RELEASE / f"{rel}.parquet", self.scope, "season_label" if "season_label" in cols else None, "season_id",
                          require_all=rel != "normalized/confirmed_non_appeared_player_seasons")

    def test_every_csv_is_in_scope(self):
        for path in sorted(RELEASE.rglob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if rows and "season_label" in rows[0]:
                seasons = {r["season_label"] for r in rows} - {"TOTAL_RS5"}
                self.assertTrue(seasons <= set(self.scope.labels), f"{path.name}: {seasons}")
                self.assertFalse(seasons & set(self.scope.excluded_labels), path.name)

    def test_primary_keys_unique(self):
        for rel, key in KEYS.items():
            if key:
                self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT {', '.join(key)} FROM {self.rel(rel)} GROUP BY ALL HAVING count(*)>1)"), 0, rel)

    def test_rows_and_schema_equal_the_v3_1_slice(self):
        for rel in KEYS:
            self.assertEqual(pq.read_schema(RELEASE / f"{rel}.parquet").remove_metadata(), pq.read_schema(FOTMOB_RELEASE / f"{rel}.parquet").remove_metadata(), rel)
            src = f"read_parquet('{(FOTMOB_RELEASE / (rel + '.parquet')).as_posix()}')"
            scoped = f"(SELECT * FROM {src} WHERE season_id IN ({self.scope.sql_ids()}))" if rel != "normalized/players" else f"(SELECT * FROM {src} WHERE player_id IN (SELECT player_id FROM {self.rel(rel)}))"
            self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT * FROM {self.rel(rel)} EXCEPT ALL SELECT * FROM {scoped})"), 0, rel)
            self.assertEqual(self.one(f"SELECT count(*) FROM (SELECT * FROM {scoped} EXCEPT ALL SELECT * FROM {self.rel(rel)})"), 0, rel)

    def test_population_counts(self):
        got = dict(self.con.execute(f"SELECT season_label, count(*) FROM {self.rel('normalized/confirmed_appeared_player_seasons')} GROUP BY 1").fetchall())
        self.assertEqual(got, EXPECTED_CONFIRMED)
        self.assertEqual(self.one(f"SELECT count(DISTINCT player_id) FROM {self.rel('curated/confirmed_appeared_player_seasons')}"), 1228)
        self.assertEqual(self.one(f"SELECT count(*) FROM {self.rel('normalized/unverified_player_seasons')}"), 691)
        self.assertEqual(self.one(f"SELECT count(*) FROM {self.rel('normalized/matches')} WHERE match_status='COMPLETED'"), 1900)

    def test_missingness_semantics_preserved(self):
        """UNKNOWN stays UNKNOWN, null stays null, zero stays zero: counts equal the v3.1 slice per status and per metric."""
        src = f"read_parquet('{(FOTMOB_RELEASE / 'normalized/player_match_appearances.parquet').as_posix()}')"
        self.assertEqual(self.con.execute(f"SELECT participation_status, count(*) FROM {self.rel('normalized/player_match_appearances')} GROUP BY 1 ORDER BY 1").fetchall(),
                         self.con.execute(f"SELECT participation_status, count(*) FROM {src} WHERE season_id IN ({self.scope.sql_ids()}) GROUP BY 1 ORDER BY 1").fetchall())
        cur = f"read_parquet('{(FOTMOB_RELEASE / 'curated/confirmed_appeared_player_seasons.parquet').as_posix()}')"
        metrics = [c for c in pq.read_schema(RELEASE / "curated/confirmed_appeared_player_seasons.parquet").names if c.startswith("m_")]
        for m in metrics:
            sql = f'SELECT count(*) FILTER (WHERE "{m}" IS NULL), count(*) FILTER (WHERE "{m}"=0) FROM {{}}'
            self.assertEqual(self.con.execute(sql.format(self.rel("curated/confirmed_appeared_player_seasons"))).fetchone(),
                             self.con.execute(sql.format(f"(SELECT * FROM {cur} WHERE season_id IN ({self.scope.sql_ids()}))")).fetchone(), m)

    def test_season_data_provenance_never_points_to_excluded_season(self):
        """Profiles (player-level) may sit in a 2019_2020 capture folder; season data must not."""
        folders = [label.replace("/", "_") for label in self.scope.excluded_labels]
        checks = [("normalized/player_match_appearances", "raw_path"), ("normalized/metric_observations", "raw_path"), ("normalized/matches", "fixture_raw_path"),
                  ("normalized/historical_position_observations", "raw_path"), ("normalized/teams", "fixture_raw_path"), ("curated/confirmed_appeared_player_seasons", "stats_raw_path"),
                  ("normalized/substitution_evidence_registry", "raw_source_reference")]
        for rel, col in checks:
            for folder in folders:
                self.assertEqual(self.one(f"SELECT count(*) FROM {self.rel(rel)} WHERE {col} LIKE '%{folder}%'"), 0, f"{rel}.{col}")
            self.assertEqual(self.one(f"SELECT count(*) FROM {self.rel(rel)} WHERE {col} IS NULL"),
                             self.one(f"SELECT count(*) FROM read_parquet('{(FOTMOB_RELEASE / (rel + '.parquet')).as_posix()}') WHERE {col} IS NULL AND season_id IN ({self.scope.sql_ids()})"), f"{rel}.{col} nulls")

    def test_players_are_exactly_those_referenced(self):
        tables = [r for r in KEYS if r != "normalized/players" and "player_id" in pq.read_schema(RELEASE / f"{r}.parquet").names]
        union = " UNION ".join(f"SELECT player_id FROM {self.rel(t)}" for t in tables)
        self.assertEqual(self.one(f"SELECT count(*) FROM ({union})"), self.one(f"SELECT count(*) FROM {self.rel('normalized/players')}"))

    def test_recalculated_totals_and_conflicts(self):
        summary = json.loads((RELEASE / "metadata/canonical_summary_rs5.json").read_text(encoding="utf-8"))
        total = summary["population_by_season"][-1]
        self.assertEqual((total["confirmed_appeared"], total["unverified"], total["player_seasons"]), (2747, 691, 3438))
        self.assertEqual(summary["open_metric_conflicts"], 36)
        self.assertEqual(summary["metrics_without_any_value_in_scope"], ["key_passes"])
        with (RELEASE / "quality_reports/referential_integrity_report_rs5.csv").open(encoding="utf-8") as handle:
            self.assertTrue(all(r["status"] == "PASS" for r in csv.DictReader(handle)))

    def test_dictionary_has_no_six_season_counts(self):
        with (RELEASE / "manifests/metric_dictionary_rs5.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 53)
        self.assertNotIn("historical_seasons_with_values", rows[0])
        self.assertTrue(all(0 <= int(r["rs5_seasons_with_values"]) <= 5 for r in rows))

    def test_crawl_log_is_referenced_not_copied(self):
        self.assertFalse((RELEASE / "manifests/collection_manifest.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
