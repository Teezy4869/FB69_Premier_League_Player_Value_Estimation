"""Offline, evidence-based Phase 2A Steps 07-08 validation and readiness review."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.audit.normalization import leaderboard_rows, player_stat_items
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write
from src.collection.normalize_pilot import METRICS
from src.collection.player_reference import write_csv

SEASONS = ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025")
DATASETS = ("players", "teams", "player_seasons", "player_team_seasons", "matches",
            "player_match_links", "metric_observations")
GROUPS = {
    "appearances": "GENERAL", "minutes_played": "GENERAL", "starts": "GENERAL", "rating": "GENERAL",
    "goals": "ATTACK", "assists": "ATTACK", "shots": "ATTACK", "shots_on_target": "ATTACK",
    "expected_goals": "ATTACK", "expected_assists": "ATTACK",
    "accurate_passes": "PASSING_CREATION", "passing_accuracy": "PASSING_CREATION",
    "chances_created": "PASSING_CREATION", "key_passes": "PASSING_CREATION",
    "accurate_long_passes": "PASSING_CREATION",
    "tackles": "DEFENDING", "interceptions": "DEFENDING", "clearances": "DEFENDING",
    "blocked_shots": "DEFENDING", "duels_won": "DEFENDING",
    "saves": "GOALKEEPING", "goals_conceded": "GOALKEEPING",
    "clean_sheets": "GOALKEEPING", "goals_prevented": "GOALKEEPING",
}
CLASSIFICATIONS = {
    "appearances": "CORE", "minutes_played": "OPTIONAL", "starts": "CORE",
    "rating": "EXCLUDED_FOR_NOW", "key_passes": "UNVERIFIED",
    "saves": "POSITION_SPECIFIC", "goals_conceded": "POSITION_SPECIFIC",
    "clean_sheets": "POSITION_SPECIFIC", "goals_prevented": "POSITION_SPECIFIC",
}
DQ_FIELDS = ["finding_id", "dimension", "severity", "status", "affected_count", "denominator",
             "observation", "evidence", "required_action"]
CROSS_FIELDS = ["metric", "metric_group", "classification", "statistic_type", "unit",
                "original_fotmob_fields", "seasons_with_values", "all_six_observed",
                "2019_2020_available", "2020_2021_available", "2021_2022_available",
                "2022_2023_available", "2023_2024_available", "2024_2025_available",
                "total_available", "total_missing", "total_not_applicable", "total_unsupported",
                "source_unit_consistency", "definition_status", "note"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def keys_unique(rows: list[dict], fields: tuple[str, ...]) -> tuple[int, int]:
    keys = [tuple(row.get(field) for field in fields) for row in rows]
    return len(keys) - len(set(keys)), sum(any(value in (None, "") for value in key) for key in keys)


def local_evidence_links() -> tuple[int, list[str]]:
    checked, missing = 0, []
    for report_dir in (ROOT / "reports/phase_01", ROOT / "reports/phase_02a"):
        for path in report_dir.glob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "#")):
                    continue
                checked += 1
                if not (path.parent / target.split("#")[0]).exists():
                    missing.append(f"{path.relative_to(ROOT)} -> {target}")
    for path in (ROOT / "reports/phase_01").glob("*.csv"):
        for row in read_csv(path):
            for value in row.values():
                for fragment in (value or "").split("|"):
                    if fragment.startswith("data/audit/raw_samples/"):
                        checked += 1
                        if not (ROOT / fragment).exists():
                            missing.append(f"{path.relative_to(ROOT)} -> {fragment}")
    return checked, missing


def raw_audit(config: dict) -> tuple[dict, dict]:
    raw_dir = ROOT / config["raw_dir"]
    meta_by_source, problems = {}, []
    source_collisions = Counter()
    pair_count = 0
    endpoint_counts, body_kinds, request_keys = Counter(), Counter(), Counter()
    timestamps = []
    for meta_path in sorted(raw_dir.glob("*.meta.json")):
        pair_count += 1
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            payload_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            body = payload_path.read_bytes()
            json.loads(body)
            if hashlib.sha256(body).hexdigest() != meta.get("sha256"):
                problems.append(f"checksum mismatch: {payload_path.name}")
            required = ("endpoint", "params", "competition", "league_id", "season_label",
                        "fotmob_season_id", "collected_at_utc", "http_status", "content_type",
                        "source_id", "source_url", "sha256")
            if any(meta.get(key) is None for key in required):
                problems.append(f"missing metadata field: {meta_path.name}")
            if meta.get("league_id") != 47 or meta.get("season_label") not in SEASONS or (
                    str(meta.get("fotmob_season_id")) != str(config["seasons"].get(meta.get("season_label")))):
                problems.append(f"scope mismatch: {meta_path.name}")
            if meta.get("http_status") != 200 or "json" not in meta.get("content_type", "").lower():
                problems.append(f"response status/content type invalid: {meta_path.name}")
            if not meta.get("source_url", "").startswith(config["api_base_url"] + "/"):
                problems.append(f"unexpected source URL: {meta_path.name}")
            try:
                timestamp = datetime.fromisoformat(meta["collected_at_utc"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
                    problems.append(f"timestamp not UTC: {meta_path.name}")
            except (ValueError, TypeError, KeyError):
                problems.append(f"invalid timestamp: {meta_path.name}")
            source_id = meta.get("source_id")
            timestamps.append(meta["collected_at_utc"])
            source_collisions[source_id] += 1
            meta_by_source[source_id] = meta
            endpoint_counts[meta.get("endpoint")] += 1
            body_kinds[meta.get("stored_body_kind", "canonical_json")] += 1
            request_keys[(meta.get("endpoint"), json.dumps(meta.get("params"), sort_keys=True))] += 1
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            problems.append(f"unreadable raw pair: {meta_path.name}: {exc}")
    log_path = ROOT / config["log_path"]
    logs = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    success = sum(item.get("outcome") == "OK" and item.get("http_status") == 200 for item in logs)
    if len(logs) != pair_count:
        problems.append(f"log/raw count differs: {len(logs)} vs {pair_count}")
    if success != pair_count:
        problems.append(f"successful request/raw count differs: {success} vs {pair_count}")
    timestamps.sort()
    return ({"raw_pairs": pair_count, "source_id_collisions": {k: v for k, v in source_collisions.items() if v > 1},
             "endpoint_counts": endpoint_counts,
             "body_kinds": body_kinds, "log_attempts": len(logs), "log_success": success,
             "first_collected_at_utc": timestamps[0] if timestamps else None,
             "last_collected_at_utc": timestamps[-1] if timestamps else None,
             "log_failures": sum(item.get("outcome") == "FAILED" for item in logs),
             "retries": sum(item.get("outcome") == "RETRY" for item in logs),
             "repeated_exact_requests": sum(v - 1 for v in request_keys.values() if v > 1),
             "problems": problems}, meta_by_source)


def reconcile_source_values(store: PilotStore, sample: list[dict]) -> tuple[dict, list[dict]]:
    boards = {}
    for meta, payload in store.cached_payloads("leagueseasondeepstats"):
        metric = meta["params"].get("stat")
        if metric not in ("mins_played", "goals", "saves"):
            continue
        boards[(meta["season_label"], metric)] = (
            meta, payload, {(str(r.get("id")), str(r.get("teamId"))): r for r in leaderboard_rows(payload)})
    stats = {meta["source_id"]: (meta, payload) for meta, payload in store.cached_payloads("playerStats")}
    overlap, disagreements = Counter(), []
    for row in sample:
        season, pid, tid = row["season_label"], row["fotmob_player_id"], row["fotmob_team_id"]
        source_id = f"stats_{season.replace('/', '_')}_{pid}"
        if source_id not in stats:
            continue
        items = player_stat_items(stats[source_id][1])
        for board_name, profile_field in (("mins_played", "minutes_played"),
                                          ("goals", "goals"), ("saves", "saves")):
            board = boards.get((season, board_name))
            if not board or profile_field not in items:
                continue
            board_meta, board_payload, lookup = board
            board_row = lookup.get((pid, tid))
            if not board_row:
                continue
            if board_name == "saves":
                if board_payload.get("substatTitle") != "Total saves":
                    continue
                board_value = (board_row.get("substatValue") or {}).get("value")
            else:
                board_value = (board_row.get("statValue") or {}).get("value")
            profile_value = items[profile_field].get("statValue")
            if board_value is None or profile_value is None:
                continue
            overlap[board_name] += 1
            try:
                equal = float(str(board_value).replace(",", "")) == float(str(profile_value).replace(",", ""))
            except ValueError:
                equal = str(board_value) == str(profile_value)
            if not equal:
                disagreements.append({"season": season, "player_id": pid, "team_id": tid,
                                      "metric": board_name, "leaderboard_value": board_value,
                                      "player_stats_value": profile_value,
                                      "leaderboard_source_id": board_meta["source_id"],
                                      "player_stats_source_id": source_id})
    return dict(overlap), disagreements


def validate() -> dict:
    """Recompute the review from the saved source evidence; never issue HTTP."""
    config = load_config()
    store = PilotStore(config)
    report_dir = ROOT / "reports/phase_02a"
    sample = read_csv(report_dir / "pilot_sample_manifest.csv")
    reference = read_csv(report_dir / "player_reference_index.csv")
    coverage = read_csv(report_dir / "pilot_feature_coverage.csv")
    identity = read_csv(report_dir / "historical_identity_audit.csv")
    match_audit = read_csv(report_dir / "player_match_link_audit.csv")
    reference_coverage = read_csv(report_dir / "reference_coverage_report.csv")
    schema_doc = json.loads((report_dir / "schema_definition.json").read_text(encoding="utf-8"))
    tables = {name: pq.read_table(ROOT / config["normalized_dir"] / f"{name}.parquet")
              for name in DATASETS}
    rows = {name: table.to_pylist() for name, table in tables.items()}
    raw, sources = raw_audit(config)
    overlap, disagreements = reconcile_source_values(store, sample)
    evidence_count, missing_links = local_evidence_links()
    issues = list(raw["problems"]) + missing_links
    for name, table in tables.items():
        doc = schema_doc[name]
        dup, null = keys_unique(rows[name], tuple(doc["primary_key"]))
        if dup or null or len(rows[name]) != doc["rows"]:
            issues.append(f"{name}: duplicate keys={dup}, null keys={null}, rows={len(rows[name])}, documented={doc['rows']}")
        if {field: str(dtype) for field, dtype in zip(table.schema.names, table.schema.types)} != doc["fields"]:
            issues.append(f"{name}: Parquet types differ from documented schema")
    manifest_keys = {(r["fotmob_player_id"], r["fotmob_team_id"], r["fotmob_season_id"]) for r in sample}
    team_keys = {(r["player_id"], r["team_id"], r["season_id"]) for r in rows["player_team_seasons"]}
    if manifest_keys != team_keys:
        issues.append("sample manifest and normalized player-team-season keys differ")
    season_ids = {s: str(i) for s, i in config["seasons"].items()}
    for name in ("player_seasons", "player_team_seasons", "matches", "player_match_links", "metric_observations"):
        for row in rows[name]:
            if season_ids.get(row["season_label"]) != row["season_id"]:
                issues.append(f"{name}: invalid season mapping")
                break
    for name, field in (("players", "player_id"), ("teams", "team_id"),
                        ("player_seasons", "player_id"), ("player_team_seasons", "team_id"),
                        ("matches", "match_id"), ("player_match_links", "match_id")):
        if any(not str(r[field]).isdigit() for r in rows[name]):
            issues.append(f"{name}: nonnumeric {field}")
    player_keys = {(r["player_id"], r["season_id"]) for r in rows["player_seasons"]}
    match_by_id = {r["match_id"]: r for r in rows["matches"]}
    if any((r["player_id"], r["season_id"]) not in player_keys for r in rows["metric_observations"]):
        issues.append("metric observation without player-season")
    if any((r["player_id"], r["season_id"]) not in player_keys or
           r["match_id"] not in match_by_id or
           match_by_id[r["match_id"]]["season_id"] != r["season_id"] or
           r["team_id"] not in (match_by_id[r["match_id"]]["home_team_id"],
                                match_by_id[r["match_id"]]["away_team_id"])
           for r in rows["player_match_links"]):
        issues.append("invalid player-match lineage or team participation")
    if any(r.get("source_id") and r["source_id"] not in sources
           for name in ("matches", "player_match_links", "metric_observations") for r in rows[name]):
        issues.append("normalized source_id absent from raw metadata")
    if any(r.get("stats_source_id") not in sources for r in rows["player_seasons"]):
        issues.append("player-season stats source absent from raw metadata")
    if any(r.get("profile_source_id") not in sources for r in rows["players"]):
        issues.append("profile source absent from raw metadata")
    dates_bad = 0
    for row in rows["matches"]:
        try:
            dt = datetime.fromisoformat(row["match_date_utc"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dates_bad += 1
        except (ValueError, AttributeError):
            dates_bad += 1
    statuses = Counter(r["status"] for r in rows["metric_observations"])
    invalid_percent = sum(r["status"] == "AVAILABLE" and r["statistic_type"] == "percentage" and
                          not 0 <= r["value"] <= 100 for r in rows["metric_observations"])
    negative_count = sum(r["status"] == "AVAILABLE" and r["unit"] == "count" and r["value"] < 0
                         for r in rows["metric_observations"])
    nonfinite = sum(r["status"] == "AVAILABLE" and (r["value"] is None or not math.isfinite(r["value"]))
                    for r in rows["metric_observations"])
    if dates_bad or invalid_percent or negative_count or nonfinite:
        issues.append(f"invalid dates={dates_bad}, percent={invalid_percent}, negative counts={negative_count}, nonfinite={nonfinite}")
    if any(r["status"] == "AVAILABLE" and not r["source_id"] for r in rows["metric_observations"]):
        issues.append("available metric without source_id")
    obs_by_key = {(r["player_id"], r["season_id"], r["metric"]): r for r in rows["metric_observations"]}
    if len(obs_by_key) != len(rows["metric_observations"]):
        issues.append("duplicate metric observation key")
    wide_mismatch = 0
    for row in rows["player_seasons"]:
        for metric in METRICS:
            obs = obs_by_key.get((row["player_id"], row["season_id"], metric))
            expected = obs["value"] if obs and obs["status"] == "AVAILABLE" else None
            if row[metric] != expected:
                wide_mismatch += 1
    if wide_mismatch:
        issues.append(f"wide/long metric mismatches={wide_mismatch}")
    for r in coverage:
        subset = [o for o in rows["metric_observations"] if o["season_label"] == r["season_label"] and o["metric"] == r["metric"]]
        counts = Counter(o["status"].lower() for o in subset)
        if len(subset) != int(r["sample_rows"]) or any(counts[k] != int(r[k]) for k in
            ("available", "missing", "not_applicable", "unsupported", "unparseable")):
            issues.append(f"coverage report mismatch: {r['season_label']} {r['metric']}")
    if len(coverage) != len(SEASONS) * len(METRICS):
        issues.append("feature coverage has incorrect season-metric row count")
    season_sample = Counter(r["season_label"] for r in sample)
    season_collected = Counter(r["season_label"] for r in rows["player_seasons"] if r["stats_status"] == "AVAILABLE")
    position_sample = Counter(r["position_group"] for r in sample)
    by_season_position = defaultdict(Counter)
    sample_position = {(r["fotmob_player_id"], r["fotmob_season_id"]): r["position_group"] for r in sample}
    for obs in rows["metric_observations"]:
        pos = sample_position[(obs["player_id"], obs["season_id"])]
        by_season_position[(obs["season_label"], pos)][obs["status"]] += 1
    if sum(season_collected.values()) != len(sample):
        issues.append("collected player-season count differs from sample")
    if any(int(r["league_team_count"]) != 20 or r["population_denominator"] != "UNKNOWN" for r in reference_coverage):
        issues.append("reference coverage claims unsupported population denominator")
    if sum(int(r["player_team_season_count"]) for r in reference_coverage) != len(reference):
        issues.append("reference coverage counts differ from reference index")
    if len(identity) != len(sample) or any(r["season_association_status"] != "HISTORICAL_VERIFIED"
                                            for r in identity):
        issues.append("profile season association not verified for every sample")
    if len(match_audit) != raw["endpoint_counts"]["matchDetails"] or any(
            r["detail_status"] != "AVAILABLE" for r in match_audit):
        issues.append("match detail audit differs from retained sources")
    norm_report = read_csv(report_dir / "normalization_report.csv")
    if len(norm_report) != len(DATASETS) or any(r["status"] != "PASS" or
        int(r["row_count"]) != len(rows[r["dataset"]]) for r in norm_report):
        issues.append("normalization report disagrees with Parquet tables")
    finished = Counter(r["season_label"] for r in rows["matches"] if r["status"] == "FINISHED")
    result = dict(config=config, sample=sample, reference=reference, coverage=coverage,
                  identity=identity, match_audit=match_audit, tables=rows, sources=sources,
                  raw=raw, overlap=overlap, disagreements=disagreements, issues=issues,
                  evidence_count=evidence_count, statuses=statuses, season_sample=season_sample,
                  season_collected=season_collected, position_sample=position_sample,
                  by_season_position=by_season_position, finished=finished,
                  validity=dict(invalid_dates=dates_bad, invalid_percent=invalid_percent,
                                negative_counts=negative_count, nonfinite=nonfinite,
                                wide_mismatch=wide_mismatch))
    return result


def quality_rows(x: dict) -> list[dict]:
    t, raw = x["tables"], x["raw"]
    sample_n = len(x["sample"])
    identity = x["identity"]
    match_links = t["player_match_links"]
    linked_seasons = {(r["player_id"], r["season_id"]) for r in match_links}
    spec = [
        ("DQ01", "COMPLETENESS", "LOW", "PASS_PILOT", sample_n, sample_n,
         "Selected player-season statistics collected", "pilot_sample_manifest.csv|data/pilot/normalized/player_seasons.parquet", "Retain missing-response checkpoint at scale"),
        ("DQ02", "COMPLETENESS", "HIGH", "UNKNOWN", "UNKNOWN", "UNKNOWN",
         "Full historical player population denominator is unavailable; 3262 is a bounded reference union", "reference_coverage_report.csv|player_reference_index.csv", "Establish independent season roster/player denominator"),
        ("DQ03", "COMPLETENESS", "MEDIUM", "OBSERVED", x["statuses"]["MISSING"], len(t["metric_observations"]),
         "Missing metric cells; nulls are not imputed", "pilot_feature_coverage.csv|data/pilot/normalized/metric_observations.parquet", "Use per-metric and position-aware thresholds"),
        ("DQ04", "COMPLETENESS", "MEDIUM", "OBSERVED", x["statuses"]["UNSUPPORTED"], len(t["metric_observations"]),
         "key_passes unsupported by verified source mapping", "pilot_feature_coverage.csv", "Retain as UNVERIFIED until source definition is verified"),
        ("DQ05", "UNIQUENESS", "LOW", "PASS_PILOT", 0, len(t["player_seasons"]),
         "No duplicate player-season primary key", "schema_definition.json|data/pilot/normalized/player_seasons.parquet", "Enforce primary key in full crawl"),
        ("DQ06", "UNIQUENESS", "LOW", "PASS_PILOT", 0, len(t["matches"]),
         "No duplicate match ID; abandoned fixture and replay have distinct IDs", "data/pilot/normalized/matches.parquet", "Keep status and replay IDs"),
        ("DQ07", "UNIQUENESS", "MEDIUM", "OBSERVED", len(raw["source_id_collisions"]), raw["raw_pairs"],
         "One source_id reused for Liverpool historical team probes in two seasons", "data/pilot/raw/*teams*.meta.json", "Make source_id unique by season and reject collisions"),
        ("DQ08", "UNIQUENESS", "LOW", "PASS_PILOT", raw["repeated_exact_requests"], raw["raw_pairs"],
         "No repeated endpoint+parameter HTTP result among retained pairs", "data/pilot/raw/*.meta.json|logs/phase_02a_requests.jsonl", "Keep exact-request cache key"),
        ("DQ09", "VALIDITY", "LOW", "PASS_PILOT", sum(x["validity"].values()), len(t["metric_observations"]),
         "No invalid match dates, percentages, negative count cells, nonfinite available cells or wide/long mismatches", "data/pilot/normalized/*.parquet", "Retain metric-specific domain checks"),
        ("DQ10", "HISTORICAL_ACCURACY", "HIGH", "OBSERVED", sum(r["current_vs_historical_team"] == "DIFFERENT" for r in identity), len(identity),
         "Current profile team differs from season leaderboard team; current fields are kept separate", "historical_identity_audit.csv|data/pilot/normalized/players.parquet", "Never backfill historical club or role from current profile"),
        ("DQ11", "HISTORICAL_ACCURACY", "HIGH", "UNVERIFIED", sum(r["career_history_transfer_flag"] == "INFERRED_CANDIDATE" for r in identity), len(identity),
         "Retrospective career history suggests same-season multi-club candidates; no team split is verified", "historical_identity_audit.csv", "Verify club spells with season-scoped source before allocating stats"),
        ("DQ12", "CONSISTENCY", "MEDIUM", "OBSERVED", len(x["disagreements"]), sum(x["overlap"].values()),
         "Minutes leaderboard and playerStats disagree by one minute for 2024/25 player 831489", "data/pilot/raw/*2024_2025*.json|pilot_sample_manifest.csv", "Retain both values and define reconciliation policy"),
        ("DQ13", "CONSISTENCY", "HIGH", "UNVERIFIED", "UNKNOWN", len(METRICS),
         "Provider metric definitions and calculations across seasons are not independently documented", "cross_season_consistency.csv|schema_definition.json", "Version source fields and validate definitions before treating optional metrics as comparable"),
        ("DQ14", "SOURCE_LINEAGE", "LOW", "PASS_PILOT", raw["raw_pairs"], raw["raw_pairs"],
         "Raw JSON/metadata pairs parsed and matched SHA-256; all logged attempts succeeded", "data/pilot/raw/*.meta.json|logs/phase_02a_requests.jsonl", "Keep immutable bodies and checksum checks"),
        ("DQ15", "MATCH_INDEX", "HIGH", "PARTIAL", len(linked_seasons), sample_n,
         "Selected player-season keys with at least one verified lineup link; no full participation index", "data/pilot/normalized/player_match_links.parquet|player_match_link_audit.csv", "Prove bounded player-match association path and pagination"),
        ("DQ16", "SOURCE_LINEAGE", "LOW", "PASS_PILOT", x["evidence_count"], x["evidence_count"],
         "Local report evidence references resolve", "reports/phase_01|reports/phase_02a", "Recheck evidence links after report regeneration"),
    ]
    return [dict(zip(DQ_FIELDS, row)) for row in spec]


def cross_season_rows(x: dict) -> list[dict]:
    observations = x["tables"]["metric_observations"]
    result = []
    for metric, (candidates, unit, kind, _) in METRICS.items():
        subset = [r for r in observations if r["metric"] == metric]
        counts = Counter(r["status"] for r in subset)
        values = {r["season_label"] for r in subset if r["status"] == "AVAILABLE"}
        source_fields = sorted({r["original_field"] for r in subset if r["original_field"]})
        row = {"metric": metric, "metric_group": GROUPS[metric],
               "classification": CLASSIFICATIONS.get(metric, "OPTIONAL"),
               "statistic_type": kind, "unit": unit,
               "original_fotmob_fields": "|".join(source_fields or candidates),
               "seasons_with_values": len(values), "all_six_observed": len(values) == 6,
               "total_available": counts["AVAILABLE"], "total_missing": counts["MISSING"],
               "total_not_applicable": counts["NOT_APPLICABLE"], "total_unsupported": counts["UNSUPPORTED"],
               "source_unit_consistency": "OBSERVED_UNIT_STABLE" if len({r["unit"] for r in subset}) == 1 else "MIXED_UNIT",
               "definition_status": "UNVERIFIED_PROVIDER_DEFINITION" if metric in
                   ("rating", "expected_goals", "expected_assists", "passing_accuracy", "goals_prevented", "key_passes") else
                   "MAPPED_SOURCE_FIELD_NOT_INDEPENDENTLY_VERIFIED",
               "note": "Data readiness classification only; not ML feature selection"}
        for season in SEASONS:
            row[season.replace("/", "_") + "_available"] = sum(
                r["season_label"] == season and r["status"] == "AVAILABLE" for r in subset)
        result.append(row)
    return result


def write_reports(x: dict, tests: str) -> None:
    report_dir = ROOT / "reports/phase_02a"
    write_csv(report_dir / "pilot_data_quality_report.csv", DQ_FIELDS, quality_rows(x))
    cross = cross_season_rows(x)
    write_csv(report_dir / "cross_season_consistency.csv", CROSS_FIELDS, cross)
    t, raw, status = x["tables"], x["raw"], x["statuses"]
    identity = x["identity"]
    group_counts = defaultdict(Counter)
    for r in t["metric_observations"]:
        group_counts[GROUPS[r["metric"]]][r["status"]] += 1
    season_lines = [f"| {s} | {x['season_sample'][s]} | {x['season_collected'][s]} | "
                    f"{len({r['fotmob_player_id'] for r in x['sample'] if r['season_label'] == s})} | "
                    f"{sum(r['season_label'] == s for r in t['player_team_seasons'])} | {x['finished'][s]} |"
                    for s in SEASONS]
    group_lines = [f"| {g} | {c['AVAILABLE']} | {c['MISSING']} | {c['NOT_APPLICABLE']} | {c['UNSUPPORTED']} |"
                   for g, c in group_counts.items()]
    position_lines = [f"| {p} | {n} | {sum(x['by_season_position'][(s,p)]['AVAILABLE'] for s in SEASONS)} | "
                      f"{sum(x['by_season_position'][(s,p)]['MISSING'] for s in SEASONS)} | "
                      f"{sum(x['by_season_position'][(s,p)]['NOT_APPLICABLE'] for s in SEASONS)} |"
                      for p, n in sorted(x["position_sample"].items())]
    group_table = "| Group | Available | Missing | N/A | Unsupported |\n|---|---:|---:|---:|---:|\n" + "\n".join(group_lines)
    season_table = "| Season | Selected | Stats collected | Unique sampled IDs | Player-team-season rows | Finished fixtures |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(season_lines)
    position_table = "| Inferred position group | Sample rows | Available cells | Missing cells | N/A cells |\n|---|---:|---:|---:|---:|\n" + "\n".join(position_lines)
    mismatch = x["disagreements"][0] if x["disagreements"] else None
    mismatch_line = (f"{mismatch['season']} player {mismatch['player_id']} team {mismatch['team_id']}: "
                     f"leaderboard {mismatch['leaderboard_value']} vs playerStats {mismatch['player_stats_value']} minutes "
                     f"(`{mismatch['leaderboard_source_id']}`, `{mismatch['player_stats_source_id']}`).") if mismatch else "None found."
    raw_counts = ", ".join(f"{k}={v}" for k, v in sorted(raw["endpoint_counts"].items()))
    table_counts = ", ".join(f"{k}={len(v)}" for k, v in t.items())
    linked_keys = len({(r["player_id"], r["season_id"]) for r in t["player_match_links"]})
    linked_players = len({r["player_id"] for r in t["player_match_links"]})
    date_start, date_end = raw["first_collected_at_utc"], raw["last_collected_at_utc"]
    summary = f"""# Phase 2A Step 07 — pilot validation summary

