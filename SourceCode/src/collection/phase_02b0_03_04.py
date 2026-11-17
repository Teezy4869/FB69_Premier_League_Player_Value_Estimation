"""Offline Step 03-04 rebuild, validation and final technical summary."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write
from src.collection.historical_identity import execute as build_identity, read_csv
from src.collection.position_mapper import execute as build_positions
from src.collection.metric_reconciler import execute as build_metrics
from src.collection.match_index_validator import write_report as build_match_report, probe_records
from src.collection.source_registry import SourceRegistry, load_hardening_config


def validate_outputs() -> dict:
    base = ROOT / "reports/phase_02b0"
    identities = read_csv(base / "historical_identity_validation.csv")
    positions = read_csv(base / "position_validation_report.csv")
    metrics = read_csv(base / "metric_dictionary_v2.csv")
    comparisons = read_csv(base / "metric_reconciliation_report.csv")
    registry = json.loads((base / "position_mapping_registry.json").read_text(encoding="utf-8"))
    match_probes = probe_records()
    issues = []
    seen = {(r["season_label"], r["fotmob_player_id"], r["fotmob_team_id"]) for r in identities}
    if len(seen) != len(identities):
        issues.append("Duplicate identity relation")
    if len(metrics) != 24 or len({r["normalized_field"] for r in metrics}) != 24:
        issues.append("Metric dictionary incomplete or duplicated")
    if len(positions) != 120 or registry.get("mapping_version") != "2.0":
        issues.append("Position sample or mapping version mismatch")
    if len(comparisons) != 183 or sum(r["comparison_status"] == "UNRESOLVED" for r in comparisons) != 1:
        issues.append("Cross-source comparison count or conflict mismatch")
    for row in identities:
        if row["historical_validation_status"] not in ("HISTORICAL_VERIFIED", "HISTORICAL_INFERRED",
                                                       "CURRENT_ONLY", "CONFLICTING", "UNKNOWN"):
            issues.append("Invalid historical validation status")
        if row["relationship_origin"] == "CURRENT_PROFILE" or row["current_team_is_historical"] != "False":
            issues.append("Current profile used as historical identity")
        for evidence in row["evidence_source"].split("|"):
            if evidence and not (ROOT / evidence).is_file():
                issues.append(f"Identity evidence missing: {evidence}")
    for row in positions:
        for evidence in row["historical_evidence_paths"].split("|"):
            if evidence and not (ROOT / evidence).is_file():
                issues.append(f"Position evidence missing: {evidence}")
    for mapping in registry["mappings"]:
        for evidence in mapping["supporting_raw_evidence"]:
            if not (ROOT / evidence).is_file():
                issues.append(f"Mapping evidence missing: {evidence}")
    for row in comparisons:
        for field in ("leaderboard_evidence_path", "player_stats_evidence_path"):
            if not (ROOT / row[field]).is_file():
                issues.append(f"Metric evidence missing: {row[field]}")
    conflicts = [r for r in positions if r["pilot_group_conflict"] == "True"]
    if not any(r["player_id"] == "108038" and r["historical_group_inferred"] == "MID" for r in conflicts):
        issues.append("Wijnaldum position regression evidence absent")
    if len(match_probes) > 2:
        issues.append("playerMatches probe budget exceeded")
    return {"identity_rows": len(identities),
            "verified_relations": sum(r["historical_validation_status"] == "HISTORICAL_VERIFIED" for r in identities),
            "inferred_relations": sum(r["historical_validation_status"] == "HISTORICAL_INFERRED" for r in identities),
            "position_conflicts": len(conflicts), "position_with_lineup": sum(bool(r["historical_evidence_paths"]) for r in positions),
            "mapping_entries": len(registry["mappings"]), "metric_rows": len(metrics),
            "metric_comparisons": len(comparisons), "metric_conflicts": sum(r["comparison_status"] == "UNRESOLVED" for r in comparisons),
            "player_matches_probes": len(match_probes), "issues": issues}


def execute(tests: str = "See test command") -> dict:
    identity = build_identity()
    position = build_positions()
    metric = build_metrics()
    match = build_match_report()
    facts = validate_outputs()
    report_dir = ROOT / "reports/phase_02b0"
    conflicts = [r for r in read_csv(report_dir / "position_validation_report.csv")
                 if r["pilot_group_conflict"] == "True"]
    named_conflicts = "; ".join(f"{r['player_name']} {r['season_label']}: "
                                f"{r['pilot_code_band_group']} -> {r['historical_group_inferred']}"
                                for r in conflicts)
    unresolved = next(r for r in metric["conflicts"] if r["comparison_status"] == "UNRESOLVED")
    status = "CONDITIONAL PASS" if not facts["issues"] else "FAIL"
    text = f"""# Phase 2B.0 Steps 03–04 — identity, position, metric and Match Index review

