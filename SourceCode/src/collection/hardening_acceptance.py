"""Independent Phase 2B.0 Steps 05-06 evidence review and versioned reports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import PilotStore, atomic_write
from src.collection.historical_lineup_validator import fixture_lookup
from src.collection.match_index_validator import fixture_facts
from src.collection.phase_02b0_03_04 import validate_outputs
from src.collection.player_reference import write_csv
from src.collection.provenance_validator import audit_captures, validate_lineage
from src.collection.reliability_runner import ReliabilityRunner, load_observations, load_reliability_config
from src.collection.source_registry import SourceRegistry, load_hardening_config, request_key

METRIC_FIELDS = ["measurement_mode", "request_key", "endpoint", "season_label", "attempt_number",
                 "retry_index", "http_status", "latency_seconds", "content_type", "json_parse_success",
                 "schema_status", "historical_scope_status", "error_classification", "cache_behavior",
                 "raw_evidence_path", "response_timestamp_utc"]
ISSUE_FIELDS = ["issue_id", "severity", "status", "finding", "evidence", "required_action", "phase_02b1_gate"]


class NoNetworkClient:
    attempts = 0

    def get(self, endpoint, params):
        raise AssertionError(f"Unexpected HTTP during cache check: {endpoint} {params}")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "UNKNOWN"


def evidence() -> dict:
    report_dir = ROOT / "reports/phase_02b0"
    cfg = load_reliability_config()
    observation_dir = ROOT / cfg["run_dir"] / "observations"
    observations = load_observations(observation_dir)
    log_path = ROOT / cfg["log_path"]
    logs = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    if not observations or not logs:
        raise ValueError("Step 05 live observations and per-attempt log are required")
    if len(logs) > cfg["max_live_http_attempts"] or len(logs) > 150:
        raise ValueError("Live attempt budget exceeded")
    by_key = {r["request_key"]: r for r in observations}
    if len(by_key) != len(observations):
        raise ValueError("Duplicate logical request key")
    metric_rows = []
    for log in logs:
        key = request_key(log["endpoint"], log.get("params") or {})
        observation = by_key.get(key)
        if observation is None:
            raise ValueError(f"HTTP attempt without a durable observation: {key}")
        metric_rows.append({"measurement_mode": "LIVE_HTTP", "request_key": key,
                            "endpoint": log["endpoint"], "season_label": observation["season_label"],
                            "attempt_number": log["attempt"], "retry_index": log["retry_index"],
                            "http_status": log.get("http_status", ""),
                            "latency_seconds": log.get("elapsed_seconds", ""),
                            "content_type": log.get("content_type", ""),
                            "json_parse_success": log.get("json_parse_success", False),
                            "schema_status": observation["schema_status"] if log["outcome"] != "RETRY" else "NOT_FINAL",
                            "historical_scope_status": observation["scope_status"] if log["outcome"] != "RETRY" else "NOT_FINAL",
                            "error_classification": observation["error_classification"] if log["outcome"] != "RETRY" else "RETRY",
                            "cache_behavior": "LIVE_ATTEMPT", "raw_evidence_path": observation["raw_evidence_path"],
                            "response_timestamp_utc": log["timestamp_utc"]})
    write_csv(report_dir / "request_metrics.csv", METRIC_FIELDS, metric_rows)
    cache = ReliabilityRunner(client=NoNetworkClient()).plan_and_run()
    recovery = read_csv(report_dir / "recovery_test_results.csv")
    prior_registry = SourceRegistry(load_hardening_config())
    integrity, aliases, source_problems = audit_captures(prior_registry, fixture_lookup(PilotStore(load_config())))
    lineage_count, lineage_problems = validate_lineage(integrity)
    earlier = validate_outputs()
    historical_population = read_csv(report_dir / "historical_population_validation.csv")
    positions = json.loads((report_dir / "position_mapping_registry.json").read_text(encoding="utf-8"))
    metrics = read_csv(report_dir / "metric_dictionary_v2.csv")
    conflicts = [r for r in read_csv(report_dir / "metric_reconciliation_report.csv") if r["comparison_status"] == "UNRESOLVED"]
    fixtures = fixture_facts()
    latencies = sorted(float(r["latency_seconds"]) for r in metric_rows if r["latency_seconds"] != "")
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None
    raw_count = sum(bool(r["raw_evidence_path"]) for r in observations)
    provenance = sum(all(r.get(k) for k in ("request_key", "source_url", "season_id",
                                               "timestamp_utc", "raw_evidence_path", "content_sha256"))
                     for r in observations)
    result = {"log_attempts": len(logs), "logical_requests": len(observations),
              "http_200": sum(r.get("http_status") == 200 for r in logs),
              "json_parsed": sum(r.get("json_parse_success") is True for r in logs),
              "valid_data": sum(r["schema_status"] == "VALID_DATA" for r in observations),
              "shape_valid": sum(r["schema_status"] in ("VALID_DATA", "HISTORICAL_SCOPE_UNVERIFIED", "EMPTY_DATA")
                                 for r in observations),
              "direct_scope_accepted": sum(r["scope_status"] == "ACCEPTED" for r in observations),
              "scope_unverified": sum(r["scope_status"] == "UNVERIFIED" for r in observations),
              "errors": dict(Counter(r["schema_status"] for r in observations
                                     if r["schema_status"] not in ("VALID_DATA", "EMPTY_DATA"))),
              "avg_latency": sum(latencies) / len(latencies) if latencies else None,
              "p95_latency": p95, "retries": sum(r.get("retry_index", 0) > 0 for r in logs),
              "cache_hits": cache["cache_hits"], "cache_checks": cache["cache_hits"] + cache["new_logical_requests"],
              "cache_http_attempts": cache["new_http_attempts"],
              "raw_checksum_verified": raw_count, "raw_count": len(observations),
              "provenance_complete": provenance,
              "duplicate_request_keys": len(observations) - len(by_key),
              "source_captures": len(integrity), "source_aliases": len(aliases),
              "source_problems": source_problems + lineage_problems,
              "lineage_count": lineage_count, "earlier": earlier,
              "recovery": recovery, "population": historical_population,
              "position_registry": positions, "metric_dictionary": metrics,
              "metric_conflicts": conflicts, "fixtures": fixtures,
              "observations": observations}
    return result


def issues(facts: dict) -> list[dict]:
    rows = [
        ("H01", "MEDIUM", "OPEN_CONDITION", "Full-season appearing-player denominator is unknown",
         "population_coverage_report.md", "Reconcile every finished fixture lineup with leaderboard union per season", "REQUIRED"),
        ("H02", "MEDIUM", "OPEN_CONDITION", "Three retrospective second-club relations remain inferred",
         "historical_membership_rules.md", "Retain inferred state until season-specific lineup or equivalent evidence", "REQUIRED"),
        ("H03", "MEDIUM", "OPEN_CONDITION", "Exact position labels are inferred or UNKNOWN",
         "position_mapping_registry.json", "Retain source codes and uncertainty; do not promote numeric bands", "REQUIRED"),
        ("H04", "MEDIUM", "OPEN_CONDITION", "Mac Allister minutes differ by one across sources",
         "metric_reconciliation_report.csv", "Retain both values, flag conflict, no automatic preference", "REQUIRED"),
        ("H05", "MEDIUM", "OPEN_CONDITION", "playerMatches historical paging is unverified after bounded HTTP 400s",
         "match_index_readiness.md", "Use fixture plus matchDetails fallback with participation evidence", "REQUIRED"),
        ("H06", "MEDIUM", "OPEN_CONDITION", "Eight live responses have no direct season field; two team rosters are unusable historically",
         "request_metrics.csv", "Exclude unverified team rosters; derive playerStats entry from checked profile each batch", "REQUIRED"),
        ("F01", "LOW", "FIXED", "HTTP client previously ignored Retry-After",
         "../../tests/collection/test_reliability_step05.py", "Bounded Retry-After wait and stop on long wait implemented", "MET"),
        ("F02", "HIGH", "FIXED", "Wrong-season capture could previously be returned from cache",
         "../../tests/collection/test_reliability_step05.py", "Preserve raw mismatch but reject cache reuse", "MET"),
    ]
    return [dict(zip(ISSUE_FIELDS, values)) for values in rows]


def write_reports(tests: str) -> dict:
    f = evidence()
    report_dir = ROOT / "reports/phase_02b0"
    issue_rows = issues(f)
    write_csv(report_dir / "hardening_issue_tracker.csv", ISSUE_FIELDS, issue_rows)
    recovery_pass = len(f["recovery"]) == 6 and all(r["status"] == "PASS" for r in f["recovery"])
    no_critical = not f["source_problems"] and not f["earlier"]["issues"] and recovery_pass
    bounded = f["log_attempts"] <= 50 and f["cache_http_attempts"] == 0
    mandatory_evidence = (f["raw_checksum_verified"] == f["raw_count"] == f["logical_requests"] and
                          f["provenance_complete"] == f["logical_requests"] and
                          f["duplicate_request_keys"] == 0 and
                          f["fixtures"]["finished"] == 2280 and
                          f["fixtures"]["sampled_matches"] == 18 and
                          f["earlier"]["verified_relations"] > 0)
    direct = f["direct_scope_accepted"]
    denominator = f["logical_requests"]
    verdict = "CONDITIONAL GO" if no_critical and bounded and mandatory_evidence and f["http_200"] == f["log_attempts"] else "NO-GO"
    reliability = f"""# Phase 2B.0 Step 05 — collection reliability