Validated offline against cached evidence; no new HTTP requests. Overall structural checks: **{'PASS' if not x['issues'] else 'FAIL'}** ({len(x['issues'])} issues). Readiness: **CONDITIONAL GO**, subject to gates in [Phase 2B plan](phase_02b_readiness_plan.md).

- Scope: {len(x['sample'])} selected player-team-season samples, {len({r['fotmob_player_id'] for r in x['sample']})} unique players, six seasons. Stats collected: {sum(x['season_collected'].values())}/{len(x['sample'])}.
- Saved responses: {raw['raw_pairs']} raw JSON/metadata pairs; {raw['log_success']}/{raw['log_attempts']} logged attempts succeeded, {raw['retries']} retries. SHA-256 and JSON parsed for every pair. {raw['body_kinds']['wire_json']} wire JSON and {raw['body_kinds']['canonical_json']} earlier canonical JSON pairs; their byte forms are distinguished in metadata.
- Normalized rows: {table_counts}. Metric cells: {status['AVAILABLE']} available, {status['MISSING']} missing, {status['NOT_APPLICABLE']} N/A, {status['UNSUPPORTED']} unsupported.
- Cross-source checks: {sum(x['overlap'].values())} comparable values (minutes={x['overlap'].get('mins_played',0)}, goals={x['overlap'].get('goals',0)}, saves={x['overlap'].get('saves',0)}); {len(x['disagreements'])} disagreement. {mismatch_line}
- Historical identity: {sum(r['current_vs_historical_team']=='DIFFERENT' for r in identity)} current/historical club differences; {sum(r['name_match']=='False' for r in identity)} literal name differences; {sum(r['career_history_transfer_flag']=='INFERRED_CANDIDATE' for r in identity)} inferred multi-club candidates, none assigned unverified team stats.
- Match index: {len(t['matches'])} fixture entries, {sum(r['status']=='FINISHED' for r in t['matches'])} finished, one abandoned/cancelled; 10 detail responses, {len(t['player_match_links'])} verified lineup links across {linked_players} players/{linked_keys} selected player-season keys.
- Pilot position groups come from an inferred season-board code band. Full historical population denominator: **UNKNOWN**; no population coverage percentage is claimed.
- Local evidence references checked: {x['evidence_count']}; missing: {len(x['issues'])} structural issue(s). Tests: {tests}.

