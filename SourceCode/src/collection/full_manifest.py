"""Transactional, append-only task identities for Phase 2B.1 collection planning."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.collection.collection_config import EXPECTED_SEASONS, ROOT, load_config
from src.collection.foundation import PilotStore, json_bytes
from src.collection.historical_lineup_validator import fixture_lookup
from src.collection.source_registry import canonical_params, request_key

STAGES = ("A", "B", "C", "D", "E", "F", "G")
STATES = ("PLANNED", "RUNNING", "FETCHED", "VALIDATED", "NORMALIZED", "ACCEPTED",
          "RETRY_PENDING", "QUARANTINED", "FAILED", "BLOCKED", "SUPERSEDED")
SATISFIED = {"VALIDATED", "NORMALIZED", "ACCEPTED", "SUPERSEDED"}
MANIFEST_FIELDS = ["task_id", "request_key", "season_label", "season_id", "stage", "resource_type",
                   "endpoint", "parameters", "dependencies", "execution_state", "attempt_count",
                   "raw_evidence_refs", "validation_result", "error_classification",
                   "last_update_utc", "context"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_full_config(path: Path | None = None) -> dict:
    cfg = yaml.safe_load((path or ROOT / "configs/full_collection.yaml").read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("Full collection config must be a mapping")
    cfg["seasons"] = {str(k): int(v) for k, v in cfg["seasons"].items()}
    pilot = load_config()
    if tuple(cfg["seasons"]) != EXPECTED_SEASONS or cfg["seasons"] != pilot["seasons"] or cfg["league_id"] != 47:
        raise ValueError("Full collection season IDs differ from verified pilot evidence")
    if cfg["workers"] != 1 or cfg["min_request_interval_seconds"] < 1.2 or cfg["max_retries"] not in (0, 1):
        raise ValueError("Execution 01 requires conservative one-worker settings")
    if not 0 < cfg["max_run_http_attempts"] <= 50 or not 0 < cfg["max_batch_size"] <= 50:
        raise ValueError("Unbounded run or batch")
    if set(cfg["verified_request_endpoints"]) != {"leagues", "leagueseasondeepstats", "matchDetails", "playerData", "playerStats"}:
        raise ValueError("Endpoint allowlist changed without validation")
    for key in ("manifest_path", "raw_dir", "quarantine_dir", "checkpoint_dir", "normalized_dir", "report_dir", "log_path"):
        p = Path(cfg[key])
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"Unsafe {key}")
    return cfg


def task_identity(season: str, stage: str, resource: str, endpoint: str | None,
                  params: dict | None, context: dict | None) -> str:
    stable = {"season": season, "stage": stage, "resource": resource,
              "endpoint": endpoint or "", "params": canonical_params(params or {}),
              "identity_context": (context or {}).get("identity", "")}
    return "tsk_" + hashlib.sha256(json_bytes(stable)).hexdigest()


class Manifest:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.bulk = False
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY, request_key TEXT, season_label TEXT NOT NULL,
              season_id INTEGER NOT NULL, stage TEXT NOT NULL, resource_type TEXT NOT NULL,
              endpoint TEXT, params_json TEXT NOT NULL, context_json TEXT NOT NULL,
              execution_state TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
              raw_evidence_refs TEXT NOT NULL DEFAULT '[]', validation_result TEXT NOT NULL DEFAULT '',
              error_classification TEXT NOT NULL DEFAULT '', last_update_utc TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_season_request ON tasks(season_label, request_key)
              WHERE request_key IS NOT NULL;
            CREATE TABLE IF NOT EXISTS dependencies (
              task_id TEXT NOT NULL REFERENCES tasks(task_id),
              depends_on TEXT NOT NULL REFERENCES tasks(task_id),
              PRIMARY KEY(task_id, depends_on), CHECK(task_id != depends_on)
            );
            CREATE TABLE IF NOT EXISTS task_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(task_id),
              old_state TEXT, new_state TEXT NOT NULL, note TEXT NOT NULL, timestamp_utc TEXT NOT NULL
            );
        """)

    def close(self) -> None:
        self.db.close()

    def add(self, season: str, season_id: int, stage: str, resource: str,
            endpoint: str | None = None, params: dict | None = None,
            context: dict | None = None, dependencies: list[str] | None = None) -> str:
        if stage not in STAGES:
            raise ValueError("Unknown collection stage")
        params, context = canonical_params(params or {}), context or {}
        key = request_key(endpoint, params) if endpoint else None
        ident = task_identity(season, stage, resource, endpoint, params, context)
        existing = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (ident,)).fetchone()
        immutable = (season, season_id, stage, resource, endpoint, json.dumps(params, sort_keys=True),
                     json.dumps(context, sort_keys=True), key)
        if existing:
            prior = (existing["season_label"], existing["season_id"], existing["stage"],
                     existing["resource_type"], existing["endpoint"], existing["params_json"],
                     existing["context_json"], existing["request_key"])
            if prior != immutable:
                raise ValueError(f"Manifest task identity collision: {ident}")
        else:
            self.db.execute("""INSERT INTO tasks(task_id,request_key,season_label,season_id,stage,resource_type,
                endpoint,params_json,context_json,execution_state,last_update_utc)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (ident, key, season, season_id, stage, resource, endpoint,
                 immutable[5], immutable[6], "PLANNED", utc_now()))
            self.db.execute("INSERT INTO task_events(task_id,old_state,new_state,note,timestamp_utc) VALUES(?,?,?,?,?)",
                            (ident, None, "PLANNED", "manifest seed", utc_now()))
        for parent in dependencies or []:
            if not self.db.execute("SELECT 1 FROM tasks WHERE task_id=?", (parent,)).fetchone():
                raise ValueError(f"Missing dependency {parent}")
            self.db.execute("INSERT OR IGNORE INTO dependencies(task_id,depends_on) VALUES(?,?)", (ident, parent))
        if not self.bulk:
            self.db.commit()
        return ident

    def task(self, ident: str) -> dict:
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (ident,)).fetchone()
        if row is None:
            raise KeyError(ident)
        result = dict(row)
        result["params"] = json.loads(result.pop("params_json"))
        result["context"] = json.loads(result.pop("context_json"))
        result["raw_evidence_refs"] = json.loads(result["raw_evidence_refs"])
        result["dependencies"] = [r[0] for r in self.db.execute(
            "SELECT depends_on FROM dependencies WHERE task_id=? ORDER BY depends_on", (ident,))]
        return result

    def all_tasks(self, season: str | None = None, stage: str | None = None) -> list[dict]:
        query = "SELECT task_id FROM tasks WHERE 1=1"
        args = []
        if season:
            query += " AND season_label=?"; args.append(season)
        if stage:
            query += " AND stage=?"; args.append(stage)
        query += " ORDER BY season_label, CASE stage WHEN 'A' THEN 0 WHEN 'C' THEN 1 WHEN 'E' THEN 2 WHEN 'B' THEN 3 WHEN 'D' THEN 4 WHEN 'F' THEN 5 ELSE 6 END, CASE resource_type WHEN 'MATCH_INDEX_GATE' THEN 0 WHEN 'MATCH_DETAIL' THEN 1 ELSE 2 END, resource_type, task_id"
        return [self.task(r[0]) for r in self.db.execute(query, args)]

    def dependencies_ready(self, ident: str) -> bool:
        return all(self.task(parent)["execution_state"] in SATISFIED
                   for parent in self.task(ident)["dependencies"])

    def transition(self, ident: str, state: str, *, attempt_increment: int = 0,
                   raw_path: str | None = None, validation: str = "", error: str = "", note: str = "") -> None:
        if state not in STATES or attempt_increment < 0:
            raise ValueError("Invalid task transition")
        task = self.task(ident)
        old = task["execution_state"]
        if old in {"ACCEPTED", "NORMALIZED"} and state != old:
            raise ValueError("Terminal task cannot be demoted")
        refs = list(task["raw_evidence_refs"])
        if raw_path and raw_path not in refs:
            refs.append(raw_path)
        with self.db:
            self.db.execute("""UPDATE tasks SET execution_state=?, attempt_count=attempt_count+?,
                raw_evidence_refs=?, validation_result=?, error_classification=?, last_update_utc=? WHERE task_id=?""",
                (state, attempt_increment, json.dumps(refs), validation or task["validation_result"],
                 error if error else ("" if state in SATISFIED else task["error_classification"]),
                 utc_now(), ident))
            self.db.execute("INSERT INTO task_events(task_id,old_state,new_state,note,timestamp_utc) VALUES(?,?,?,?,?)",
                            (ident, old, state, note, utc_now()))

    def export_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            for task in self.all_tasks():
                writer.writerow({"task_id": task["task_id"], "request_key": task["request_key"],
                    "season_label": task["season_label"], "season_id": task["season_id"],
                    "stage": task["stage"], "resource_type": task["resource_type"],
                    "endpoint": task["endpoint"], "parameters": json.dumps(task["params"], sort_keys=True),
                    "dependencies": json.dumps(task["dependencies"]), "execution_state": task["execution_state"],
                    "attempt_count": task["attempt_count"],
                    "raw_evidence_refs": json.dumps(task["raw_evidence_refs"]),
                    "validation_result": task["validation_result"],
                    "error_classification": task["error_classification"],
                    "last_update_utc": task["last_update_utc"],
                    "context": json.dumps(task["context"], sort_keys=True)})
        temp.replace(path)

    def counts(self) -> dict:
        return {"total": self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "by_state": dict(Counter(r[0] for r in self.db.execute("SELECT execution_state FROM tasks"))),
                "by_stage": dict(Counter(r[0] for r in self.db.execute("SELECT stage FROM tasks")))}


def seed_manifest(manifest: Manifest, cfg: dict) -> dict:
    fixtures = fixture_lookup(PilotStore(load_config()))
    planned = {}
    manifest.bulk = True
    try:
      for season, season_id in cfg["seasons"].items():
        league = manifest.add(season, season_id, "A", "SEASON_FIXTURES", "leagues",
                              {"id": 47, "season": season}, {"identity": "league_47"})
        boards = [manifest.add(season, season_id, "C", "CANDIDATE_LEADERBOARD", "leagueseasondeepstats",
                               {"id": 47, "season": season_id, "type": "players", "stat": metric},
                               {"identity": metric, "unit_registry": "metric_dictionary_v2"}, [league])
                  for metric in cfg["candidate_leaderboard_metrics"]]
        index = manifest.add(season, season_id, "E", "MATCH_INDEX_GATE", context={"identity": "fixture_index"},
                             dependencies=[league])
        season_fixtures = fixtures[season]
        if len(season_fixtures) != cfg["quality"]["expected_finished_fixtures_per_season"]:
            raise ValueError(f"Finished fixture count changed for {season}")
        details = []
        for fixture in season_fixtures:
            details.append(manifest.add(season, season_id, "E", "MATCH_DETAIL", "matchDetails",
                {"matchId": int(fixture["match_id"])},
                {"identity": fixture["match_id"], "fixture": fixture}, [index]))
        population = manifest.add(season, season_id, "B", "POPULATION_GATE",
                                  context={"identity": "appeared_population"},
                                  dependencies=boards + details)
        expansion = manifest.add(season, season_id, "D", "PLAYER_EXPANSION_GATE",
                                 context={"identity": "append_observed_players"}, dependencies=[population])
        membership = manifest.add(season, season_id, "D", "HISTORICAL_MEMBERSHIP_GATE",
                                  context={"identity": "season_lineup_membership"}, dependencies=[expansion])
        stats = manifest.add(season, season_id, "C", "SEASON_STATS_GATE",
                             context={"identity": "all_player_season_stats"}, dependencies=[membership])
        normalized = manifest.add(season, season_id, "F", "NORMALIZATION_GATE",
                                  context={"identity": "seven_table_normalization"},
                                  dependencies=[population, stats, membership, index])
        manifest.add(season, season_id, "G", "SEASON_ACCEPTANCE_GATE",
                     context={"identity": "season_acceptance"}, dependencies=[normalized])
        planned[season] = {"season_id": season_id, "finished_match_tasks": len(details),
                           "leaderboard_tasks": len(boards)}
    except Exception:
        manifest.db.rollback()
        raise
    else:
        manifest.db.commit()
    finally:
        manifest.bulk = False
    return planned