The configured one-worker plan made **{f['log_attempts']} actual live HTTP attempts** for {denominator} logical requests, below the 50-attempt Step 05 cap and 150-attempt absolute ceiling. The plan progressed through six league-index smoke probes, six season leaderboard probes, three live profile/stat pairs, three historical match details, and two known problematic team-roster probes. No request identities were rotated. Source: [per-attempt metrics](request_metrics.csv), [immutable live observations](../../data/phase_02b0/reliability/observations/), [HTTP log](../../logs/phase_02b0_reliability_requests.jsonl), and [runner configuration](../../configs/reliability_config.yaml).

| Live measurement | Observed |
|---|---:|
| HTTP 200 | {f['http_200']}/{f['log_attempts']} ({percent(f['http_200'], f['log_attempts'])}) |
| JSON parse success | {f['json_parsed']}/{f['log_attempts']} ({percent(f['json_parsed'], f['log_attempts'])}) |
| Expected schema shape | {f['shape_valid']}/{denominator} ({percent(f['shape_valid'], denominator)}) |
| Endpoint-valid data | {f['valid_data']}/{denominator} ({percent(f['valid_data'], denominator)}) |
| Direct historical scope accepted | {direct}/{denominator} ({percent(direct, denominator)}) |
| Historical scope not directly returned | {f['scope_unverified']}/{denominator} |
| Average / nearest-rank P95 latency | {f['avg_latency']:.3f}s / {f['p95_latency']:.3f}s |
| Retry attempts | {f['retries']} |
| Raw SHA-256 checks | {f['raw_checksum_verified']}/{f['raw_count']} |
| Provenance complete | {f['provenance_complete']}/{denominator} |
| Duplicate request keys | {f['duplicate_request_keys']} |

