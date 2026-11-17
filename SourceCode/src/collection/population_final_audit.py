"""Independent, read-only audit of Execution 02 population outputs and raw evidence."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config


def audit() -> dict:
    cfg = load_full_config()
    folder = ROOT / "data/phase_02b1/population"
    names = ("seasons", "historical_fixture_index", "historical_matches", "historical_player_population",
             "historical_appeared_players", "player_match_appearances", "player_team_season_reference")
    tables = {name: pq.read_table(folder / f"{name}.parquet").to_pylist() for name in names}
    issues = []
    key_fields = {"seasons": ("season_label",), "historical_fixture_index": ("season_label", "match_id"),
                  "historical_player_population": ("season_label", "player_id"),
                  "historical_appeared_players": ("season_label", "player_id"),
                  "player_match_appearances": ("season_label", "match_id", "player_id"),
                  "player_team_season_reference": ("season_label", "player_id", "team_id")}
    for name, fields in key_fields.items():
        keys = [tuple(row[field] for field in fields) for row in tables[name]]
        if len(keys) != len(set(keys)):
            issues.append(f"Duplicate key in {name}")
        if any(any(value is None or value == "" for value in key) for key in keys):
            issues.append(f"Missing key in {name}")
    fixture_rows = tables["historical_fixture_index"]
    eligible = {(r["season_label"], r["match_id"]): r for r in fixture_rows if r["eligible_completed"]}
    all_fixtures = {(r["season_label"], r["match_id"]): r for r in fixture_rows}
    if len(fixture_rows) != 2281 or len(eligible) != 2280:
        issues.append("Fixture index must retain 2281 entries and 2280 completed fixtures")
    abandoned = all_fixtures.get(("2023/2024", "4193691"))
    replay = all_fixtures.get(("2023/2024", "4421797"))
    if not abandoned or not abandoned["cancelled"] or abandoned["eligible_completed"] or not replay or not replay["eligible_completed"]:
        issues.append("Bournemouth-Luton abandoned/replay status mismatch")
    appearance_rows = tables["player_match_appearances"]
    if any((row["season_label"], row["match_id"]) not in eligible for row in appearance_rows):
        issues.append("Appearance references an ineligible fixture")
    if any(row["team_id"] not in (eligible[(row["season_label"], row["match_id"])]["home_team_id"],
                                   eligible[(row["season_label"], row["match_id"])]["away_team_id"])
           for row in appearance_rows if (row["season_label"], row["match_id"]) in eligible):
        issues.append("Appearance team differs from fixture")
    if any(not row["source_id"] or not row["request_key"] or not row["raw_path"] for row in appearance_rows):
        issues.append("Appearance provenance incomplete")
    population = tables["historical_player_population"]
    appeared_rows = tables["historical_appeared_players"]
    if {(r["season_label"], r["player_id"]) for r in appeared_rows} != {
        (r["season_label"], r["player_id"]) for r in population if r["evidence_status"] == "APPEARED"}:
        issues.append("Appeared-player table differs from population status")
    if any(not row["evidence_raw_paths"] for row in population):
        issues.append("Population record has no raw evidence path")
    with (ROOT / cfg["report_dir"] / "population_coverage_by_season.csv").open(encoding="utf-8", newline="") as handle:
        coverage = list(csv.DictReader(handle))
    if len(coverage) != 6:
        issues.append("Coverage report does not contain six seasons")
    by_season = defaultdict(set)
    for row in appearance_rows:
        if row["participation_status"] == "APPEARED":
            by_season[row["season_label"]].add(row["player_id"])
    for row in coverage:
        season = row["season_label"]
        if (int(row["completed_matches"]) != 380 or int(row["match_details_validated"]) != 380 or
            len(by_season[season]) != int(row["unique_appeared_players"])):
            issues.append(f"Coverage count mismatch: {season}")
        if row["status"] != "CONDITIONAL PASS":
            issues.append(f"Unexpected research acceptance status: {season}")
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        detail_tasks = [t for t in manifest.all_tasks() if t["resource_type"] == "MATCH_DETAIL"]
        gates = [t for t in manifest.all_tasks() if t["resource_type"] == "POPULATION_GATE"]
        if len(detail_tasks) != 2280 or any(t["execution_state"] != "VALIDATED" for t in detail_tasks):
            issues.append("Not all 2280 match detail tasks are validated")
        if len(gates) != 6 or any(t["execution_state"] != "VALIDATED" for t in gates):
            issues.append("Not all six population checkpoints are validated")
        for season in cfg["seasons"]:
            path = ROOT / cfg["checkpoint_dir"] / season.replace("/", "_") / "appeared_population.json"
            checkpoint = json.loads(path.read_text(encoding="utf-8"))
            if set(checkpoint["appeared_player_ids"]) != by_season[season]:
                issues.append(f"Population checkpoint differs from appearances: {season}")
    finally:
        manifest.close()
    raw_paths = {row["raw_path"] for row in appearance_rows}
    checksum_count = 0
    for ref in raw_paths:
        path = ROOT / ref
        meta_path = path.with_name("metadata.json") if path.name == "response.json" else path.with_name(
            path.name.replace(".json", ".meta.json"))
        if not path.is_file() or not meta_path.is_file():
            issues.append(f"Missing raw or metadata: {ref}")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected = meta.get("content_sha256") or meta.get("sha256")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            issues.append(f"Raw checksum mismatch: {ref}")
            continue
        checksum_count += 1
    log_path = ROOT / cfg["log_path"]
    outcomes = Counter()
    endpoints = Counter()
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            endpoints[record.get("endpoint")] += 1
            outcomes[record.get("outcome")] += 1
    if endpoints != {"matchDetails": 2258} or outcomes != {"OK": 2258}:
        issues.append("HTTP attempt count, endpoint, or outcome differs from manifest expectation")
    result = {"audit_status": "PASS" if not issues else "FAIL", "issues": issues,
              "table_rows": {name: len(rows) for name, rows in tables.items()},
              "validated_match_details": len(detail_tasks), "validated_population_gates": len(gates),
              "raw_checksums_reverified": checksum_count, "raw_paths_referenced": len(raw_paths),
              "http_attempts": sum(endpoints.values()), "http_endpoints": dict(endpoints),
              "http_outcomes": dict(outcomes),
              "participation_statuses": dict(Counter(r["participation_status"] for r in appearance_rows)),
              "research_acceptance": {r["season_label"]: r["status"] for r in coverage}}
    atomic_write(ROOT / cfg["report_dir"] / "population_final_audit.json", json_bytes(result))
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["audit_status"] == "PASS" else 1)