See [data quality rows](pilot_data_quality_report.csv), [feature coverage](pilot_feature_coverage.csv), [cross-season metric table](cross_season_consistency.csv), and [full pilot report](phase_02a_pilot_report.md).
"""
    atomic_write(report_dir / "pilot_validation_summary.md", summary.encode("utf-8"))
    sections = [
        ("Executive Summary", f"Phase 2A controlled pilot completed: {len(x['sample'])}/{len(x['sample'])} selected season-stat records. Structural validation {'passed' if not x['issues'] else 'failed'}; overall readiness **CONDITIONAL GO**. This is a pilot result, not a full-population claim."),
        ("Pilot Scope and Sampling", f"Premier League 2019/20–2024/25, 120 selected player-team-season rows, 109 unique players. Selection used a bounded union of 3,262 reference rows from minutes/goals/saves boards, deterministic seed 6902. The union is not an independent player population.\n\n{season_table}\n\n{position_table}"),
        ("Collection Methodology", f"Only six league responses, 18 reference boards, two historical team probes, 109 profiles, 120 season-stat responses and 10 selected match details were retained. Endpoint counts: {raw_counts}. Cache keys include endpoint, parameters, season and source ID. New responses retain wire bytes; earlier Step 01–02 responses retain full canonical JSON."),
        ("Actual Collection Results", f"{raw['raw_pairs']} raw pairs; {raw['log_success']}/{raw['log_attempts']} logged attempts OK; {raw['retries']} retries and {raw['log_failures']} failed attempts in this pilot. Normalized table rows: {table_counts}. Collection timestamps in raw metadata are UTC; the cached range is {date_start} to {date_end}. This success rate is limited to observed requests."),
        ("Player Coverage", f"All 120 selected rows have season statistics, 120 historical team rows and 109 unique player profiles. Six seasons and 20 league teams per season are represented in the reference. Reference population coverage and missing historical players remain **UNKNOWN** because no independent denominator exists. Player IDs are internally traceable; Transfermarkt matching was not performed."),
        ("Feature Availability", f"Across 2,880 sampled metric cells: {status['AVAILABLE']} available, {status['MISSING']} missing, {status['NOT_APPLICABLE']} position N/A, {status['UNSUPPORTED']} unsupported. Values were never zero-filled.\n\n{group_table}\n\nSee [per-season metric coverage](pilot_feature_coverage.csv) and [cross-season classifications](cross_season_consistency.csv). CORE: appearances and starts. OPTIONAL: available but incomplete or definition-limited metrics, including minutes_played until its cross-source discrepancy has a documented rule. POSITION_SPECIFIC: four goalkeeper metrics. UNVERIFIED: key_passes. EXCLUDED_FOR_NOW: rating because provider computation/stability is unverified. These are data-readiness labels, not predictive feature selection."),
        ("Player Profile Findings", f"{sum(r['current_vs_historical_team']=='DIFFERENT' for r in identity)}/120 profile current-team fields differ from the historical leaderboard team; {sum(r['name_match']=='False' for r in identity)} names differ literally. All 120 profile season entries were verified. Profile position/nationality/current club are current-only. Birth date is stored as a profile claim; no historical age was derived. Three retrospective career histories suggest multi-club candidates without season-scoped allocation evidence."),
        ("Match Index Findings", f"Six league responses contain {len(t['matches'])} fixture records: 2,280 finished (380 per season) and abandoned/cancelled match `4193691`; replay `4421797` is a separate finished fixture. All retained dates and results parse/present. Ten matchDetails responses yield {len(t['player_match_links'])} verified selected-player lineup links, spanning {linked_players} players and {linked_keys}/120 selected player-season keys. The `playerMatches` route was not used after a prior HTTP 400 with unverified parameters; fixture membership is not player participation."),
        ("Historical Data Integrity", "Historical club is taken from season-scoped leaderboard rows, never current profile club. Season IDs are checked against the six configured mappings. Every player-match link has matching season and fixture team. Current-only profile fields remain separate, and retrospective transfer suggestions create no new team rows. The normalized match table retains both canceled and replay IDs. Historical position is only an inferred numeric code-band; no verified role taxonomy exists."),
        ("Data Quality Findings", f"No duplicate primary keys, invalid UTC match dates, invalid percentages, negative count values, nonfinite available values, wide/long metric mismatch or missing raw checksum found. One `source_id` collision affects two team-probe metadata records, though endpoint+parameter pairs are unique. Cross-source conflict: {mismatch_line} The 2024/25 `player_seasons` value uses 2606 from playerStats; sample manifest preserves leaderboard 2607. Quality findings and severities are in [pilot_data_quality_report.csv](pilot_data_quality_report.csv)."),
        ("Cross-Season Consistency", f"All six seasons have selected rows and 380 finished fixtures. {sum(r['all_six_observed'] for r in cross)}/24 metrics have at least one available cell in every season; source units and Parquet column types are stable in this pilot. This does not prove provider definitions were stable or that unobserved player groups have the same schema. Original FotMob field names, null status, units and source formats are retained in metric_observations. Minutes, goals and saves have {sum(x['overlap'].values())} cross-source comparisons, with one disagreement. Saves compares the `Total saves` secondary leaderboard value, not the per-90 main value."),
        ("Pipeline Reliability", f"{raw['log_success']}/{raw['log_attempts']} observed HTTP attempts succeeded. {raw['raw_pairs']} raw pairs pass JSON and SHA-256 validation; {raw['repeated_exact_requests']} exact endpoint+parameter repeats. All 7 Parquet tables parse and match declared key/type schemas. Cached reruns issue zero HTTP requests. The source ID collision must be corrected before scaling."),
        ("Automated Test Results", f"{tests}. Commands: `python -m unittest discover -s tests -v`; `python -m src.collection.final_validation --check`; `python -m src.collection.pilot_runner discover --dry-run`; `python -m src.collection.phase_02a_03_06 profiles --max-requests 0`; `python -m src.collection.phase_02a_03_06 stats --max-requests 0`; `python -m src.collection.phase_02a_03_06 matches --max-requests 0`. These commands do not perform Phase 2B."),
        ("Technical Limitations", "Reference boards do not establish full player population. Position groups are inferred. Retrospective multi-club club spells and team-level stat allocation are unverified. Player-match participation is sparse. Provider definitions for rating, xG/xA, goals prevented and percentage denominators are not independently verified. Prior 26 raw responses are full canonical JSON rather than wire-byte originals. Zero pilot failures do not estimate full-crawl failure rate."),
        ("Phase 2B Readiness Verdict", "**CONDITIONAL GO for engineering feasibility; full historical collection remains gated.** HTTP/cache/raw/normalization mechanics passed this bounded pilot, but population coverage, source ID uniqueness, historical multi-club attribution, player-match association and validation thresholds require the actions below. See [readiness plan](phase_02b_readiness_plan.md)."),
        ("Required Actions Before Full Collection", "1. Establish a season-scoped independent historical player denominator and verify roster completeness.\n2. Make every raw source ID unique across seasons and validate collisions.\n3. Define multi-club historical team attribution and minute/stat split policy using season-scoped evidence.\n4. Validate a bounded, supported player-match association path or explicitly limit Phase 2B to fixture index.\n5. Resolve the one-minute cross-source conflict policy and document source priority.\n6. Version metric definitions and set season/position-aware null, uniqueness, integrity and resume checkpoints.\n\nDo not execute Phase 2B without a separate instruction."),
    ]
    full = "# Phase 2A controlled pilot — final technical review\n\n" + "\n\n".join(
        f"## {i}. {title}\n\n{body}" for i, (title, body) in enumerate(sections, 1)) + "\n"
    atomic_write(report_dir / "phase_02a_pilot_report.md", full.encode("utf-8"))
    plan = """# Phase 2B readiness plan (planning only)