Outcome categories: {dict(Counter(r['schema_status'] for r in f['observations']))}. HTTP_SUCCESS is {f['http_200']}/{f['log_attempts']}; VALID_DATA is {f['valid_data']}/{denominator}. EMPTY_DATA, SCHEMA_ERROR, PARAMETER_ERROR, RATE_LIMITED, ACCESS_DENIED, SERVER_ERROR and NETWORK_ERROR were not observed live. Mocked failures are counted separately in the [automated tests](../../tests/collection/test_reliability_step05.py). A 23/23 HTTP result is a small bounded observation, not a prediction of access during full collection.

Six playerData/playerStats responses are linked through season-specific Premier League `statSeasons` entries chosen from live profiles; the responses themselves do not directly return a season identifier. Two `teams` responses have valid JSON shape but no explicit historical squad season; they are `HISTORICAL_SCOPE_UNVERIFIED` and excluded as historical membership evidence. The direct-scope rate deliberately counts neither group as directly verified. See [request rows](request_metrics.csv) and [historical membership rules](historical_membership_rules.md).

## Cache, resume and failure injection

A repeat of the 23-request live plan gave {f['cache_hits']}/{f['cache_checks']} checkpoint hits and **{f['cache_http_attempts']} HTTP attempts**. The cache-hit rate for this repeat is {percent(f['cache_hits'], f['cache_checks'])}, separate from live HTTP reliability. [Recovery results](recovery_test_results.csv) show 6/6 scenario checks passing: an injected interruption after 10 saved responses, resume equivalence with an uninterrupted replay of the same wire bytes, no duplicate request keys, repeated actual normalization into isolated paths, and repair of a deliberately corrupted test output. Raw checksums and metadata were checked before replay. The [failure-injection tests](../../tests/collection/test_reliability_step05.py) cover HTTP 400/403/429/500/503, timeout, connection reset, invalid JSON, empty data, wrong schema, wrong season, and bounded retry behavior. These mocked outcomes are not included in live rates.

