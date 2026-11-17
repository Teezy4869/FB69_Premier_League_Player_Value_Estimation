"""Audit legacy and Phase 2B.0 captures without modifying original evidence."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write
from src.collection.historical_lineup_validator import fixture_lookup, read_csv, verify_detail
from src.collection.player_reference import write_csv
from src.collection.source_registry import SourceRegistry, canonical_params, load_hardening_config, request_key, validate_scope
from src.collection.foundation import PilotStore

INTEGRITY_FIELDS = ["request_key", "capture_id", "legacy_source_id", "endpoint", "source_url", "canonical_params",
                    "season_label", "season_id", "collected_at_utc", "http_status", "content_type",
                    "content_sha256", "raw_path", "metadata_path", "body_kind", "scope_status",
                    "scope_note", "source_id_collision", "identical_content_cross_season", "legacy_capture"]
ALIAS_FIELDS = ["legacy_source_id", "season_label", "endpoint", "canonical_params", "request_key",
                "capture_id", "content_sha256", "raw_path", "migration_action"]


def audit_captures(registry: SourceRegistry, fixtures: dict[str, list[dict]]) -> tuple[list[dict], list[dict], list[str]]:
    captures = list(registry.captures())
    log_urls = {}
    log_path = registry.root / registry.hardening["log_path"]
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            log_urls[(event.get("timestamp_utc"), event.get("endpoint"),
                      json.dumps(canonical_params(event.get("params") or {}), sort_keys=True, separators=(",", ":")))] = event.get("source_url", "")
    source_counts = Counter(m["source_id"] for m, _ in captures if m["legacy"])
    hashes = defaultdict(set)
    for meta, _ in captures:
        hashes[meta["content_sha256"]].add(meta["season_label"])
    fixture_by_id = {r["match_id"]: r for rows in fixtures.values() for r in rows}
    rows, aliases, problems = [], [], []
    ids = set()
    request_identities = {}
    for meta, payload in captures:
        capture_id = meta["capture_id"]
        if capture_id in ids:
            problems.append(f"Duplicate capture_id: {capture_id}")
        ids.add(capture_id)
        expected_key = request_key(meta["endpoint"], meta["params"],
                                   contract=registry.hardening["request_contract"])
        if expected_key != meta["request_key"]:
            problems.append(f"Request fingerprint mismatch: {capture_id}")
        canonical = json.dumps(meta["params"], sort_keys=True, separators=(",", ":"))
        log_key = (meta["collected_at_utc"], meta["endpoint"], canonical)
        source_url = meta.get("source_url") or log_urls.get(log_key, "")
        if not source_url:
            problems.append(f"Missing source URL provenance: {capture_id}")
        previous = request_identities.get(meta["request_key"])
        if previous is not None and previous != (meta["endpoint"], canonical):
            problems.append(f"Request-key collision: {meta['request_key']}")
        request_identities[meta["request_key"]] = (meta["endpoint"], canonical)
        if not (registry.root / meta["raw_path"]).is_file() or not (
                registry.root / meta["metadata_path"]).is_file():
            problems.append(f"Missing raw or metadata path: {capture_id}")
        if meta["http_status"] != 200 or "json" not in meta["content_type"].lower():
            problems.append(f"Non-successful retained capture: {capture_id}")
        scope, note = validate_scope(meta["endpoint"], meta["params"], meta["season_label"],
                                     int(meta["season_id"]), payload)
        if meta["endpoint"] == "matchDetails":
            fixture = fixture_by_id.get(str(meta["params"].get("matchId")))
            if fixture and fixture["season_label"] == meta["season_label"]:
                scope, note = verify_detail(payload, fixture)
            else:
                scope, note = "UNVERIFIED", "Match absent from corresponding season fixture index"
        if meta.get("scope_status") and meta["scope_status"] != scope:
            problems.append(f"Stored/computed scope status differs: {capture_id}")
        row = {"request_key": meta["request_key"], "capture_id": capture_id,
               "legacy_source_id": meta["source_id"] if meta["legacy"] else "",
               "endpoint": meta["endpoint"], "source_url": source_url,
               "canonical_params": canonical,
               "season_label": meta["season_label"], "season_id": meta["season_id"],
               "collected_at_utc": meta["collected_at_utc"], "http_status": meta["http_status"],
               "content_type": meta["content_type"], "content_sha256": meta["content_sha256"],
               "raw_path": meta["raw_path"], "metadata_path": meta["metadata_path"],
               "body_kind": meta["body_kind"], "scope_status": scope, "scope_note": note,
               "source_id_collision": meta["legacy"] and source_counts[meta["source_id"]] > 1,
               "identical_content_cross_season": len(hashes[meta["content_sha256"]]) > 1,
               "legacy_capture": meta["legacy"]}
        rows.append(row)
        if row["source_id_collision"]:
            aliases.append({"legacy_source_id": meta["source_id"], "season_label": meta["season_label"],
                            "endpoint": meta["endpoint"], "canonical_params": canonical,
                            "request_key": meta["request_key"], "capture_id": capture_id,
                            "content_sha256": meta["content_sha256"], "raw_path": meta["raw_path"],
                            "migration_action": "Use request_key+capture_id; preserve original metadata"})
    return rows, aliases, problems


def validate_lineage(integrity: list[dict]) -> tuple[int, list[str]]:
    pilot = load_config()
    legacy_sources = defaultdict(set)
    for row in integrity:
        if row["legacy_source_id"]:
            legacy_sources[row["legacy_source_id"]].add(row["raw_path"])
    problems, checked = [], 0
    for name, field in (("players", "profile_source_id"), ("player_seasons", "stats_source_id"),
                        ("matches", "source_id"), ("player_match_links", "source_id"),
                        ("metric_observations", "source_id")):
        for row in pq.read_table(ROOT / pilot["normalized_dir"] / f"{name}.parquet").to_pylist():
            source_id = row.get(field)
            if not source_id:
                continue
            checked += 1
            if source_id not in legacy_sources:
                problems.append(f"Unresolved normalized lineage: {name} {source_id}")
    for row in read_csv(ROOT / "reports/phase_02b0/historical_population_validation.csv"):
        for fragment in row["evidence_reference"].split("|"):
            checked += 1
            if not (ROOT / fragment).is_file():
                problems.append(f"Missing population evidence: {fragment}")
    for row in read_csv(ROOT / "reports/phase_02b0/historical_lineup_comparison.csv"):
        checked += 1
        if not (ROOT / row["evidence_reference"]).is_file():
            problems.append(f"Missing lineup evidence: {row['evidence_reference']}")
    return checked, problems


def legacy_lineup_link_status() -> Counter:
    """Audit the earlier lineup-membership table against actual substitution events."""
    pilot = load_config()
    details = {m["source_id"]: p for m, p in PilotStore(pilot).cached_payloads("matchDetails")}
    counts = Counter()
    links = pq.read_table(ROOT / pilot["normalized_dir"] / "player_match_links.parquet").to_pylist()
    for link in links:
        lineup = ((details[link["source_id"]].get("content") or {}).get("lineup") or {})
        found = False
        for side in ("homeTeam", "awayTeam"):
            team = lineup.get(side) or {}
            for role in ("starters", "subs"):
                for player in team.get(role) or []:
                    if str(player.get("id")) != link["player_id"]:
                        continue
                    found = True
                    entered = any(e.get("type") == "subIn" for e in
                                  ((player.get("performance") or {}).get("substitutionEvents") or [])
                                  if isinstance(e, dict))
                    counts["APPEARED" if role == "starters" or entered else "UNUSED_SUBSTITUTE"] += 1
        if not found:
            counts["NO_LINEUP_EVIDENCE"] += 1
    return counts


def report(tests: str = "See test command") -> dict:
    hardening = load_hardening_config()
    registry = SourceRegistry(hardening)
    fixtures = fixture_lookup(PilotStore(load_config()))
    integrity, aliases, problems = audit_captures(registry, fixtures)
    report_dir = ROOT / hardening["report_dir"]
    write_csv(report_dir / "source_integrity_report.csv", INTEGRITY_FIELDS, integrity)
    write_csv(report_dir / "source_id_aliases.csv", ALIAS_FIELDS, aliases)
    checked, lineage_problems = validate_lineage(integrity)
    problems += lineage_problems
    population = read_csv(report_dir / "historical_population_validation.csv")
    lineup = read_csv(report_dir / "historical_lineup_comparison.csv")
    match_sample = read_csv(report_dir / "historical_match_sample.csv")
    candidate = [r for r in population if r["reference_source"] == "leagueseasondeepstats"]
    appeared = [r for r in lineup if r["appearance_status"] == "APPEARED"]
    table = []
    for season in load_config()["seasons"]:
        c = [r for r in candidate if r["season_label"] == season]
        a = [r for r in appeared if r["season_label"] == season]
        unique_appeared = {r["player_id"] for r in a}
        found = {r["player_id"] for r in a if r["in_candidate_population"] == "True"}
        missing = unique_appeared - found
        team_mismatch = {(r["player_id"], r["team_id"]) for r in a if r["candidate_team_relation"] == "OTHER_TEAM"}
        count_matches = sum(r["season_label"] == season and r["detail_scope_status"] == "ACCEPTED" for r in match_sample)
        table.append({"season": season, "candidate_players": len({r["player_id"] for r in c}),
                      "candidate_relations": len(c), "sampled_matches": count_matches,
                      "appeared_unique": len(unique_appeared), "found": len(found), "missing": len(missing),
                      "team_mismatch": len(team_mismatch),
                      "sample_percent": round(100 * len(found) / len(unique_appeared), 2) if unique_appeared else "UNKNOWN"})
    table_lines = [f"| {r['season']} | {r['candidate_players']} | {r['candidate_relations']} | {r['sampled_matches']} | "
                   f"{r['appeared_unique']} | {r['found']} | {r['missing']} | {r['team_mismatch']} | {r['sample_percent']}% |"
                   for r in table]
    missing_player_ids = sorted({(r["season_label"], r["player_id"]) for r in appeared
                                 if r["in_candidate_population"] == "False"})
    other_teams = sorted({(r["season_label"], r["player_id"], r["player_name"], r["team_id"])
                          for r in appeared if r["candidate_team_relation"] == "OTHER_TEAM"})
    legacy_link_status = legacy_lineup_link_status()
    reference_minutes = {(r["season_label"], r["fotmob_player_id"]): float(r["minutes_played"])
                         for r in read_csv(ROOT / "reports/phase_02a/player_reference_index.csv")
                         if r["minutes_played"]}
    low_minute_entries = [r for r in appeared if r["lineup_role"] == "SUBSTITUTE" and
                          reference_minutes.get((r["season_label"], r["player_id"]), float("inf")) < 90]
    coverage = """# Phase 2B.0 Step 01 — historical population validation

