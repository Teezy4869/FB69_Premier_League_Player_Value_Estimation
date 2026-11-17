"""Evidence-first capture validation and batch stop decisions for Phase 2B.1."""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from collections import Counter
from pathlib import Path

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.historical_lineup_validator import verify_detail
from src.collection.reliability_runner import profile_entry, schema_state
from src.collection.source_registry import canonical_params, validate_scope
from src.collection.statistics_catalog import board_spec
from src.collection.statistics_semantics import collapse_stat_occurrences

BATCH_FIELDS = ["task_id", "request_key", "season_label", "stage", "resource_type", "decision",
                "schema_status", "scope_status", "error_classification", "raw_path", "capture_id",
                "missing_value_count", "note"]


def metric_rules() -> dict:
    with (ROOT / "reports/phase_02b0/metric_dictionary_v2.csv").open(encoding="utf-8", newline="") as handle:
        return {r["normalized_field"]: r for r in csv.DictReader(handle)}


def recovered_source_url(meta: dict) -> str:
    if meta.get("source_url"):
        return meta["source_url"]
    path = ROOT / "reports/phase_02b0/source_integrity_report.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["capture_id"] == meta["capture_id"]:
                return row["source_url"]
    return ""


def inspect_capture(task: dict, meta: dict, payload: dict,
                    profile_payload: dict | None = None) -> dict:
    raw_path = meta.get("raw_path", "")
    base = {"task_id": task["task_id"], "request_key": task["request_key"],
            "season_label": task["season_label"], "stage": task["stage"],
            "resource_type": task["resource_type"], "raw_path": raw_path,
            "capture_id": meta.get("capture_id", ""), "missing_value_count": 0,
            "schema_status": "NOT_CHECKED", "scope_status": "NOT_CHECKED",
            "error_classification": "", "decision": "QUARANTINED", "note": ""}

    def reject(reason: str, code: str = "QUALITY_ERROR") -> dict:
        base.update({"decision": "QUARANTINED", "error_classification": code, "note": reason})
        return base

    if not raw_path or not (ROOT / raw_path).is_file():
        return reject("Missing raw response", "RAW_MISSING")
    body = (ROOT / raw_path).read_bytes()
    if hashlib.sha256(body).hexdigest() != meta.get("content_sha256"):
        return reject("Raw SHA-256 mismatch", "RAW_CORRUPTION")
    if not all((meta.get("capture_id"), meta.get("collected_at_utc"), recovered_source_url(meta),
                meta.get("content_sha256"), meta.get("request_key"))):
        return reject("Incomplete capture provenance", "PROVENANCE_INCOMPLETE")
    cross_season_profile = (task["endpoint"] == "playerData" and
                            meta.get("season_label") != task["season_label"] and
                            profile_entry(payload, task["season_label"]) is not None)
    if (meta["request_key"] != task["request_key"] or meta.get("endpoint") != task["endpoint"] or
            (not cross_season_profile and meta.get("season_label") != task["season_label"]) or
            (not cross_season_profile and str(meta.get("season_id")) != str(task["season_id"])) or
            canonical_params(meta.get("params") or {}) != canonical_params(task["params"])):
        return reject("Request identity or season metadata differs", "REQUEST_IDENTITY_COLLISION")
    if meta.get("http_status") != 200 or "json" not in meta.get("content_type", "").lower():
        return reject("HTTP or content type invalid", "HTTP_OR_CONTENT_ERROR")
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return reject("Raw body is not JSON", "JSON_PARSE_ERROR")
    if decoded != payload:
        return reject("Cached payload differs from wire body", "RAW_PAYLOAD_MISMATCH")
    schema, schema_note = schema_state(task["endpoint"], payload, task["params"])
    base["schema_status"] = schema
    if schema == "SCHEMA_ERROR":
        return reject(schema_note, "SCHEMA_ERROR")
    scope, scope_note = validate_scope(task["endpoint"], task["params"], task["season_label"],
                                       task["season_id"], payload)
    if task["endpoint"] == "matchDetails":
        scope, scope_note = verify_detail(payload, task["context"]["fixture"])
    if task["endpoint"] == "playerData":
        entry = profile_entry(payload, task["season_label"])
        if not entry:
            return reject("No target Premier League season entry in profile", "MISSING_SEASON_ENTRY")
        scope, scope_note = "PROFILE_ENTRY_LINKED", (f"Target season entry {entry}; current profile fields remain CURRENT_ONLY" +
                                                    (f"; reused capture from {meta['season_label']}" if cross_season_profile else ""))
    if task["endpoint"] == "playerStats":
        expected = task["params"].get("seasonId")
        if not profile_payload or profile_entry(profile_payload, task["season_label"]) != expected:
            return reject("playerStats season entry lacks checked profile support", "UNVERIFIED_SEASON_ENTRY")
        scope, scope_note = "PROFILE_ENTRY_LINKED", "Season entry checked against playerData; no direct season field"
    base["scope_status"] = scope
    if scope in ("HISTORICAL_SCOPE_MISMATCH", "REJECTED"):
        return reject(scope_note, "HISTORICAL_SCOPE_MISMATCH")
    if scope == "UNVERIFIED":
        return reject(scope_note, "HISTORICAL_SCOPE_UNVERIFIED")

    missing = 0
    if task["endpoint"] == "leagues":
        fixtures = payload["fixtures"]["allMatches"]
        ids = [str(item.get("id")) for item in fixtures]
        if len(ids) != len(set(ids)) or any(not x.isdigit() for x in ids):
            return reject("Duplicate or missing fixture IDs", "DUPLICATE_OR_MISSING_ID")
        completed = sum(bool((item.get("status") or {}).get("finished")) and
                        not bool((item.get("status") or {}).get("cancelled")) for item in fixtures)
        if completed != 380:
            return reject(f"Completed fixture count {completed}, expected 380", "FIXTURE_COUNT_MISMATCH")
    if task["endpoint"] == "leagueseasondeepstats":
        stat = task["params"]["stat"]
        spec = board_spec(stat)
        if spec is None:
            return reject("Metric is absent from validated leaderboard plan", "METRIC_UNIT_MISMATCH")
        rules = metric_rules().get(spec["metric"])
        if rules and rules["aggregation_type"] != spec["aggregation"]:
            return reject("Metric dictionary aggregation changed", "METRIC_UNIT_MISMATCH")
        if rules and rules["unit"] != spec["unit"] and spec["metric"] not in (
                "expected_goals", "expected_assists", "goals_prevented"):
            return reject("Metric dictionary unit changed", "METRIC_UNIT_MISMATCH")
        if spec.get("required_substat_title") and payload.get("substatTitle") != spec["required_substat_title"]:
            return reject("Required leaderboard substat is absent", "METRIC_UNIT_MISMATCH")
        keys = []
        for row in payload["statsData"]:
            pid, tid = str(row.get("id")), str(row.get("teamId"))
            if not pid.isdigit() or not tid.isdigit():
                return reject("Missing leaderboard player/team ID", "MISSING_ID")
            keys.append((pid, tid))
            value = (row.get("substatValue") if spec["source_field"] == "substatValue.value" else row.get("statValue")) or {}
            if not isinstance(value, dict):
                return reject("Metric source field has unexpected type", "SCHEMA_ERROR")
            if value.get("value") is None:
                missing += 1  # Explicit missing, never coerced to zero.
        if len(keys) != len(set(keys)):
            return reject("Duplicate leaderboard player/team key", "DUPLICATE_ID")
    participation_note = ""
    statistics_note = ""
    if task["endpoint"] == "playerStats":
        items, duplicate_conflicts = collapse_stat_occurrences(payload)
        missing += sum(item["raw_value"] is None for item in items.values())
        if duplicate_conflicts:
            statistics_note = f"{len(duplicate_conflicts)} duplicate source-field conflicts retained for reconciliation"
        elif not items:
            statistics_note = "empty statistic items; metric cells remain MISSING"
    if task["endpoint"] == "matchDetails":
        general = payload["general"]
        if str(general.get("matchId")) != str(task["params"]["matchId"]):
            return reject("Match ID differs from request", "MISSING_ID")
        lineup = (payload.get("content") or {}).get("lineup") or {}
        if lineup.get("lineupType") != "standard":
            participation_note = "participation lineup not standard"
        else:
            seen = set()
            gaps = []
            for side, team_id in (("homeTeam", task["context"]["fixture"]["home_team_id"]),
                                  ("awayTeam", task["context"]["fixture"]["away_team_id"])):
                team = lineup.get(side) or {}
                if str(team.get("id")) != team_id:
                    return reject("Lineup team differs from season fixture", "HISTORICAL_SCOPE_MISMATCH")
                for role in ("starters", "subs"):
                    members = team.get(role)
                    if not isinstance(members, list):
                        gaps.append(f"{side}.{role}")
                        continue
                    if role == "starters" and len(members) != 11:
                        gaps.append(f"{side}.starters_count={len(members)}")
                    for member in members:
                        pid = str(member.get("id")) if isinstance(member, dict) else "None"
                        if not pid.isdigit():
                            return reject("Missing lineup player ID", "DUPLICATE_OR_MISSING_ID")
                        if pid in seen:
                            return reject("Duplicate player within match lineup", "DUPLICATE_OR_MISSING_ID")
                        seen.add(pid)
            if gaps:
                participation_note = "missing lineup lists: " + ", ".join(gaps)
    base.update({"decision": "VALIDATED", "missing_value_count": missing,
                 "note": f"{schema_note}; {scope_note}" +
                         (f"; {participation_note}" if participation_note else "") +
                         (f"; {statistics_note}" if statistics_note else "")})
    return base