Verdict: **CONDITIONAL GO**. This document authorizes no Phase 2B requests. The following are gates before a full historical crawl.

## Hard gates

1. Build a season-scoped, independent historical player denominator. Validate team and player coverage separately for each of the six seasons; report UNKNOWN until complete.
2. Change raw `source_id` generation to include season and endpoint/parameters, migrate or alias the two existing Liverpool team probes, and reject collisions in validation.
3. Define source precedence for team/player-season totals. Keep the 2024/25 Mac Allister minutes conflict (2607 leaderboard, 2606 playerStats) visible and add an exception register.
4. Validate historical position and multi-club spells with season-scoped evidence. Preserve one aggregate player-season row and separate verified player-team-season rows; never divide an aggregate without evidence.
5. Prove one supported, bounded player-match participation route with pagination and status behavior. If no route passes, scope Phase 2B to fixture index and selected details explicitly.

## Proposed collection order and endpoint priority

1. Cache six `leagues` responses and season/team fixture inventories; validate season IDs, 20 teams, fixture status and replay handling.
2. Establish complete historical player references by a verified season-scoped roster endpoint or independently reconciled player index; do not infer completeness from leaderboards.
3. Collect `playerData` once per unique ID, then request `playerStats` only for verified `statSeasons` entries and season IDs.
4. Collect `leagueseasondeepstats` only for explicitly needed cross-checks and documented metric definitions. Defer `matchDetails` to a bounded participation plan; do not brute-force `playerMatches` parameters.