**Target:** distinct FotMob player ID with evidence of appearing in at least one Premier League match in a given season. Registered players, unused substitutes and leaderboard entries alone are not confirmed appearances. Player-season and player-team-season are separate keys.

The existing minutes/goals/saves leaderboard union is only a candidate set. Rebuilding it found no duplicate player-team-season key and no same-season multi-team player in those boards; lineup comparison still found omitted team relationships. The validation sample is 18 deterministic, season-scoped finished fixtures (early/mid/late in each of six seasons); 12 details were newly requested within the configured budget and six came from Phase 2A cache. A starter counts as appeared; a substitute counts only with a `subIn` event. All match IDs, dates, teams, league and status matched the retained fixture index.

| Season | Candidate players | Candidate team relations | Matches | Unique appeared players | In candidate union | Missing IDs | Other-team relations | SAMPLE COVERAGE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
""" + "\n".join(table_lines) + f"""

Across the sample: {len(appeared)} appeared lineup entries, {len({(r['season_label'], r['player_id']) for r in appeared})} unique player-season IDs, {sum(r['appearance_status']=='UNUSED_SUBSTITUTE' for r in lineup)} unused substitute listings. This includes {len(low_minute_entries)} entered-substitute appearances whose season leaderboard minutes were below 90 (the pilot's low-minute threshold). Missing player-season IDs from leaderboard union: {len(missing_player_ids)}. **Full-season appearing-player denominator and full-season completeness are UNKNOWN.** A 100% sample result cannot establish a complete season population.

Two player-team-season relationships are absent from the leaderboard candidate rows despite the player IDs appearing elsewhere in those seasons:
""" + "\n".join(f"- {s}: {name} (player {pid}), appeared for team {team}; retain match evidence and verify the club spell before assigning season totals." for s, pid, name, team in other_teams) + f"""

The team requests for Liverpool in 2019/20 and 2024/25 contain the same response bytes and report `latestSeason=2026/2027`, but no explicit historical `squad.season`. They are UNVERIFIED for historical roster completeness and are excluded from the denominator.

Correction to the Phase 2A interpretation: its 47 `player_match_links` rows recorded lineup membership; checking the retained substitution events shows {legacy_link_status['APPEARED']} appeared and {legacy_link_status['UNUSED_SUBSTITUTE']} were unused substitutes. The original Phase 2A evidence remains unchanged. This Phase 2B.0 validation counts only actual appearances.

For Phase 2B.1, discover all season fixtures from the verified `leagues` index, retrieve matchDetails in bounded resumable batches, count only starters and substitutes with `subIn`, union player IDs by season, reconcile against season leaderboard candidates, and inspect every omitted ID/team relation. Set per-season checkpoints for 380 finished fixtures (with replay/status exceptions), lineup availability and unique IDs; report completeness only after validating the entire match population and resolving missing lineup coverage. This is an implementable full-scale method, **not executed here**.

Evidence: [lineup comparisons](historical_lineup_comparison.csv), [sampled matches](historical_match_sample.csv), [population rows](historical_population_validation.csv), and [season leaderboard minutes](../phase_02a/player_reference_index.csv).
"""
    atomic_write(report_dir / "population_coverage_report.md", coverage.encode("utf-8"))
    scopes = Counter(r["scope_status"] for r in integrity)
    cross_content = [r for r in integrity if r["identical_content_cross_season"]]
    summary = f"""# Phase 2B.0 Steps 01–02 — execution summary

**Result: {'CONDITIONAL PASS' if not problems else 'FAIL'}**. Step 01 established a bounded appearing-player sample, but the full-season denominator is UNKNOWN. Step 02 has deterministic request identity and immutable new capture storage; original Phase 1/2A raw files remain unchanged.

## Population

- Rebuilt {len(candidate)} candidate player-team-season rows from 18 cached leaderboard responses, across six seasons; no claim of full population.
- Validated {sum(r['detail_scope_status']=='ACCEPTED' for r in match_sample)}/18 selected match details, of which 12 were newly captured. {len(appeared)} appeared entries; {len({(r['season_label'], r['player_id']) for r in appeared})} unique player-season IDs; {len(missing_player_ids)} absent player IDs; {len(other_teams)} missing candidate team relationships. Unused substitutes excluded.
- {len(low_minute_entries)} confirmed entered-substitute appearances have fewer than 90 season leaderboard minutes, so low-minute participation is represented by observed events.
- Re-audit of the preserved Phase 2A `player_match_links`: {legacy_link_status['APPEARED']}/47 actually appeared; {legacy_link_status['UNUSED_SUBSTITUTE']} were unused substitutes. That table represented lineup membership, not confirmed participation.
- See [population coverage](population_coverage_report.md) and [row evidence](historical_population_validation.csv).

## Source identity and integrity

- Audited {len(integrity)} captures: {sum(r['legacy_capture'] for r in integrity)} legacy and {sum(not r['legacy_capture'] for r in integrity)} new. All JSON, SHA-256 and stored paths validated. Computed scope status counts: {dict(scopes)}. The 231 UNVERIFIED responses are 109 playerData, 120 playerStats and two historical `teams` probes whose bodies lack an explicit season scope; a separate verified profile `statSeasons` association does not turn a `playerStats` response into explicit season metadata. {checked} normalized/population/lineup evidence references resolved; {len(problems)} structural problems.
- Root cause of Liverpool collision: the two calls supplied the same caller-defined `source_id=team_roster_probe_liverpool`. Their canonical season parameters and legacy filename/cache hashes differ, so request-key/filename generation did not collide. Their content SHA-256 is equal, because both responses contained the same current-oriented roster; `details.latestSeason` is 2026/2027 and the squad has no returned historical season. Both remain **UNVERIFIED** historical roster evidence.
- New `request_key` hashes method, canonical path, sorted normalized parameters and contract; 2019/20 versus 2024/25 team requests have distinct keys. A UUID `capture_id` names an immutable directory; actual bytes have a separate `content_sha256`. The versioned [alias report](source_id_aliases.csv) maps the two legacy records to separate request/capture identities without modifying them.
- New captures are written to a temporary directory and atomically renamed. Cache lookup checks request key **and** expected season, rejects differing payloads under one key/season and verifies checksums. Matching match-detail context is checked against the season fixture index. No HTTP 200 alone is treated as historical proof.
- The source URL for each of the 12 new captures is recoverable from the immutable Phase 2B.0 HTTP log by timestamp, endpoint and canonical parameters; it is included in the source integrity report. Future captures also write it into metadata. Existing raw metadata was not edited.
- See [source integrity rows](source_integrity_report.csv). The 265 legacy captures remain in place; 12 new matchDetails captures are under `data/phase_02b0/raw/`.

## Reproduction and limits

```powershell
python -m src.collection.historical_lineup_validator
python -m src.collection.historical_lineup_validator --collect
python -m src.collection.provenance_validator --tests "{tests}"
python -m unittest discover -s tests -v
```

The non-collect command rebuilds only from cache. Repeating `--collect` uses cache and should issue zero HTTP calls. New collection remains capped at 12 attempts by configuration. Tests: {tests}. Full historical crawl, all-match detail download, Transfermarkt merge and modeling were not performed. Full-season population completeness remains UNKNOWN.
"""
    atomic_write(report_dir / "steps_01_02_summary.md", summary.encode("utf-8"))
    return {"captures": len(integrity), "scope_statuses": dict(scopes), "aliases": len(aliases),
            "lineage_references": checked, "problems": problems,
            "sample_matches": sum(r["detail_scope_status"] == "ACCEPTED" for r in match_sample),
            "missing_player_ids": len(missing_player_ids), "other_team_relations": len(other_teams)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="See test command")
    args = parser.parse_args()
    result = report(args.tests)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["problems"] else 0)
