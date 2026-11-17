"""Run and log real tests, audit the planned manifest, and estimate collection volume."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.reliability_runner import load_observations, load_reliability_config
from src.collection.source_registry import SourceRegistry, load_hardening_config


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_test_suite(report_dir: Path) -> dict:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = now()
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", check=False)
    finished = now()
    log = result.stdout
    atomic_write(report_dir / "test_execution.log", log.encode("utf-8"))
    match = re.search(r"Ran (\d+) tests? in ([\d.]+)s", log)
    failures = re.search(r"failures=(\d+)", log)
    errors = re.search(r"errors=(\d+)", log)
    skipped = re.search(r"skipped=(\d+)", log)
    data = {"command": "python -m unittest discover -s tests -v",
            "executable": sys.executable, "started_utc": started, "finished_utc": finished,
            "exit_code": result.returncode, "tests_run": int(match.group(1)) if match else None,
            "duration_seconds_reported": float(match.group(2)) if match else None,
            "failures": int(failures.group(1)) if failures else 0,
            "errors": int(errors.group(1)) if errors else 0,
            "skipped": int(skipped.group(1)) if skipped else 0,
            "log_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest(),
            "last_line": next((line for line in reversed(log.splitlines()) if line.strip()), "")}
    atomic_write(report_dir / "test_execution.json", json_bytes(data))
    return data


def dependency_report(report_dir: Path) -> dict:
    modules = {"requests": "requests", "pandas": "pandas", "PyYAML": "yaml", "pyarrow": "pyarrow"}
    versions = {}
    for distribution in modules:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "MISSING"
    check = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace", check=False)
    atomic_write(report_dir / "dependency_check.log", check.stdout.encode("utf-8"))
    return {"requirements": (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines(),
            "installed_versions": versions, "pip_check_exit_code": check.returncode,
            "pip_check_output": check.stdout.strip()}


def manifest_audit(manifest: Manifest, cfg: dict) -> dict:
    tasks = manifest.all_tasks()
    by_id = {t["task_id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Duplicate task IDs")
    descendants = defaultdict(list)
    indegree = {}
    for task in tasks:
        parents = task["dependencies"]
        if any(p not in by_id for p in parents):
            raise ValueError("Manifest has missing dependencies")
        indegree[task["task_id"]] = len(parents)
        for parent in parents:
            descendants[parent].append(task["task_id"])
    queue = deque(k for k, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        parent = queue.popleft(); visited += 1
        for child in descendants[parent]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(tasks):
        raise ValueError("Manifest dependency cycle")
    seasons = {}
    for season, season_id in cfg["seasons"].items():
        group = [t for t in tasks if t["season_label"] == season]
        details = [t for t in group if t["resource_type"] == "MATCH_DETAIL"]
        boards = [t for t in group if t["resource_type"] == "CANDIDATE_LEADERBOARD"]
        if len(details) != 380 or len(boards) != 3 or any(t["season_id"] != season_id for t in group):
            raise ValueError(f"Incomplete season plan: {season}")
        seasons[season] = {"season_id": season_id, "tasks": len(group),
                           "match_details": len(details), "leaderboards": len(boards)}
    http_tasks = [t for t in tasks if t["endpoint"]]
    duplicate_context_keys = len(http_tasks) - len({(t["season_label"], t["request_key"]) for t in http_tasks})
    if duplicate_context_keys:
        raise ValueError("Manifest request identity collision")
    return {"total": len(tasks), "http_tasks": len(http_tasks), "local_gates": len(tasks)-len(http_tasks),
            "validated": sum(t["execution_state"] == "VALIDATED" for t in tasks),
            "validated_http": sum(t["execution_state"] == "VALIDATED" for t in http_tasks),
            "duplicate_context_request_keys": duplicate_context_keys,
            "acyclic": True, "by_state": dict(Counter(t["execution_state"] for t in tasks)),
            "seasons": seasons}


def storage_plan(report_dir: Path, cfg: dict, manifest_info: dict) -> dict:
    registry = SourceRegistry(load_hardening_config())
    samples = defaultdict(list)
    for meta, _ in registry.captures():
        samples[meta["endpoint"]].append((ROOT / meta["raw_path"]).stat().st_size)
    reliability = load_reliability_config()
    for row in load_observations(ROOT / reliability["run_dir"] / "observations"):
        if row["raw_evidence_path"]:
            samples[row["endpoint"]].append((ROOT / row["raw_evidence_path"]).stat().st_size)
    with (ROOT / "reports/phase_02b0/historical_identity_validation.csv").open(encoding="utf-8", newline="") as handle:
        candidates = [r for r in csv.DictReader(handle) if r["relationship_origin"] == "SEASON_SCOPED_LEADERBOARD"]
    profile_proxy = len({r["fotmob_player_id"] for r in candidates})
    stats_proxy = len({(r["season_label"], r["fotmob_player_id"]) for r in candidates})
    known = {"leagues": 6, "leagueseasondeepstats": 18, "matchDetails": 2280}
    proxy = {**known, "playerData": profile_proxy, "playerStats": stats_proxy}
    means = {k: sum(values)/len(values) for k, values in samples.items() if values}
    fixed_bytes = sum(n*means[k] for k, n in known.items())
    proxy_bytes = sum(n*means[k] for k, n in proxy.items())
    text = f"""# Phase 2B.1 Execution 01 — request and raw-storage plan

