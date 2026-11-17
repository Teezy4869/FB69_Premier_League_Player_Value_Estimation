"""Collect match lineups in bounded batches and publish evidence-scoped population tables."""
from __future__ import annotations

import argparse
import csv
import io
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.collection.batch_quality import inspect_capture
from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write, json_bytes
from src.collection.full_manifest import Manifest, load_full_config
from src.collection.full_orchestrator import registries, run
from src.collection.historical_lineup_validator import verify_detail


def participation_rows(payload: dict, fixture: dict, meta: dict) -> tuple[list[dict], list[str]]:
    """Return all lineup listings. An absent substitute event field is UNKNOWN."""
    issues = []
    if verify_detail(payload, fixture)[0] != "ACCEPTED":
        return [], [f"WRONG_SEASON_OR_FIXTURE:{fixture['match_id']}"]
    lineup = (payload.get("content") or {}).get("lineup") or {}
    if lineup.get("lineupType") != "standard":
        return [], [f"MISSING_STANDARD_LINEUP:{fixture['match_id']}"]
    rows, seen = [], set()
    for side, team_id in (("homeTeam", fixture["home_team_id"]),
                          ("awayTeam", fixture["away_team_id"])):
        team = lineup.get(side) or {}
        if str(team.get("id")) != team_id:
            issues.append(f"LINEUP_TEAM_MISMATCH:{fixture['match_id']}:{side}")
            continue
        for role, members in (("STARTER", team.get("starters")), ("SUBSTITUTE", team.get("subs"))):
            if members is None or not isinstance(members, list):
                issues.append(f"MISSING_LINEUP_LIST:{fixture['match_id']}:{team_id}:{role}")
                continue
            if role == "STARTER" and len(members) != 11:
                issues.append(f"INCOMPLETE_STARTERS:{fixture['match_id']}:{team_id}:{len(members)}")
            for member in members:
                pid = str(member.get("id")) if isinstance(member, dict) else "None"
                if not pid.isdigit():
                    issues.append(f"MISSING_PLAYER_ID:{fixture['match_id']}:{team_id}")
                    continue
                key = (fixture["match_id"], pid)
                if key in seen:
                    issues.append(f"DUPLICATE_MATCH_PLAYER:{fixture['match_id']}:{pid}")
                    continue
                seen.add(key)
                perf = member.get("performance") or {}
                events = perf.get("substitutionEvents")
                event_types = {e.get("type") for e in events if isinstance(e, dict)} if isinstance(events, list) else set()
                if role == "STARTER":
                    status = "APPEARED"
                elif "subIn" in event_types:
                    status = "APPEARED"
                elif not isinstance(events, list) or "subOut" in event_types:
                    status = "UNKNOWN"
                else:
                    status = "UNUSED_SUBSTITUTE"
                rows.append({"season_label": fixture["season_label"], "season_id": fixture["season_id"],
                             "match_id": fixture["match_id"], "match_date_utc": fixture["match_date_utc"],
                             "team_id": team_id, "player_id": pid, "player_name": member.get("name") or "",
                             "lineup_role": role, "substitution_events": "|".join(sorted(event_types)),
                             "participation_status": status, "source_id": meta["source_id"],
                             "capture_id": meta["capture_id"], "request_key": meta["request_key"],
                             "raw_path": meta["raw_path"], "collected_at_utc": meta["collected_at_utc"]})
    return rows, issues


def reconcile_sets(candidate_ids: set[str], appeared_relations: set[tuple[str, str]]) -> dict:
    """Keep a player-season distinct from its possibly multiple club relations."""
    appeared_ids = {player_id for player_id, _ in appeared_relations}
    clubs = Counter(player_id for player_id, _ in appeared_relations)
    return {"appeared_ids": appeared_ids, "missing_candidates": appeared_ids - candidate_ids,
            "candidate_unconfirmed": candidate_ids - appeared_ids,
            "multi_club_ids": {player_id for player_id, count in clubs.items() if count > 1}}


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader(); writer.writerows(rows)
    atomic_write(path, buffer.getvalue().encode("utf-8"))