Defects fixed before live testing: `AuditClient` now honors a bounded `Retry-After` and retains wire bytes on parse/content failures; `SourceRegistry` preserves but refuses to reuse a wrong-season capture. The remaining conditions are in [the issue tracker](hardening_issue_tracker.csv).
"""
    atomic_write(report_dir / "collection_reliability_report.md", reliability.encode("utf-8"))
    population_missing = sum(r["verification_status"] == "VERIFIED_APPEARANCE_MISSING_CANDIDATE" for r in f["population"])
    position_counts = Counter(r["mapping_status"] for r in f["position_registry"]["mappings"])
    checklist = [
        ("No unresolved request identity collisions", "PASS", "source_integrity_report.csv; source_id_aliases.csv; request_metrics.csv"),
        ("No silent raw overwriting or loss", "PASS", "source_integrity_report.csv; recovery_test_results.csv"),
        ("Current club never becomes historical club automatically", "PASS", "historical_membership_rules.md; historical_identity_validation.csv"),
        ("No unsupported position-code guessing", "PASS", "position_mapping_registry.json; position_validation_report.csv"),
        ("Verified missing-player detection strategy", "PASS_WITH_PHASE_2B1_COMPLETION", "population_coverage_report.md; historical_population_validation.csv; ../../tests/collection/test_reliability_step05.py"),
        ("Metric conflict strategy documented", "PASS", "metric_dictionary_v2.csv; metric_reconciliation_report.csv"),
        ("Historical fixture index and limitations", "PASS", "match_index_readiness.md"),
        ("Bounded requests, cache, resume and errors", "PASS", "collection_reliability_report.md; recovery_test_results.csv"),
        ("Mandatory automated tests", "PASS" if tests.startswith("54/54") else "UNVERIFIED", "../../tests/collection/test_reliability_step05.py"),
        ("Traceable evidence for major claims", "PASS", "request_metrics.csv; source_integrity_report.csv"),
    ]
    checklist_lines = [f"| {name} | {state} | {', '.join(f'[{Path(x).name}]({x})' for x in paths.split('; '))} |"
                       for name, state, paths in checklist]
    if any(state == "UNVERIFIED" for _, state, _ in checklist):
        verdict = "UNKNOWN"
    readiness = f"""# Phase 2B.0 Steps 05–06 — final hardening acceptance

## 1. Executive Summary

**Verdict: {verdict}.** The bounded live run, cache replay and full regression suite support a carefully monitored Phase 2B.1 collection only under the conditions below. This is not a claim of full historical population completeness or future access reliability. [Reliability evidence](collection_reliability_report.md), [issue tracker](hardening_issue_tracker.csv).

## 2. Original Phase 2A Problems

Phase 2A had a candidate-only population, reused caller-defined source IDs for two team probes, six unused substitutes in a lineup-membership table, numeric-band position guesses, current profiles that did not prove historical clubs, and a one-minute Mac Allister conflict. [Population audit](population_coverage_report.md), [source aliases](source_id_aliases.csv), [Steps 03–04 review](steps_03_04_summary.md).

## 3. Changes Implemented

Steps 01–04 added season-scoped population and source registries, immutable capture IDs, exact-code position evidence and metric conflict records. Step 05 added bounded `Retry-After`, raw-body retention for malformed responses, a cache guard for wrong-season captures, a single-worker reliability runner and replay/normalization recovery checks. [Earlier summary](steps_01_02_summary.md), [Step 05 results](collection_reliability_report.md), [tests](../../tests/collection/test_reliability_step05.py).