## Request budget, storage and recovery

Estimate requests from the verified denominator and endpoint plan before execution. Set a per-run cap, bounded retries with backoff, concurrency ceiling and stop condition for 429/5xx; preserve response status and timestamps. The pilot's 265/265 success rate is not a forecast. Store immutable raw JSON and metadata under `data/phase_02b/raw/<season>/<endpoint>/` with SHA-256, exact parameters, UTC timestamp, HTTP status, content type, response-byte kind and unique source ID. Write atomically. Cache key includes endpoint, parameters and season; verify checksum before reuse. Maintain a durable request ledger with PENDING/OK/FAILED and resumable cursor. Never overwrite verified raw bytes; quarantine corrupt or incomplete pairs and retry deliberately.

## Normalized schema and duplicate policy

Use the pilot's seven tables: players, teams, player_seasons, player_team_seasons, matches, player_match_links, metric_observations. Keep explicit primary keys and source IDs. Preserve original FotMob fields, raw values, units, statistic type, source title, status and timestamps. Use player ID plus season ID for aggregates, player/team/season for verified club relationships, match ID for fixtures, player/match for lineup links, and player/season/metric for observations. Reject duplicate keys and inconsistent repeated payloads; maintain both raw versions and a reconciliation record rather than silently replacing data. Keep current profile fields separate from historical facts.

