"""Conditional six-season FotMob release with independent referential/rebuild checks."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.execution01_preflight import run_test_suite
from src.collection.execution04_identity import OUT as IDENTITY, appearance_status
from src.collection.execution05_acceptance import OUT as QUALITY, REPORT, csv_read, csv_write, sha
from src.collection.foundation import atomic_write, json_bytes
from src.collection.population_execution02 import participation_rows
from src.collection.statistics_semantics import collapse_stat_occurrences, value_status

RELEASE = ROOT / "data/releases/fotmob_epl_2019_2025_v2"
SEASONS = ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025")


def read(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()


def key_check(rows: list[dict], fields: tuple[str, ...], name: str) -> list[dict]:
    keys = [tuple(r.get(f) for f in fields) for r in rows]
    duplicates = len(keys) - len(set(keys))
    nulls = sum(any(v is None or v == "" for v in key) for key in keys)
    return [{"check": name + "_PRIMARY_KEY", "status": "PASS" if not duplicates and not nulls else "FAIL",
             "failures": duplicates + nulls, "detail": f"duplicates={duplicates}; nulls={nulls}"}]


def referential(tables: dict[str, list[dict]]) -> list[dict]:
    players = {r["player_id"] for r in tables["players"]}
    seasons = {r["season_id"] for r in tables["seasons"]}
    teams = {(r["season_id"], r["team_id"]) for r in tables["teams"]}
    matches = {r["match_id"]: r for r in tables["matches"]}
    player_seasons = {(r["season_id"], r["player_id"]) for r in tables["player_seasons"]}
    result = []
    keys = {"players": ("player_id",), "teams": ("season_id", "team_id"), "seasons": ("season_id",),
            "matches": ("match_id",), "player_seasons": ("season_id", "player_id"),
            "player_team_seasons": ("season_id", "player_id", "team_id"),
            "player_match_appearances": ("match_id", "player_id"),
            "historical_position_observations": ("season_id", "match_id", "player_id", "source_field")}
    for name, fields in keys.items():
        if name == "historical_position_observations":
            # Multiple positions can be observed for one player/match/source field only if raw duplicates exist.
            result += key_check(tables[name], fields, name)
        else:
            result += key_check(tables[name], fields, name)
    checks = {
        "PLAYER_SEASON_FOREIGN_KEYS": sum(r["player_id"] not in players or r["season_id"] not in seasons for r in tables["player_seasons"]),
        "TEAM_SEASON_FOREIGN_KEYS": sum(r["season_id"] not in seasons for r in tables["teams"]),
        "MATCH_FOREIGN_KEYS": sum(r["season_id"] not in seasons or
                                  (r["season_id"], r["home_team_id"]) not in teams or
                                  (r["season_id"], r["away_team_id"]) not in teams for r in tables["matches"]),
        "MEMBERSHIP_FOREIGN_KEYS": sum((r["season_id"], r["player_id"]) not in player_seasons or
                                       (r["season_id"], r["team_id"]) not in teams for r in tables["player_team_seasons"]),
        "APPEARANCE_FOREIGN_KEYS": sum(r["player_id"] not in players or r["match_id"] not in matches or
                                       (r["season_id"], r["team_id"]) not in teams or
                                       matches.get(r["match_id"], {}).get("season_id") != r["season_id"] for r in tables["player_match_appearances"]),
        "POSITION_FOREIGN_KEYS": sum(r["player_id"] not in players or r["match_id"] not in matches or
                                     (r["season_id"], r["team_id"]) not in teams for r in tables["historical_position_observations"]),
        "METRIC_FOREIGN_KEYS": sum((r["season_id"], r["player_id"]) not in player_seasons for r in tables["metric_observations"]),
        "WIDE_FOREIGN_KEYS": sum((r["season_id"], r["player_id"]) not in player_seasons for r in tables["player_season_metrics_wide"]),
    }
    for name, failures in checks.items():
        result.append({"check": name, "status": "PASS" if not failures else "FAIL", "failures": failures, "detail": ""})
    for s in SEASONS:
        sid = next(r["season_id"] for r in tables["seasons"] if r["season_label"] == s)
        count = sum(r["season_id"] == sid and r["eligible_completed"] == "True" for r in tables["matches"])
        result.append({"check": s + "_COMPLETED_MATCHES", "status": "PASS" if count == 380 else "FAIL",
                       "failures": abs(count-380), "detail": f"count={count}"})
    by_id = {r["match_id"]: r for r in tables["matches"]}
    replay_ok = by_id.get("4193691", {}).get("eligible_completed") == "False" and by_id.get("4421797", {}).get("eligible_completed") == "True"
    result.append({"check": "BOURNEMOUTH_LUTON_REPLAY", "status": "PASS" if replay_ok else "FAIL",
                   "failures": 0 if replay_ok else 1, "detail": "abandoned 4193691 excluded; replay 4421797 included"})
    return result


def reproduce_six_matches(tables: dict[str, list[dict]]) -> list[dict]:
    first = {}
    for match in tables["matches"]:
        if match["eligible_completed"] == "True":
            first.setdefault(match["season_label"], match)
    by_match = defaultdict(list)
    for row in tables["player_match_appearances"]:
        by_match[row["match_id"]].append(row)
    rows = []
    for season in SEASONS:
        fixture = first[season]
        links = by_match[fixture["match_id"]]
        raw_path = links[0]["raw_path"]
        meta_path = (ROOT / raw_path).with_name("metadata.json")
        if not meta_path.exists():
            meta_path = (ROOT / raw_path).with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body = (ROOT / raw_path).read_bytes()
        raw_sha = hashlib.sha256(body).hexdigest()
        expected_sha = meta.get("content_sha256", meta.get("sha256"))
        payload = json.loads(body)
        lineage_meta = {field: links[0][field] for field in
                        ("source_id", "capture_id", "request_key", "raw_path", "collected_at_utc")}
        reconstructed, issues = participation_rows(payload, fixture, lineage_meta)
        expected = {(r["player_id"], r["team_id"], r["participation_status"]) for r in links}
        actual = {(r["player_id"], r["team_id"], appearance_status(r)) for r in reconstructed}
        passed = not issues and raw_sha == expected_sha and expected == actual
        rows.append({"season_label": season, "match_id": fixture["match_id"], "raw_path": raw_path,
                     "raw_sha256_valid": raw_sha == expected_sha, "expected_links": len(expected),
                     "rebuilt_links": len(actual), "status": "PASS" if passed else "FAIL",
                     "issues": "|".join(issues)})
    return rows


def reproduce_six_metrics(tables: dict[str, list[dict]]) -> list[dict]:
    wide = {(r["season_id"], r["player_id"]): r for r in tables["player_season_metrics_wide"]}
    first = {}
    for r in tables["metric_observations"]:
        if (r["source_endpoint"] == "playerStats" and r["metric_name"] == "goals" and
            r["metric_status"] in ("OBSERVED", "OBSERVED_ZERO") and
            wide[(r["season_id"], r["player_id"])]["s_goals"] != "CONFLICTING"):
            first.setdefault(r["season_label"], r)
    rows = []
    for season in SEASONS:
        r = first[season]
        path = ROOT / r["raw_path"]
        meta_path = path.with_name("metadata.json")
        if not meta_path.exists():
            meta_path = path.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body = path.read_bytes()
        expected_sha = meta.get("content_sha256", meta.get("sha256"))
        selected, conflicts = collapse_stat_occurrences(json.loads(body))
        source = selected.get(r["original_source_field"])
        value = value_status(source["raw_value"])[1] if source else None
        curated = wide[(r["season_id"], r["player_id"])]["m_goals"]
        passed = (hashlib.sha256(body).hexdigest() == expected_sha and value == r["value"] == curated and
                  str((meta.get("params") or {}).get("playerId")) == r["player_id"])
        rows.append({"season_label": season, "player_id": r["player_id"], "metric_name": "goals",
                     "raw_path": r["raw_path"], "rebuilt_value": value, "observed_value": r["value"],
                     "curated_value": curated, "raw_conflicts": len(conflicts), "status": "PASS" if passed else "FAIL"})
    return rows


def release() -> dict:
    checkpoint_path = REPORT / "execution05_checkpoint.json"
    if not checkpoint_path.exists():
        raise ValueError("Execution 05 acceptance checkpoint missing")
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    acceptance = checkpoint["season_acceptance"]
    for season in SEASONS:
        if not (REPORT / f"season_{season.replace('/', '_')}_acceptance.md").exists():
            raise ValueError(f"Missing season acceptance report: {season}")
    if set(acceptance) != set(SEASONS) or checkpoint["raw"]["accepted_tasks_without_valid_raw"]:
        raise ValueError("Critical raw integrity or season scope failure")
    if any(status in ("FAIL", "INCOMPLETE") for status in acceptance.values()):
        raise ValueError("Failed/incomplete season cannot enter six-season release")
    source_files = {name: IDENTITY / (name + ".parquet") for name in (
        "players", "teams", "seasons", "matches", "player_seasons", "player_team_seasons",
        "player_match_appearances", "historical_position_observations")}
    source_files["metric_observations"] = ROOT / "data/phase_02b1/statistics/metric_observations.parquet"
    source_files["player_season_metrics_wide"] = QUALITY / "player_season_metrics_wide.parquet"
    tables = {name: read(path) for name, path in source_files.items()}
    checks = referential(tables)
    csv_write(REPORT / "referential_integrity_report.csv", checks, list(checks[0]))
    if any(r["status"] != "PASS" for r in checks):
        raise ValueError("Critical referential integrity failure; release stopped")
    samples = reproduce_six_matches(tables)
    csv_write(REPORT / "execution06_reproducibility_samples.csv", samples, list(samples[0]))
    metric_samples = reproduce_six_metrics(tables)
    csv_write(REPORT / "execution06_metric_rebuild_samples.csv", metric_samples, list(metric_samples[0]))
    if any(r["status"] != "PASS" for r in samples + metric_samples):
        raise ValueError("Critical raw-to-normalized reproducibility failure")
    tests = run_test_suite(REPORT / "execution06_tests")
    if tests["exit_code"]:
        raise ValueError("Full automated tests failed; release stopped")
    # Stage into a sibling directory; publish only after every file is verified.
    stage = RELEASE.with_name(RELEASE.name + ".staging")
    if stage.exists():
        # A prior interrupted staging directory is retained for inspection.
        raise ValueError(f"Existing release staging directory requires review: {stage}")
    for name, source in source_files.items():
        folder = "curated" if name == "player_season_metrics_wide" else "normalized"
        dest = stage / folder / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        if sha(dest) != sha(source):
            raise ValueError(f"Release copy checksum mismatch: {name}")
    report_files = ["raw_integrity_report.csv", "normalization_report.csv", "source_lineage_report.csv",
                    "metric_reconciliation_report.csv", "batch_quality_report.csv", "player_population_quality.csv",
                    "cross_season_feature_coverage.csv", "collection_gap_report.csv", "data_quality_issue_tracker.csv",
                    "referential_integrity_report.csv", "execution06_reproducibility_samples.csv",
                    "execution06_metric_rebuild_samples.csv"]
    for name in report_files:
        dest = stage / "quality_reports" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPORT / name, dest)
    for name, source in (("collection_manifest.sqlite", ROOT / "data/phase_02b1/collection_manifest.sqlite"),
                         ("metric_dictionary_v3.csv", REPORT / "metric_dictionary_v3.csv")):
        dest = stage / "manifests" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    for season in SEASONS:
        source = REPORT / f"season_{season.replace('/', '_')}_acceptance.md"
        shutil.copyfile(source, stage / "quality_reports" / source.name)
    known_issues = [
        "16,314 substitute lineup entries have UNKNOWN participation; they are excluded from confirmed appearances.",
        "575 comparable source metric conflicts are preserved in long observations; curated cells are null.",
        "key_passes has no supported source values; missing values are never zero-filled.",
        "Historical broad position groups are inferred exact-code mappings; current profile position is CURRENT_ONLY.",
        "playerMatches historical paging remains unverified after prior HTTP 400; matchDetails is the verified fallback.",
        "12 legacy normalization/season acceptance gates remain PLANNED under the older absolute-participation contract."]
    table_manifest = []
    for name, source in source_files.items():
        folder = "curated" if name == "player_season_metrics_wide" else "normalized"
        dest = stage / folder / source.name
        table_manifest.append({"table": name, "path": f"{folder}/{source.name}", "rows": len(tables[name]),
                               "sha256": sha(dest), "schema_version": "2b1-v1"})
    manifest = {"dataset_version": "fotmob_epl_2019_2025_v2", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "FotMob unofficial JSON interface", "league_id": "47", "seasons": list(SEASONS),
                "season_acceptance": acceptance, "overall_verdict": "CONDITIONAL_GO",
                "tables": table_manifest, "raw_storage": "data/phase_02b1/raw; data/phase_02b0/raw; data/pilot/raw",
                "raw_integrity": checkpoint["raw"], "known_limitations": known_issues,
                "reproduce_commands": ["python -m src.collection.execution04_identity --max-requests 0",
                                       "python -m src.collection.execution05_acceptance",
                                       "python -m src.collection.execution06_release"],
                "test_command": tests["command"], "tests_run": tests["tests_run"], "test_exit_code": tests["exit_code"]}
    (stage / "metadata").mkdir(parents=True, exist_ok=True)
    atomic_write(stage / "metadata/release_manifest.json", json_bytes(manifest))
    dictionary = ["# Data dictionary", "", "All IDs are original FotMob identifiers stored as strings. Seasons are EPL season IDs, competition 47.", "",
                  "| Table | Grain | Meaning |", "|---|---|---|",
                  "| players | player_id | Profile snapshot; current_team_id and current_position are CURRENT_ONLY. |",
                  "| teams | season_id, team_id | Names observed in season fixture responses. |",
                  "| seasons | season_id | Six season labels and competition ID. |",
                  "| matches | match_id | Completed and cancelled fixtures, with status and source path. |",
                  "| player_seasons | season_id, player_id | APPEARED, UNKNOWN_PARTICIPATION, or UNUSED_SUBSTITUTE_ONLY. |",
                  "| player_team_seasons | season_id, player_id, team_id | Confirmed only from appearance links; other records UNRESOLVED. |",
                  "| player_match_appearances | match_id, player_id | STARTED, SUBSTITUTED_ON, UNUSED_SUBSTITUTE, UNKNOWN. |",
                  "| historical_position_observations | match_id, player_id, source_field | Exact raw position codes and Phase 2B.0 mapping status. |",
                  "| metric_observations | season_id, player_id, metric_name, source_endpoint, team_id, capture_id | Long-form original observations. |",
                  "| player_season_metrics_wide | season_id, player_id | m_ numeric metric and s_ status pairs; conflicts null. |", "",
                  "Units and aggregation semantics for all 53 metrics are in manifests/metric_dictionary_v3.csv. "
                  "A null numeric value must be read with its s_ status. No per-90, rating, or percentage aggregation is performed."]
    atomic_write(stage / "metadata/data_dictionary.md", ("\n".join(dictionary)+"\n").encode("utf-8"))
    er = ["# Entity relationships", "", "```mermaid", "erDiagram", "  PLAYERS ||--o{ PLAYER_SEASONS : has",
          "  SEASONS ||--o{ PLAYER_SEASONS : contains", "  SEASONS ||--o{ MATCHES : contains",
          "  TEAMS ||--o{ MATCHES : plays", "  PLAYER_SEASONS ||--o{ PLAYER_TEAM_SEASONS : has",
          "  PLAYER_SEASONS ||--o{ METRIC_OBSERVATIONS : has", "  MATCHES ||--o{ PLAYER_MATCH_APPEARANCES : has",
          "  PLAYERS ||--o{ PLAYER_MATCH_APPEARANCES : has", "```", "",
          "Player-season totals are stored once per player and season. Multi-club memberships remain separate rows."]
    atomic_write(stage / "metadata/entity_relationships.md", ("\n".join(er)+"\n").encode("utf-8"))
    atomic_write(stage / "metadata/known_issues.md", ("# Known issues\n\n" + "\n".join(f"- {x}" for x in known_issues)+"\n").encode("utf-8"))
    readme = ["# FotMob EPL 2019–2025 historical dataset, v2", "", "Verdict: **CONDITIONAL_GO**. Six seasons are included with conditional acceptance.", "",
              "Raw captures remain immutable in the repository data directories and are referenced by raw_path columns. "
              "normalized/ contains source-scoped entities; curated/ contains a convenience player-season table. "
              "Validated means identity, scope, checksum and relationships passed the available controls; it does not resolve UNKNOWN participation. "
              "The curated table retains one player-season row with explicit metric statuses and multi-club references.", "",
              "See metadata/data_dictionary.md, metadata/entity_relationships.md, metadata/known_issues.md, "
              "metadata/release_manifest.json, and quality_reports/ for evidence and limitations.", "",
              "## Reproduction", "", "From repository root: `python -m src.collection.execution04_identity --max-requests 0`, "
              "`python -m src.collection.execution05_acceptance`, then `python -m src.collection.execution06_release`. "
              "The last command checks the existing versioned release against the manifest on a repeat run. "
              "The full test command is `python -m unittest discover -s tests -v`.", "",
              "Collection methodology: leagues fixture index and completed matchDetails lineups establish historical appearances; "
              "playerData supplies current profile snapshot; playerStats supplies season-entry observations; "
              "leaderboards are comparison sources, not a complete player denominator. No Transfermarkt or ML data is included."]
    atomic_write(stage / "README.md", ("\n".join(readme)+"\n").encode("utf-8"))
    if RELEASE.exists():
        # Repeated execution is an integrity check, not an overwrite.
        existing = json.loads((RELEASE / "metadata/release_manifest.json").read_text(encoding="utf-8"))
        if {x["table"]: x["sha256"] for x in existing["tables"]} != {x["table"]: x["sha256"] for x in table_manifest}:
            raise ValueError("Existing release differs from regenerated table checksums")
        shutil.rmtree(stage)
    else:
        stage.rename(RELEASE)
    report = ["# Phase 2B.1 final acceptance", "", "## 1. Executive Summary", "",
              "CONDITIONAL_GO for the confirmed historical EPL appeared-player scope; all six seasons are CONDITIONAL_PASS.", "",
              "## 2. Collection Scope", "", "FotMob, EPL competition 47, seasons 2019/20–2024/25, Level 2+.", "",
              "## 3. Data Collection Architecture", "", "Immutable raw captures, SQLite manifest, versioned normalized tables, curated wide player-season table.", "",
              "## 4. Actual Data Collected", "", str({x['table']: x['rows'] for x in table_manifest}), "",
              "## 5. Coverage by Season", "", str(acceptance), "",
              "## 6. Historical Player Population", "", "3,262 confirmed appeared player-seasons; 586 uncertain-only and 204 unused-only season listings. 1,757 unique profile IDs.", "",
              "## 7. Statistics Availability", "", "53 canonical metrics, 207,043 long observations; key_passes unsupported. See cross_season_feature_coverage.csv.", "",
              "## 8. Player Profiles", "", "1,757/1,757 unique discovered IDs have ID-verified profile captures; current club/position remain current-only.", "",
              "## 9. Historical Team Membership", "", "3,323 confirmed relations, 812 unresolved, 61 multi-club player-seasons.", "",
              "## 10. Match Index", "", "2,280 completed league matches; abandoned Bournemouth–Luton 4193691 excluded, replay 4421797 included.", "",
              "## 11. Data Quality and Missingness", "", "16,314 UNKNOWN substitute listings, 7,290 UNUSED_SUBSTITUTE listings. Null metric cells retain explicit status.", "",
              "## 12. Historical Consistency", "", "Historical club and position evidence are match-scoped; inferred exact-code positions remain marked as such.", "",
              "## 13. Source Provenance", "", f"{checkpoint['raw']['verified_references']} raw references checksum verified; lineage paths preserved.", "",
              f"{checkpoint['raw']['semantic_rejected_references']} prior null playerStats attempts remain in raw storage but are excluded from accepted normalized lineage.", "",
              "## 14. Data Integrity", "", f"{len(checks)} referential/identity checks passed; {len(samples)} match and {len(metric_samples)} metric raw rebuild samples passed.", "",
              "## 15. Testing and Reproducibility", "", f"{tests['tests_run']} automated tests passed; exit code {tests['exit_code']}. See execution06_tests/test_execution.log.", "",
              "## 16. Remaining Issues", "", "\n".join(f"- {x}" for x in known_issues), "",
              "## 17. Dataset Release Contents", "", f"`{RELEASE.relative_to(ROOT).as_posix()}/` with normalized, curated, metadata, quality_reports and manifests.", "",
              "## 18. Final Acceptance Verdict", "", "CONDITIONAL_GO: confirmed core records and reproducibility checks passed; unresolved participation and source conflicts prevent unconditional GO.", "",
              "## 19. Handover Instructions", "", "Use the release manifest and data dictionary; filter APPEARED and confirmed links for participation analysis; inspect s_ metric statuses before numeric use. "
              "Run the three reproduction commands in README.md. Do not interpret current profile club/position as historical."]
    atomic_write(REPORT / "phase_02b1_final_acceptance.md", ("\n".join(report)+"\n").encode("utf-8"))
    result = {"verdict": "CONDITIONAL_GO", "season_acceptance": acceptance, "tables": table_manifest,
              "referential_checks": len(checks), "reproduction_samples": len(samples) + len(metric_samples), "tests": tests,
              "release_dir": RELEASE.relative_to(ROOT).as_posix()}
    atomic_write(REPORT / "execution06_checkpoint.json", json_bytes(result))
    return result


if __name__ == "__main__":
    print(json.dumps(release(), ensure_ascii=False))