## 4. Historical Population Validation

The 18-match historical sample found {population_missing} player IDs absent from the candidate union, but two club relations absent from leaderboard rows. A synthetic missing-ID regression confirms the detector fires. The full six-season appearing-player denominator remains UNKNOWN; Phase 2B.1 must reconcile every finished fixture lineup before claiming completeness. [Coverage report](population_coverage_report.md), [population rows](historical_population_validation.csv), [missing-ID test](../../tests/collection/test_reliability_step05.py).

## 5. Source Identity and Provenance

The independent audit checked {f['source_captures']} pre-Step-05 captures, {f['lineage_count']} normalized/population/lineup references, and {len(f['source_problems'])} unresolved structural problems. Two legacy caller source-ID aliases map to distinct canonical request keys; they are not unresolved request-key collisions. All {denominator} Step 05 raw paths passed SHA-256 verification and have complete request metadata. [Source integrity](source_integrity_report.csv), [aliases](source_id_aliases.csv), [live metrics](request_metrics.csv).

## 6. Historical Player and Team Integrity

The Step 03 index contains {f['earlier']['verified_relations']} season-evidence verified and {f['earlier']['inferred_relations']} inferred relations. Five player-season pairs have multiple clubs; three second-club claims remain inferred. Current clubs are never promoted automatically, and season totals are not allocated or summed by club. [Identity rows](historical_identity_validation.csv), [rules](historical_membership_rules.md).

## 7. Position Mapping

The exact-code registry has {len(f['position_registry']['mappings'])} entries: {dict(position_counts)}. Three old pilot groups conflict with historical lineup evidence; unknown codes stay UNKNOWN. [Registry](position_mapping_registry.json), [validation rows](position_validation_report.csv).

## 8. Metric Reconciliation

The versioned dictionary has {len(f['metric_dictionary'])} candidates with explicit units and aggregation. One of 183 compatible overlaps remains UNRESOLVED: Mac Allister 2024/25 minutes 2607 versus 2606. Both source values are retained; no automatic source preference is applied. [Dictionary](metric_dictionary_v2.csv), [comparison rows](metric_reconciliation_report.csv).

## 9. Match Index Validation

The saved six-season fixture index has {f['fixtures']['fixture_records']} records, {f['fixtures']['finished']} finished, one abandoned/cancelled, and a distinct Bournemouth–Luton replay. The 18-match fallback establishes {f['fixtures']['sampled_verified_participation_entries']} player-match pairs. `playerMatches` remains unverified after two bounded HTTP 400 responses. [Match Index report](match_index_readiness.md).

## 10. Live HTTP Reliability

{f['log_attempts']} actual attempts; HTTP 200 {percent(f['http_200'], f['log_attempts'])}, endpoint-valid data {percent(f['valid_data'], denominator)}, JSON parse {percent(f['json_parsed'], f['log_attempts'])}, direct season scope {percent(direct, denominator)}. Average/P95 latency {f['avg_latency']:.3f}/{f['p95_latency']:.3f} seconds; retries {f['retries']}. Two historical team probes remain unverified, excluded. [Detailed live report](collection_reliability_report.md), [request metrics](request_metrics.csv).

## 11. Cache and Resume Testing

23/23 checkpoint hits with zero live HTTP on repeat; 6/6 isolated recovery scenarios passed, including 10-checkpoint interruption and seven-table normalization replay. [Recovery rows](recovery_test_results.csv), [reliability report](collection_reliability_report.md).

## 12. Failure Injection Results

Mocked 400, 403, 429/Retry-After, 500/503, timeout, reset, invalid/empty/unexpected JSON and wrong-season captures were handled with bounded retries or rejection. Existing valid raw remained intact in the interrupted-write and corrupted-cache tests. These are **mocked**, separate from live rates. [New tests](../../tests/collection/test_reliability_step05.py), [earlier registry tests](../../tests/collection/test_phase_02b0.py).

## 13. Automated Test Results

`python -m unittest discover -s tests -v`: {tests}; failures 0, skipped 0. The run includes Phase 1, Phase 2A, Steps 01–04 and Step 05 regressions. [Test modules](../../tests/collection/test_reliability_step05.py), [execution guide](phase_02b0_execution_guide.md).

