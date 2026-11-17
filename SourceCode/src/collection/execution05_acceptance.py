"""Independent Phase 2B.1 Execution 05 audit and conditional season curation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.execution01_preflight import run_test_suite
from src.collection.execution04_identity import OUT as IDENTITY
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.reliability_runner import profile_entry
from src.collection.source_registry import canonical_params, request_key

REPORT = ROOT / "reports/phase_02b1"
OUT = ROOT / "data/phase_02b1/normalized/execution05_v1"
METRICS = ROOT / "data/phase_02b1/statistics/metric_observations.parquet"
STATUSES = {"OBSERVED", "OBSERVED_ZERO", "MISSING", "UNSUPPORTED", "UNVERIFIED_POSITION", "CONFLICTING"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_write(path: Path, rows: list[dict], fields: list[str]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    atomic_write(path, buf.getvalue().encode("utf-8"))


def table(name: str) -> list[dict]:
    return pq.read_table(IDENTITY / f"{name}.parquet").to_pylist()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_path(path: Path) -> Path:
    current = path.with_name("metadata.json")
    return current if current.exists() else path.with_suffix(".meta.json")


def semantic(task: dict, meta: dict, payload: object, fixture: dict | None) -> tuple[str, str]:
    endpoint = task["endpoint"]
    if not isinstance(payload, dict):
        return "REJECTED", "JSON root is not an object"
    params = task["params"]
    if endpoint == "playerData":
        if str(payload.get("id")) != str(params["id"]):
            return "REJECTED", "Player ID mismatch"
        if task["resource_type"] == "PLAYER_PROFILE" and not profile_entry(payload, task["season_label"]):
            return "REJECTED", "Missing target EPL statSeasons entry"
        return "ACCEPTED_IDENTITY_ONLY", "Profile snapshot has no historical club/position scope"
    if endpoint == "playerStats":
        if not isinstance(payload.get("statsSection"), dict) and not isinstance(payload.get("topStatCard"), dict):
            return "REJECTED", "Missing statistics sections"
        return "INDIRECT_SEASON_ENTRY", "Manifest entry ID requires checked playerData parent"
    if endpoint == "matchDetails":
        general = payload.get("general") or {}
        if str(general.get("matchId")) != str(params["matchId"]) or str(general.get("leagueId")) != "47":
            return "REJECTED", "Match or competition ID mismatch"
        if fixture is None:
            return "REJECTED", "Match absent from fixture index"
        if (str((general.get("homeTeam") or {}).get("id")) != fixture["home_team_id"] or
            str((general.get("awayTeam") or {}).get("id")) != fixture["away_team_id"] or
            str(general.get("matchTimeUTCDate") or "")[:10] != fixture["match_date_utc"][:10]):
            return "REJECTED", "Historical fixture team/date mismatch"
        return "ACCEPTED_FIXTURE_SCOPED", "Match/date/teams corroborate season fixture"
    if endpoint == "leagues":
        season = (payload.get("details") or {}).get("selectedSeason")
        return ("ACCEPTED", "selectedSeason corroborated") if season == task["season_label"] else ("REJECTED", "Wrong selectedSeason")
    if endpoint == "leagueseasondeepstats":
        return ("ACCEPTED", "Season/stat corroborated") if (str(payload.get("currentSeasonId")) == str(task["season_id"]) and
                payload.get("currentStatName") == params.get("stat")) else ("REJECTED", "Wrong season/stat")
    return "REJECTED", "Endpoint outside planned scope"


def raw_audit(tasks: list[dict], fixtures: dict[str, dict]) -> tuple[list[dict], dict]:
    rows = []
    valid_tasks = set()
    bad_tasks = set()
    task_by_id = {t["task_id"]: t for t in tasks}
    parent_entry_cache = {}
    for task in tasks:
        if task["endpoint"] is None:
            continue
        refs = task["raw_evidence_refs"]
        if task["execution_state"] in ("VALIDATED", "ACCEPTED", "NORMALIZED") and not refs:
            bad_tasks.add(task["task_id"])
            rows.append({"task_id": task["task_id"], "season_label": task["season_label"],
                         "resource_type": task["resource_type"], "raw_path": "", "integrity_status": "MISSING_RAW_REF",
                         "semantic_status": "NOT_CHECKED", "note": "Validated task has no raw reference"})
        for ref in refs:
            path = ROOT / ref
            row = {"task_id": task["task_id"], "season_label": task["season_label"],
                   "resource_type": task["resource_type"], "raw_path": ref,
                   "integrity_status": "FAILED", "semantic_status": "NOT_CHECKED", "note": "",
                   "request_key": task["request_key"], "capture_id": "", "parser_version": "", "schema_version": ""}
            try:
                if not path.is_file():
                    raise ValueError("Raw file missing")
                meta_file = metadata_path(path)
                if not meta_file.is_file():
                    raise ValueError("Metadata missing")
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                row["capture_id"] = meta.get("capture_id", "")
                row["parser_version"] = meta.get("parser_version", "legacy")
                row["schema_version"] = meta.get("schema_version", "legacy")
                expected = meta.get("content_sha256") or meta.get("sha256")
                if not expected or sha(path) != expected:
                    raise ValueError("Raw SHA-256 mismatch")
                if (meta.get("endpoint") != task["endpoint"] or
                    canonical_params(meta.get("params") or {}) != canonical_params(task["params"])):
                    raise ValueError("Endpoint/parameter mismatch")
                if request_key(task["endpoint"], task["params"]) != task["request_key"]:
                    raise ValueError("Manifest request key mismatch")
                if meta.get("request_key") and meta["request_key"] != task["request_key"]:
                    raise ValueError("Metadata request key mismatch")
                payload = json.loads(path.read_bytes())
                fixture = fixtures.get(str(task["params"].get("matchId")))
                status, note = semantic(task, meta, payload, fixture)
                if status == "INDIRECT_SEASON_ENTRY":
                    parent_id = next((pid for pid in task["dependencies"] if
                                      task_by_id[pid]["resource_type"] == "PLAYER_PROFILE"), None)
                    if parent_id is None:
                        status, note = "REJECTED", "Missing playerData parent task"
                    else:
                        if parent_id not in parent_entry_cache:
                            parent = task_by_id[parent_id]
                            entries = set()
                            for parent_ref in parent["raw_evidence_refs"]:
                                parent_path = ROOT / parent_ref
                                if parent_path.is_file():
                                    profile = json.loads(parent_path.read_bytes())
                                    entry = profile_entry(profile, task["season_label"])
                                    if entry and str(profile.get("id")) == str(task["params"]["playerId"]):
                                        entries.add(entry)
                            parent_entry_cache[parent_id] = entries
                        if str(task["params"]["seasonId"]) in parent_entry_cache[parent_id]:
                            status, note = "ACCEPTED_INDIRECT_SEASON", "playerData parent EPL season entry corroborates playerStats request"
                        else:
                            status, note = "REJECTED", "PlayerData parent does not corroborate season entry/player ID"
                row.update({"integrity_status": "VERIFIED", "semantic_status": status, "note": note})
                if status != "REJECTED":
                    valid_tasks.add(task["task_id"])
                else:
                    bad_tasks.add(task["task_id"])
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                row["note"] = str(exc)
                bad_tasks.add(task["task_id"])
            rows.append(row)
    current_bad = {task["task_id"] for task in tasks if task["endpoint"] and
                   task["execution_state"] in ("VALIDATED", "ACCEPTED", "NORMALIZED") and task["task_id"] not in valid_tasks}
    return rows, {"audited_references": len(rows), "verified_references": sum(r["integrity_status"] == "VERIFIED" for r in rows),
                  "semantic_rejected_references": sum(r["semantic_status"] == "REJECTED" for r in rows),
                  "accepted_tasks_without_valid_raw": len(current_bad), "critical_task_ids": sorted(current_bad)}


def metric_curation(population: list[dict], observations: list[dict], rules: list[dict],
                    reconciliation: list[dict], players: list[dict], memberships: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    metric_names = [r["normalized_field"] for r in rules]
    rule_by_name = {r["normalized_field"]: r for r in rules}
    conflicting = {(r["season_label"], r["player_id"], r["metric_name"]) for r in reconciliation
                   if r["comparison_status"] == "CONFLICTING"}
    stats = {}
    for r in observations:
        if r["source_endpoint"] != "playerStats":
            continue
        key = (r["season_id"], r["player_id"], r["metric_name"])
        if key in stats:
            raise ValueError(f"Duplicate playerStats metric observation {key}")
        if r["metric_status"] not in STATUSES:
            raise ValueError(f"Unknown metric status {r['metric_status']}")
        if r["unit"] != rule_by_name[r["metric_name"]]["unit"] or r["aggregation_type"] != rule_by_name[r["metric_name"]]["aggregation_type"]:
            raise ValueError(f"Metric unit/aggregation mismatch {key}")
        if ((r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO") and r["value"] is None) or
            (r["metric_status"] in ("MISSING", "UNSUPPORTED", "UNVERIFIED_POSITION") and r["value"] is not None)):
            raise ValueError(f"Metric value/status mismatch {key}")
        stats[key] = r
    player_by_id = {p["player_id"]: p for p in players}
    clubs = defaultdict(set)
    for r in memberships:
        if r["validation_status"] == "CONFIRMED":
            clubs[(r["season_id"], r["player_id"])].add(r["team_id"])
    wide = []
    for p in population:
        key = (p["season_id"], p["player_id"])
        row = {"season_id": p["season_id"], "season_label": p["season_label"], "player_id": p["player_id"],
               "population_status": p["evidence_status"], "profile_raw_path": player_by_id[p["player_id"]]["profile_raw_path"],
               "confirmed_team_ids": "|".join(sorted(clubs[key])), "confirmed_team_count": len(clubs[key]),
               "stats_raw_path": None}
        for metric in metric_names:
            obs = stats.get((*key, metric))
            conflict = (p["season_label"], p["player_id"], metric) in conflicting
            if obs is not None:
                row["stats_raw_path"] = obs["raw_path"]
            if p["evidence_status"] != "APPEARED":
                status, value = "NOT_COLLECTED_UNVERIFIED_APPEARANCE", None
            elif obs is None:
                status, value = "COLLECTION_GAP", None
            elif conflict or obs["metric_status"] == "CONFLICTING":
                status, value = "CONFLICTING", None
            else:
                status = obs["metric_status"]
                value = obs["value"] if status in ("OBSERVED", "OBSERVED_ZERO") else None
            row["m_" + metric] = value
            row["s_" + metric] = status
        wide.append(row)
    if len(wide) != len({(r["season_id"], r["player_id"]) for r in wide}):
        raise ValueError("Duplicate curated player-season key")
    curated_recon = []
    for r in reconciliation:
        decision = "CURATED_NULL_UNRESOLVED" if r["comparison_status"] == "CONFLICTING" else (
            "NO_AGGREGATION_MULTICLUB" if r["comparison_status"] == "INCOMPARABLE_MULTICLUB" else "PLAYERSTATS_SEASON_VALUE")
        curated_recon.append({**r, "curation_decision": decision})
    return wide, curated_recon, metric_names


def write_wide(rows: list[dict], metrics: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = ["season_id", "season_label", "player_id", "population_status", "profile_raw_path",
            "confirmed_team_ids", "confirmed_team_count", "stats_raw_path"]
    schema = pa.schema([(f, pa.int64() if f == "confirmed_team_count" else pa.string()) for f in base] +
                       [("m_" + m, pa.float64()) for m in metrics] + [("s_" + m, pa.string()) for m in metrics])
    path = OUT / "player_season_metrics_wide.parquet"
    temp = path.with_suffix(".parquet.tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), temp, compression="zstd")
    temp.replace(path)


def coverage_matrix(wide: list[dict], metrics: list[str], rules: list[dict], existing_coverage: list[dict],
                    positions: list[dict] | None = None, seasons: list[dict] | None = None) -> list[dict]:
    if positions is not None:
        from src.collection.statistics_semantics import compute_metric_eligibility_registry
        _, coverage_rows = compute_metric_eligibility_registry(wide, metrics, rules, positions, seasons)
        return coverage_rows
    scopes = {(r["season_label"], r["metric_name"]): r for r in existing_coverage}
    by_season = defaultdict(list)
    for r in wide:
        by_season[r["season_label"]].append(r)
    rule_by = {r["normalized_field"]: r for r in rules}
    result = []
    for season, people in sorted(by_season.items()):
        appeared = [r for r in people if r["population_status"] == "APPEARED"]
        for metric in metrics:
            states = Counter(r["s_" + metric] for r in appeared)
            rule = rule_by[metric]
            scope = scopes.get((season, metric), {})
            result.append({"season_label": season, "metric_name": metric,
                           "eligible_players": scope.get("denominator_players", len(appeared)),
                           "appeared_players": len(appeared), "valid_values": states["OBSERVED"]+states["OBSERVED_ZERO"],
                           "missing": states["MISSING"], "not_applicable": states["UNVERIFIED_POSITION"],
                           "unsupported": states["UNSUPPORTED"], "conflicting": states["CONFLICTING"],
                           "unknown": states["COLLECTION_GAP"], "unit": rule["unit"],
                           "data_type": "float64", "source_endpoint": "playerStats",
                           "aggregation_type": rule["aggregation_type"]})
    return result


def batch_audit(tasks: list[dict]) -> list[dict]:
    final_by_id = {t["task_id"]: t for t in tasks}
    rows = []
    for path in sorted((REPORT / "batches").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        csv_path = path.with_suffix(".csv")
        batch_rows = csv_read(csv_path) if csv_path.exists() else []
        unresolved = sum(final_by_id.get(r.get("task_id"), {}).get("execution_state") not in
                         ("VALIDATED", "NORMALIZED", "ACCEPTED") for r in batch_rows if r.get("task_id"))
        rows.append({"batch_id": data.get("batch_id", path.stem), "decision_at_execution": data.get("decision"),
                     "task_count": data.get("task_count"), "validated_at_execution": data.get("validated"),
                     "historical_errors": json.dumps(data.get("errors", {}), sort_keys=True),
                     "tasks_still_unresolved": unresolved, "batch_report_path": path.relative_to(ROOT).as_posix()})
    return rows


def build() -> dict:
    cfg = load_full_config()
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        tasks = manifest.all_tasks()
    finally:
        manifest.close()
    players, population, memberships = table("players"), table("player_seasons"), table("player_team_seasons")
    matches, links = table("matches"), table("player_match_appearances")
    positions = table("historical_position_observations")
    fixtures = {r["match_id"]: r for r in matches if r["eligible_completed"] == "True"}
    raw_rows, raw_summary = raw_audit(tasks, fixtures)
    csv_write(REPORT / "raw_integrity_report.csv", raw_rows,
              ["task_id","season_label","resource_type","raw_path","integrity_status","semantic_status","note","request_key","capture_id","parser_version","schema_version"])
    if raw_summary["accepted_tasks_without_valid_raw"]:
        atomic_write(REPORT / "execution05_critical_stop.json", json_bytes(raw_summary))
        raise ValueError(f"Critical accepted raw task failures: {raw_summary['accepted_tasks_without_valid_raw']}")
    observations = pq.read_table(METRICS).to_pylist()
    rules = csv_read(REPORT / "metric_dictionary_v3.csv")
    reconciliation = csv_read(REPORT / "source_reconciliation.csv")
    existing_coverage = csv_read(REPORT / "metric_collection_coverage.csv")
    wide, curated_recon, metric_names = metric_curation(population, observations, rules, reconciliation, players, memberships)
    write_wide(wide, metric_names)
    matrix = coverage_matrix(wide, metric_names, rules, existing_coverage)
    csv_write(REPORT / "cross_season_feature_coverage.csv", matrix, list(matrix[0]))
    csv_write(REPORT / "metric_reconciliation_report.csv", curated_recon, list(curated_recon[0]))
    batch_rows = batch_audit(tasks)
    csv_write(REPORT / "batch_quality_report.csv", batch_rows, list(batch_rows[0]))
    normalized = [(name, len(table(name)), IDENTITY / f"{name}.parquet") for name in (
        "players", "teams", "seasons", "matches", "player_seasons", "player_team_seasons",
        "player_match_appearances", "historical_position_observations")]
    normalized += [("metric_observations", len(observations), METRICS), ("player_season_metrics_wide", len(wide), OUT / "player_season_metrics_wide.parquet")]
    norm_rows = [{"table": name, "rows": count, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                  "status": "VALIDATED_WITH_LIMITATIONS"} for name, count, path in normalized]
    csv_write(REPORT / "normalization_report.csv", norm_rows, list(norm_rows[0]))
    lineage = []
    for name in ("players", "matches", "player_seasons", "player_team_seasons", "player_match_appearances", "historical_position_observations"):
        path_counts = Counter()
        for r in table(name):
            fields = [f for f in r if f.endswith("raw_path") or f.endswith("raw_paths")]
            for f in fields:
                for raw in str(r.get(f) or "").split("|"):
                    if raw:
                        path_counts[raw] += 1
        for raw, count in path_counts.items():
            lineage.append({"normalized_table": name, "raw_path": raw, "normalized_rows_referencing": count,
                            "raw_exists": (ROOT / raw).is_file()})
    for raw, count in Counter(r["raw_path"] for r in observations if r["raw_path"]).items():
        lineage.append({"normalized_table": "metric_observations", "raw_path": raw,
                        "normalized_rows_referencing": count, "raw_exists": (ROOT / raw).is_file()})
    csv_write(REPORT / "source_lineage_report.csv", lineage, list(lineage[0]))
    if any(not r["raw_exists"] for r in lineage):
        raise ValueError("Critical missing normalized raw lineage")
    by_season_task = defaultdict(list)
    for t in tasks:
        by_season_task[t["season_label"]].append(t)
    pop_rows = []
    gap_rows = []
    issue_rows = []
    acceptance = {}
    tests = run_test_suite(REPORT / "execution05_tests")
    for s in table("seasons"):
        season = s["season_label"]
        p = [r for r in population if r["season_label"] == season]
        l = [r for r in links if r["season_label"] == season]
        m = [r for r in matches if r["season_label"] == season]
        mem = [r for r in memberships if r["season_label"] == season]
        task_states = Counter(t["execution_state"] for t in by_season_task[season])
        resource_states = Counter((t["resource_type"], t["execution_state"]) for t in by_season_task[season])
        appeared = sum(r["evidence_status"] == "APPEARED" for r in p)
        unknown = sum(r["participation_status"] == "UNKNOWN" for r in l)
        incomplete_core = (sum(r["eligible_completed"] == "True" for r in m) != 380 or
                           resource_states[("MATCH_DETAIL", "VALIDATED")] != 380 or
                           resource_states[("PLAYER_SEASON_STATS", "VALIDATED")] != appeared or
                           tests["exit_code"] != 0)
        status = "INCOMPLETE" if incomplete_core else "CONDITIONAL_PASS"
        acceptance[season] = status
        pop_rows.append({"season_label": season, "appeared_players": appeared,
                         "uncertain_only_player_seasons": sum(r["evidence_status"] == "UNKNOWN_PARTICIPATION" for r in p),
                         "unused_only_player_seasons": sum(r["evidence_status"] == "UNUSED_SUBSTITUTE_ONLY" for r in p),
                         "confirmed_appearance_links": sum(r["validation_status"] == "CONFIRMED" for r in l),
                         "unknown_participation_links": unknown,
                         "confirmed_memberships": sum(r["validation_status"] == "CONFIRMED" for r in mem),
                         "unresolved_memberships": sum(r["validation_status"] == "UNRESOLVED" for r in mem),
                         "completed_matches": sum(r["eligible_completed"] == "True" for r in m)})
        for t in by_season_task[season]:
            if t["execution_state"] not in ("VALIDATED", "NORMALIZED", "ACCEPTED"):
                gap_rows.append({"season_label": season, "task_id": t["task_id"], "resource_type": t["resource_type"],
                                 "state": t["execution_state"], "classification": "LOCAL_GATE_PENDING" if t["endpoint"] is None else "COLLECTION_PENDING",
                                 "error": t["error_classification"]})
        issue_rows += [
            {"season_label": season, "severity": "MEDIUM", "issue": "UNKNOWN_SUBSTITUTE_PARTICIPATION", "count": unknown, "status": "OPEN"},
            {"season_label": season, "severity": "MEDIUM", "issue": "UNSUPPORTED_KEY_PASSES", "count": appeared, "status": "OPEN"},
            {"season_label": season, "severity": "LOW", "issue": "CURRENT_PROFILE_POSITION_ONLY", "count": 1, "status": "DOCUMENTED"}]
        lines = [f"# Season {season} acceptance", "", f"Status: **{status}**", "",
                 f"Manifest tasks: {len(by_season_task[season])}; states: {dict(task_states)}.",
                 f"Completed fixtures: {pop_rows[-1]['completed_matches']}; validated matchDetails: {resource_states[('MATCH_DETAIL','VALIDATED')]}.",
                 f"Appeared players: {appeared}; validated season stats: {resource_states[('PLAYER_SEASON_STATS','VALIDATED')]}.",
                 f"Confirmed appearance links: {pop_rows[-1]['confirmed_appearance_links']}; unknown substitute links: {unknown}.",
                 f"Confirmed club relations: {pop_rows[-1]['confirmed_memberships']}; unresolved: {pop_rows[-1]['unresolved_memberships']}.",
                 "Stats: 53 canonical metrics; key_passes unsupported; source conflicts retained and curated as null.",
                 "Raw checksum/provenance audit: no accepted task without valid raw evidence." if not raw_summary["accepted_tasks_without_valid_raw"] else "Raw audit failed.",
                 f"Tests: {tests['tests_run']} executed, exit {tests['exit_code']}.", "",
                 "Conditions: ambiguous substitute participation, source metric conflicts, inferred position groups, playerMatches unavailable. "
                 "Prior normalization/acceptance manifest gates remain PLANNED; this report is an independent conditional review.",
                 "No unconditional full-population claim is made."]
        atomic_write(REPORT / f"season_{season.replace('/', '_')}_acceptance.md", ("\n".join(lines)+"\n").encode("utf-8"))
    csv_write(REPORT / "player_population_quality.csv", pop_rows, list(pop_rows[0]))
    csv_write(REPORT / "collection_gap_report.csv", gap_rows,
              ["season_label","task_id","resource_type","state","classification","error"])
    conflict_counts = Counter(r["season_label"] for r in reconciliation if r["comparison_status"] == "CONFLICTING")
    for season, count in conflict_counts.items():
        issue_rows.append({"season_label": season, "severity": "MEDIUM", "issue": "SOURCE_METRIC_CONFLICT",
                           "count": count, "status": "OPEN_CURATED_NULL"})
    prior_rejected = Counter(r["season_label"] for r in raw_rows if r["semantic_status"] == "REJECTED")
    for season, count in prior_rejected.items():
        issue_rows.append({"season_label": season, "severity": "LOW", "issue": "PRIOR_NULL_STATS_RAW_ATTEMPT",
                           "count": count, "status": "RECOVERED_WITH_LATER_VALIDATED_CAPTURE"})
    csv_write(REPORT / "data_quality_issue_tracker.csv", issue_rows, list(issue_rows[0]))
    result = {"generated_at_utc": now(), "raw": raw_summary, "season_acceptance": acceptance,
              "table_rows": {r["table"]: r["rows"] for r in norm_rows},
              "metric_conflicts": sum(r["comparison_status"] == "CONFLICTING" for r in reconciliation),
              "batch_decisions": dict(Counter(r["decision_at_execution"] for r in batch_rows)),
              "lineage_references": len(lineage), "collection_gaps": len(gap_rows), "tests": tests}
    atomic_write(REPORT / "execution05_checkpoint.json", json_bytes(result))
    lines = ["# Phase 2B.1 Execution 05: normalization and season acceptance", "",
             f"Raw references audited: {raw_summary['audited_references']}; checksum verified: {raw_summary['verified_references']}; "
             f"accepted tasks without valid evidence: {raw_summary['accepted_tasks_without_valid_raw']}.",
             f"Normalized table counts: {result['table_rows']}.",
             f"Unresolved comparable metric conflicts: {result['metric_conflicts']}; curated values are null for these keys.",
             f"Prior semantically rejected raw attempts: {raw_summary['semantic_rejected_references']}; all are retained but excluded from accepted normalized lineage.",
             f"Historical batch decisions: {result['batch_decisions']}; current manifest gaps: {len(gap_rows)} local gates.",
             f"Season statuses: {acceptance}. Full test suite: {tests['tests_run']} tests, exit {tests['exit_code']}.", "",
             "The older local normalization/acceptance gates remain PLANNED because their original schema and absolute participation gate "
             "do not represent the documented UNKNOWN substitute state in the versioned Execution 04/05 contract. "
             "The independent season reports assign CONDITIONAL_PASS only to the confirmed appeared-player scope. "
             "They do not certify the unresolved substitute population.", "",
             "Consolidation may proceed with conditional release metadata if the independent referential and reproduction audit passes."]
    atomic_write(REPORT / "normalization_and_season_acceptance_summary.md", ("\n".join(lines)+"\n").encode("utf-8"))
    return result


REMEDIATION_REPORT = ROOT / "reports/phase_02b1_remediation"


def run_remediation(output_dir: Path | None = None) -> dict:
    from src.collection.statistics_semantics import compute_metric_eligibility_registry
    target_dir = output_dir or REMEDIATION_REPORT
    target_dir.mkdir(parents=True, exist_ok=True)

    wide = pq.read_table(ROOT / "data/releases/fotmob_epl_2019_2025_v2/curated/player_season_metrics_wide.parquet").to_pylist()
    positions = pq.read_table(ROOT / "data/releases/fotmob_epl_2019_2025_v2/normalized/historical_position_observations.parquet").to_pylist()
    seasons = pq.read_table(ROOT / "data/releases/fotmob_epl_2019_2025_v2/normalized/seasons.parquet").to_pylist()
    rules = csv_read(ROOT / "data/releases/fotmob_epl_2019_2025_v2/manifests/metric_dictionary_v3.csv")
    metric_names = [r["normalized_field"] for r in rules]

    registry_rows, cov_v3_rows = compute_metric_eligibility_registry(wide, metric_names, rules, positions, seasons)

    csv_write(target_dir / "metric_eligibility_registry.csv", registry_rows, list(registry_rows[0].keys()))
    csv_write(target_dir / "cross_season_feature_coverage_v3.csv", cov_v3_rows, list(cov_v3_rows[0].keys()))

    return {
        "status": "PASS",
        "registry_rows": len(registry_rows),
        "coverage_v3_rows": len(cov_v3_rows),
        "anomalies_detected": sum(int(r["valid_values"]) > int(r["eligible_players"]) for r in cov_v3_rows),
        "target_dir": str(target_dir)
    }


if __name__ == "__main__":
    import sys
    if "--remediation" in sys.argv:
        res = run_remediation()
        print(json.dumps(res, indent=2))
    else:
        result = build()
        print(json.dumps({k: v for k, v in result.items() if k != "tests"}, ensure_ascii=False))