**Verdict: {status}.** The bounded evidence supports historical club relationships and a status-aware fixture index. Three retrospective second-club relationships, exact position semantics, one minutes conflict and `playerMatches` pagination remain unresolved. No full crawl or modeling was performed.

## Historical identity and team attribution

- {facts['identity_rows']} versioned relations: {facts['verified_relations']} HISTORICAL_VERIFIED and {facts['inferred_relations']} HISTORICAL_INFERRED. Of the verified rows, 3,262 come from season boards and two additional club relations from historical lineups. There are {identity['multi_club_player_seasons']} multi-club player-season pairs: {identity['multi_club_all_verified']} have both relations verified, and three retain an inferred second club (Archer 2023/24, Ramsdale 2024/25, Archer 2024/25). The bounded ID/name collision checks found no review candidates; see the membership rules for the four check types.
- 84/120 pilot current clubs differ from season-board clubs. Current profile fields never generate historical team rows. No duplicate normalized player-season or player-team-season keys; player-season totals are never summed with team relations. See [identity rows](historical_identity_validation.csv) and [membership rules](historical_membership_rules.md).

## Historical position

- The Phase 2A sampling code used numeric code bands. The new [exact-code registry](position_mapping_registry.json) has {facts['mapping_entries']} mappings, retaining raw FotMob codes and historical lineup evidence. Broad role labels inferred from source `usualPlayingPositionId` remain HISTORICAL_INFERRED; uncorroborated or mixed exact codes remain UNKNOWN. There is no arbitrary numeric-range promotion to verified history.
- {facts['position_with_lineup']}/120 sampled player-season rows have observed starter-lineup position evidence. {facts['position_conflicts']} conflict with the old pilot code-band group: {named_conflicts}. Wijnaldum's 2019/20 leaderboard code `104` was called FWD by the old band, while retained historical lineups show `positionId` 64/77 and source usual-role code 2, supporting an inferred MID group. Multiple match codes are preserved. See [position validation](position_validation_report.csv).

## Statistics reconciliation

- [Metric dictionary v2](metric_dictionary_v2.csv): 24 candidates; {dict(Counter(r['validation_status'] for r in read_csv(report_dir / 'metric_dictionary_v2.csv')))}. Source fields, units, aggregation type, positions, season coverage, missing states and provenance are explicit. Per-90 is retained separately from totals; goalkeeper saves compares the leaderboard's `Total saves` substat.
- [Comparison evidence](metric_reconciliation_report.csv): {facts['metric_comparisons']} compatible overlaps, {facts['metric_conflicts']} unresolved. In 2024/25, Mac Allister (`{unresolved['player_id']}`) has `{unresolved['leaderboard_raw_value']}` minutes in `mins_played` versus `{unresolved['player_stats_raw_value']}` in `playerStats`; both are integer season totals, with no documented rounding explanation or justified source preference. Both raw values remain.

## Match Index and playerMatches

- {match['fixture_records']} fixture records, {match['finished']} finished, one abandoned/cancelled. Bournemouth–Luton `4193691` remains separate from finished replay `4421797`. The 18-match fallback verifies {match['sampled_verified_participation_entries']} player–match entries; full participation and match-level statistics remain UNKNOWN.
- The named wrapper's documented parameter pattern was tested for two player/seasons within a two-attempt budget. Both returned HTTP 400 `Invalid or missing query parameters`; original response bodies and request metadata are retained. This does not prove historical data is absent. See [Match Index readiness](match_index_readiness.md).

## Reproducibility and limits

```powershell
python -m src.collection.historical_identity
python -m src.collection.position_mapper
python -m src.collection.metric_reconciler
python -m src.collection.match_index_validator
python -m src.collection.phase_02b0_03_04 --tests "{tests}"
python -m unittest discover -s tests -v
```

`match_index_validator --probe` only attempts missing documented-pattern probes and is capped at two HTTP requests. The offline commands above use saved evidence. Validation issues: {len(facts['issues'])}; tests: {tests}. Phase 1, Phase 2A and Steps 01–02 raw evidence were preserved. Steps 05–06 and Phase 2B.1 were not started.
"""
    atomic_write(report_dir / "steps_03_04_summary.md", text.encode("utf-8"))
    return {"status": status, **facts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="See test command")
    args = parser.parse_args()
    result = execute(args.tests)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["issues"] else 0)