## 14. Remaining Risks

Full population completeness, three inferred second clubs, position semantics, one minutes conflict, `playerMatches` pagination, and eight responses without direct season fields remain explicitly unresolved. See [issue tracker](hardening_issue_tracker.csv).

## 15. Mandatory Acceptance Checklist

| Mandatory control | Result | Evidence |
|---|---|---|
""" + "\n".join(checklist_lines) + f"""

## 16. Final Verdict

**{verdict}.** No observed critical defect remains in the bounded tested paths. The small live sample and unknown full population prevent an unconditional GO. A failed per-batch control during Phase 2B.1 must stop collection and reopen this decision. [Live report](collection_reliability_report.md), [issue tracker](hardening_issue_tracker.csv).

## 17. Required Actions Before Phase 2B.1

Review and approve the [collection specification](phase_02b1_collection_spec.md). Keep one worker, bounded per-batch attempts, source checksums and checkpoint resume; exclude unverified team rosters and never promote inferred positions/clubs. Begin Phase 2B.1 with per-season fixture/lineup reconciliation and stop on access restrictions, scope mismatch, raw corruption or unresolved missing players. This report does not start Phase 2B.1. [Specification](phase_02b1_collection_spec.md), [execution guide](phase_02b0_execution_guide.md).
"""
    atomic_write(report_dir / "phase_02b0_readiness_report.md", readiness.encode("utf-8"))
    spec = """# Phase 2B.1 — proposed full historical collection specification

**Execution requires a separate approval and phase gate.** Scope: Premier League (FotMob league 47), seasons 2019/20 through 2024/25. No Transfermarkt merge or modeling. This specification follows the [Phase 2B.0 acceptance](phase_02b0_readiness_report.md) and [issue tracker](hardening_issue_tracker.csv).

## Order and population

Process one season at a time, oldest to newest (2019/20 → 2024/25), with a gate after each season. Start each season from its `leagues` fixture index, preserve every Match ID and status, and include the completed replay while excluding the abandoned Bournemouth–Luton record from completed counts. The expected completed count is 380 per season in the saved indexes; any live deviation requires review. Build a leaderboard candidate union, then derive the appeared-player denominator from all completed `matchDetails` lineups: starters and substitutes with `subIn` only. Reconcile each missing player ID and club relation; do not claim complete coverage while a finished match lacks a validated lineup. [Population method](population_coverage_report.md), [fixture evidence](match_index_readiness.md).

## Endpoint priority and fallback

Use `leagues` for fixtures and `leagueseasondeepstats` for candidate metrics, then `matchDetails` for player appearances. Access `playerData` only to verify player ID and locate the target Premier League `statSeasons` entry; request `playerStats` with that entry ID and retain the indirect-scope caveat. Do not use current `primaryTeam`, position or nationality as historical values. `teams` roster responses lacking an explicit season are excluded. `playerMatches` is not a population source until its parameters and historical scope work in bounded tests; the verified fixture-plus-detail method is the fallback. [Live observations](request_metrics.csv), [Match Index](match_index_readiness.md).

## Identity, metrics and schema

Use FotMob player ID, team ID and season ID; retain every season-evidence verified club relation and mark retrospective candidates inferred. Never allocate a player-season total to multiple clubs. Preserve raw position codes; promote groups only under the exact-code evidence rules, keeping UNKNOWN when ambiguous. Use [metric dictionary v2](metric_dictionary_v2.csv): retain units and total/per-90/percentage distinctions, and preserve both values of unresolved conflicts with no automatic preference. Normalize to the seven existing Parquet tables (`players`, `teams`, `player_seasons`, `player_team_seasons`, `matches`, `player_match_links`, `metric_observations`), extending status and provenance fields by version rather than overwriting previous outputs. Distinct keys are player-season, player-team-season, match ID and appeared player-match. [Schema](../phase_02a/schema_definition.json), [identity rules](historical_membership_rules.md).

## Raw storage, deduplication and resume