These are **planning estimates**, not requests executed or guaranteed population counts. The [manifest](collection_manifest.csv) contains {manifest_info['total']} tasks: {manifest_info['http_tasks']} fixed HTTP tasks and {manifest_info['local_gates']} local gates. {manifest_info['validated_http']} fixed HTTP tasks already reuse verified saved raw; up to {manifest_info['http_tasks']-manifest_info['validated_http']} fixed HTTP tasks remain uncached in this manifest. Execution 01 sent **zero** collection HTTP requests. [Preflight](preflight_report.md), [prior population audit](../phase_02b0/population_coverage_report.md).

| Endpoint | Fixed tasks | Candidate-based dynamic proxy | Saved raw sample count | Mean sample bytes |
|---|---:|---:|---:|---:|
""" + "\n".join(f"| `{ep}` | {known.get(ep,0)} | {proxy.get(ep,0)-known.get(ep,0)} | {len(samples[ep])} | {means.get(ep,0):,.0f} |"
                    for ep in ("leagues", "leagueseasondeepstats", "matchDetails", "playerData", "playerStats")) + f"""

The leaderboard candidate proxy is **{profile_proxy} distinct player IDs** and **{stats_proxy} player-season IDs**; appendable tasks use actual appeared-player evidence instead. If every candidate became an appeared player, the simple proxy would be {sum(proxy.values()):,} logical HTTP tasks, including {manifest_info['http_tasks']:,} fixed tasks. This is neither a lower nor an upper bound on final requests: the full appeared-player denominator is unknown, profile reuse may reduce calls, and missing leaderboard players may add calls. At the observed endpoint means, fixed raw JSON would be about {fixed_bytes/1_000_000:,.1f} MB and candidate-proxy raw JSON about {proxy_bytes/1_000_000:,.1f} MB, excluding metadata, retries, quarantines and Parquet. Response sizes can change substantially. [Metric dictionary](../phase_02b0/metric_dictionary_v2.csv), [saved response evidence](../phase_02b0/source_integrity_report.csv).

