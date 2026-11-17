"""Execution 04: bounded identity collection and evidence-scoped normalized indexes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.audit.client import AuditClient, BudgetExceeded
from src.collection.collection_config import ROOT, load_config
from src.collection.execution01_preflight import run_test_suite
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import registries
from src.collection.reliability_runner import schema_state

OUT = ROOT / "data/phase_02b1/normalized/execution04_v1"
REPORT = ROOT / "reports/phase_02b1"
RESOURCE = "PLAYER_IDENTITY_PROFILE"


def read(name: str) -> list[dict]:
    return pq.read_table(ROOT / "data/phase_02b1/population" / (name + ".parquet")).to_pylist()


def discovered_population() -> list[dict]:
    """Include lineup IDs excluded from the appeared/uncertain population as unused-only."""
    rows = read("historical_player_population")
    known = {(r["season_id"], r["player_id"]) for r in rows}
    unused = defaultdict(list)
    for r in read("player_match_appearances"):
        key = (r["season_id"], r["player_id"])
        if key not in known:
            if r["participation_status"] != "UNUSED_SUBSTITUTE":
                raise ValueError(f"Unindexed non-unused lineup player: {key}")
            unused[key].append(r)
    for (sid, pid), observations in unused.items():
        first = observations[0]
        rows.append({"season_label": first["season_label"], "season_id": sid,
                     "player_id": pid, "player_name": first["player_name"],
                     "evidence_status": "UNUSED_SUBSTITUTE_ONLY", "in_candidate_population": False,
                     "appeared_match_count": 0, "team_count": 0,
                     "evidence_raw_paths": "|".join(sorted({r["raw_path"] for r in observations}))})
    return rows


def csv_out(name: str, rows: list[dict], fields: list[str]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    atomic_write(REPORT / name, buf.getvalue().encode("utf-8"))


def parquet_out(name: str, rows: list[dict], fields: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([(field, pa.string()) for field in fields])
    table = pa.Table.from_pylist([{f: None if r.get(f) is None else str(r[f]) for f in fields}
                                 for r in rows], schema=schema)
    path = OUT / (name + ".parquet")
    temp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, temp, compression="zstd")
    temp.replace(path)


def profile_cache(current, old, pid: str):
    for registry in (current, old):
        for meta, payload in registry.lookup_any_season("playerData", {"id": pid}):
            if not isinstance(payload, dict) or str(payload.get("id")) != pid:
                raise ValueError(f"Cached profile identity/schema failure: {pid}: {meta['raw_path']}")
            return meta, payload
    return None


def profile_plan(manifest: Manifest, cfg: dict, current, old) -> tuple[dict, int]:
    population = discovered_population()
    first = {}
    for row in population:
        first.setdefault(row["player_id"], row)
    cached = 0
    for pid, row in sorted(first.items(), key=lambda item: int(item[0])):
        item = profile_cache(current, old, pid)
        if item is not None:
            cached += 1
            continue
        ident = manifest.add(row["season_label"], int(row["season_id"]), "D", RESOURCE,
                             "playerData", {"id": pid}, {"identity": "identity_" + pid})
    return first, cached


def collect(manifest: Manifest, cfg: dict, current, old, limit: int) -> dict:
    pilot = dict(load_config())
    pilot.update({"request_budget": limit, "max_retries": cfg["max_retries"],
                  "backoff_seconds": cfg["backoff_seconds"],
                  "max_retry_after_seconds": cfg["max_retry_after_seconds"],
                  "min_request_interval_seconds": cfg["min_request_interval_seconds"],
                  "request_timeout_seconds": cfg["request_timeout_seconds"],
                  "max_response_bytes": cfg["max_response_bytes"]})
    client = AuditClient(pilot, ROOT / cfg["log_path"])
    states = Counter(); errors = Counter()
    for task in manifest.all_tasks():
        if task["resource_type"] != RESOURCE or task["execution_state"] not in ("PLANNED", "RETRY_PENDING", "RUNNING"):
            continue
        if client.attempts >= limit:
            break
        pid = str(task["params"]["id"])
        item = profile_cache(current, old, pid)
        if item:
            manifest.transition(task["task_id"], "VALIDATED", raw_path=item[0]["raw_path"],
                                validation="IDENTITY_ONLY", note="Cache recovered before HTTP")
            states["CACHE"] += 1
            continue
        manifest.transition(task["task_id"], "RUNNING", note="Identity-only profile request")
        before = client.attempts
        try:
            result = client.get("playerData", {"id": pid})
        except BudgetExceeded:
            manifest.transition(task["task_id"], "RETRY_PENDING", error="REQUEST_BUDGET_EXCEEDED",
                                note="Bounded attempt budget reached")
            break
        attempts = client.attempts - before
        payload = result.get("payload")
        if not isinstance(payload, dict) or str(payload.get("id")) != pid:
            status = result["record"].get("http_status")
            classification = "ACCESS_DENIED" if status == 403 else "RATE_LIMITED" if status == 429 else (
                "SERVER_ERROR" if status and status >= 500 else "PROFILE_SCHEMA_OR_HTTP_ERROR")
            state = "RETRY_PENDING" if classification == "SERVER_ERROR" else "QUARANTINED"
            manifest.transition(task["task_id"], state, attempt_increment=attempts,
                                error=classification, note=f"Profile response rejected: HTTP {status}")
            states[state] += 1; errors[classification] += 1
            if classification in ("ACCESS_DENIED", "RATE_LIMITED") or errors[classification] >= 3:
                break
            continue
        meta, _ = current.capture("playerData", {"id": pid}, task["season_label"], result)
        manifest.transition(task["task_id"], "VALIDATED", attempt_increment=attempts,
                            raw_path=meta["raw_path"], validation="IDENTITY_ONLY",
                            note="ID/schema verified; current fields remain current-only")
        states["VALIDATED"] += 1
    return {"http_attempts": client.attempts, "states": dict(states), "errors": dict(errors)}


def identity_fields(payload: dict) -> dict:
    info = payload.get("playerInformation") or []
    country = next((x for x in info if isinstance(x, dict) and x.get("title") == "Country"), {})
    birth = payload.get("birthDate") or {}
    position = (payload.get("positionDescription") or {}).get("primaryPosition") or {}
    team = payload.get("primaryTeam") or {}
    return {"profile_name": payload.get("name") or None,
            "birth_date": (birth.get("utcTime") or "")[:10] or None,
            "nationality_code": country.get("countryCode") or None,
            "nationality_name": (country.get("value") or {}).get("fallback") or None,
            "current_team_id": str(team["id"]) if team.get("id") is not None else None,
            "current_position": position.get("label") or None}


def appearance_status(row: dict) -> str:
    if row["lineup_role"] == "STARTER" and row["participation_status"] == "APPEARED":
        return "STARTED"
    if row["lineup_role"] == "SUBSTITUTE" and row["participation_status"] == "APPEARED" and "subIn" in (row["substitution_events"] or "").split("|"):
        return "SUBSTITUTED_ON"
    if row["lineup_role"] == "SUBSTITUTE" and row["participation_status"] == "UNUSED_SUBSTITUTE":
        return "UNUSED_SUBSTITUTE"
    return "UNKNOWN"


def normalize(manifest: Manifest, cfg: dict, current, old, collection: dict) -> dict:
    population = discovered_population()
    appearances = read("player_match_appearances")
    fixtures = read("historical_fixture_index")
    refs = read("player_team_season_reference")
    existing_relations = {(r["season_id"], r["player_id"], r["team_id"]) for r in refs}
    unused_relations = defaultdict(list)
    for r in appearances:
        key = (r["season_id"], r["player_id"], r["team_id"])
        if key not in existing_relations and r["participation_status"] == "UNUSED_SUBSTITUTE":
            unused_relations[key].append(r)
    for (sid, pid, tid), observations in unused_relations.items():
        first = observations[0]
        refs.append({"season_label": first["season_label"], "season_id": sid, "player_id": pid,
                     "team_id": tid, "membership_status": "UNUSED_SUBSTITUTE_ONLY",
                     "in_candidate_relation": False, "appeared_match_count": 0,
                     "evidence_raw_paths": "|".join(sorted({r["raw_path"] for r in observations}))})
    seasons = read("seasons")
    first = {}
    for row in population:
        first.setdefault(row["player_id"], row)
    players, missing = [], []
    for pid, row in sorted(first.items(), key=lambda item: int(item[0])):
        item = profile_cache(current, old, pid)
        info = identity_fields(item[1]) if item else {}
        players.append({"player_id": pid, "lineup_name": row["player_name"], **info,
                        "profile_status": "VERIFIED_ID" if item else "MISSING",
                        "profile_raw_path": item[0]["raw_path"] if item else None,
                        "profile_collected_at_utc": item[0]["collected_at_utc"] if item else None})
        if not item:
            missing.append({"season_label": row["season_label"], "player_id": pid,
                            "match_id": "", "category": "PROFILE_MISSING", "detail": "No verified cached or collected playerData"})
    player_by_id = {p["player_id"]: p for p in players}
    match_by_id = {r["match_id"]: r for r in fixtures}
    if len(match_by_id) != len(fixtures) or any(r["season_id"] != match_by_id[r["match_id"]]["season_id"] for r in appearances):
        raise ValueError("Critical match ID collision or wrong-season appearance")
    matches = [{**r, "competition_id": "47", "match_status": "COMPLETED" if r["eligible_completed"] else "CANCELLED_OR_ABANDONED"}
               for r in fixtures]
    if Counter(r["season_label"] for r in matches if r["eligible_completed"]) != Counter({s["season_label"]: 380 for s in seasons}):
        raise ValueError("Critical completed fixture count mismatch")
    by_match = {r["match_id"]: r for r in matches}
    links = []
    seen = set()
    for r in appearances:
        key = (r["match_id"], r["player_id"])
        if key in seen or not by_match[r["match_id"]]["eligible_completed"] or r["team_id"] not in (
                by_match[r["match_id"]]["home_team_id"], by_match[r["match_id"]]["away_team_id"]):
            raise ValueError(f"Critical duplicate/invalid appearance link {key}")
        seen.add(key)
        status = appearance_status(r)
        links.append({**r, "participation_status": status, "starting_status": "STARTED" if status == "STARTED" else "NOT_STARTED",
                      "substitution_status": "SUB_IN_VERIFIED" if status == "SUBSTITUTED_ON" else (r["substitution_events"] or "UNSPECIFIED"),
                      "evidence_source": "matchDetails.lineup", "validation_status": "CONFIRMED" if status in ("STARTED", "SUBSTITUTED_ON") else "UNRESOLVED" if status == "UNKNOWN" else "NOT_APPEARED"})
    player_seasons = [{**r, "profile_status": player_by_id[r["player_id"]]["profile_status"]} for r in population]
    memberships = [{**r, "validation_status": "CONFIRMED" if r["membership_status"] == "APPEARED" else "UNRESOLVED"} for r in refs]
    confirmed = defaultdict(set)
    for r in links:
        if r["validation_status"] == "CONFIRMED":
            confirmed[(r["season_label"], r["player_id"], r["team_id"])].add(r["match_id"])
    for r in memberships:
        key = (r["season_label"], r["player_id"], r["team_id"])
        if (r["validation_status"] == "CONFIRMED") != bool(confirmed[key]) or int(r["appeared_match_count"]) != len(confirmed[key]):
            raise ValueError(f"Critical membership/appearance mismatch {key}")
    appeared_population = {(r["season_label"], r["player_id"]) for r in population if r["evidence_status"] == "APPEARED"}
    linked_population = {(season, pid) for (season, pid, _), match_ids in confirmed.items() if match_ids}
    if appeared_population != linked_population:
        raise ValueError("Critical appeared-player population versus match-link mismatch")
    teams = {}
    fixture_names = {}
    for fixture_path in {r["fixture_raw_path"] for r in matches}:
        fixture_body = (ROOT / fixture_path).read_bytes()
        fixture_meta_path = (ROOT / fixture_path).with_name("metadata.json")
        if not fixture_meta_path.exists():
            fixture_meta_path = (ROOT / fixture_path).with_suffix(".meta.json")
        fixture_meta = json.loads(fixture_meta_path.read_text(encoding="utf-8"))
        if hashlib.sha256(fixture_body).hexdigest() != fixture_meta.get("content_sha256", fixture_meta.get("sha256")):
            raise ValueError(f"Critical fixture raw checksum mismatch: {fixture_path}")
        payload = json.loads(fixture_body)
        for item in (payload.get("fixtures") or {}).get("allMatches") or []:
            for side in ("home", "away"):
                member = item.get(side) or {}
                if member.get("id") is not None:
                    fixture_names[(fixture_path, str(member["id"]))] = member
    for r in matches:
        for side in ("home", "away"):
            tid = r[f"{side}_team_id"]
            name = fixture_names.get((r["fixture_raw_path"], tid), {})
            teams[(r["season_id"], tid)] = {"season_id": r["season_id"], "season_label": r["season_label"],
                "team_id": tid, "team_name": name.get("name"), "short_name": name.get("shortName"),
                "fixture_raw_path": r["fixture_raw_path"]}
    registry = json.loads((ROOT / "reports/phase_02b0/position_mapping_registry.json").read_text(encoding="utf-8"))
    mapping = {(m["source_field"], str(m["original_fotmob_code"])): m for m in registry["mappings"]}
    positions = []
    for raw_path, match_links in _group_paths(links).items():
        body = (ROOT / raw_path).read_bytes()
        meta_path = (ROOT / raw_path).with_name("metadata.json")
        if not meta_path.exists():
            meta_path = (ROOT / raw_path).with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if hashlib.sha256(body).hexdigest() != meta.get("content_sha256", meta.get("sha256")):
            raise ValueError(f"Critical raw checksum mismatch: {raw_path}")
        payload = json.loads(body)
        match_id = str((payload.get("general") or {}).get("matchId"))
        if any(r["match_id"] != match_id for r in match_links):
            raise ValueError(f"Critical match raw identity mismatch: {raw_path}")
        lineup = (payload.get("content") or {}).get("lineup") or {}
        for side in ("homeTeam", "awayTeam"):
            team = lineup.get(side) or {}
            for role in ("starters", "subs"):
                for member in team.get(role) or []:
                    pid = str(member.get("id"))
                    for field in ("positionId", "usualPlayingPositionId"):
                        value = member.get(field)
                        if value is None:
                            continue
                        code = str(value)
                        m = mapping.get((field, code))
                        positions.append({"season_id": by_match[match_id]["season_id"], "match_id": match_id,
                            "player_id": pid, "team_id": str(team.get("id")), "lineup_role": role.upper(),
                            "source_field": field, "original_code": code,
                            "mapped_group": m["broader_position_group"] if m else "UNKNOWN",
                            "mapping_status": m["mapping_status"] if m else "UNKNOWN",
                            "mapping_version": registry["mapping_version"], "raw_path": raw_path})
    profile_cov = []
    for s in seasons:
        rows = [r for r in population if r["season_id"] == s["season_id"]]
        count = sum(player_by_id[r["player_id"]]["profile_status"] == "VERIFIED_ID" for r in rows)
        profile_cov.append({"season_label": s["season_label"], "season_id": s["season_id"],
                            "population": len(rows), "profiles_verified": count, "profiles_missing": len(rows)-count})
    multi = []
    by_player_season = defaultdict(list)
    for r in memberships:
        if r["validation_status"] == "CONFIRMED":
            by_player_season[(r["season_label"], r["player_id"])].append(r)
    for (season, pid), rows in sorted(by_player_season.items()):
        if len(rows) > 1:
            multi.append({"season_label": season, "player_id": pid, "team_ids": "|".join(sorted(r["team_id"] for r in rows)),
                          "team_count": len(rows), "confirmed_match_count": sum(int(r["appeared_match_count"]) for r in rows),
                          "season_population_rows": 1, "evidence_raw_paths": "|".join(sorted({p for r in rows for p in (r["evidence_raw_paths"] or "").split("|") if p}))})
    membership_report = [{"season_label": s["season_label"], "confirmed": sum(r["validation_status"] == "CONFIRMED" for r in memberships if r["season_id"] == s["season_id"]),
                          "unresolved": sum(r["validation_status"] == "UNRESOLVED" for r in memberships if r["season_id"] == s["season_id"]),
                          "multi_club_players": sum(r["season_label"] == s["season_label"] for r in multi)} for s in seasons]
    historical_groups = defaultdict(set)
    for r in positions:
        if r["source_field"] == "usualPlayingPositionId" and r["mapped_group"] != "UNKNOWN":
            historical_groups[(r["season_id"], r["player_id"])].add(r["mapped_group"])
    current_codes = {"goalkeeper": "GK", "defender": "DEF", "midfielder": "MID", "forward": "FWD"}
    current_differences = Counter()
    for (sid, pid), groups in historical_groups.items():
        if pid not in player_by_id:
            continue
        current_group = current_codes.get((player_by_id[pid].get("current_position") or "").lower())
        if current_group and current_group not in groups:
            current_differences[sid] += 1
    position_report = [{"season_label": s["season_label"], "observations": sum(r["season_id"] == s["season_id"] for r in positions),
                        "mapped_inferred": sum(r["season_id"] == s["season_id"] and r["mapping_status"] == "HISTORICAL_INFERRED" for r in positions),
                        "unknown": sum(r["season_id"] == s["season_id"] and r["mapping_status"] == "UNKNOWN" for r in positions),
                        "current_profile_role_differences": current_differences[s["season_id"]],
                        "profile_position_is_current_only": "True"} for s in seasons]
    match_report = [{"season_label": s["season_label"], "fixture_rows": sum(r["season_id"] == s["season_id"] for r in matches),
                     "completed": sum(r["season_id"] == s["season_id"] and r["eligible_completed"] for r in matches),
                     "cancelled_or_abandoned": sum(r["season_id"] == s["season_id"] and not r["eligible_completed"] for r in matches)} for s in seasons]
    app_report = [{"season_label": s["season_label"], **{status.lower(): sum(r["season_id"] == s["season_id"] and r["participation_status"] == status for r in links)
                  for status in ("STARTED", "SUBSTITUTED_ON", "UNUSED_SUBSTITUTE", "UNKNOWN")}} for s in seasons]
    stat_rows = pq.read_table(ROOT / "data/phase_02b1/statistics/metric_observations.parquet",
                              filters=[("metric_name", "=", "appearances")]).to_pylist()
    match_counts = Counter((r["season_label"], r["player_id"]) for r in links if r["validation_status"] == "CONFIRMED")
    stat_comparison = []
    for r in stat_rows:
        actual = match_counts[(r["season_label"], r["player_id"])]
        stated = r["value"] if r["metric_status"] == "OBSERVED" else None
        stat_comparison.append({"season_label": r["season_label"], "player_id": r["player_id"],
                                "confirmed_match_appearances": actual, "season_stats_appearances": stated,
                                "comparison_status": "MATCH" if stated is not None and actual == stated else
                                "DISCREPANCY" if stated is not None else "SOURCE_MISSING",
                                "stats_raw_path": r["raw_path"]})
    exceptions = missing + [{"season_label": r["season_label"], "player_id": r["player_id"], "match_id": r["match_id"],
                             "category": "UNKNOWN_PARTICIPATION", "detail": r["raw_path"]} for r in links if r["participation_status"] == "UNKNOWN"]
    for name, rows, fields in [
        ("players", players, ["player_id","lineup_name","profile_name","birth_date","nationality_code","nationality_name","current_team_id","current_position","profile_status","profile_raw_path","profile_collected_at_utc"]),
        ("teams", list(teams.values()), ["season_id","season_label","team_id","team_name","short_name","fixture_raw_path"]),
        ("seasons", seasons, list(seasons[0])),
        ("matches", matches, list(matches[0])),
        ("player_seasons", player_seasons, list(player_seasons[0])),
        ("player_team_seasons", memberships, list(memberships[0])),
        ("player_match_appearances", links, list(links[0])),
        ("historical_position_observations", positions, list(positions[0]))]:
        parquet_out(name, rows, fields)
    for name, rows, fields in [
        ("player_profile_coverage.csv", profile_cov, list(profile_cov[0])),
        ("historical_membership_validation.csv", membership_report, list(membership_report[0])),
        ("historical_position_validation.csv", position_report, list(position_report[0])),
        ("multi_club_player_report.csv", multi, ["season_label","player_id","team_ids","team_count","confirmed_match_count","season_population_rows","evidence_raw_paths"]),
        ("match_index_coverage.csv", match_report, list(match_report[0])),
        ("player_match_appearance_coverage.csv", app_report, list(app_report[0])),
        ("profile_match_collection_exceptions.csv", exceptions, ["season_label","player_id","match_id","category","detail"])]:
        csv_out(name, rows, fields)
    csv_out("appearance_statistics_reconciliation.csv", stat_comparison,
            ["season_label","player_id","confirmed_match_appearances","season_stats_appearances","comparison_status","stats_raw_path"])
    result = {"unique_players": len(players), "verified_profiles": len(players)-len(missing), "missing_profiles": len(missing),
              "player_seasons": len(player_seasons), "memberships_confirmed": sum(r["validation_status"] == "CONFIRMED" for r in memberships),
              "memberships_unresolved": sum(r["validation_status"] == "UNRESOLVED" for r in memberships),
              "multi_club_player_seasons": len(multi), "completed_matches": sum(r["eligible_completed"] for r in matches),
              "fixture_rows": len(matches), "appearance_statuses": dict(Counter(r["participation_status"] for r in links)),
              "position_observations": len(positions),
              "appearance_stats_comparison": dict(Counter(r["comparison_status"] for r in stat_comparison)),
              "profile_coverage_by_season": profile_cov, "membership_validation_by_season": membership_report,
              "match_index_by_season": match_report, "appearance_coverage_by_season": app_report,
              "position_validation_by_season": position_report,
              "collection": collection}
    atomic_write(REPORT / "execution04_checkpoint.json", json_bytes(result))
    return result


def _group_paths(rows: list[dict]) -> dict[str, list[dict]]:
    result = defaultdict(list)
    for r in rows:
        result[r["raw_path"]].append(r)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--collect-only", action="store_true", help="Persist one bounded profile batch without rebuilding normalized tables")
    parser.add_argument("--max-requests", type=int, default=50)
    args = parser.parse_args()
    cfg = load_full_config()
    if not 0 <= args.max_requests <= cfg["max_run_http_attempts"]:
        parser.error("Request budget must be at most configured 50")
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        current, old = registries(cfg)
        first, cached = profile_plan(manifest, cfg, current, old)
        collection = collect(manifest, cfg, current, old, args.max_requests) if args.collect and args.max_requests else {"http_attempts": 0, "states": {}, "errors": {}}
        collection["cached_profiles"] = cached
        if args.collect_only:
            states = Counter(t["execution_state"] for t in manifest.all_tasks() if t["resource_type"] == RESOURCE)
            checkpoint = {"collection": collection, "profile_tasks_by_state": dict(states)}
            atomic_write(REPORT / "execution04_collection_checkpoint.json", json_bytes(checkpoint))
            print(json.dumps(checkpoint))
            return 0
        result = normalize(manifest, cfg, current, old, collection)
        identity_ids = {str(t["params"]["id"]) for t in manifest.all_tasks() if t["resource_type"] == RESOURCE}
        log_rows = [json.loads(line) for line in (ROOT / cfg["log_path"]).read_text(encoding="utf-8").splitlines()]
        identity_log = [r for r in log_rows if r.get("endpoint") == "playerData" and str((r.get("params") or {}).get("id")) in identity_ids]
        result["http_attempts_execution04_total"] = len(identity_log)
        result["http_outcomes_execution04_total"] = dict(Counter(str(r.get("http_status")) for r in identity_log))
        tests = run_test_suite(REPORT / "execution04_tests")
        result["tests"] = tests
        pending = Counter(t["execution_state"] for t in manifest.all_tasks() if t["resource_type"] == RESOURCE)
        result["profile_tasks_by_state"] = dict(pending)
        atomic_write(REPORT / "execution04_checkpoint.json", json_bytes(result))
        lines = ["# Phase 2B.1 Execution 04: historical identity and match index", "",
                 "Status: CONDITIONAL PASS" if not result["missing_profiles"] and not tests["exit_code"] else "Status: INCOMPLETE / CONDITIONAL", "",
                 f"Profiles: {result['verified_profiles']}/{result['unique_players']} unique IDs; missing {result['missing_profiles']}.",
                 f"Player-seasons: {result['player_seasons']}; confirmed memberships: {result['memberships_confirmed']}; unresolved: {result['memberships_unresolved']}; multi-club player-seasons: {result['multi_club_player_seasons']}.",
                 f"Matches: {result['completed_matches']} completed / {result['fixture_rows']} fixture records. Bournemouth–Luton abandoned 4193691 is excluded; replay 4421797 retained.",
                 f"Appearance statuses: {result['appearance_statuses']}. Only STARTED and SUBSTITUTED_ON count as confirmed.",
                 f"Historical position observations: {result['position_observations']}; labels are Phase 2B.0 inferred exact-code mappings, never current profile positions.",
                 f"Season-stat appearance reconciliation: {result['appearance_stats_comparison']}; discrepancies are reported, not rewritten.",
                 f"HTTP attempts this run: {collection['http_attempts']}; errors: {collection['errors']}; profile checkpoint: {dict(pending)}.",
                 f"HTTP attempts for Execution 04 profile IDs, all runs: {result['http_attempts_execution04_total']}; response statuses: {result['http_outcomes_execution04_total']}.",
                 f"Tests: {tests['tests_run']} run, exit code {tests['exit_code']}; see execution04_tests/test_execution.log.", "",
                 "`playerMatches` remains unverified after prior HTTP 400 and was not retried. UNKNOWN substitutes remain unresolved. No season acceptance is asserted.", "",
                 "Raw lineage is retained in profile_raw_path, fixture_raw_path, appearance raw_path, membership evidence_raw_paths, and historical position raw_path.", "",
                 "Resume: `python -m src.collection.execution04_identity --collect --max-requests 50`."]
        lines += ["", "## Season coverage", "",
                  "| Season | Profile IDs | Confirmed membership | Unresolved membership | Completed matches | Started | Substituted on | Unknown |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for p, m, match, app in zip(result["profile_coverage_by_season"], result["membership_validation_by_season"],
                                    result["match_index_by_season"], result["appearance_coverage_by_season"]):
            lines.append(f"| {p['season_label']} | {p['profiles_verified']}/{p['population']} | {m['confirmed']} | {m['unresolved']} | {match['completed']} | {app['started']} | {app['substituted_on']} | {app['unknown']} |")
        lines += ["", "The normalized outputs are versioned under `data/phase_02b1/normalized/execution04_v1/`. "
                  "The CSV reports in this directory retain profile, membership, position, fixture, appearance, multi-club, exception, and season-stat comparisons."]
        atomic_write(REPORT / "historical_identity_and_match_index_report.md", ("\n".join(lines)+"\n").encode("utf-8"))
        print(json.dumps({k:v for k,v in result.items() if k != "tests"}, ensure_ascii=False))
        return 0 if tests["exit_code"] == 0 else 2
    finally:
        manifest.close()


if __name__ == "__main__":
    raise SystemExit(main())