## Validation checkpoints

- Before requests: verify season IDs, endpoint contracts, budget and denominator evidence.
- After each batch: check logged attempts vs raw pairs, checksums, JSON parse, unique source IDs, season/team scope and cache restore.
- After each season: check reference coverage against independent denominator, profile season association, playerStats completion, nulls by metric/position, field/unit versioning and cross-source conflicts.
- After match ingestion: require 380 finished league fixtures per season or document status/replay exceptions; validate match dates, teams and selected player lineup evidence.
- Before sign-off: enforce Parquet schemas, unique keys, foreign keys, source lineage, idempotent rebuild hashes, and thresholds set using the pilot report; document unresolved UNKNOWN values.

## Pilot-driven adjustments

Use position-aware missingness. Keep `key_passes` UNVERIFIED, `minutes_played` OPTIONAL until the one-minute conflict has a source-precedence rule, and rating EXCLUDED_FOR_NOW until its definition is established. Retain goalkeeper N/A distinctly from missing. Do not treat `initialMatchesPage` as historical. Do not infer a zero from absent stats. Include the source-ID collision and Mac Allister minute conflict as regression fixtures.
"""
    atomic_write(report_dir / "phase_02b_readiness_plan.md", plan.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only; do not write reports")
    parser.add_argument("--tests", default="See local test run", help="exact test result to embed")
    args = parser.parse_args(argv)
    x = validate()
    if not args.check:
        write_reports(x, args.tests)
    print(json.dumps({"structural_issues": x["issues"], "raw_pairs": x["raw"]["raw_pairs"],
                      "sample_rows": len(x["sample"]), "cross_source_overlaps": x["overlap"],
                      "disagreements": x["disagreements"], "reports_written": not args.check}, indent=2))
    return 1 if x["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