Batch budgeting remains at most {cfg['max_run_http_attempts']} actual HTTP attempts including retries per explicitly authorized run, one worker and a configured minimum interval of {cfg['min_request_interval_seconds']} seconds based on the bounded pilot setting. These numbers do not authorize a full crawl. [Configuration](../../configs/full_collection.yaml), [previous live measurements](../phase_02b0/collection_reliability_report.md).
"""
    atomic_write(report_dir / "request_storage_plan.md", text.encode("utf-8"))
    return {"fixed_http_tasks": manifest_info["http_tasks"], "validated_fixed_http": manifest_info["validated_http"],
            "candidate_profile_proxy": profile_proxy, "candidate_stats_proxy": stats_proxy,
            "candidate_total_http_proxy": sum(proxy.values()), "fixed_raw_mb_estimate": round(fixed_bytes/1_000_000, 1),
            "candidate_raw_mb_estimate": round(proxy_bytes/1_000_000, 1)}


def execute() -> dict:
    cfg = load_full_config()
    report_dir = ROOT / cfg["report_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        manifest_info = manifest_audit(manifest, cfg)
    finally:
        manifest.close()
    dependencies = dependency_report(report_dir)
    tests = run_test_suite(report_dir)
    planning = storage_plan(report_dir, cfg, manifest_info)
    old = SourceRegistry(load_hardening_config())
    previous_capture_count = len(list(old.captures()))  # Reads and verifies all old SHA-256 values.
    pilot = load_config()
    normalized = {}
    for path in sorted((ROOT / pilot["normalized_dir"]).glob("*.parquet")):
        normalized[path.stem] = pq.read_metadata(path).num_rows
    batch_paths = sorted((report_dir / "batches").glob("*.json"))
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in batch_paths]
    prior_issues = []
    with (ROOT / "reports/phase_02b0/hardening_issue_tracker.csv").open(encoding="utf-8", newline="") as handle:
        prior_issues = [r for r in csv.DictReader(handle) if r["status"] == "OPEN_CONDITION"]
    mandatory_pass = (tests["exit_code"] == 0 and tests["tests_run"] is not None and tests["failures"] == 0 and
                      tests["errors"] == 0 and manifest_info["acyclic"] and
                      manifest_info["validated"] >= 52 and
                      previous_capture_count == 277 and
                      all(v != "MISSING" for v in dependencies["installed_versions"].values()) and
                      all(b["decision"] == "PASS" for b in batches))
    status = "PASS" if mandatory_pass else "FAIL"
    report = f"""# Phase 2B.1 Execution 01 — repository and environment preflight

**{status}.** This preflight built and checked the control plane only. It made **zero Phase 2B.1 collection HTTP attempts**. [Manifest](collection_manifest.csv), [configuration](../../configs/full_collection.yaml), [batch results](batches/), [test log](test_execution.log).

## Actual repository and reusable components

Project root: `{ROOT}`. Existing dependencies are declared in [requirements.txt](../../requirements.txt); installed versions: {dependencies['installed_versions']}. `pip check` exit code: {dependencies['pip_check_exit_code']} ([output](dependency_check.log)). No dependency installation was needed. The repository already has `AuditClient` for paced/retried HTTP, `SourceRegistry` for canonical request keys and immutable SHA-256 captures, `historical_lineup_validator` for finished fixtures and appearances, `metric_reconciler`/dictionary v2, `position_mapper`, and seven pilot Parquet schemas. [Prior source audit](../phase_02b0/source_integrity_report.csv), [metric registry](../phase_02b0/metric_dictionary_v2.csv), [pilot schema](../phase_02a/schema_definition.json).

Prior raw checksum scan: {previous_capture_count} Phase 1/2A/2B.0 captures; pilot normalized table row counts: {normalized}. The new source registry writes to a distinct `data/phase_02b1/raw` tree; no previous report or raw capture was rewritten. [Source design](../phase_02b0/steps_01_02_summary.md), [new manifest](collection_manifest.csv).

## Scope and unresolved controls

Season IDs match cached FotMob league evidence and pilot configuration: {cfg['seasons']}. The manifest is acyclic and has {manifest_info['total']} tasks, including {manifest_info['http_tasks']} fixed request tasks and {manifest_info['local_gates']} local gates. Each season has 380 finished `matchDetails` tasks; the abandoned Bournemouth–Luton ID is excluded and the replay retained. The {len(prior_issues)} open Phase 2B.0 conditions remain explicit: unknown full population, three inferred second clubs, unresolved position meanings, the Mac Allister minutes conflict, unverified `playerMatches`, and responses lacking direct season context. [Issue tracker](../phase_02b0/hardening_issue_tracker.csv), [plan](request_storage_plan.md).

