"""Build and independently validate the corrected, versioned EPL release v3.1."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.final_acceptance_fix import SEASONS, digest
from src.collection.release_manifest import physical_inventory, verify_manifest, write_manifest
from src.collection.remediation_release_v3 import write_csv, write_parquet
from src.collection.statistics_semantics import compute_metric_eligibility_registry

VERSION = "fotmob_epl_2019_2025_v3_1"
PARENT = "fotmob_epl_2019_2025_v3"
SOURCE_NORM = ("players", "teams", "seasons", "matches", "metric_observations", "historical_position_observations")


def csv_read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assert_unique(rows: list[dict], keys: tuple[str, ...], label: str) -> None:
    values = [tuple(r[k] for k in keys) for r in rows]
    if len(values) != len(set(values)) or any(any(v is None or v == "" for v in key) for key in values):
        raise ValueError(f"INVALID_PRIMARY_KEY:{label}")


def verify_part1(root: Path) -> dict:
    report = root / "reports/final_acceptance_fix"
    state = json.loads((report / "acceptance_fix_state.json").read_text(encoding="utf-8"))
    if state.get("status") != "AUDITED" or len(state.get("completed_seasons", [])) != len(SEASONS):
        raise ValueError("PART1_AUDIT_INCOMPLETE")
    snapshot = json.loads((report / "release_preservation_snapshot.json").read_text(encoding="utf-8"))
    for files in snapshot.values():
        for rel, expected in files.items():
            if digest(root / rel) != expected:
                raise ValueError(f"PARENT_RELEASE_CHANGED:{rel}")
    if state.get("raw_checksum_verified") != state.get("matches_audited"):
        raise ValueError("PART1_RAW_CHECKSUM_GATE")
    return state


def build(root: Path = ROOT, *, require_full_tests: bool = True, promote: bool = True) -> dict:
    part1 = verify_part1(root)
    report = root / "reports/final_acceptance_fix"
    parent = root / "data/releases" / PARENT
    provisional = root / "data/staging/fotmob_epl_2019_2025_v3_1_provisional"
    target = root / "data/releases" / VERSION
    if require_full_tests:
        tests = json.loads((report / "test_environment_report.json").read_text(encoding="utf-8"))
        if tests.get("exit_code") != 0 or tests.get("failed") or tests.get("errored") or not tests.get("executed_tests"):
            raise ValueError("FULL_TEST_SUITE_NOT_PASSING")
    stage_root = root / "data/staging"
    stage_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="fotmob_v3_1_candidate_", dir=stage_root))
    try:
        for sub in ("normalized", "curated", "metadata", "quality_reports", "manifests"):
            (stage / sub).mkdir()
        for name in SOURCE_NORM:
            shutil.copy2(parent / "normalized" / (name + ".parquet"), stage / "normalized" / (name + ".parquet"))
        for path in (parent / "manifests").iterdir():
            if path.is_file():
                shutil.copy2(path, stage / "manifests" / path.name)
        for name in ("player_match_appearances", "complete_player_season_classification",
                     "confirmed_appeared_player_seasons", "unverified_player_seasons",
                     "confirmed_non_appeared_player_seasons", "substitution_evidence_registry"):
            shutil.copy2(provisional / (name + ".parquet"), stage / "normalized" / (name + ".parquet"))
        pma = pq.read_table(stage / "normalized/player_match_appearances.parquet").to_pylist()
        pop = pq.read_table(stage / "normalized/complete_player_season_classification.parquet").to_pylist()
        matches = pq.read_table(stage / "normalized/matches.parquet").to_pylist()
        original_pts = pq.read_table(provisional / "player_team_seasons.parquet").to_pylist()
        seasons = pq.read_table(stage / "normalized/seasons.parquet").to_pylist()
        players = pq.read_table(stage / "normalized/players.parquet").to_pylist()
        teams = pq.read_table(stage / "normalized/teams.parquet").to_pylist()
        positions = pq.read_table(stage / "normalized/historical_position_observations.parquet").to_pylist()
        metrics = pq.read_table(stage / "normalized/metric_observations.parquet").to_pylist()
        wide = pq.read_table(parent / "curated/player_season_metrics_wide.parquet").to_pylist()
        assert_unique(pma, ("match_id", "player_id"), "player_match")
        assert_unique(pop, ("season_id", "player_id"), "player_season")
        assert_unique(original_pts, ("season_id", "player_id", "team_id"), "player_team_season")
        assert_unique(wide, ("season_id", "player_id"), "wide")
        pop_map = {(r["season_id"], r["player_id"]): r for r in pop}
        if {(r["season_id"], r["player_id"]) for r in wide} != set(pop_map):
            raise ValueError("WIDE_POPULATION_KEY_MISMATCH")
        accepted = {k for k, r in pop_map.items() if r["population_category"] == "CONFIRMED_APPEARED"}
        if any(r["population_category"] == "CONFIRMED_NON_APPEARED" for r in pop):
            raise ValueError("UNSUPPORTED_NONAPPEARED_POPULATION")
        pma_positive = defaultdict(set)
        for r in pma:
            if r["participation_status"] in ("STARTED", "SUBSTITUTED_ON"):
                pma_positive[(r["season_id"], r["player_id"], r["team_id"])].add(r["match_id"])
        for k in accepted:
            if not any(key[:2] == k for key in pma_positive):
                raise ValueError(f"CONFIRMED_WITHOUT_POSITIVE_EVIDENCE:{k}")
        if any(r["participation_status"] == "UNUSED_SUBSTITUTE" for r in pma):
            raise ValueError("UNSUPPORTED_UNUSED_SUBSTITUTE")
        player_seasons = []
        for r in pop:
            k = (r["season_id"], r["player_id"])
            status = "APPEARED" if k in accepted else "UNKNOWN_PARTICIPATION"
            player_seasons.append({"season_label": r["season_label"], "season_id": r["season_id"],
                                   "player_id": r["player_id"], "player_name": r["player_name"],
                                   "evidence_status": status, "in_candidate_population": True,
                                   "appeared_match_count": r["confirmed_appearance_count"],
                                   "team_count": r["confirmed_team_count"] if k in accepted else r["associated_team_count"],
                                   "evidence_raw_paths": r["evidence_raw_paths"], "profile_status": r["profile_status"]})
        write_parquet(stage / "normalized/player_seasons.parquet", player_seasons, list(player_seasons[0]))
        team_seasons = []
        for r in original_pts:
            count = len(pma_positive.get((r["season_id"], r["player_id"], r["team_id"]), set()))
            team_seasons.append({**r, "appeared_match_count": count,
                                 "membership_status": "APPEARED" if count else "UNVERIFIED",
                                 "validation_status": "CONFIRMED" if count else "UNRESOLVED"})
        write_parquet(stage / "normalized/player_team_seasons.parquet", team_seasons, list(team_seasons[0]))
        for r in wide:
            r["population_status"] = "APPEARED" if (r["season_id"], r["player_id"]) in accepted else "UNKNOWN_PARTICIPATION"
        valid_metric_statuses = {"OBSERVED", "OBSERVED_ZERO", "OBSERVED_SOURCE_REVISED", "OBSERVED_FALLBACK_LEADERBOARD"}
        for r in wide:
            if r["population_status"] != "APPEARED":
                continue
            for field, status in r.items():
                if field.startswith("s_") and ((status in valid_metric_statuses) != (r.get("m_" + field[2:]) is not None)):
                    raise ValueError(f"METRIC_STATUS_VALUE_MISMATCH:{r['season_id']}:{r['player_id']}:{field}")
        write_parquet(stage / "curated/player_season_metrics_wide.parquet", wide, list(wide[0]))
        curated_appeared = [r for r in wide if r["population_status"] == "APPEARED"]
        write_parquet(stage / "curated/confirmed_appeared_player_seasons.parquet", curated_appeared, list(wide[0]))
        rules = csv_read(stage / "manifests/metric_dictionary_v3.csv")
        metric_names = [r["normalized_field"] for r in rules]
        registry, coverage = compute_metric_eligibility_registry(wide, metric_names, rules, positions, seasons)
        if len(coverage) != len(SEASONS) * len(metric_names):
            raise ValueError("COVERAGE_MATRIX_INCOMPLETE")
        for r in coverage:
            if r["eligible_players"] == 0:
                r["coverage_fraction"] = ""
                r["coverage_status"] = "UNDEFINED"
            elif r["valid_values"] > r["eligible_players"] or float(r["coverage_fraction"]) > 1.0:
                raise ValueError(f"COVERAGE_ABOVE_100:{r['season_label']}:{r['metric_name']}")
        write_csv(stage / "quality_reports/cross_season_feature_coverage.csv", coverage, list(coverage[0]))
        write_csv(stage / "manifests/metric_eligibility_registry.csv", registry, list(registry[0]))
        season_map = {r["season_label"]: r["season_id"] for r in seasons}
        by_season = []
        appearance = []
        for season in SEASONS:
            ps = [r for r in pop if r["season_label"] == season]
            pm = [r for r in pma if r["season_label"] == season]
            comp = [r for r in matches if r["season_label"] == season and str(r["eligible_completed"]).lower() == "true"]
            psc = Counter(r["population_category"] for r in ps)
            pmc = Counter(r["participation_status"] for r in pm)
            by_season.append({"season_label": season, "season_id": season_map[season],
                              "completed_matches": len(comp), "player_seasons": len(ps),
                              "confirmed_appeared": psc["CONFIRMED_APPEARED"],
                              "confirmed_non_appeared": psc["CONFIRMED_NON_APPEARED"],
                              "unverified": psc["UNVERIFIED"], "conflicting": psc["CONFLICTING"],
                              "unknown_player_matches": pmc["UNKNOWN"]})
            match_unknown = {r["match_id"] for r in pm if r["participation_status"] in ("UNKNOWN", "CONFLICTING")}
            appearance.append({"season_label": season, "season_id": season_map[season],
                               "completed_matches": len(comp), "fully_resolved_matches": len(comp) - len(match_unknown),
                               "total_player_match_records": len(pm), "started_count": pmc["STARTED"],
                               "substituted_on_count": pmc["SUBSTITUTED_ON"],
                               "unused_substitute_count": pmc["UNUSED_SUBSTITUTE"], "unknown_count": pmc["UNKNOWN"],
                               "conflicting_count": pmc["CONFLICTING"],
                               "resolved_ratio_pct": round(100 * (pmc["STARTED"] + pmc["SUBSTITUTED_ON"] + pmc["UNUSED_SUBSTITUTE"]) / len(pm), 2),
                               "appeared_ratio_pct": round(100 * (pmc["STARTED"] + pmc["SUBSTITUTED_ON"]) / len(pm), 2)})
        if any(r["completed_matches"] != 380 or r["confirmed_appeared"] + r["confirmed_non_appeared"] + r["unverified"] + r["conflicting"] != r["player_seasons"] for r in by_season):
            raise ValueError("SEASON_POPULATION_GATE")
        write_csv(stage / "quality_reports/appearance_coverage.csv", appearance, list(appearance[0]))
        write_csv(stage / "quality_reports/population_reconciliation.csv", by_season, list(by_season[0]))
        conflicts = csv_read(root / "reports/phase_02b1_remediation/metric_conflict_root_causes.csv")
        conflict_actions = Counter(r["resolution_action"] for r in conflicts)
        wide_map = {(r["season_label"], r["player_id"]): r for r in wide}
        metric_rules = {r["normalized_field"]: r for r in rules}
        for r in conflicts:
            if not all(r.get(k) for k in ("canonical_metric", "unit", "aggregation_type", "resolution_action", "root_cause_explanation", "board_raw_path", "stats_raw_path")):
                raise ValueError("CONFLICT_RULE_OR_PROVENANCE_MISSING")
            if not (root / r["board_raw_path"]).is_file() or not (root / r["stats_raw_path"]).is_file():
                raise ValueError("CONFLICT_RAW_SOURCE_MISSING")
            rule = metric_rules.get(r["canonical_metric"])
            if not rule or rule["unit"] != r["unit"] or rule["aggregation_type"] != r["aggregation_type"]:
                raise ValueError("CONFLICT_UNIT_OR_AGGREGATION_MISMATCH")
            item = wide_map.get((r["season_label"], r["player_id"]))
            m = r["canonical_metric"]
            if r["resolution_action"] == "PRESERVED_UNRESOLVED_NULL":
                if not item or item.get("s_" + m) != "CONFLICTING" or item.get("m_" + m) is not None:
                    raise ValueError("UNRESOLVED_CONFLICT_CURATED_AS_VALUE")
            else:
                expected_status = "OBSERVED" if r["resolution_action"] == "RESOLVED_ROUNDING_TOLERANCE" else "OBSERVED_SOURCE_REVISED"
                if not item or item.get("s_" + m) != expected_status or item.get("m_" + m) is None or abs(item["m_" + m] - float(r["curated_resolved_value"])) > 1e-7:
                    raise ValueError("RESOLVED_CONFLICT_CURATED_MISMATCH")
        write_csv(stage / "quality_reports/metric_reconciliation_report.csv", conflicts, list(conflicts[0]))
        xg_quality = []
        for season in SEASONS:
            for metric in ("expected_goals", "expected_assists"):
                cov = next(r for r in coverage if r["season_label"] == season and r["metric_name"] == metric)
                xg_quality.append({"season_label": season, "metric_name": metric,
                                   "coverage_window_status": "UNKNOWN_COVERAGE_WINDOW",
                                   "source_reported_grain": "PLAYER_SEASON_VALUE",
                                   "partial_season_suspected": season == "2019/2020",
                                   "verified_window_start_utc": "", "verified_window_end_utc": "",
                                   "eligible_players": cov["eligible_players"], "observed_players": cov["valid_values"],
                                   "source_evidence": "playerStats|leagueseasondeepstats; no explicit observation-window dates in saved season metadata",
                                   "handling": "Preserve source value; do not assert full-season total or zero-fill missing periods"})
        write_csv(stage / "quality_reports/historical_xg_xa_coverage_quality.csv", xg_quality, list(xg_quality[0]))
        source_raw_report = parent / "quality_reports/raw_integrity_report.csv"
        shutil.copy2(source_raw_report, stage / "quality_reports/raw_integrity_report.csv")
        checks = quality_checks(root, stage, pma, pop, player_seasons, team_seasons, wide,
                                curated_appeared, matches, players, teams, seasons, metrics,
                                positions, coverage, registry, conflicts, part1)
        write_csv(stage / "quality_reports/referential_integrity_report.csv", checks, list(checks[0]))
        if any(r["status"] == "FAIL" for r in checks):
            raise ValueError("RELEASE_QUALITY_GATE_FAILED")
        summary = {"dataset_version": VERSION, "parent_release_version": PARENT,
                   "population_by_season": by_season, "appearance_by_season": appearance,
                   "metric_coverage_rows": len(coverage),
                   "coverage_above_100": sum(r["eligible_players"] and r["valid_values"] > r["eligible_players"] for r in coverage),
                   "coverage_undefined": sum(r["coverage_status"] == "UNDEFINED" for r in coverage),
                   "metric_conflict_actions": dict(conflict_actions),
                   "xg_xa_coverage_quality": xg_quality,
                   "quality_gates": checks, "season_acceptance": {s: "CONDITIONAL_PASS" for s in SEASONS},
                   "release_verdict": "CONDITIONAL_GO"}
        save_json(stage / "metadata/canonical_summary.json", summary)
        write_documentation(stage, summary)
        unknown_total = sum(r["unknown_player_matches"] for r in by_season)
        unverified_total = sum(r["unverified"] for r in by_season)
        unresolved_conflicts = conflict_actions["PRESERVED_UNRESOLVED_NULL"]
        known = [f"{unknown_total:,} player-match bench statuses remain UNKNOWN; {unverified_total} player-seasons remain UNVERIFIED.",
                 "No match has independently documented complete negative substitution coverage.",
                 f"{unresolved_conflicts} metric conflicts remain CONFLICTING with curated null values.",
                 "Historical xG/xA observation windows are not independently date-bounded; 2019/20 partial-season coverage is suspected."]
        manifest = write_manifest(stage, version=VERSION, parent_version=PARENT,
                                  seasons=list(SEASONS), quality_status="CONDITIONAL_GO",
                                  known_limitations=known,
                                  reproduction_commands=["python -m src.collection.final_acceptance_fix --workspace D:\\PTIT\\Hoc_may\\FB69",
                                                         "python -m src.collection.full_test_runner",
                                                         "python -m src.collection.final_acceptance_release --workspace D:\\PTIT\\Hoc_may\\FB69"])
        verify_manifest(stage)
        if promote:
            if target.exists():
                previous = verify_manifest(target)
                lhs = {r["path"]: r["sha256"] for r in physical_inventory(stage)}
                rhs = {r["path"]: r["sha256"] for r in physical_inventory(target)}
                if lhs != rhs:
                    raise ValueError("EXISTING_RELEASE_CONTENT_DIFFERS_NO_OVERWRITE")
                if stage.resolve().parent != stage_root.resolve() or not stage.name.startswith("fotmob_v3_1_candidate_"):
                    raise ValueError("UNSAFE_CANDIDATE_CLEANUP_PATH")
                shutil.rmtree(stage)
            else:
                os.replace(stage, target)
            verify_manifest(target)
            active = target
        else:
            active = stage
        return {"release_path": str(active), "promoted": promote,
                "checksummed_files": manifest["checksummed_files"],
                "total_files": manifest["total_files"], "parquet_tables": manifest["parquet_tables"],
                "summary": summary}
    except Exception:
        failed = stage.with_name(stage.name + "_FAILED")
        if stage.exists():
            os.replace(stage, failed)
        raise


def quality_checks(root: Path, stage: Path, pma: list[dict], pop: list[dict], ps: list[dict],
                   pts: list[dict], wide: list[dict], curated: list[dict], matches: list[dict],
                   players: list[dict], teams: list[dict], seasons: list[dict], metrics: list[dict],
                   positions: list[dict], coverage: list[dict], registry: list[dict],
                   conflicts: list[dict], part1: dict) -> list[dict]:
    checks = []
    def gate(name: str, failures: int, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if failures == 0 else "FAIL", "failures": failures, "detail": detail})
    tables = {"players": (players, ("player_id",)), "teams": (teams, ("season_id", "team_id")),
              "seasons": (seasons, ("season_id",)), "matches": (matches, ("match_id",)),
              "player_seasons": (ps, ("season_id", "player_id")),
              "player_team_seasons": (pts, ("season_id", "player_id", "team_id")),
              "player_match_appearances": (pma, ("match_id", "player_id")),
              "complete_population": (pop, ("season_id", "player_id")),
              "wide": (wide, ("season_id", "player_id")),
              "curated_appeared": (curated, ("season_id", "player_id"))}
    for name, (rows, keys) in tables.items():
        vals = [tuple(r.get(k) for k in keys) for r in rows]
        gate(name + "_PRIMARY_KEY", len(vals) - len(set(vals)) + sum(any(v is None or v == "" for v in key) for key in vals), f"rows={len(rows)}")
    player_ids = {r["player_id"] for r in players}
    season_ids = {r["season_id"] for r in seasons}
    team_ids = {(r["season_id"], r["team_id"]) for r in teams}
    match_map = {r["match_id"]: r for r in matches}
    ps_keys = {(r["season_id"], r["player_id"]) for r in ps}
    pts_keys = {(r["season_id"], r["player_id"], r["team_id"]) for r in pts}
    gate("PLAYER_SEASON_FOREIGN_KEYS", sum(r["player_id"] not in player_ids or r["season_id"] not in season_ids for r in ps), "player and season references")
    gate("MATCH_TEAM_SEASON_KEYS", sum((r["season_id"], r["home_team_id"]) not in team_ids or (r["season_id"], r["away_team_id"]) not in team_ids for r in matches), "historical home/away teams")
    gate("APPEARANCE_FOREIGN_KEYS", sum(r["match_id"] not in match_map or (r["season_id"], r["player_id"], r["team_id"]) not in pts_keys or match_map[r["match_id"]]["season_id"] != r["season_id"] for r in pma), "match and historical club relationship")
    gate("METRIC_FOREIGN_KEYS", sum((r["season_id"], r["player_id"]) not in ps_keys for r in metrics), "metric observations to player-season")
    gate("POSITION_FOREIGN_KEYS", sum(r["match_id"] not in match_map or (r["season_id"], r["team_id"]) not in team_ids for r in positions), "historical position references")
    gate("POSITIVE_POPULATION_EVIDENCE", sum(r["population_category"] == "CONFIRMED_APPEARED" and not r["confirmed_appearance_count"] for r in pop), "confirmed appeared requires match evidence")
    gate("NO_UNSUPPORTED_NEGATIVE", sum(r["participation_status"] == "UNUSED_SUBSTITUTE" for r in pma) + sum(r["population_category"] == "CONFIRMED_NON_APPEARED" for r in pop), "unknowns retained")
    gate("POPULATION_PARTITION", abs(len(ps) - len(pop)) + abs(len(wide) - len(pop)) + abs(len(curated) - sum(r["population_category"] == "CONFIRMED_APPEARED" for r in pop)), "exclusive categories and curated")
    gate("COVERAGE_BOUNDS", sum(r["eligible_players"] > 0 and (r["valid_values"] > r["eligible_players"] or float(r["coverage_fraction"]) > 1) for r in coverage), "all metric-season rows")
    gate("COVERAGE_UNDEFINED", sum(r["eligible_players"] == 0 and (r["coverage_status"] != "UNDEFINED" or r["coverage_fraction"] != "") for r in coverage), "zero denominator")
    gate("CONFLICT_NULL_PRESERVED", sum(r["resolution_action"] == "PRESERVED_UNRESOLVED_NULL" and r["curated_resolved_status"] != "CONFLICTING" for r in conflicts), "source conflicts remain visible")
    legacy = csv_read(root / "reports/phase_02b1_remediation/quality_gate_evidence_registry.csv")
    gate("LEGACY_GATE_DISPOSITION", sum(r["remediated_state"] != "SUPERSEDED" or r["predecessors_satisfied"] != "True" or not r["evidence_pointer"] or not r["replacement_mechanism"] for r in legacy), f"documented_legacy_gates={len(legacy)}")
    gate("RAW_MATCH_CHECKSUMS", 0 if part1["raw_checksum_verified"] == part1["matches_audited"] else 1, "Part 1 audited matchDetails checksum evidence")
    gate("ABANDONED_REPLAY", 0 if any(r["match_id"] == "4193691" and str(r["eligible_completed"]).lower() == "false" for r in matches) and any(r["match_id"] == "4421797" and str(r["eligible_completed"]).lower() == "true" for r in matches) and not any(r["match_id"] == "4193691" for r in pma) else 1, "Bournemouth-Luton")
    for season in SEASONS:
        count = sum(r["season_label"] == season and str(r["eligible_completed"]).lower() == "true" for r in matches)
        gate(season + "_MATCH_COUNT", abs(count - 380), f"completed={count}")
    return checks


def write_documentation(stage: Path, summary: dict) -> None:
    rows = summary["population_by_season"]
    table = "\n".join(f"| {r['season_label']} | {r['completed_matches']} | {r['confirmed_appeared']} | {r['confirmed_non_appeared']} | {r['unverified']} | {r['unknown_player_matches']} |" for r in rows)
    readme = f"""# FotMob EPL 2019–2025 release v3.1

