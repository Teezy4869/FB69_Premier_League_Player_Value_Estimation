"""Phase 2B.1 control plane; Execution 01 never invokes its live mode."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import uuid
from collections import Counter
from pathlib import Path

from src.audit.client import AuditClient, BudgetExceeded
from src.collection.batch_quality import batch_decision, inspect_capture, write_batch_report
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config, seed_manifest
from src.collection.historical_lineup_validator import fixture_lookup, verify_detail
from src.collection.reliability_runner import classify_empty_stats_payload, profile_entry, schema_state
from src.collection.source_registry import SourceRegistry, load_hardening_config, validate_scope


def registries(cfg: dict, client: AuditClient | None = None) -> tuple[SourceRegistry, SourceRegistry]:
    hardening = load_hardening_config()
    old = SourceRegistry(hardening)
    current = dict(hardening)
    current.update({"raw_dir": cfg["raw_dir"],
                    "legacy_raw_dir": "data/phase_02b1/legacy_empty",
                    "log_path": cfg["log_path"], "lineup_request_budget": 0,
                    "parser_version": cfg["parser_version"], "schema_version": cfg["schema_version"]})
    return SourceRegistry(current, client=client), old


def cached(task: dict, current: SourceRegistry, old: SourceRegistry):
    params, season, endpoint = task["params"], task["season_label"], task["endpoint"]
    exact = current.lookup(endpoint, params, season) or old.lookup(endpoint, params, season)
    if exact is not None or endpoint != "playerData":
        return exact
    for registry in (current, old):
        for meta, payload in registry.lookup_any_season(endpoint, params):
            if profile_entry(payload, season):
                return meta, payload
    return None


def profile_for_stats(task: dict, manifest: Manifest, current: SourceRegistry, old: SourceRegistry) -> dict | None:
    for parent_id in task["dependencies"]:
        parent = manifest.task(parent_id)
        if parent["resource_type"] == "PLAYER_PROFILE":
            item = cached(parent, current, old)
            return item[1] if item else None
    return None


def quarantine_body(cfg: dict, task: dict, result: dict, reason: str) -> str:
    body = result.get("raw_body")
    if body is None:
        return ""
    capture_id = "quarantine_" + uuid.uuid4().hex
    directory = ROOT / cfg["quarantine_dir"] / capture_id
    temp = directory.with_name("." + directory.name + ".tmp")
    temp.mkdir(parents=True, exist_ok=False)
    record = result["record"]
    metadata = {"request_key": task["request_key"], "capture_id": capture_id,
                "task_id": task["task_id"],
                "season_label": task["season_label"], "endpoint": task["endpoint"],
                "params": task["params"], "timestamp_utc": record.get("timestamp_utc"),
                "http_status": record.get("http_status"), "source_url": record.get("source_url"),
                "content_sha256": hashlib.sha256(body).hexdigest(), "reason": reason,
                "parser_version": cfg["parser_version"], "schema_version": cfg["schema_version"],
                "validation_status": "QUARANTINED"}
    for name, data in (("response.bin", body), ("metadata.json", json_bytes(metadata))):
        with (temp / name).open("xb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.rename(temp, directory)
    return (directory / "response.bin").relative_to(ROOT).as_posix()


def task_row(task: dict, decision: str, note: str, raw_path: str = "", capture_id: str = "",
             schema: str = "", scope: str = "", error: str = "", missing: int = 0) -> dict:
    return {"task_id": task["task_id"], "request_key": task["request_key"],
            "season_label": task["season_label"], "stage": task["stage"],
            "resource_type": task["resource_type"], "decision": decision,
            "schema_status": schema, "scope_status": scope, "error_classification": error,
            "raw_path": raw_path, "capture_id": capture_id, "missing_value_count": missing,
            "note": note}


def population_from_details(manifest: Manifest, season: str, current: SourceRegistry, old: SourceRegistry) -> dict:
    appeared = set()
    appeared_links = set()
    unknown_links = set()
    match_tasks = [t for t in manifest.all_tasks(season, "E") if t["resource_type"] == "MATCH_DETAIL"]
    if len(match_tasks) != 380 or any(t["execution_state"] != "VALIDATED" for t in match_tasks):
        raise ValueError("Complete validated match details required for population gate")
    for task in match_tasks:
        item = cached(task, current, old)
        if item is None:
            raise ValueError(f"Missing validated match raw: {task['task_id']}")
        _, payload = item
        if verify_detail(payload, task["context"]["fixture"])[0] != "ACCEPTED":
            raise ValueError(f"Match fixture mismatch: {task['task_id']}")
        lineup = (payload.get("content") or {}).get("lineup") or {}
        if lineup.get("lineupType") != "standard":
            raise ValueError(f"No standard lineup: {task['task_id']}")
        seen_player_ids = set()
        for side, team_id in (("homeTeam", task["context"]["fixture"]["home_team_id"]),
                              ("awayTeam", task["context"]["fixture"]["away_team_id"])):
            team = lineup.get(side) or {}
            if str(team.get("id")) != team_id:
                raise ValueError(f"Lineup team mismatch: {task['task_id']}")
            if not isinstance(team.get("starters"), list) or not isinstance(team.get("subs"), list):
                raise ValueError(f"Incomplete lineup lists: {task['task_id']}")
            if len(team["starters"]) != 11:
                raise ValueError(f"Expected eleven starters: {task['task_id']}")
            for role in ("starters", "subs"):
                for member in team.get(role) or []:
                    pid = str(member.get("id"))
                    if not pid.isdigit():
                        raise ValueError(f"Invalid player ID: {task['task_id']}")
                    if pid in seen_player_ids:
                        raise ValueError(f"Duplicate match player ID: {task['task_id']} {pid}")
                    seen_player_ids.add(pid)
                    events = (member.get("performance") or {}).get("substitutionEvents")
                    event_types = {e.get("type") for e in events if isinstance(e, dict)} if isinstance(events, list) else set()
                    entered = role == "starters" or "subIn" in event_types
                    if entered:
                        appeared.add((pid, team_id))
                        appeared_links.add((pid, task["context"]["fixture"]["match_id"], team_id))
                    elif not isinstance(events, list) or "subOut" in event_types:
                        unknown_links.add((pid, task["context"]["fixture"]["match_id"], team_id))
    with (ROOT / "reports/phase_02b0/historical_identity_validation.csv").open(encoding="utf-8", newline="") as handle:
        candidates = {(r["fotmob_player_id"], r["fotmob_team_id"]) for r in csv.DictReader(handle)
                      if r["season_label"] == season and r["relationship_origin"] == "SEASON_SCOPED_LEADERBOARD"}
    candidate_players = {pid for pid, _ in candidates}
    return {"season_label": season, "appeared_relations": sorted(appeared, key=lambda x: (int(x[0]), int(x[1]))),
            "appeared_match_links": sorted(appeared_links, key=lambda x: (int(x[1]), int(x[0]), int(x[2]))),
            "unknown_match_links": sorted(unknown_links, key=lambda x: (int(x[1]), int(x[0]), int(x[2]))),
            "appeared_player_ids": sorted({pid for pid, _ in appeared}, key=int),
            "missing_candidate_player_ids": sorted({pid for pid, _ in appeared if pid not in candidate_players}, key=int),
            "missing_candidate_club_relations": sorted(appeared - candidates, key=lambda x: (int(x[0]), int(x[1]))),
            "validated_match_count": len(match_tasks)}


def local_gate(task: dict, manifest: Manifest, cfg: dict,
               current: SourceRegistry, old: SourceRegistry) -> dict:
    season, resource = task["season_label"], task["resource_type"]
    try:
        if resource == "MATCH_INDEX_GATE":
            count = len(fixture_lookup(PilotStore(load_config()))[season])
            if count != 380:
                raise ValueError(f"Finished fixture count {count} != 380")
            note = "380 finished fixtures verified from season-scoped leagues raw"
        elif resource == "POPULATION_GATE":
            population = population_from_details(manifest, season, current, old)
            path = ROOT / cfg["checkpoint_dir"] / season.replace("/", "_") / "appeared_population.json"
            atomic_write(path, json_bytes(population))
            note = f"{len(population['appeared_player_ids'])} appeared IDs; {len(population['missing_candidate_player_ids'])} missing candidates"
            manifest.transition(task["task_id"], "VALIDATED", raw_path=path.relative_to(ROOT).as_posix(),
                                validation="POPULATION_RECONCILED", note=note)
            return task_row(task, "VALIDATED", note, path.relative_to(ROOT).as_posix())
        elif resource == "PLAYER_EXPANSION_GATE":
            path = ROOT / cfg["checkpoint_dir"] / season.replace("/", "_") / "appeared_population.json"
            population = json.loads(path.read_text(encoding="utf-8"))
            membership = next(t for t in manifest.all_tasks(season, "D")
                              if t["resource_type"] == "HISTORICAL_MEMBERSHIP_GATE")
            for pid in population["appeared_player_ids"]:
                profile = manifest.add(season, task["season_id"], "D", "PLAYER_PROFILE", "playerData",
                                       {"id": int(pid)}, {"identity": f"profile_{pid}"}, [task["task_id"]])
                manifest.add(season, task["season_id"], "D", "HISTORICAL_MEMBERSHIP_GATE",
                             context=membership["context"], dependencies=[profile])
            note = f"Appended {len(population['appeared_player_ids'])} profile tasks from appeared IDs"
        elif resource == "HISTORICAL_MEMBERSHIP_GATE":
            note = "Every appeared-player profile task validated; historical clubs remain lineup-derived"
        elif resource == "SEASON_STATS_GATE":
            note = "All appended playerStats tasks validated; unresolved metric conflicts remain flagged"
        elif resource == "NORMALIZATION_GATE":
            from src.collection.full_season_gate import validate_full_season
            gate = validate_full_season(cfg, season, current, old)
            if gate["issues"]:
                manifest.transition(task["task_id"], "BLOCKED", error="FULL_NORMALIZATION_GATE_FAILED",
                                    note="; ".join(gate["issues"][:5]))
                return task_row(task, "BLOCKED", "; ".join(gate["issues"][:5]),
                                error="FULL_NORMALIZATION_GATE_FAILED")
            note = "Seven full-season tables validated against lineup population and raw lineage"
        elif resource == "SEASON_ACCEPTANCE_GATE":
            from src.collection.full_season_gate import validate_full_season
            gate = validate_full_season(cfg, season, current, old)
            if gate["issues"]:
                manifest.transition(task["task_id"], "BLOCKED", error="SEASON_ACCEPTANCE_FAILED",
                                    note="; ".join(gate["issues"][:5]))
                return task_row(task, "BLOCKED", "; ".join(gate["issues"][:5]),
                                error="SEASON_ACCEPTANCE_FAILED")
            note = "Complete season fixture, appearance, identity and provenance checks passed"
            manifest.transition(task["task_id"], "ACCEPTED", validation=note, note=note)
            return task_row(task, "ACCEPTED", note)
        else:
            raise ValueError(f"Unsupported local gate: {resource}")
        manifest.transition(task["task_id"], "VALIDATED", validation=note, note=note)
        return task_row(task, "VALIDATED", note)
    except (ValueError, OSError, KeyError) as exc:
        manifest.transition(task["task_id"], "QUARANTINED", error=type(exc).__name__, note=str(exc))
        return task_row(task, "QUARANTINED", str(exc), error=type(exc).__name__)


def process_task(task: dict, manifest: Manifest, cfg: dict, current: SourceRegistry,
                 old: SourceRegistry, client: AuditClient | None, execute: bool) -> dict | None:
    if task["endpoint"] is None:
        return local_gate(task, manifest, cfg, current, old)
    try:
        item = cached(task, current, old)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        manifest.transition(task["task_id"], "QUARANTINED", error="CACHE_CORRUPTION", note=str(exc))
        return task_row(task, "QUARANTINED", str(exc), error="CACHE_CORRUPTION")
    if item is None:
        if not execute:
            return None
        if client is None:
            raise ValueError("Live client missing")
        manifest.transition(task["task_id"], "RUNNING", note="HTTP request started")
        before = client.attempts
        try:
            result = client.get(task["endpoint"], task["params"])
        except BudgetExceeded:
            manifest.transition(task["task_id"], "RETRY_PENDING", attempt_increment=client.attempts-before,
                                error="REQUEST_BUDGET_EXCEEDED", note="Run budget exhausted")
            raise
        attempts = client.attempts - before
        manifest.transition(task["task_id"], "RUNNING", attempt_increment=attempts,
                            note=f"{attempts} actual HTTP attempt(s)")
        payload = result.get("payload")
        if payload is None:
            error = classify_empty_stats_payload(task["endpoint"], result["record"], result.get("raw_body"))
            raw = quarantine_body(cfg, task, result, error)
            state = "RETRY_PENDING" if error in ("SERVER_ERROR", "NETWORK_ERROR") else "QUARANTINED"
            manifest.transition(task["task_id"], state, raw_path=raw, error=error, note="HTTP response not accepted")
            return task_row(task, state, result["record"].get("error", error), raw, error=error)
        schema, _ = schema_state(task["endpoint"], payload, task["params"])
        scope, _ = validate_scope(task["endpoint"], task["params"], task["season_label"],
                                  task["season_id"], payload)
        if task["endpoint"] == "matchDetails":
            scope, _ = verify_detail(payload, task["context"]["fixture"])
        if schema == "SCHEMA_ERROR" or scope in ("HISTORICAL_SCOPE_MISMATCH", "REJECTED"):
            error = "SCHEMA_ERROR" if schema == "SCHEMA_ERROR" else "HISTORICAL_SCOPE_MISMATCH"
            raw = quarantine_body(cfg, task, result, error)
            manifest.transition(task["task_id"], "QUARANTINED", raw_path=raw, error=error,
                                note="HTTP 200 response failed pre-capture validation")
            return task_row(task, "QUARANTINED", "HTTP 200 failed schema or scope", raw,
                            schema=schema, scope=scope, error=error)
        try:
            item = current.capture(task["endpoint"], task["params"], task["season_label"], result,
                                   {"date": task["context"]["fixture"]["match_date_utc"][:10],
                                    "home_team_id": task["context"]["fixture"]["home_team_id"],
                                    "away_team_id": task["context"]["fixture"]["away_team_id"]}
                                   if task["endpoint"] == "matchDetails" else None)
        except (ValueError, FileExistsError, OSError) as exc:
            manifest.transition(task["task_id"], "QUARANTINED", error="RAW_CAPTURE_ERROR", note=str(exc))
            return task_row(task, "QUARANTINED", str(exc), error="RAW_CAPTURE_ERROR")
        manifest.transition(task["task_id"], "FETCHED", raw_path=item[0]["raw_path"],
                            validation="HTTP_200_CAPTURED", note="Immutable raw capture committed")
    meta, payload = item
    profile = profile_for_stats(task, manifest, current, old) if task["endpoint"] == "playerStats" else None
    assessment = inspect_capture(task, meta, payload, profile)
    if assessment["decision"] == "VALIDATED":
        manifest.transition(task["task_id"], "VALIDATED", raw_path=meta["raw_path"],
                            validation=assessment["scope_status"], note=assessment["note"])
        if task["resource_type"] == "PLAYER_PROFILE":
            entry = profile_entry(payload, task["season_label"])
            stats_task = manifest.add(task["season_label"], task["season_id"], "C", "PLAYER_SEASON_STATS",
                                      "playerStats", {"playerId": task["params"]["id"], "seasonId": entry},
                                      {"identity": f"stats_{task['params']['id']}_{entry}"}, [task["task_id"]])
            gate = next(t for t in manifest.all_tasks(task["season_label"], "C")
                        if t["resource_type"] == "SEASON_STATS_GATE")
            manifest.add(task["season_label"], task["season_id"], "C", "SEASON_STATS_GATE",
                         context=gate["context"], dependencies=[stats_task])
    else:
        manifest.transition(task["task_id"], "QUARANTINED", raw_path=meta["raw_path"],
                            validation=assessment["scope_status"],
                            error=assessment["error_classification"], note=assessment["note"])
    return assessment


def run(cfg: dict, manifest: Manifest, *, season: str | None, stage: str | None,
        batch_size: int, resume: bool, execute: bool, max_requests: int) -> dict:
    client = None
    if execute:
        pilot = load_config()
        client_cfg = dict(pilot)
        client_cfg.update({"request_budget": max_requests, "max_retries": cfg["max_retries"],
                           "backoff_seconds": cfg["backoff_seconds"],
                           "max_retry_after_seconds": cfg["max_retry_after_seconds"],
                           "min_request_interval_seconds": cfg["min_request_interval_seconds"],
                           "request_timeout_seconds": cfg["request_timeout_seconds"],
                           "max_response_bytes": cfg["max_response_bytes"]})
        client = AuditClient(client_cfg, ROOT / cfg["log_path"])
    current, old = registries(cfg, client)
    rows = []
    for item in manifest.all_tasks(season, stage):
        if len(rows) >= batch_size:
            break
        task = manifest.task(item["task_id"])
        state = task["execution_state"]
        if state in ("VALIDATED", "NORMALIZED", "ACCEPTED", "QUARANTINED", "FAILED"):
            continue
        if state == "BLOCKED" and not (resume and task["error_classification"] in (
                "FULL_NORMALIZATION_GATE_FAILED", "SEASON_ACCEPTANCE_FAILED")):
            continue
        if state == "RUNNING" and not resume:
            continue
        if not manifest.dependencies_ready(task["task_id"]):
            continue
        try:
            outcome = process_task(task, manifest, cfg, current, old, client, execute)
        except BudgetExceeded:
            outcome = task_row(task, "RETRY_PENDING", "Run HTTP attempt budget exhausted",
                               error="REQUEST_BUDGET_EXCEEDED")
            rows.append(outcome)
            break
        if outcome is None:
            if state == "RUNNING" and resume and not execute:
                manifest.transition(task["task_id"], "RETRY_PENDING", error="NO_COMMITTED_CAPTURE",
                                    note="Interrupted request has no validated raw capture")
                rows.append(task_row(task, "RETRY_PENDING", "No committed capture; live retry requires a later authorized run",
                                     error="NO_COMMITTED_CAPTURE"))
            continue
        rows.append(outcome)
        interim = batch_decision(rows, cfg)
        if interim["decision"] == "STOP" or outcome["error_classification"] in ("ACCESS_DENIED", "RATE_LIMITED"):
            break
    report_path, decision = write_batch_report(rows, cfg)
    manifest.export_csv(ROOT / cfg["report_dir"] / "collection_manifest.csv")
    return {"batch_report": report_path.relative_to(ROOT).as_posix(), "batch_decision": decision,
            "http_attempts": client.attempts if client else 0, "manifest": manifest.counts()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-manifest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--season", choices=list(load_full_config()["seasons"]))
    parser.add_argument("--stage", choices=list("ABCDEFG"))
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validation-only", action="store_true")
    parser.add_argument("--from-raw", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--report-status", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Explicitly permit bounded live HTTP (not used in Execution 01)")
    args = parser.parse_args(argv)
    cfg = load_full_config()
    if not 0 < args.batch_size <= cfg["max_batch_size"]:
        parser.error("batch-size exceeds configured limit")
    if args.execute and (args.validation_only or args.from_raw or args.dry_run or args.report_status or
                         not 0 < args.max_requests <= cfg["max_run_http_attempts"]):
        parser.error("live mode requires explicit bounded --max-requests and no read-only flags")
    if not args.execute and args.max_requests:
        parser.error("--max-requests only applies to explicit live mode")
    if args.validation_only and not args.from_raw:
        parser.error("--validation-only requires --from-raw")
    path = ROOT / cfg["manifest_path"]
    if not path.exists() and not args.init_manifest:
        parser.error("Initialize the manifest first with --init-manifest")
    manifest = Manifest(path)
    try:
        if args.init_manifest:
            plan = seed_manifest(manifest, cfg)
            manifest.export_csv(ROOT / cfg["report_dir"] / "collection_manifest.csv")
            print(json.dumps({"seeded": plan, "counts": manifest.counts(), "http_attempts": 0}, indent=2))
            return 0
        if args.report_status:
            print(json.dumps({"manifest": manifest.counts(), "http_attempts": 0}, indent=2))
            return 0
        if args.dry_run:
            eligible = [t for t in manifest.all_tasks(args.season, args.stage)
                        if (t["execution_state"] in ("PLANNED", "RETRY_PENDING", "FETCHED") or
                            (args.resume and t["execution_state"] == "BLOCKED" and
                             t["error_classification"] in ("FULL_NORMALIZATION_GATE_FAILED",
                                                           "SEASON_ACCEPTANCE_FAILED")))
                        and manifest.dependencies_ready(t["task_id"])]
            print(json.dumps({"eligible_count": len(eligible), "sample_task_ids": [t["task_id"] for t in eligible[:args.batch_size]],
                              "by_resource": dict(Counter(t["resource_type"] for t in eligible)),
                              "manifest": manifest.counts(), "http_attempts": 0}, indent=2))
            return 0
        if not (args.validation_only or args.from_raw or args.execute):
            parser.error("Select --dry-run, --report-status, --validation-only --from-raw, or --execute")
        result = run(cfg, manifest, season=args.season, stage=args.stage,
                     batch_size=args.batch_size, resume=args.resume,
                     execute=args.execute, max_requests=args.max_requests)
        print(json.dumps(result, indent=2))
        return 0 if result["batch_decision"]["decision"] != "STOP" else 2
    finally:
        manifest.close()


if __name__ == "__main__":
    raise SystemExit(main())
