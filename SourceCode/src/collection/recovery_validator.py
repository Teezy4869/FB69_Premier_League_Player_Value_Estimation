"""Replay saved Step 05 bodies to test interruption, resume and normalization isolation."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write
from src.collection.reliability_runner import ReliabilityRunner, load_observations, load_reliability_config
from src.collection.source_registry import request_key
from src.collection.player_reference import write_csv

FIELDS = ["scenario", "status", "observed", "expected", "evidence", "note"]


class ReplayClient:
    def __init__(self, original: dict, stop_after: int | None = None):
        self.original = original
        self.stop_after = stop_after
        self.attempts = 0

    def get(self, endpoint: str, params: dict) -> dict:
        if self.stop_after is not None and self.attempts >= self.stop_after:
            raise RuntimeError("Injected checkpoint interruption")
        key = request_key(endpoint, params)
        row = self.original[key]
        body = (ROOT / row["raw_evidence_path"]).read_bytes()
        self.attempts += 1
        return {"record": {"timestamp_utc": row["timestamp_utc"],
                           "http_status": row["http_status"],
                           "content_type": row["content_type"],
                           "source_url": row["source_url"],
                           "json_parse_success": row["json_parse_success"],
                           "elapsed_seconds": row["response_latency_seconds"],
                           "retry_index": 0},
                "payload": json.loads(body), "raw_body": body}


def logical_signature(rows: list[dict]) -> list[tuple]:
    return sorted((r["request_key"], r["season_label"], r["schema_status"],
                   r["scope_status"], r["content_sha256"]) for r in rows)


def table_signature(directory: Path) -> tuple:
    result = []
    for path in sorted(directory.glob("*.parquet")):
        table = pq.read_table(path)
        rows = table.to_pylist()
        result.append((path.name, len(rows), hashlib.sha256(
            json.dumps(rows, sort_keys=True, default=str).encode("utf-8")).hexdigest()))
    return tuple(result)


def execute() -> list[dict]:
    cfg = load_reliability_config()
    originals = load_observations(ROOT / cfg["run_dir"] / "observations")
    if not originals:
        raise ValueError("Live reliability observations are required before recovery replay")
    original = {r["request_key"]: r for r in originals}
    if len(original) != len(originals):
        raise ValueError("Duplicate live request identity")
    results = []
    with tempfile.TemporaryDirectory(prefix="step05_replay_", dir=ROOT / cfg["run_dir"]) as temporary:
        temp = Path(temporary).resolve()
        if not temp.is_relative_to(ROOT.resolve()):
            raise ValueError("Replay target escaped workspace")
        # Both plans use exactly the same saved wire bytes; there is no HTTP in replay.
        resumed_cfg = dict(cfg)
        resumed_cfg["run_dir"] = (temp / "resumed").relative_to(ROOT).as_posix()
        resumed_cfg["log_path"] = (temp / "resumed_log.jsonl").relative_to(ROOT).as_posix()
        interrupted = ReliabilityRunner(resumed_cfg, ReplayClient(original, stop_after=10))
        try:
            interrupted.plan_and_run()
            raise AssertionError("Injected interruption did not occur")
        except RuntimeError as exc:
            if str(exc) != "Injected checkpoint interruption":
                raise
        partial = load_observations(interrupted.observation_dir)
        results.append({"scenario": "injected_checkpoint_interruption", "status": "PASS" if len(partial) == 10 else "FAIL",
                        "observed": len(partial), "expected": 10,
                        "evidence": "saved live response replay", "note": "Ten committed checkpoints survive interruption"})
        resumed = ReliabilityRunner(resumed_cfg, ReplayClient(original))
        resume_summary = resumed.plan_and_run()
        resume_rows = load_observations(resumed.observation_dir)
        fresh_cfg = dict(cfg)
        fresh_cfg["run_dir"] = (temp / "uninterrupted").relative_to(ROOT).as_posix()
        fresh_cfg["log_path"] = (temp / "uninterrupted_log.jsonl").relative_to(ROOT).as_posix()
        fresh = ReliabilityRunner(fresh_cfg, ReplayClient(original))
        fresh.plan_and_run()
        fresh_rows = load_observations(fresh.observation_dir)
        equal = logical_signature(resume_rows) == logical_signature(fresh_rows) == logical_signature(originals)
        results.append({"scenario": "resume_equals_uninterrupted", "status": "PASS" if equal else "FAIL",
                        "observed": len(resume_rows), "expected": len(originals),
                        "evidence": "saved live response replay", "note": "Logical key, status, scope and SHA-256 agree"})
        results.append({"scenario": "checkpoint_cache_hits", "status": "PASS" if resume_summary["cache_hits"] == 10 else "FAIL",
                        "observed": resume_summary["cache_hits"], "expected": 10,
                        "evidence": "saved live response replay", "note": "Previously committed requests were not fetched again"})
        results.append({"scenario": "duplicate_request_keys", "status": "PASS" if len(resume_rows) == len({r["request_key"] for r in resume_rows}) else "FAIL",
                        "observed": len(resume_rows) - len({r["request_key"] for r in resume_rows}), "expected": 0,
                        "evidence": "replayed checkpoints", "note": "One committed observation per logical request"})
        # Run the actual Phase 2A normalizer against original raw input but isolated output paths.
        norm_cfg = dict(load_config())
        norm_cfg["normalized_dir"] = (temp / "normalized").relative_to(ROOT).as_posix()
        norm_cfg["report_dir"] = (temp / "reports").relative_to(ROOT).as_posix()
        (ROOT / norm_cfg["report_dir"]).mkdir(parents=True, exist_ok=True)
        source_manifest = ROOT / "reports/phase_02a/pilot_sample_manifest.csv"
        shutil.copyfile(source_manifest, ROOT / norm_cfg["report_dir"] / source_manifest.name)
        from src.collection import normalize_pilot
        with patch.object(normalize_pilot, "load_config", return_value=norm_cfg):
            normalize_pilot.normalize()
            first = table_signature(ROOT / norm_cfg["normalized_dir"])
            normalize_pilot.normalize()
            second = table_signature(ROOT / norm_cfg["normalized_dir"])
            damaged = ROOT / norm_cfg["normalized_dir"] / "player_seasons.parquet"
            damaged.write_bytes(b"simulated partial output")
            normalize_pilot.normalize()
            repaired = table_signature(ROOT / norm_cfg["normalized_dir"])
        results.append({"scenario": "normalization_idempotency", "status": "PASS" if first == second and len(first) == 7 else "FAIL",
                        "observed": len(second), "expected": 7,
                        "evidence": "isolated Phase 2A normalizer output", "note": "Seven table logical hashes stable over two runs"})
        results.append({"scenario": "partial_output_recovery", "status": "PASS" if first == repaired else "FAIL",
                        "observed": len(repaired), "expected": 7,
                        "evidence": "isolated Phase 2A normalizer output", "note": "Corrupted test output rebuilt from preserved raw"})
        # The temporary directory is resolved inside the workspace before its context cleanup.
    write_csv(ROOT / "reports/phase_02b0/recovery_test_results.csv", FIELDS, results)
    if any(r["status"] != "PASS" for r in results):
        raise AssertionError("One or more recovery checks failed")
    return results


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2))