Parent: `{PARENT}`. Verdict: **CONDITIONAL_GO** for controlled downstream data integration.

The player-match and player-season tables use the Part 1 audited evidence. Unknown bench participation remains unknown. All six seasons have conditional acceptance.

| Season | Completed matches | Confirmed appeared player-seasons | Confirmed non-appeared | Unverified | Unknown player-matches |
|---|---:|---:|---:|---:|---:|
{table}

See `metadata/release_manifest.json` for all file hashes and physical row counts. The manifest excludes only itself from its checksummed inventory. `metadata/canonical_summary.json` drives the reports. Raw FotMob captures are referenced, not copied or modified.
"""
    (stage / "README.md").write_text(readme, encoding="utf-8")
    (stage / "metadata/reproduction_guide.md").write_text("# Offline reproduction\n\n```powershell\ncd D:\\PTIT\\Hoc_may\\FB69\npython -m src.collection.final_acceptance_fix --workspace D:\\PTIT\\Hoc_may\\FB69\npython -m src.collection.full_test_runner\npython -m src.collection.final_acceptance_release --workspace D:\\PTIT\\Hoc_may\\FB69\n```\n\nInput v2/v3 releases and raw captures must retain their recorded SHA-256 hashes. The builder validates a temporary candidate and promotes only after all mandatory gates pass. A repeated build verifies identical content and does not overwrite an existing different release. The manifest creation timestamp is excluded from data-content reproducibility comparison.\n", encoding="utf-8")
    (stage / "metadata/schema_definitions.md").write_text("# Schema contract\n\nPrimary grains: player-season `(season_id, player_id)`; player-team-season `(season_id, player_id, team_id)`; player-match `(match_id, player_id)`; match `(match_id)`. Identifiers remain string typed in the normalized tables. `UNKNOWN` participation and `UNVERIFIED` population are distinct from confirmed non-appearance. `quality_reports/historical_xg_xa_coverage_quality.csv` records uncertain observation windows. `quality_reports/cross_season_feature_coverage.csv` leaves undefined ratios blank. Physical schemas and SHA-256 schema digests are listed in the release manifest.\n", encoding="utf-8")
    unknown_total = sum(r["unknown_player_matches"] for r in rows)
    unverified_total = sum(r["unverified"] for r in rows)
    unresolved_conflicts = summary["metric_conflict_actions"]["PRESERVED_UNRESOLVED_NULL"]
    (stage / "metadata/known_issues.md").write_text(f"# Known limitations\n\n- {unknown_total:,} player-match bench entries remain UNKNOWN; {unverified_total} player-seasons remain UNVERIFIED.\n- {unresolved_conflicts} metric definition conflicts remain null and traceable.\n- Historical xG/xA coverage windows lack independently verified start/end dates; 2019/20 partial coverage is suspected.\n- Goalkeeper eligibility depends on historical lineup position evidence; unknown positions are counted separately.\n", encoding="utf-8")
    cov_by_season = defaultdict(list)
    for row in summary["xg_xa_coverage_quality"]:
        cov_by_season[row["season_label"]].append(row)
    conflict_by_season = Counter(r["season_label"] for r in csv_read(stage / "quality_reports/metric_reconciliation_report.csv") if r["resolution_action"] == "PRESERVED_UNRESOLVED_NULL")
    for row in rows:
        season = row["season_label"]
        coverage_text = ", ".join(f"{r['metric_name']}: {r['observed_players']}/{r['eligible_players']} ({r['coverage_window_status']})" for r in cov_by_season[season])
        body = f"# {season} corrected acceptance\n\nSeason ID: {row['season_id']}. Status: **CONDITIONAL_PASS**.\n\n- Completed matches: {row['completed_matches']}.\n- Confirmed appeared: {row['confirmed_appeared']}; confirmed non-appeared: {row['confirmed_non_appeared']}; unverified: {row['unverified']}.\n- Unknown player-match participation: {row['unknown_player_matches']}.\n- xG/xA coverage: {coverage_text}. Full metric matrix: `cross_season_feature_coverage.csv`.\n- Unresolved metric conflicts: {conflict_by_season[season]}. Raw conflict paths: `metric_reconciliation_report.csv`.\n- Historical club relationships and 380-match scope: validated in `referential_integrity_report.csv`.\n- Goalkeeper eligibility and unknown historical positions: `../manifests/metric_eligibility_registry.csv`.\n- Source integrity: Part 1 checked 2,280 raw matchDetails SHA-256 values; this release manifest checksums every non-manifest file.\n- Quality issues: unknown bench participation and observation-window limits remain.\n"
        (stage / "quality_reports" / f"season_{season.replace('/', '_')}_acceptance.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--no-promote", action="store_true")
    args = parser.parse_args()
    result = build(args.workspace, promote=not args.no_promote)
    print(json.dumps({k: v for k, v in result.items() if k != "summary"}, indent=2))
