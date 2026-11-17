"""Rebuild Execution 03 metric evidence and coverage from the immutable raw cache."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import pyarrow as pa
import pyarrow.parquet as pq

from src.collection.batch_quality import inspect_capture
from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import cached, registries, profile_for_stats
from src.collection.statistics_catalog import board_spec, load_statistics_config, write_csv
from src.collection.statistics_dictionary import dictionary_rows
from src.collection.statistics_semantics import (collapse_stat_occurrences, leaderboard_coverage,
                                                 metric_denominator, validate_board_filter, value_status)
from src.collection.source_registry import canonical_params

OBS_FIELDS = ["season_label", "season_id", "player_id", "player_name", "team_id", "team_count",
              "metric_name", "metric_group", "original_metric_name", "original_source_field",
              "source_title", "raw_value", "value", "source_format", "source_reported_unit",
              "unit", "aggregation_type", "source_endpoint", "source_component",
              "source_per90", "season_entry", "metric_status", "request_key", "capture_id",
              "collection_timestamp", "collected_at_utc", "raw_path", "in_appeared_population"]
EX_FIELDS = ["season_label", "player_id", "metric_name", "exception_type", "detail",
             "request_key", "capture_id", "raw_path"]
RECON_FIELDS = ["season_label", "player_id", "metric_name", "board_team_id", "board_value",
                "player_stats_value", "unit", "aggregation_type", "comparison_status",
                "board_capture_id", "player_stats_capture_id"]


def exception(season="", player="", metric="", kind="", detail="", meta=None):
    meta = meta or {}
    return {"season_label": season, "player_id": player, "metric_name": metric,
            "exception_type": kind, "detail": detail, "request_key": meta.get("request_key", ""),
            "capture_id": meta.get("capture_id", ""), "raw_path": meta.get("raw_path", "")}


def observation(*, season, season_id, player, name, team, team_count, metric, group, field,
                title, raw, unit, aggregation, endpoint, component, per90, entry, status,
                meta=None, in_population=True, source_format="", source_reported_unit=""):
    meta = meta or {}
    return dict(zip(OBS_FIELDS, [season, str(season_id), str(player), name or "", str(team) if team is not None else "",
        int(team_count or 0), metric, group, field or "", field or "", title or "", "" if raw is None else str(raw),
        value_status(raw)[1], source_format or "", source_reported_unit or "", unit, aggregation,
        endpoint, component or "", "" if per90 is None else str(per90),
        entry or "", status, meta.get("request_key", ""), meta.get("capture_id", ""),
        meta.get("collected_at_utc", ""), meta.get("collected_at_utc", ""),
        meta.get("raw_path", ""), bool(in_population)]))


def player_metric(item: dict | None, rule: dict) -> tuple[object, str, str, object]:
    aliases = [x.strip() for x in rule["original_source_fields"].split("|") if x.strip()]
    if not aliases or rule["normalized_field"] == "key_passes":
        return None, "", "", None
    for field in aliases:
        per90 = field.endswith(".per90")
        base = field[:-6] if per90 else field
        if base in item:
            source = item[base]
            return (source["source_per90"] if per90 else source["raw_value"],
                    field, source.get("title") or "", source.get("source_per90"))
    return None, aliases[0], "", None


def reconcile(observations: list[dict]) -> list[dict]:
    """Only compare a season total to a same-unit board value for a one-club player."""
    indexed = defaultdict(list)
    for row in observations:
        if row["source_endpoint"] in ("playerStats", "leagueseasondeepstats") and row["value"] is not None:
            indexed[(row["season_label"], row["player_id"], row["metric_name"],
                     row["unit"], row["aggregation_type"])].append(row)
    result = []
    for (season, player, metric, unit, aggregation), rows in indexed.items():
        boards = [r for r in rows if r["source_endpoint"] == "leagueseasondeepstats"]
        stats = [r for r in rows if r["source_endpoint"] == "playerStats"]
        for board in boards:
            for stat in stats:
                board_raw = board["raw_value"]
                decimals = len(board_raw.split(".", 1)[1]) if "." in board_raw and "e" not in board_raw.lower() else 0
                displayed = float(Decimal(str(stat["value"])).quantize(
                    Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))
                status = ("INCOMPARABLE_MULTICLUB" if board["team_count"] > 1 else
                          "MATCH" if abs(board["value"] - stat["value"]) < 1e-9 else
                          "MATCH_ROUNDED" if displayed == board["value"] else "CONFLICTING")
                result.append(dict(zip(RECON_FIELDS, [season, player, metric, board["team_id"],
                    board["value"], stat["value"], unit, aggregation, status,
                    board["capture_id"], stat["capture_id"]])))
    return sorted(result, key=lambda r: (r["season_label"], r["metric_name"], r["player_id"]))


def build_report() -> dict:
    cfg = load_statistics_config()
    full = load_full_config()
    report_dir = ROOT / cfg["report_dir"]
    output_dir = ROOT / cfg["metric_output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    population = pq.read_table(ROOT / cfg["population_path"], columns=[
        "season_label", "season_id", "player_id", "player_name", "team_count"]).to_pylist()
    people = {(r["season_label"], r["player_id"]): r for r in population}
    appeared = defaultdict(set)
    for row in population:
        appeared[row["season_label"]].add(row["player_id"])
    rules = dictionary_rows()
    rules_by_name = {r["normalized_field"]: r for r in rules}
    observations, exceptions, board_report = [], [], []
    manifest = Manifest(ROOT / full["manifest_path"])
    current, old = registries(full)
    try:
        tasks = manifest.all_tasks()
        by_type = defaultdict(list)
        for task in tasks:
            by_type[task["resource_type"]].append(task)
        boards = by_type["CANDIDATE_LEADERBOARD"] + by_type["SEASON_METRIC_LEADERBOARD"]
        confirmed_gk = defaultdict(set)
        for task in boards:
            season = task["season_label"]
            spec = board_spec(task["params"]["stat"])
            if spec is None:
                continue
            result = cached(task, current, old) if task["execution_state"] == "VALIDATED" else None
            if result is None:
                exceptions.append(exception(season, metric=spec["metric"], kind="BOARD_UNAVAILABLE",
                                            detail=task["execution_state"]))
                continue
            meta, payload = result
            quality = inspect_capture(task, meta, payload)
            filter_status = validate_board_filter(payload, task["params"])
            coverage = leaderboard_coverage(payload, appeared[season])
            board_report.append({"season_label": season, "metric_name": spec["metric"],
                "leaderboard_stat": spec["stat"], "unit": spec["unit"], "aggregation_type": spec["aggregation"],
                "validation_decision": quality["decision"], "filter_status": filter_status,
                **coverage, "capture_id": meta["capture_id"], "raw_path": meta["raw_path"]})
            if quality["decision"] != "VALIDATED" or filter_status in ("HISTORICAL_SCOPE_MISMATCH", "TEAM_FILTER_MISMATCH"):
                exceptions.append(exception(season, metric=spec["metric"], kind="BOARD_QUALITY_STOP",
                    detail=quality["error_classification"] or filter_status, meta=meta))
                continue
            if coverage["status"] == "DUPLICATE_PLAYER_ID":
                exceptions.append(exception(season, metric=spec["metric"], kind="DUPLICATE_PLAYER_ID",
                    detail=str(coverage["returned_rows"]), meta=meta))
            if spec["stat"] == "saves":
                confirmed_gk[season].update(str(row["id"]) for row in payload["statsData"])
            for row in payload["statsData"]:
                pid = str(row["id"])
                person = people.get((season, pid), {})
                value_key = "substatValue" if spec["source_field"].startswith("substat") else "statValue"
                value_node = row.get(value_key)
                raw = value_node.get("value") if isinstance(value_node, dict) else None
                status, _ = value_status(raw)
                observations.append(observation(season=season, season_id=task["season_id"], player=pid,
                    name=row.get("name") or person.get("player_name"), team=row.get("teamId"),
                    team_count=person.get("team_count", 0), metric=spec["metric"], group=spec["group"],
                    field=spec["stat"] + "." + spec["source_field"], title=value_node.get("name", "") if isinstance(value_node, dict) else "",
                    raw=raw, unit=spec["unit"], aggregation=spec["aggregation"], endpoint=task["endpoint"],
                    component="statsData", per90=None, entry="", status=status, meta=meta,
                    in_population=bool(person),
                    source_format=value_node.get("format", "") if isinstance(value_node, dict) else ""))
                if not person:
                    exceptions.append(exception(season, pid, spec["metric"], "OUTSIDE_APPEARED_POPULATION",
                                                "Leaderboard ID has no confirmed appearance", meta))
        profiles = {(t["season_label"], str(t["params"]["id"])): t for t in by_type["PLAYER_PROFILE"]}
        stats = {(t["season_label"], str(t["params"]["playerId"])): t for t in by_type["PLAYER_SEASON_STATS"]}
        for person in population:
            season, pid = person["season_label"], person["player_id"]
            task = stats.get((season, pid))
            profile = profiles.get((season, pid))
            meta, items, entry = None, {}, ""
            state = "COLLECTION_PENDING"
            if task and task["execution_state"] == "VALIDATED":
                result = cached(task, current, old)
                if result is not None:
                    meta, payload = result
                    profile_payload = profile_for_stats(task, manifest, current, old)
                    quality = inspect_capture(task, meta, payload, profile_payload)
                    if quality["decision"] == "VALIDATED":
                        items, conflicts = collapse_stat_occurrences(payload)
                        entry = str(task["params"].get("seasonId", ""))
                        state = "VALIDATED"
                        for conflict in conflicts:
                            exceptions.append(exception(season, pid, conflict["original_field"],
                                "DUPLICATE_SOURCE_FIELD_CONFLICT", json.dumps(conflict), meta))
                    else:
                        state = "COLLECTION_FAILED"
                        exceptions.append(exception(season, pid, kind="STATS_QUALITY_STOP",
                            detail=quality["error_classification"], meta=meta))
            elif task and task["execution_state"] in ("FAILED", "QUARANTINED", "BLOCKED"):
                state = "MISSING" if task["error_classification"] == "NO_STATS_PAYLOAD" else "COLLECTION_FAILED"
                exceptions.append(exception(season, pid, kind=task["error_classification"] or "PLAYER_STATS_COLLECTION_FAILED",
                    detail=task["error_classification"] or task["execution_state"],
                    meta={"request_key": task["request_key"],
                          "raw_path": "|".join(task["raw_evidence_refs"])}))
            elif profile and profile["execution_state"] in ("FAILED", "QUARANTINED", "BLOCKED"):
                state = "UNVERIFIED_SEASON_ENTRY"
            for rule in rules:
                metric = rule["normalized_field"]
                if state == "VALIDATED":
                    raw, field, title, per90 = player_metric(items, rule)
                    status, _ = value_status(raw)
                    if metric == "key_passes":
                        status = "UNSUPPORTED"
                    elif rule["applicable_positions"] == "GK_ONLY" and pid not in confirmed_gk[season] and raw is None:
                        status = "UNVERIFIED_POSITION"
                else:
                    raw, field, title, per90, status = None, "", "", None, state
                observations.append(observation(season=season, season_id=person["season_id"], player=pid,
                    name=person["player_name"], team=None, team_count=person["team_count"],
                    metric=metric, group=rule["metric_group"], field=field, title=title,
                    raw=raw, unit=rule["unit"], aggregation=rule["aggregation_type"], endpoint="playerStats",
                    component=items.get(field.removesuffix(".per90"), {}).get("component", "") if field else "",
                    per90=per90, entry=entry, status=status, meta=meta,
                    source_format=items.get(field.removesuffix(".per90"), {}).get("stat_format", "") if field else ""))
        reconciliation = reconcile(observations)
        conflicts = {(r["season_label"], r["player_id"], r["metric_name"], r["board_capture_id"], r["player_stats_capture_id"])
                     for r in reconciliation if r["comparison_status"] == "CONFLICTING"}
        conflict_rows = {(s, p, m, c) for s, p, m, b, t in conflicts for c in (b, t)}
        for row in observations:
            if (row["season_label"], row["player_id"], row["metric_name"], row["capture_id"]) in conflict_rows:
                row["metric_status"] = "CONFLICTING"
        for row in reconciliation:
            if row["comparison_status"] == "CONFLICTING":
                exceptions.append(exception(row["season_label"], row["player_id"], row["metric_name"],
                    "SOURCE_VALUE_CONFLICT", f"board={row['board_value']}; playerStats={row['player_stats_value']}"))
        identities = Counter((r["season_label"], r["player_id"], r["metric_name"],
                              r["source_endpoint"], r["team_id"], r["capture_id"]) for r in observations)
        for identity, count in identities.items():
            if count > 1:
                exceptions.append(exception(identity[0], identity[1], identity[2],
                                            "DUPLICATE_OBSERVATION", f"count={count}"))
        for row in observations:
            value = row["value"]
            if value is not None and ((row["unit"] == "percent" and not 0 <= value <= 100) or
                (row["unit"] == "count" and value < 0) or
                (row["unit"] == "minutes" and value < 0)):
                exceptions.append(exception(row["season_label"], row["player_id"], row["metric_name"],
                    "NUMERIC_RANGE_REVIEW", f"{value} {row['unit']}", row))
        coverage_rows = []
        for season in full["seasons"]:
            for rule in rules:
                metric = rule["normalized_field"]
                denominator = metric_denominator(appeared[season], confirmed_gk[season],
                    rule["applicable_positions"] == "GK_ONLY")
                rows = [r for r in observations if r["season_label"] == season and
                        r["metric_name"] == metric and r["player_id"] in denominator]
                by_status = Counter(r["metric_status"] for r in rows if r["source_endpoint"] == "playerStats")
                observed = {r["player_id"] for r in rows if r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO", "CONFLICTING")}
                coverage_rows.append({"season_label": season, "metric_name": metric,
                    "metric_group": rule["metric_group"], "denominator_scope":
                    "CONFIRMED_GK_FROM_SAVES_BOARD" if rule["applicable_positions"] == "GK_ONLY" else "ALL_APPEARED",
                    "denominator_players": len(denominator), "observed_players_any_source": len(observed),
                    "coverage_fraction": round(len(observed) / len(denominator), 6) if denominator else None,
                    "player_stats_observed": by_status["OBSERVED"] + by_status["OBSERVED_ZERO"] + by_status["CONFLICTING"],
                    "player_stats_zero": by_status["OBSERVED_ZERO"], "player_stats_missing": by_status["MISSING"],
                    "player_stats_conflicting": by_status["CONFLICTING"],
                    "player_stats_pending": by_status["COLLECTION_PENDING"],
                    "player_stats_failed": by_status["COLLECTION_FAILED"] + by_status["UNVERIFIED_SEASON_ENTRY"],
                    "player_stats_unsupported": by_status["UNSUPPORTED"]})
        # Write all products atomically so a rerun after an interrupted batch is deterministic.
        table = pa.Table.from_pylist(observations, schema=pa.schema([
            pa.field(f, pa.float64() if f == "value" else pa.int64() if f == "team_count" else
                     pa.bool_() if f == "in_appeared_population" else pa.string()) for f in OBS_FIELDS]))
        tmp = output_dir / "metric_observations.parquet.tmp"
        pq.write_table(table, tmp, compression="zstd")
        tmp.replace(output_dir / "metric_observations.parquet")
        write_csv(report_dir / "metric_collection_coverage.csv", coverage_rows, list(coverage_rows[0]))
        write_csv(report_dir / "leaderboard_completeness_report.csv", board_report, list(board_report[0]))
        write_csv(report_dir / "metric_collection_exceptions.csv", exceptions, EX_FIELDS)
        write_csv(report_dir / "source_reconciliation.csv", reconciliation, RECON_FIELDS)
        summary = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "appeared_player_seasons": len(population), "dictionary_metrics": len(rules),
            "leaderboards_validated": len(board_report), "observations": len(observations),
            "metrics_with_observed_values": len({r["metric_name"] for r in observations if
                r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO", "CONFLICTING")}),
            "metrics_without_observed_values": sorted(set(rules_by_name) - {r["metric_name"] for r in observations if
                r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO", "CONFLICTING")}),
            "player_stats_validated": sum(t["execution_state"] == "VALIDATED" for t in stats.values()),
            "exceptions": dict(Counter(e["exception_type"] for e in exceptions)),
            "reconciliation": dict(Counter(r["comparison_status"] for r in reconciliation)),
            "seasons": {s: {"appeared": len(appeared[s]), "confirmed_goalkeepers": len(confirmed_gk[s]),
                "profiles_by_state": dict(Counter(t["execution_state"] for t in profiles.values() if t["season_label"] == s)),
                "stats_by_state": dict(Counter(t["execution_state"] for t in stats.values() if t["season_label"] == s)),
                "stats_validated": sum(t["season_label"] == s and t["execution_state"] == "VALIDATED" for t in stats.values()),
                "players_with_valid_stat": len({r["player_id"] for r in observations if r["season_label"] == s and
                    r["in_appeared_population"] and r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO", "CONFLICTING")}),
                "metrics_with_observed_values": len({r["metric_name"] for r in observations if
                    r["season_label"] == s and r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO", "CONFLICTING")}),
                "leaderboards": sum(r["season_label"] == s for r in board_report)} for s in full["seasons"]}}
        for season, x in summary["seasons"].items():
            x["collection_state"] = ("COMPLETE" if x["stats_validated"] == x["appeared"] and
                x["profiles_by_state"].get("VALIDATED", 0) == x["appeared"] and x["leaderboards"] == 22
                else "PARTIAL")
        request_signatures = {(t["endpoint"], tuple(sorted(canonical_params(t["params"]).items())))
                              for t in tasks if t["endpoint"] in ("playerData", "playerStats", "leagueseasondeepstats")}
        request_rows = []
        for line in (ROOT / full["log_path"]).open(encoding="utf-8"):
            record = json.loads(line)
            identity = (record.get("endpoint"), tuple(sorted(canonical_params(record.get("params") or {}).items())))
            if identity in request_signatures:
                request_rows.append(record)
        request_identity_counts = Counter((r["endpoint"], tuple(sorted(canonical_params(r["params"]).items())))
                                          for r in request_rows)
        summary["requests"] = {"attempts": len(request_rows),
            "unique_request_identities": len(request_identity_counts),
            "repeated_request_identities": sum(n > 1 for n in request_identity_counts.values()),
            "task_level_recollection_attempts": sum(n - 1 for n in request_identity_counts.values()),
            "by_endpoint": dict(Counter(r["endpoint"] for r in request_rows)),
            "transport_retry_attempts": sum(int(r.get("retry_index") or 0) > 0 for r in request_rows),
            "http_non_200": sum(r.get("http_status") != 200 for r in request_rows),
            "outcomes": dict(Counter(r.get("outcome", "UNKNOWN") for r in request_rows))}
        quality_counts = Counter()
        quality_errors = Counter()
        for path in (report_dir / "batches").glob("batch_*.csv"):
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if not rows or not any(r["resource_type"] in (
                "PLAYER_PROFILE", "PLAYER_SEASON_STATS", "SEASON_METRIC_LEADERBOARD") for r in rows):
                continue
            decision_path = path.with_suffix(".json")
            if not decision_path.is_file():
                raise ValueError(f"Missing original batch decision: {decision_path}")
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            quality_counts[decision["decision"]] += 1
            quality_errors.update(decision["errors"])
        summary["quality_gate_batches"] = dict(quality_counts)
        summary["quality_gate_errors_historical"] = dict(quality_errors)
        summary["current_unresolved_task_errors"] = dict(Counter(t["error_classification"]
            for t in tasks if t["error_classification"] and t["execution_state"] in
            ("QUARANTINED", "FAILED", "BLOCKED", "RETRY_PENDING")))
        atomic_write(report_dir / "season_statistics_summary.json", json_bytes(summary))
        lines = ["# Phase 2B.1 Execution 03: Season Statistics", "",
                 f"Generated: {summary['generated_at_utc']}", "",
                 f"Appeared player-seasons: {len(population)}; dictionary metrics: {len(rules)}; leaderboard captures: {len(board_report)}.",
                 "", "| Season | State | Appeared | Represented by valid statistic | playerStats validated | Boards | Metrics observed | Confirmed GK |",
                 "|---|---|---:|---:|---:|---:|---:|---:|"]
        for season, x in summary["seasons"].items():
            lines.append(f"| {season} | {x['collection_state']} | {x['appeared']} | {x['players_with_valid_stat']} | {x['stats_validated']} | {x['leaderboards']} | {x['metrics_with_observed_values']} | {x['confirmed_goalkeepers']} |")
        lines.extend(["", "## Core metric coverage", "",
                      "| Season | Minutes | Goals | xG | xA | Saves | Key passes |", "|---|---:|---:|---:|---:|---:|---:|"])
        core = {(r["season_label"], r["metric_name"]): r for r in coverage_rows}
        for season in full["seasons"]:
            values = []
            for metric in ("minutes_played", "goals", "expected_goals", "expected_assists", "saves", "key_passes"):
                row = core[(season, metric)]
                values.append(f"{row['observed_players_any_source']}/{row['denominator_players']}")
            lines.append("| " + season + " | " + " | ".join(values) + " |")
        lines.extend(["", "Ranked boards with fewer rows than appeared players have PARTIAL_RANKED_OR_FILTERED status unless explicit pagination metadata exists.",
            "COMPLETE means all planned collection tasks passed their season gates; it does not mean every metric is available for every appeared player.",
            "Board team tags are retained. A playerStats season total is compared with a leaderboard value only for a one-club appeared player and the same metric, unit, and aggregation.",
            "Missing values are never imputed as zero. Goalkeeper denominators use only IDs confirmed by the saves leaderboard and are a lower-bound position cohort.",
            "The API payload does not provide a stable explicit unit for every source item; source_reported_unit remains blank in those observations. Normalized unit and source format are separate columns.",
            "Current playerData profile fields are excluded; only the checked EPL statSeasons entry supports playerStats scope.",
            "", f"Requests: {summary['requests']}", f"Exceptions: {summary['exceptions']}",
            f"Quality gates (historical batches): {summary['quality_gate_batches']}; errors seen: {summary['quality_gate_errors_historical']}",
            f"Current unresolved task errors: {summary['current_unresolved_task_errors']}",
            f"Reconciliation: {summary['reconciliation']}",
            f"Metrics with no observed values at this checkpoint: {summary['metrics_without_observed_values']}",
            "", "Detailed per-season, per-metric denominators and missingness are in metric_collection_coverage.csv.",
            "The source API has no verified pagination or team-filter contract in these captures; no unverified page or team probes were made."])
        pending = sum(t["execution_state"] in ("PLANNED", "RUNNING", "RETRY_PENDING", "FETCHED")
                      for t in tasks if t["resource_type"] in ("PLAYER_PROFILE", "PLAYER_SEASON_STATS"))
        if pending:
            lines.extend(["", "## Resume", "", f"Pending player tasks: {pending}.", "",
                          "```powershell", "python -m src.collection.statistics_recover_sparse",
                          "python -m src.collection.statistics_execution03 --execute --max-batches 100 --max-requests 50",
                          "python -m src.collection.statistics_report", "```"])
        else:
            lines.extend(["", "## Checkpoint", "",
                          "No player task is pending or retryable. No collection resume is required.",
                          "Regenerate reports without HTTP: `python -m src.collection.statistics_report` and `python -m src.collection.statistics_audit`."])
        atomic_write(report_dir / "full_season_statistics_report.md", ("\n".join(lines) + "\n").encode("utf-8"))
        return summary
    finally:
        manifest.close()


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build_report(), indent=2))