Verified endpoint assumptions: `leagues`, `leagueseasondeepstats`, `matchDetails`, `playerData`, `playerStats`. `teams` current squad responses cannot prove historical membership and `playerMatches` is excluded pending a working historical contract. Cache identity uses request key plus season; raw SHA-256 and provenance are checked before validation. `FETCHED` stays separate from `VALIDATED`. The Stage F/G validator checks seven complete-season tables, all 380 fixtures, appeared-player links, metric states and raw lineage. It remains BLOCKED until collection finishes and a full-season normalizer produces those tables; this preflight does not certify an uncollected season. [Quality-gate source](../../src/collection/full_season_gate.py), [batch gate](../../src/collection/batch_quality.py), [runner](../../src/collection/full_orchestrator.py), [prior limitations](../phase_02b0/phase_02b0_readiness_report.md).

## Real automated tests and raw-only batch checks

Command: `{tests['command']}`. Exit code **{tests['exit_code']}**; tests **{tests['tests_run']}**, failures **{tests['failures']}**, errors **{tests['errors']}**, skipped **{tests['skipped']}**. The complete actual output is [test_execution.log](test_execution.log); machine summary and SHA-256 are [test_execution.json](test_execution.json). No manually supplied test-count string is accepted.

Cached validation has accepted {manifest_info['validated']} task results across six seasons using prior raw evidence; machine-readable batch decisions are [under batches](batches/). It did not fetch any missing match detail. Full-season population tasks remain dependent on all 380 validated match details per season, and dynamic player tasks are appendable only from observed appearances. [Manifest](collection_manifest.csv), [batch gate](../../src/collection/batch_quality.py).

## Execution 02 gate

Infrastructure dry-run, manifest dependencies, cache-only resume and batch quarantine rules are operational. **A full-season normalization producer and complete-season acceptance tests remain required before declaring any season accepted.** Execution 02 also needs a separately authorized bounded run budget. The request/storage numbers are estimates, not completed collection. [Execution guide](execution_guide.md), [planning report](request_storage_plan.md).
"""
    atomic_write(report_dir / "preflight_report.md", report.encode("utf-8"))
    guide = """# Phase 2B.1 Execution 01 — reproducible commands

Run from `D:\\PTIT\\Hoc_may\\FB69`. These commands use saved evidence and make zero collection HTTP requests:

```powershell
python -m src.collection.full_orchestrator --init-manifest
python -m src.collection.full_orchestrator --report-status
python -m src.collection.full_orchestrator --dry-run --batch-size 10
python -m src.collection.full_orchestrator --season 2019/2020 --stage A --dry-run
python -m src.collection.full_orchestrator --validation-only --from-raw --batch-size 50 --resume
python -m src.collection.execution01_preflight
```

`--init-manifest` is idempotent and preserves checkpoint states. `--validation-only --from-raw` checks existing responses and never calls the API. The runner also supports `--season`, `--stage`, `--batch-size`, `--resume`, `--max-requests`, and `--report-status`. Live `--execute` requires an explicit run budget of 1–50 actual attempts including retries and is **not part of Execution 01**. It must not be used until Execution 02 is separately authorized and the Stage F/G blockers are closed. [Configuration](../../configs/full_collection.yaml), [manifest](collection_manifest.csv), [preflight](preflight_report.md).
"""
    atomic_write(report_dir / "execution_guide.md", guide.encode("utf-8"))
    result = {"status": status, "tests": tests, "manifest": manifest_info,
              "planning": planning, "prior_capture_count": previous_capture_count,
              "batch_reports": len(batches), "open_conditions": len(prior_issues),
              "phase_02b1_collection_http_attempts": 0}
    atomic_write(report_dir / "preflight_status.json", json_bytes(result))
    return result


if __name__ == "__main__":
    result = execute()
    print(json.dumps({"status": result["status"], "tests": result["tests"],
                      "manifest": result["manifest"], "planning": result["planning"],
                      "phase_02b1_collection_http_attempts": 0}, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