def batch_decision(rows: list[dict], cfg: dict) -> dict:
    errors = Counter(r["error_classification"] for r in rows if r["error_classification"])
    critical = {"RAW_MISSING", "RAW_CORRUPTION", "RAW_PAYLOAD_MISMATCH", "RAW_CAPTURE_ERROR",
                "CACHE_CORRUPTION", "REQUEST_IDENTITY_COLLISION",
                "HISTORICAL_SCOPE_MISMATCH", "PROVENANCE_INCOMPLETE", "DUPLICATE_ID", "DUPLICATE_OR_MISSING_ID"}
    stop = any(errors[x] for x in critical)
    stop |= errors["SCHEMA_ERROR"] >= cfg["quality"]["max_consecutive_schema_errors"]
    # A contiguous burst of HTTP-200 JSON-null playerStats responses can reflect
    # a transient source fault, even when isolated nulls are legitimate gaps.
    stop |= len(rows) >= 3 and all(r.get("error_classification") == "NO_STATS_PAYLOAD" for r in rows[-3:])
    stop |= errors["ACCESS_DENIED"] > 0 or errors["RATE_LIMITED"] > 0
    stop |= errors["SERVER_ERROR"] >= cfg["quality"]["max_consecutive_server_errors"]
    return {"decision": "STOP" if stop else "REVIEW" if errors else "PASS",
            "task_count": len(rows), "validated": sum(r["decision"] == "VALIDATED" for r in rows),
            "errors": dict(errors), "missing_metric_values": sum(int(r.get("missing_value_count") or 0) for r in rows)}


def write_batch_report(rows: list[dict], cfg: dict) -> tuple[Path, dict]:
    report_dir = ROOT / cfg["report_dir"] / "batches"
    report_dir.mkdir(parents=True, exist_ok=True)
    batch_id = "batch_" + uuid.uuid4().hex
    decision = batch_decision(rows, cfg)
    decision["batch_id"] = batch_id
    csv_path = report_dir / (batch_id + ".csv")
    temp = csv_path.with_name(csv_path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATCH_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    temp.replace(csv_path)
    atomic_write(report_dir / (batch_id + ".json"), json_bytes(decision))
    return csv_path, decision
