"""Execution 01 manifest, cache, dependency and batch-gate regressions."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.collection.batch_quality import batch_decision, inspect_capture
from src.collection.collection_config import ROOT
from src.collection.full_manifest import Manifest, load_full_config, seed_manifest
from src.collection.full_season_gate import validate_full_season
from src.collection.full_orchestrator import run
from src.collection.normalize_pilot import schemas
from src.collection.source_registry import SourceRegistry, load_hardening_config


class Execution01Tests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_full_config()

    def test_six_season_manifest_dag_and_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Manifest(Path(temp) / "manifest.sqlite")
            try:
                plan = seed_manifest(manifest, self.cfg)
                self.assertEqual(manifest.counts()["total"], 2346)
                self.assertEqual({r["finished_match_tasks"] for r in plan.values()}, {380})
                season = manifest.all_tasks("2023/2024")
                match = [t for t in season if t["resource_type"] == "MATCH_DETAIL"]
                ids = {str(t["params"]["matchId"]) for t in match}
                self.assertNotIn("4193691", ids)
                self.assertIn("4421797", ids)
                index = next(t for t in season if t["resource_type"] == "MATCH_INDEX_GATE")
                board = [t for t in season if t["resource_type"] == "CANDIDATE_LEADERBOARD"]
                population = next(t for t in season if t["resource_type"] == "POPULATION_GATE")
                self.assertTrue(all(t["dependencies"] == [index["task_id"]] for t in match))
                self.assertEqual(len(population["dependencies"]), 383)
                self.assertTrue({t["task_id"] for t in match + board}.issubset(population["dependencies"]))
                self.assertFalse(manifest.dependencies_ready(population["task_id"]))
                seed_manifest(manifest, self.cfg)
                self.assertEqual(manifest.counts()["total"], 2346)
            finally:
                manifest.close()

    def test_dynamic_append_preserves_identity_and_state(self):
        with tempfile.TemporaryDirectory() as temp:
            m = Manifest(Path(temp) / "manifest.sqlite")
            try:
                parent = m.add("2019/2020", 14022, "B", "POPULATION_GATE", context={"identity": "pop"})
                profile = m.add("2019/2020", 14022, "D", "PLAYER_PROFILE", "playerData",
                                {"id": 108038}, {"identity": "profile_108038"}, [parent])
                self.assertEqual(profile, m.add("2019/2020", 14022, "D", "PLAYER_PROFILE", "playerData",
                                                {"id": 108038}, {"identity": "profile_108038"}, [parent]))
                self.assertEqual(m.counts()["total"], 2)
                m.transition(parent, "FETCHED", raw_path="example.json", attempt_increment=2)
                self.assertFalse(m.dependencies_ready(profile))
                m.transition(parent, "VALIDATED", validation="season population checked")
                self.assertTrue(m.dependencies_ready(profile))
                self.assertEqual(m.task(parent)["attempt_count"], 2)
                self.assertEqual(m.task(parent)["raw_evidence_refs"], ["example.json"])
                with self.assertRaisesRegex(ValueError, "identity collision"):
                    m.add("2019/2020", 14022, "D", "PLAYER_PROFILE", "playerData",
                          {"id": 108038}, {"identity": "profile_108038", "changed": True}, [parent])
            finally:
                m.close()

    def test_real_cached_league_and_saves_have_valid_quality(self):
        registry = SourceRegistry(load_hardening_config())
        with tempfile.TemporaryDirectory() as temp:
            m = Manifest(Path(temp) / "manifest.sqlite")
            try:
                season = "2019/2020"
                league_id = m.add(season, 14022, "A", "SEASON_FIXTURES", "leagues",
                                  {"id": 47, "season": season}, {"identity": "league_47"})
                board_id = m.add(season, 14022, "C", "CANDIDATE_LEADERBOARD", "leagueseasondeepstats",
                                 {"id": 47, "season": 14022, "type": "players", "stat": "saves"},
                                 {"identity": "saves"}, [league_id])
                for ident in (league_id, board_id):
                    task = m.task(ident)
                    meta, payload = registry.lookup(task["endpoint"], task["params"], season)
                    self.assertEqual(inspect_capture(task, meta, payload)["decision"], "VALIDATED")
                self.assertEqual(batch_decision([inspect_capture(m.task(board_id), *registry.lookup(
                    "leagueseasondeepstats", m.task(board_id)["params"], season))], self.cfg)["decision"], "PASS")
            finally:
                m.close()

    def test_wrong_season_and_corrupt_raw_stop_batch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase_02b1") as temp:
            self.assertTrue(Path(temp).resolve().is_relative_to(ROOT.resolve()))
            m = Manifest(Path(temp) / "manifest.sqlite")
            try:
                ident = m.add("2019/2020", 14022, "A", "SEASON_FIXTURES", "leagues",
                              {"id": 47, "season": "2019/2020"}, {"identity": "league_47"})
                task = m.task(ident)
                payload = {"details": {"selectedSeason": "2024/2025"}, "fixtures": {"allMatches": [{"id": 1}]}}
                body = json.dumps(payload).encode()
                path = Path(temp) / "response.json"
                path.write_bytes(body)
                meta = {"raw_path": path.relative_to(ROOT).as_posix(), "content_sha256": hashlib.sha256(body).hexdigest(),
                        "capture_id": "cap_test", "collected_at_utc": "2026-11-02T00:00:00Z",
                        "source_url": "https://example.test/leagues", "request_key": task["request_key"],
                        "endpoint": "leagues", "season_label": "2019/2020", "season_id": 14022,
                        "params": task["params"], "http_status": 200, "content_type": "application/json"}
                wrong = inspect_capture(task, meta, payload)
                self.assertEqual(wrong["error_classification"], "HISTORICAL_SCOPE_MISMATCH")
                self.assertEqual(batch_decision([wrong], self.cfg)["decision"], "STOP")
                path.write_bytes(b"corrupted")
                corrupt = inspect_capture(task, meta, payload)
                self.assertEqual(corrupt["error_classification"], "RAW_CORRUPTION")
                self.assertEqual(batch_decision([corrupt], self.cfg)["decision"], "STOP")
            finally:
                m.close()

    def test_cache_only_runner_resumes_without_http(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase_02b1") as temp:
            self.assertTrue(Path(temp).resolve().is_relative_to(ROOT.resolve()))
            cfg = dict(self.cfg)
            cfg.update({"report_dir": (Path(temp) / "reports").relative_to(ROOT).as_posix(),
                        "raw_dir": (Path(temp) / "raw").relative_to(ROOT).as_posix(),
                        "quarantine_dir": (Path(temp) / "quarantine").relative_to(ROOT).as_posix(),
                        "log_path": (Path(temp) / "requests.jsonl").relative_to(ROOT).as_posix()})
            m = Manifest(Path(temp) / "manifest.sqlite")
            try:
                m.add("2019/2020", 14022, "A", "SEASON_FIXTURES", "leagues",
                      {"id": 47, "season": "2019/2020"}, {"identity": "league_47"})
                first = run(cfg, m, season="2019/2020", stage="A", batch_size=1,
                            resume=False, execute=False, max_requests=0)
                self.assertEqual(first["http_attempts"], 0)
                self.assertEqual(first["batch_decision"]["validated"], 1)
                second = run(cfg, m, season="2019/2020", stage="A", batch_size=1,
                             resume=True, execute=False, max_requests=0)
                self.assertEqual(second["batch_decision"]["task_count"], 0)
                self.assertEqual(m.counts()["by_state"], {"VALIDATED": 1})
                interrupted = m.add("2019/2020", 14022, "D", "PLAYER_PROFILE", "playerData",
                                    {"id": 999999999}, {"identity": "interrupted_profile"})
                m.transition(interrupted, "RUNNING", note="simulated process interruption")
                resumed = run(cfg, m, season="2019/2020", stage="D", batch_size=1,
                              resume=True, execute=False, max_requests=0)
                self.assertEqual(resumed["http_attempts"], 0)
                self.assertEqual(m.task(interrupted)["execution_state"], "RETRY_PENDING")
            finally:
                m.close()

    def test_full_season_gate_rejects_partial_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase_02b1") as temp:
            cfg = dict(self.cfg)
            cfg.update({"normalized_dir": (Path(temp) / "normalized").relative_to(ROOT).as_posix(),
                        "checkpoint_dir": (Path(temp) / "checkpoints").relative_to(ROOT).as_posix()})
            result = validate_full_season(cfg, "2019/2020", None, None)
            self.assertEqual(len(result["issues"]), 8)
            self.assertIn("Missing full-season table: matches", result["issues"])
            self.assertIn("Missing complete appeared-population checkpoint", result["issues"])

    def test_full_season_gate_requires_real_raw_lineups(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase_02b1") as temp:
            cfg = dict(self.cfg)
            cfg.update({"normalized_dir": (Path(temp) / "normalized").relative_to(ROOT).as_posix(),
                        "checkpoint_dir": (Path(temp) / "checkpoints").relative_to(ROOT).as_posix()})
            season_folder = Path(temp) / "normalized/2019_2020"
            season_folder.mkdir(parents=True)
            for name, schema in schemas().items():
                pq.write_table(pa.Table.from_pylist([], schema=schema), season_folder / f"{name}.parquet")
            checkpoint = Path(temp) / "checkpoints/2019_2020/appeared_population.json"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_text(json.dumps({"season_label": "2019/2020", "validated_match_count": 380,
                                              "appeared_match_links": [], "appeared_relations": [],
                                              "appeared_player_ids": []}), encoding="utf-8")
            registry = SourceRegistry(load_hardening_config())
            result = validate_full_season(cfg, "2019/2020", registry, registry)
            self.assertTrue(any("Missing raw match detail" in issue for issue in result["issues"]))
            self.assertTrue(any("Population checkpoint differs from raw lineups" in issue
                                for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