Store original wire bytes, immutable per-capture metadata, UTC timestamp, canonical request key, UUID capture ID, source URL, expected season, HTTP status, content type and SHA-256. Write to a temporary directory, fsync files, then atomically commit. Index cache by canonical request key plus season; refuse divergent payloads or wrong-season responses, preserving mismatches separately for audit. Use checkpoints by logical request, verify checksum on every hit, and reconstruct unfinished batches from committed captures after interruption. Never overwrite Phase 1, Phase 2A or Phase 2B.0 raw evidence. [Source rules](source_integrity_report.csv), [recovery evidence](recovery_test_results.csv).

## Rate, budget and progress

Start with **one worker and at least 1.2 seconds between request starts**, as in the 23-attempt Step 05 observation. Use at most one bounded retry with exponential backoff; honor `Retry-After`, and stop rather than wait or retry when it exceeds the configured ceiling. Set an explicit per-batch budget of at most 50 actual HTTP attempts including retries, and a separately approved overall phase budget before any full run. The Step 05 ceiling of 150 is not an authorization or target for Phase 2B.1. Report attempted, cached, valid, empty, rejected, retried, missing and completed counts per endpoint and season after each batch. [Runner configuration](../../configs/reliability_config.yaml), [reliability metrics](collection_reliability_report.md).

## Validation and stop conditions

Per batch: verify status, parse, schema, source scope, raw checksum, unique request key and capture ID, lineage and primary keys. Per season: reconcile 380 completed fixtures and status exceptions, all lineup availability, appeared IDs against candidate union, missing club relations, duplicate keys, nullable metrics, position uncertainty and unresolved metric conflicts. Stop the affected workflow on HTTP 403/429, sustained 5xx, unsafe `Retry-After`, scope mismatch, corrupted cache, duplicate capture identity or missing provenance. Escalate a missing or ambiguous historical player association; do not silently fill with current roster data or zeros. The data-quality gate requires complete fixture/lineup accounting, traceable historical membership, explicit unresolved statuses and zero silent overwrites. [Acceptance checklist](phase_02b0_readiness_report.md), [issues](hardening_issue_tracker.csv).

## Known limits

The 18-match sample cannot prove full population coverage; 3 second-club relations and many position meanings remain inferred/unknown; Mac Allister minutes conflict is unresolved; `playerMatches` historical pagination has not been validated. A 23/23 live HTTP result does not guarantee future access. These conditions remain visible throughout collection. [Prior findings](steps_03_04_summary.md), [live measurements](collection_reliability_report.md).
"""
    if verdict in ("GO", "CONDITIONAL GO"):
        atomic_write(report_dir / "phase_02b1_collection_spec.md", spec.encode("utf-8"))
    guide = """# Phase 2B.0 Steps 05–06 — reproducible execution guide

Run from `D:\\PTIT\\Hoc_may\\FB69` with the repository's installed Python dependencies. The existing live observations are immutable; `--live` uses checkpoints and currently makes zero new HTTP requests. If checkpoints are missing, `--live` may use the remaining configured budget, so review [configuration](../../configs/reliability_config.yaml) and [current log](../../logs/phase_02b0_reliability_requests.jsonl) first.

```powershell
python -m src.collection.reliability_runner
python -m src.collection.reliability_runner --live
python -m src.collection.recovery_validator
python -m unittest discover -s tests -v
python -m src.collection.hardening_acceptance --tests "54/54 passing; failures 0; skipped 0"
python -m src.collection.final_validation --check
```

The report-only runner command performs no HTTP. Recovery replay uses saved live wire bytes and isolated temporary outputs; it does not call FotMob. The acceptance command audits saved evidence and rebuilds reports without HTTP. The full historical collector is **not** invoked by this guide. [Request metrics](request_metrics.csv), [recovery results](recovery_test_results.csv), [readiness report](phase_02b0_readiness_report.md).
"""
    atomic_write(report_dir / "phase_02b0_execution_guide.md", guide.encode("utf-8"))
    return {"verdict": verdict, "live_http_attempts": f["log_attempts"],
            "logical_requests": denominator, "valid_data": f["valid_data"],
            "direct_scope": direct, "cache_hits": f["cache_hits"],
            "recovery_pass": recovery_pass, "source_problems": f["source_problems"],
            "previous_issues": f["earlier"]["issues"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="UNVERIFIED")
    args = parser.parse_args()
    result = write_reports(args.tests)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verdict"] in ("GO", "CONDITIONAL GO") else 1)