def _parquet(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    boolean_fields = {"finished", "cancelled", "eligible_completed", "in_candidate_population",
                      "in_candidate_relation"}
    integer_fields = {"eligible_completed_matches", "appeared_match_count", "team_count"}
    schema = pa.schema([(field, pa.bool_() if field in boolean_fields else
                         pa.int64() if field in integer_fields else pa.string()) for field in fields])
    def convert(field: str, value: object):
        if value is None or value == "":
            return None
        if field in boolean_fields:
            return str(value).lower() == "true"
        if field in integer_fields:
            return int(value)
        return str(value)
    table = pa.Table.from_pylist([{field: convert(field, row.get(field)) for field in fields}
                                 for row in rows], schema=schema)
    temporary = path.with_name(path.name + ".tmp")
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(path)


def _saved_task(task: dict, cfg: dict, old) -> tuple[dict, dict] | None:
    """Load committed current raw by task reference, avoiding a full in-memory raw index."""
    prior = old.lookup(task["endpoint"], task["params"], task["season_label"])
    if prior is not None:
        return prior
    prefix = cfg["raw_dir"].rstrip("/") + "/"
    for ref in task["raw_evidence_refs"]:
        if not ref.startswith(prefix):
            continue
        raw = ROOT / ref
        if not raw.is_file():
            continue
        meta_path = raw.with_name("metadata.json")
        if not meta_path.is_file():
            continue
        return json.loads(meta_path.read_text(encoding="utf-8")), json.loads(raw.read_bytes())
    return None


def build_outputs(cfg: dict, manifest: Manifest) -> dict:
    report_dir = ROOT / cfg["report_dir"]
    output_dir = ROOT / "data/phase_02b1/population"
    _, old = registries(cfg)
    captures = {m["source_id"]: m for m, _ in old.captures() if m.get("source_id")}
    with (ROOT / "reports/phase_02a/player_reference_index.csv").open(encoding="utf-8", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    candidates = defaultdict(list)
    for row in candidate_rows:
        candidates[(row["season_label"], row["fotmob_player_id"])].append(row)

    seasons, fixtures, appearances, population, memberships = [], [], [], [], []
    reconciliation, coverage, exceptions = [], [], []
    progress = {"phase": "phase_02b1_execution_02", "seasons": {}}
    for season, season_id in cfg["seasons"].items():
        label_id = str(season_id)
        league_task = next(t for t in manifest.all_tasks(season, "A") if t["resource_type"] == "SEASON_FIXTURES")
        league_meta, league_payload = _saved_task(league_task, cfg, old)
        league_quality = inspect_capture(league_task, league_meta, league_payload)
        if league_quality["decision"] != "VALIDATED":
            raise ValueError(f"Season fixture raw failed validation: {season}: {league_quality['note']}")
        all_matches = (league_payload.get("fixtures") or {}).get("allMatches") or []
        completed = {}
        seen_fixture = set()
        for item in all_matches:
            match_id = str(item.get("id"))
            status = item.get("status") or {}
            eligible = bool(status.get("finished")) and not bool(status.get("cancelled"))
            home, away = str((item.get("home") or {}).get("id")), str((item.get("away") or {}).get("id"))
            if not match_id.isdigit() or match_id in seen_fixture or not home.isdigit() or not away.isdigit():
                exceptions.append({"season_label": season, "match_id": match_id, "player_id": "",
                                   "category": "INVALID_FIXTURE_IDENTITY", "detail": "Duplicate/missing match or team ID"})
            seen_fixture.add(match_id)
            row = {"season_label": season, "season_id": label_id, "match_id": match_id,
                   "match_date_utc": status.get("utcTime") or "", "home_team_id": home, "away_team_id": away,
                   "finished": str(bool(status.get("finished"))), "cancelled": str(bool(status.get("cancelled"))),
                   "eligible_completed": str(eligible), "status_reason": (status.get("reason") or {}).get("long") or "",
                   "score": status.get("scoreStr") or "", "fixture_source_id": league_meta["source_id"],
                   "fixture_raw_path": league_meta["raw_path"],
                   "fixture_collected_at_utc": league_meta["collected_at_utc"]}
            fixtures.append(row)
            if eligible:
                completed[match_id] = row
        if len(completed) != 380:
            exceptions.append({"season_label": season, "match_id": "", "player_id": "",
                               "category": "COMPLETED_FIXTURE_COUNT", "detail": str(len(completed))})
        if season == "2023/2024":
            by_id = {row["match_id"]: row for row in fixtures if row["season_label"] == season}
            abandoned, replay = by_id.get("4193691"), by_id.get("4421797")
            if (not abandoned or not replay or abandoned["cancelled"] != "True" or
                abandoned["eligible_completed"] != "False" or replay["eligible_completed"] != "True" or
                (abandoned["home_team_id"], abandoned["away_team_id"]) !=
                (replay["home_team_id"], replay["away_team_id"])):
                exceptions.append({"season_label": season, "match_id": "4193691|4421797", "player_id": "",
                                   "category": "BOURNEMOUTH_LUTON_REPLAY_MISMATCH",
                                   "detail": "Abandoned fixture and replay statuses or teams differ"})
        season_appearances = []
        validated_matches, usable_matches = 0, 0
        for task in manifest.all_tasks(season, "E"):
            if task["resource_type"] != "MATCH_DETAIL":
                continue
            match_id = str(task["params"]["matchId"])
            if task["execution_state"] != "VALIDATED":
                exceptions.append({"season_label": season, "match_id": match_id, "player_id": "",
                                   "category": "MATCH_DETAIL_PENDING", "detail": task["execution_state"]})
                continue
            item = _saved_task(task, cfg, old)
            if item is None:
                exceptions.append({"season_label": season, "match_id": match_id, "player_id": "",
                                   "category": "RAW_MISSING", "detail": "Validated task has no raw"})
                continue
            meta, payload = item
            quality = inspect_capture(task, meta, payload)
            if quality["decision"] != "VALIDATED":
                exceptions.append({"season_label": season, "match_id": match_id, "player_id": "",
                                   "category": quality["error_classification"], "detail": quality["note"]})
                continue
            validated_matches += 1
            fixture = completed[match_id]
            rows, issues = participation_rows(payload, fixture, meta)
            for issue in issues:
                category, _, detail = issue.partition(":")
                exceptions.append({"season_label": season, "match_id": match_id, "player_id": "",
                                   "category": category, "detail": detail})
            if rows and not issues:
                usable_matches += 1
                season_appearances.extend(rows)
        appearances.extend(season_appearances)
        appeared = defaultdict(list)
        uncertain = defaultdict(list)
        for row in season_appearances:
            key = (row["player_id"], row["team_id"])
            if row["participation_status"] == "APPEARED":
                appeared[key].append(row)
            elif row["participation_status"] == "UNKNOWN":
                uncertain[key].append(row)
                exceptions.append({"season_label": season, "match_id": row["match_id"],
                                   "player_id": row["player_id"], "category": "UNKNOWN_PARTICIPATION",
                                   "detail": row["raw_path"]})
        candidate_ids = {pid for s, pid in candidates if s == season}
        comparison = reconcile_sets(candidate_ids, set(appeared))
        appeared_ids = comparison["appeared_ids"]
        uncertain_ids = {pid for pid, _ in uncertain} - appeared_ids
        all_ids = candidate_ids | appeared_ids | uncertain_ids
        for pid in sorted(all_ids, key=int):
            sightings = [r for (p, _), rows in appeared.items() if p == pid for r in rows]
            uncertain_sightings = [r for (p, _), rows in uncertain.items() if p == pid for r in rows]
            candidate = candidates.get((season, pid), [])
            status = "APPEARED" if sightings else "UNKNOWN_PARTICIPATION" if pid in uncertain_ids else "CANDIDATE_ONLY"
            refs = sorted({r["raw_path"] for r in sightings + uncertain_sightings} |
                          {captures[src]["raw_path"] for row in candidate
                           for src in row["evidence_source_ids"].split("|") if src in captures})
            population.append({"season_label": season, "season_id": label_id, "player_id": pid,
                               "player_name": sightings[0]["player_name"] if sightings else
                               candidate[0]["player_name"] if candidate else "",
                               "evidence_status": status, "in_candidate_population": str(bool(candidate)),
                               "appeared_match_count": str(len({r["match_id"] for r in sightings})),
                               "team_count": str(len({r["team_id"] for r in sightings})),
                               "evidence_raw_paths": "|".join(refs)})
        relation_keys = {(r["fotmob_player_id"], r["fotmob_team_id"]) for r in candidate_rows
                         if r["season_label"] == season} | set(appeared) | set(uncertain)
        candidate_by_relation = {(r["fotmob_player_id"], r["fotmob_team_id"]): r for r in candidate_rows
                                 if r["season_label"] == season}
        for pid, team_id in sorted(relation_keys, key=lambda x: (int(x[0]), int(x[1]))):
            sightings = appeared.get((pid, team_id), [])
            candidate = candidate_by_relation.get((pid, team_id))
            unknown = uncertain.get((pid, team_id), [])
            refs = sorted({r["raw_path"] for r in sightings + unknown} |
                          ({captures[src]["raw_path"] for src in candidate["evidence_source_ids"].split("|")
                            if src in captures} if candidate else set()))
            memberships.append({"season_label": season, "season_id": label_id, "player_id": pid,
                                "team_id": team_id, "membership_status": "APPEARED" if sightings else
                                "UNKNOWN_PARTICIPATION" if unknown else "LEADERBOARD_CANDIDATE_ONLY",
                                "in_candidate_relation": str(candidate is not None),
                                "appeared_match_count": str(len({r["match_id"] for r in sightings})),
                                "evidence_raw_paths": "|".join(refs)})
        multiclu = Counter(pid for pid, _ in appeared)
        unknown_count = sum(r["participation_status"] == "UNKNOWN" for r in season_appearances)
        unknown_matches = {r["match_id"] for r in season_appearances
                           if r["participation_status"] == "UNKNOWN"}
        unambiguous_matches = usable_matches - len(unknown_matches)
        missing_candidates = comparison["missing_candidates"]
        candidate_unconfirmed = comparison["candidate_unconfirmed"]
        season_exception_categories = {e["category"] for e in exceptions if e["season_label"] == season}
        critical_categories = {"INVALID_FIXTURE_IDENTITY", "COMPLETED_FIXTURE_COUNT",
                               "BOURNEMOUTH_LUTON_REPLAY_MISMATCH", "RAW_MISSING",
                               "RAW_CORRUPTION", "HISTORICAL_SCOPE_MISMATCH", "DUPLICATE_OR_MISSING_ID",
                               "WRONG_SEASON_OR_FIXTURE", "LINEUP_TEAM_MISMATCH",
                               "DUPLICATE_MATCH_PLAYER", "MISSING_PLAYER_ID"}
        if season_exception_categories & critical_categories:
            status = "FAIL"
        elif validated_matches != 380:
            status = "INCOMPLETE"
        elif usable_matches != 380 or unknown_count or season_exception_categories:
            status = "CONDITIONAL PASS"
        else:
            status = "PASS"
        coverage_row = {"season_label": season, "season_id": label_id,
                        "completed_matches": str(len(completed)), "match_details_validated": str(validated_matches),
                        "matches_with_usable_lineup": str(usable_matches),
                        "usable_lineup_percent": f"{100*usable_matches/len(completed):.2f}" if completed else "0.00",
                        "matches_with_unambiguous_participation": str(unambiguous_matches),
                        "unambiguous_participation_percent":
                            f"{100*unambiguous_matches/len(completed):.2f}" if completed else "0.00",
                        "unique_appeared_players": str(len(appeared_ids)),
                        "candidate_players": str(len(candidate_ids)),
                        "appeared_in_candidates": str(len(appeared_ids & candidate_ids)),
                        "appeared_missing_from_candidates": str(len(missing_candidates)),
                        "candidate_without_confirmed_appearance": str(len(candidate_unconfirmed)),
                        "uncertain_only_players": str(len(uncertain_ids)),
                        "uncertain_only_missing_from_candidates": str(len(uncertain_ids - candidate_ids)),
                        "player_team_season_relationships": str(len(appeared)),
                        "multi_club_appeared_players": str(sum(count > 1 for count in multiclu.values())),
                        "unknown_participation_records": str(unknown_count), "status": status}
        coverage.append(coverage_row)
        reconciliation.append({**coverage_row,
                               "missing_candidate_player_ids": "|".join(sorted(missing_candidates, key=int)),
                               "candidate_unconfirmed_player_ids": "|".join(sorted(candidate_unconfirmed, key=int)),
                               "uncertain_only_player_ids": "|".join(sorted(uncertain_ids, key=int)),
                               "multi_club_player_ids": "|".join(sorted((pid for pid, n in multiclu.items() if n > 1), key=int))})
        seasons.append({"season_label": season, "season_id": label_id, "competition_id": "47",
                        "eligible_completed_matches": str(len(completed)), "status": status,
                        "fixture_source_id": league_meta["source_id"]})
        progress["seasons"][season] = coverage_row

    table_specs = {
        "historical_fixture_index": (fixtures, list(fixtures[0])),
        "historical_matches": (fixtures, list(fixtures[0])),
        "seasons": (seasons, list(seasons[0])),
        "historical_player_population": (population, ["season_label", "season_id", "player_id", "player_name",
                                                      "evidence_status", "in_candidate_population",
                                                      "appeared_match_count", "team_count", "evidence_raw_paths"]),
        "historical_appeared_players": ([r for r in population if r["evidence_status"] == "APPEARED"],
                                       ["season_label", "season_id", "player_id", "player_name", "evidence_status",
                                        "in_candidate_population", "appeared_match_count", "team_count", "evidence_raw_paths"]),
        "player_match_appearances": (appearances, ["season_label", "season_id", "match_id", "match_date_utc",
                                                  "team_id", "player_id", "player_name", "lineup_role",
                                                  "substitution_events", "participation_status", "source_id",
                                                  "capture_id", "request_key", "raw_path", "collected_at_utc"]),
        "player_team_season_reference": (memberships, ["season_label", "season_id", "player_id", "team_id",
                                                       "membership_status", "in_candidate_relation",
                                                       "appeared_match_count", "evidence_raw_paths"]),
    }
    for name, (rows, fields) in table_specs.items():
        _parquet(output_dir / f"{name}.parquet", rows, fields)
    _csv(report_dir / "population_reconciliation.csv", reconciliation, list(reconciliation[0]))
    _csv(report_dir / "population_coverage_by_season.csv", coverage, list(coverage[0]))
    _csv(report_dir / "population_exceptions.csv", exceptions,
         ["season_label", "match_id", "player_id", "category", "detail"])
    fixture_season = {row["match_id"]: row["season_label"] for row in fixtures}
    http_by_season = Counter()
    http_outcomes = Counter()
    http_failure_categories = Counter()
    log_path = ROOT / cfg["log_path"]
    if log_path.is_file():
        with log_path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("endpoint") != "matchDetails":
                    continue
                http_by_season[fixture_season.get(str((record.get("params") or {}).get("matchId")), "UNKNOWN")] += 1
                http_outcomes[record.get("outcome", "UNKNOWN")] += 1
                if record.get("outcome") != "OK":
                    http_failure_categories[str(record.get("http_status") or record.get("error") or "UNKNOWN")] += 1
    progress["collection_http_attempts_total"] = sum(http_by_season.values())
    progress["collection_http_attempts"] = progress["collection_http_attempts_total"]
    progress["all_completed_match_details_validated"] = all(
        int(row["match_details_validated"]) == 380 for row in coverage)
    progress["http_attempts_by_season"] = dict(http_by_season)
    progress["http_outcomes"] = dict(http_outcomes)
    progress["http_failure_categories"] = dict(http_failure_categories)
    progress["outputs"] = {name: (output_dir / f"{name}.parquet").relative_to(ROOT).as_posix()
                           for name in table_specs}
    progress["exception_count"] = len(exceptions)
    atomic_write(report_dir / "population_collection_progress.json", json_bytes(progress))
    report = ["# Phase 2B.1 Execution 02 — historical appeared-player population", "",
              "The population counts only starters and substitutes with an explicit `subIn`. An unused substitute does not count. A missing substitution field remains UNKNOWN. The three validated season leaderboards (`mins_played`, `goals`, `saves`) are candidate evidence only; assists, passing, defending and other groups have no validated season-wide contract in the saved evidence. Registration is not inferred from lineup listings, and current roster data is excluded.", "",
              "| Season | Completed fixtures | Validated details | Usable lineups | Unambiguous matches | Appeared players | Candidate players | Uncertain-only players | Missing candidates | Multi-club players | Unknown records | Status |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in coverage:
        report.append("| " + " | ".join(row[key] for key in (
            "season_label", "completed_matches", "match_details_validated", "matches_with_usable_lineup",
            "matches_with_unambiguous_participation",
            "unique_appeared_players", "candidate_players", "uncertain_only_players",
            "appeared_missing_from_candidates",
            "multi_club_appeared_players", "unknown_participation_records", "status")) + " |")
    report += ["", f"Exceptions: {len(exceptions)}. See [exact records](population_exceptions.csv), "
               "[reconciliation](population_reconciliation.csv), [coverage](population_coverage_by_season.csv), "
               "and [progress](population_collection_progress.json).",
               "Every detail counted as validated was rechecked against its raw SHA-256, request identity, "
               "JSON schema and season-scoped fixture context before population extraction.",
               f"HTTP attempts logged for this stage: {progress['collection_http_attempts_total']}; "
               f"outcomes: {progress['http_outcomes']}; failure categories: {progress['http_failure_categories']}.",
               "", "Parquet outputs: " + ", ".join(
                   f"[{name}](../../data/phase_02b1/population/{name}.parquet)" for name in table_specs) + ".",
               "", "The 2023/24 fixture index retains abandoned Bournemouth–Luton match 4193691 as ineligible "
               "and includes replay 4421797 among the 380 eligible completed matches.",
               "", "A season is INCOMPLETE until all 380 eligible match details are validated. "
               "This output does not authorize collection of player season statistics.",
               "", "Resume from the manifest without repeating validated requests:",
               "```powershell",
               "python -m src.collection.population_execution02 --execute --max-batches 50 --max-requests 50",
               "python -m src.collection.population_execution02 --report-only",
               "```"]
    audit_path = report_dir / "population_final_audit.json"
    if audit_path.is_file():
        final_audit = json.loads(audit_path.read_text(encoding="utf-8"))
        report += ["", f"Independent output/raw audit: **{final_audit['audit_status']}**; "
                   f"{final_audit['raw_checksums_reverified']} raw checksums reverified; "
                   f"{final_audit['http_attempts']} logged HTTP attempts. "
                   "[Machine audit](population_final_audit.json)."]
    test_path = report_dir / "execution02_tests/test_execution.json"
    if test_path.is_file():
        tests = json.loads(test_path.read_text(encoding="utf-8"))
        report += ["", f"Automated tests: `{tests['command']}`; exit code {tests['exit_code']}; "
                   f"{tests['tests_run']} run, {tests['failures']} failures, {tests['errors']} errors. "
                   "[Full actual log](execution02_tests/test_execution.log), "
                   "[machine result](execution02_tests/test_execution.json)."]
    atomic_write(report_dir / "historical_population_collection_report.md", "\n".join(report).encode("utf-8"))
    return progress


def collect(cfg: dict, manifest: Manifest, max_batches: int, max_requests: int) -> dict:
    batches = []
    for season in cfg["seasons"]:
        for _ in range(max_batches - len(batches)):
            pending = [t for t in manifest.all_tasks(season, "E")
                       if t["resource_type"] == "MATCH_DETAIL" and t["execution_state"] != "VALIDATED"]
            if not pending:
                population_gate = next(t for t in manifest.all_tasks(season, "B")
                                       if t["resource_type"] == "POPULATION_GATE")
                if population_gate["execution_state"] != "VALIDATED":
                    gate = run(cfg, manifest, season=season, stage="B", batch_size=1,
                               resume=True, execute=False, max_requests=0)
                    if gate["batch_decision"]["decision"] != "PASS":
                        return {"stop_reason": "POPULATION_GATE_NOT_PASS", "batches": batches}
                break
            result = run(cfg, manifest, season=season, stage="E", batch_size=cfg["max_batch_size"],
                         resume=True, execute=True, max_requests=max_requests)
            batches.append({"season": season, **result})
            print(json.dumps({"season": season, "batch": len(batches),
                              "http_attempts": result["http_attempts"],
                              "decision": result["batch_decision"],
                              "remaining_match_details": len(pending)-result["batch_decision"]["validated"]}), flush=True)
            decision = result["batch_decision"]
            budget_only = decision["decision"] == "REVIEW" and set(decision["errors"]) == {
                "REQUEST_BUDGET_EXCEEDED"} and decision["validated"] > 0
            if (decision["decision"] != "PASS" and not budget_only) or result["http_attempts"] == 0:
                return {"stop_reason": "BATCH_NOT_PASS_OR_NO_PROGRESS", "batches": batches}
            time.sleep(cfg["min_request_interval_seconds"])
        if len(batches) >= max_batches:
            break
    return {"stop_reason": "BATCH_LIMIT_OR_COMPLETE", "batches": batches}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Allow bounded match detail HTTP batches")
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--max-requests", type=int, default=50)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    cfg = load_full_config()
    if args.execute == args.report_only or not 0 < args.max_batches <= 50 or not 0 < args.max_requests <= 50:
        parser.error("Choose --execute or --report-only with bounded positive limits")
    manifest = Manifest(ROOT / cfg["manifest_path"])
    try:
        execution = collect(cfg, manifest, args.max_batches, args.max_requests) if args.execute else None
        progress = build_outputs(cfg, manifest)
        if execution:
            progress["http_attempts_this_run"] = sum(b["http_attempts"] for b in execution["batches"])
            progress["execution_stop_reason"] = execution["stop_reason"]
            atomic_write(ROOT / cfg["report_dir"] / "population_collection_progress.json", json_bytes(progress))
        print(json.dumps({"status_by_season": {s: r["status"] for s, r in progress["seasons"].items()},
                          "http_attempts_this_run": progress.get("http_attempts_this_run", 0),
                          "execution_stop_reason": progress.get("execution_stop_reason", "REPORT_ONLY")}, indent=2))
        return 0 if not execution or execution["stop_reason"] == "BATCH_LIMIT_OR_COMPLETE" else 2
    finally:
        manifest.close()


if __name__ == "__main__":
    raise SystemExit(main())
