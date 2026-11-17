"""Prompt 02 Task A: build the five-season FotMob research release from frozen FotMob v3.1.

Method: every season-bearing table is a row filter of v3.1 on the official season_ids from the central scope.
FotMob builders key every value by season (BASELINE_AUDIT_REPORT section 4), so no value is recomputed per row.
Season totals, coverage, the metric dictionary's season counts, integrity checks and the manifest are rebuilt.
`players` keeps only players referenced by an in-scope season table. Raw captures are referenced, never copied.

The build happens in a temporary folder. It is validated, then promoted. An existing release with different content
is never overwritten.

Usage: python -I src/research_scope/build_fotmob_rs5.py
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.phase3.tm_common import FOTMOB_RELEASE, file_hash, verify_fotmob_unchanged  # noqa: E402
from src.research_scope.scope import ROOT, ScopeViolation, check_table, load_scope  # noqa: E402

VERSION = "fotmob_epl_2020_2025_rs5_v1"
RELEASE = ROOT / "data/releases" / VERSION
SOURCE = FOTMOB_RELEASE
# Table -> primary key, from the v3.1 schema contract (metadata/schema_definitions.md) and observed grains.
KEYS = {
    "normalized/players": ("player_id",), "normalized/seasons": ("season_id",), "normalized/teams": ("season_id", "team_id"), "normalized/matches": ("match_id",),
    "normalized/player_seasons": ("season_id", "player_id"), "normalized/complete_player_season_classification": ("season_id", "player_id"),
    "normalized/confirmed_appeared_player_seasons": ("season_id", "player_id"), "normalized/confirmed_non_appeared_player_seasons": ("season_id", "player_id"),
    "normalized/unverified_player_seasons": ("season_id", "player_id"), "normalized/player_team_seasons": ("season_id", "player_id", "team_id"),
    "normalized/player_match_appearances": ("match_id", "player_id"), "normalized/substitution_evidence_registry": ("match_id", "player_id"),
    "normalized/historical_position_observations": None, "normalized/metric_observations": None,
    "curated/confirmed_appeared_player_seasons": ("season_id", "player_id"), "curated/player_season_metrics_wide": ("season_id", "player_id"),
}
ROW_LEVEL_CSV = ("quality_reports/metric_reconciliation_report.csv", "quality_reports/raw_integrity_report.csv", "quality_reports/cross_season_feature_coverage.csv",
                 "quality_reports/historical_xg_xa_coverage_quality.csv", "quality_reports/population_reconciliation.csv", "quality_reports/appearance_coverage.csv",
                 "manifests/metric_eligibility_registry.csv")
COPIED = ("manifests/metric_reconciliation_registry_v3.json",)
REFERENCED = ("manifests/collection_manifest.sqlite",)


def filter_csv(src: Path, dst: Path, labels: set[str]) -> dict:
    """Keep the header and in-scope rows. Each kept line is written back byte-for-byte."""
    data = src.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    trailing = lines[-1] == ""
    body = lines[:-1] if trailing else lines
    header = next(csv.reader([body[0]]))
    column = header.index("season_label")
    kept, dropped, records, current = [body[0]], Counter(), [], []
    # A quoted field may hold a newline, so lines are grouped into full CSV records first.
    for line in body[1:]:
        current.append(line)
        joined = newline.join(current)
        if joined.count('"') % 2 == 0:
            records.append(joined)
            current = []
    if current:
        raise ScopeViolation(f"{src.name}: unterminated quoted field")
    for record in records:
        season = next(csv.reader(io.StringIO(record)))[column]
        if season in labels:
            kept.append(record)
        else:
            dropped[season] += 1
    out = newline.join(kept) + (newline if trailing else "")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
    return {"rows_in": len(records), "rows_out": len(kept) - 1, "dropped_by_season": dict(dropped)}


def build(out: Path) -> dict:
    scope = load_scope()
    ids = pa.array(list(scope.season_ids), pa.string())
    con = duckdb.connect(":memory:")
    log: dict = {"tables": {}, "csv": {}}
    season_tables = {}
    for rel in KEYS:
        if rel == "normalized/players":
            continue
        table = pq.read_table(SOURCE / f"{rel}.parquet")
        filtered = table.filter(pc.is_in(table["season_id"], value_set=ids))
        season_tables[rel] = filtered
        log["tables"][rel] = {"rows_in": table.num_rows, "rows_out": filtered.num_rows}
    referenced = set()
    for rel, table in season_tables.items():
        if "player_id" in table.column_names:
            referenced.update(table["player_id"].to_pylist())
    players = pq.read_table(SOURCE / "normalized/players.parquet")
    season_tables["normalized/players"] = players.filter(pc.is_in(players["player_id"], value_set=pa.array(sorted(referenced), pa.string())))
    log["tables"]["normalized/players"] = {"rows_in": players.num_rows, "rows_out": season_tables["normalized/players"].num_rows}
    for rel, table in season_tables.items():
        path = out / f"{rel}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path, compression="zstd")
        con.execute(f"CREATE VIEW {rel.replace('/', '__')} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    for rel in ROW_LEVEL_CSV:
        log["csv"][rel] = filter_csv(SOURCE / rel, out / rel, set(scope.labels))
    for rel in COPIED:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / rel, out / rel)
    labels = set(scope.labels)
    for name in sorted((SOURCE / "quality_reports").glob("season_*_acceptance.md")):
        label = name.stem.replace("season_", "").replace("_acceptance", "").replace("_", "/")
        if label in labels:
            shutil.copy2(name, out / "quality_reports" / name.name)
    log["validation"] = validate(con, scope, out)
    log["recalculated"] = recalculate(con, scope, out)
    write_dictionary(con, scope, out)
    return log


def validate(con, scope, out: Path) -> dict:
    """Stop the build on any scope, key, schema, value or referential failure."""
    results = {}
    for rel, key in KEYS.items():
        view = rel.replace("/", "__")
        cols = [r[0] for r in con.execute(f"DESCRIBE {view}").fetchall()]
        if rel != "normalized/players":
            results[f"{rel}:scope"] = check_table(con, view, scope, "season_label" if "season_label" in cols else None, "season_id",
                                                  require_all=rel != "normalized/confirmed_non_appeared_player_seasons", where=rel)
        if key:
            dup = con.execute(f"SELECT count(*) FROM (SELECT {', '.join(key)} FROM {view} GROUP BY ALL HAVING count(*)>1)").fetchone()[0]
            nulls = con.execute(f"SELECT count(*) FROM {view} WHERE " + " OR ".join(f"{k} IS NULL" for k in key)).fetchone()[0]
            if dup or nulls:
                raise ScopeViolation(f"{rel}: primary key {key} has {dup} duplicates and {nulls} nulls")
        # Same schema, and every rs5 row is an unchanged v3.1 row (EXCEPT ALL in both directions over the in-scope slice).
        source = f"read_parquet('{(SOURCE / (rel + '.parquet')).as_posix()}')"
        if pq.read_schema(SOURCE / f"{rel}.parquet").remove_metadata() != pq.read_schema(out / f"{rel}.parquet").remove_metadata():
            raise ScopeViolation(f"{rel}: schema differs from v3.1")
        scoped = f"(SELECT * FROM {source} WHERE season_id IN ({scope.sql_ids()}))" if rel != "normalized/players" else f"(SELECT * FROM {source} WHERE player_id IN (SELECT player_id FROM {view}))"
        diff = con.execute(f"SELECT (SELECT count(*) FROM (SELECT * FROM {view} EXCEPT ALL SELECT * FROM {scoped})) + (SELECT count(*) FROM (SELECT * FROM {scoped} EXCEPT ALL SELECT * FROM {view}))").fetchone()[0]
        if diff:
            raise ScopeViolation(f"{rel}: {diff} rows differ from the in-scope v3.1 slice")
        results[f"{rel}:rows_equal_v3_1_slice"] = True
    checks = {
        "player_seasons -> players": "SELECT count(*) FROM normalized__player_seasons ANTI JOIN normalized__players USING (player_id)",
        "player_match_appearances -> matches": "SELECT count(*) FROM normalized__player_match_appearances ANTI JOIN normalized__matches USING (match_id)",
        "player_match_appearances -> player_seasons": "SELECT count(*) FROM normalized__player_match_appearances ANTI JOIN normalized__player_seasons USING (season_id, player_id)",
        "player_team_seasons -> teams": "SELECT count(*) FROM normalized__player_team_seasons ANTI JOIN normalized__teams USING (season_id, team_id)",
        "player_team_seasons -> player_seasons": "SELECT count(*) FROM normalized__player_team_seasons ANTI JOIN normalized__player_seasons USING (season_id, player_id)",
        "matches -> teams (home)": "SELECT count(*) FROM normalized__matches m ANTI JOIN normalized__teams t ON t.season_id=m.season_id AND t.team_id=m.home_team_id",
        "matches -> teams (away)": "SELECT count(*) FROM normalized__matches m ANTI JOIN normalized__teams t ON t.season_id=m.season_id AND t.team_id=m.away_team_id",
        "metric_observations -> player_seasons": "SELECT count(*) FROM normalized__metric_observations ANTI JOIN normalized__player_seasons USING (season_id, player_id)",
        "position_observations -> matches": "SELECT count(*) FROM normalized__historical_position_observations ANTI JOIN normalized__matches USING (match_id)",
        "confirmed (normalized) = curated confirmed keys": "SELECT count(*) FROM (SELECT season_id, player_id FROM normalized__confirmed_appeared_player_seasons EXCEPT SELECT season_id, player_id FROM curated__confirmed_appeared_player_seasons) UNION ALL SELECT count(*) FROM (SELECT season_id, player_id FROM curated__confirmed_appeared_player_seasons EXCEPT SELECT season_id, player_id FROM normalized__confirmed_appeared_player_seasons)",
        "confirmed + unverified = player_seasons": "SELECT abs((SELECT count(*) FROM normalized__player_seasons) - (SELECT count(*) FROM normalized__confirmed_appeared_player_seasons) - (SELECT count(*) FROM normalized__unverified_player_seasons) - (SELECT count(*) FROM normalized__confirmed_non_appeared_player_seasons))",
        "players without any in-scope row": "SELECT count(*) FROM normalized__players ANTI JOIN normalized__player_seasons USING (player_id) ANTI JOIN normalized__player_match_appearances USING (player_id)",
    }
    integrity = []
    for name, sql in checks.items():
        failures = sum(r[0] for r in con.execute(sql).fetchall())
        integrity.append({"check": name, "status": "PASS" if failures == 0 else "FAIL", "failures": failures})
    write_rows(out / "quality_reports/referential_integrity_report_rs5.csv", integrity)
    if any(r["status"] == "FAIL" for r in integrity):
        raise ScopeViolation(f"Referential integrity failed: {[r for r in integrity if r['status'] == 'FAIL']}")
    results["referential_integrity_checks"] = len(integrity)
    return results


def recalculate(con, scope, out: Path) -> dict:
    """Season totals, recomputed from the rs5 tables, then compared with the filtered historical per-season rows."""
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    population, appearance = [], []
    for s in scope.seasons:
        sid = s.season_id
        n = lambda sql: q(sql.format(sid=sid))[0][0]  # noqa: E731
        population.append({"season_label": s.season, "season_id": sid, "completed_matches": n("SELECT count(*) FROM normalized__matches WHERE season_id='{sid}' AND match_status='COMPLETED'"),
                           "non_completed_matches": n("SELECT count(*) FROM normalized__matches WHERE season_id='{sid}' AND match_status<>'COMPLETED'"),
                           "player_seasons": n("SELECT count(*) FROM normalized__player_seasons WHERE season_id='{sid}'"), "confirmed_appeared": n("SELECT count(*) FROM normalized__confirmed_appeared_player_seasons WHERE season_id='{sid}'"),
                           "confirmed_non_appeared": n("SELECT count(*) FROM normalized__confirmed_non_appeared_player_seasons WHERE season_id='{sid}'"), "unverified": n("SELECT count(*) FROM normalized__unverified_player_seasons WHERE season_id='{sid}'"),
                           "unknown_player_matches": n("SELECT count(*) FROM normalized__player_match_appearances WHERE season_id='{sid}' AND participation_status='UNKNOWN'"),
                           "distinct_confirmed_players": n("SELECT count(DISTINCT player_id) FROM normalized__confirmed_appeared_player_seasons WHERE season_id='{sid}'")})
        status = dict(q(f"SELECT participation_status, count(*) FROM normalized__player_match_appearances WHERE season_id='{sid}' GROUP BY 1"))
        total = sum(status.values())
        appearance.append({"season_label": s.season, "season_id": sid, "total_player_match_records": total, "started_count": status.get("STARTED", 0), "substituted_on_count": status.get("SUBSTITUTED_ON", 0),
                           "unknown_count": status.get("UNKNOWN", 0), "other_status_count": total - sum(status.get(k, 0) for k in ("STARTED", "SUBSTITUTED_ON", "UNKNOWN")),
                           "appeared_ratio_pct": round(100 * (status.get("STARTED", 0) + status.get("SUBSTITUTED_ON", 0)) / total, 2)})
    for rows, keys in ((population, ("completed_matches", "player_seasons", "confirmed_appeared", "confirmed_non_appeared", "unverified", "unknown_player_matches", "non_completed_matches", "distinct_confirmed_players")),
                       (appearance, ("total_player_match_records", "started_count", "substituted_on_count", "unknown_count", "other_status_count"))):
        rows.append({"season_label": "TOTAL_RS5", "season_id": "", **{k: sum(r[k] for r in rows) for k in keys}, **({"appeared_ratio_pct": round(100 * sum(r["started_count"] + r["substituted_on_count"] for r in rows) / sum(r["total_player_match_records"] for r in rows), 2)} if rows is appearance else {})})
    population[-1]["distinct_confirmed_players"] = q("SELECT count(DISTINCT player_id) FROM normalized__confirmed_appeared_player_seasons")[0][0]
    write_rows(out / "quality_reports/population_reconciliation_rs5.csv", population)
    write_rows(out / "quality_reports/appearance_coverage_rs5.csv", appearance)
    # Cross-check with the historical per-season rows (same seasons, independently computed by the v3.1 builder).
    historical = {r[0]: r for r in q(f"SELECT season_label, completed_matches, player_seasons, confirmed_appeared, confirmed_non_appeared, unverified, unknown_player_matches FROM read_csv('{(out / 'quality_reports/population_reconciliation.csv').as_posix()}', all_varchar=true)")}
    mismatches = [r["season_label"] for r in population[:-1] if tuple(str(r[k]) for k in ("completed_matches", "player_seasons", "confirmed_appeared", "confirmed_non_appeared", "unverified", "unknown_player_matches")) != historical[r["season_label"]][1:]]
    if mismatches:
        raise ScopeViolation(f"Recomputed season totals disagree with v3.1 for {mismatches}")
    # Metric coverage over the five seasons (from the per-season rows the v3.1 builder produced).
    cov = q(f"""SELECT metric_name, count(*) seasons, sum(valid_values::INT) valid, sum(eligible_players::INT) eligible, sum(missing::INT) missing, sum(unsupported::INT) unsupported, sum(conflicting::INT) conflicting,
                count(*) FILTER (WHERE valid_values::INT>0) seasons_with_values, string_agg(DISTINCT coverage_status, '|' ORDER BY coverage_status) statuses
                FROM read_csv('{(out / 'quality_reports/cross_season_feature_coverage.csv').as_posix()}', all_varchar=true) GROUP BY 1 ORDER BY 1""")
    summary = [{"metric_name": m, "seasons_in_scope": n, "seasons_with_values": w, "valid_values": v, "eligible_player_seasons": e, "coverage_fraction_rs5": round(v / e, 6) if e else None,
                "missing": mi, "unsupported": u, "conflicting": c, "coverage_statuses": st} for m, n, v, e, mi, u, c, w, st in cov]
    write_rows(out / "quality_reports/metric_coverage_summary_rs5.csv", summary)
    conflicts = q(f"SELECT season_label, curated_resolved_status, count(*) FROM read_csv('{(out / 'quality_reports/metric_reconciliation_report.csv').as_posix()}', all_varchar=true) GROUP BY ALL ORDER BY ALL")
    wide_cols = [r[0] for r in q("DESCRIBE curated__confirmed_appeared_player_seasons")]
    s_cols = [c for c in wide_cols if c.startswith("s_")]
    status_counts = Counter()
    for c in s_cols:
        for value, count in q(f'SELECT "{c}", count(*) FROM curated__confirmed_appeared_player_seasons GROUP BY 1'):
            status_counts[value] += count
    summary_json = {"dataset_version": VERSION, "scope_id": scope.scope_id, "population_by_season": population, "appearance_by_season": appearance,
                    "metric_conflicts_by_season_status": [{"season_label": a, "curated_resolved_status": b, "rows": n} for a, b, n in conflicts],
                    "open_metric_conflicts": sum(n for _, b, n in conflicts if b == "CONFLICTING"), "curated_confirmed_status_cells": dict(sorted(status_counts.items())),
                    "metric_observation_status": dict(q("SELECT metric_status, count(*) FROM normalized__metric_observations GROUP BY 1 ORDER BY 1")),
                    "metrics_without_any_value_in_scope": [r["metric_name"] for r in summary if r["seasons_with_values"] == 0]}
    (out / "metadata").mkdir(parents=True, exist_ok=True)
    (out / "metadata/canonical_summary_rs5.json").write_text(json.dumps(summary_json, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"population_total": population[-1], "open_metric_conflicts": summary_json["open_metric_conflicts"], "metrics_without_values": summary_json["metrics_without_any_value_in_scope"]}


def write_dictionary(con, scope, out: Path) -> None:
    """Definitions are reused unchanged; season-count columns are recomputed for the rs5 seasons."""
    with (SOURCE / "manifests/metric_dictionary_v3.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seasons_with = defaultdict(int)
    for metric, n in con.execute(f"""SELECT metric_name, count(*) FILTER (WHERE valid_values::INT>0) FROM read_csv('{(out / 'quality_reports/cross_season_feature_coverage.csv').as_posix()}', all_varchar=true) GROUP BY 1""").fetchall():
        seasons_with[metric] = n
    dropped = ("historical_seasons_with_values", "sample_available", "sample_missing", "sample_not_applicable", "sample_unsupported")
    result = []
    for r in rows:
        kept = {k: v for k, v in r.items() if k not in dropped}
        kept["rs5_seasons_with_values"] = seasons_with.get(r["normalized_field"], 0)
        kept["rs5_seasons_in_scope"] = len(scope.labels)
        result.append(kept)
    write_rows(out / "manifests/metric_dictionary_rs5.csv", result)
    # Column dictionary for every rs5 table.
    entries = []
    for rel in KEYS:
        for field in pq.read_schema(out / f"{rel}.parquet"):
            entries.append({"table": rel, "column": field.name, "type": str(field.type), "primary_key": field.name in (KEYS[rel] or ()), "origin": "unchanged from fotmob_epl_2019_2025_v3_1"})
    write_rows(out / "metadata/data_dictionary_rs5.csv", entries)


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def content_hashes(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): file_hash(p) for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "release_manifest.json"}


def write_manifest(folder: Path, log: dict, fotmob: dict) -> None:
    scope = load_scope()
    con = duckdb.connect()
    files = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name == "release_manifest.json":
            continue
        rel = path.relative_to(folder).as_posix()
        entry = {"path": rel, "bytes": path.stat().st_size, "sha256": file_hash(path)}
        if path.suffix == ".parquet":
            relation = f"read_parquet('{path.as_posix()}')"
            entry["rows"] = con.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()]
            if "season_id" in cols:
                entry["rows_by_season_id"] = dict(con.execute(f"SELECT season_id, count(*) FROM {relation} GROUP BY 1 ORDER BY 1").fetchall())
            entry["columns"] = len(cols)
        files.append(entry)
    source_manifest = SOURCE / "metadata/release_manifest.json"
    manifest = {
        "dataset_version": VERSION, "parent_release_version": "fotmob_epl_2019_2025_v3_1", "scope_id": scope.scope_id, "scope_config_sha256": file_hash(ROOT / "configs/research_scope.yaml"),
        "decision": "D9: five seasons 2020/21-2024/25; 2019/20 excluded", "research_objective": "A (D6)", "seasons": list(scope.labels), "season_ids": list(scope.season_ids), "excluded_seasons": list(scope.excluded_labels),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "method": "Season row filter of v3.1; rows verified equal to the in-scope v3.1 slice; totals, coverage, integrity and dictionary season counts recomputed",
        "quality_status": "CONDITIONAL_GO (inherited from v3.1: UNKNOWN bench participation and unverified metric windows remain)",
        "source": {"release": "data/releases/fotmob_epl_2019_2025_v3_1", "release_manifest_sha256": file_hash(source_manifest), "fotmob_preflight": fotmob,
                   "referenced_not_copied": {r: {"path": f"data/releases/fotmob_epl_2019_2025_v3_1/{r}", "sha256": file_hash(SOURCE / r), "note": "Crawl log covering all six seasons; kept outside the rs5 release"} for r in REFERENCED},
                   "raw_captures": "Referenced by raw_path columns; not copied or modified"},
        "code_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in (ROOT / "src/research_scope/build_fotmob_rs5.py", ROOT / "src/research_scope/scope.py", ROOT / "src/phase3/tm_common.py")},
        "environment": {"python": sys.version.split()[0], "duckdb": duckdb.__version__, "pyarrow": pa.__version__},
        "build_log": log, "inventory_policy": "Every file is checksummed except this manifest, whose self-hash would be circular.", "files": files,
        "reproduction": "python -I src/research_scope/build_fotmob_rs5.py (rebuilds in a temporary folder and refuses to overwrite different content)",
    }
    (folder / "metadata/release_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_readme(folder: Path, log: dict) -> None:
    scope = load_scope()
    pop = json.loads((folder / "metadata/canonical_summary_rs5.json").read_text(encoding="utf-8"))["population_by_season"]
    lines = [f"# FotMob EPL research release `{VERSION}`", "", "Parent: `fotmob_epl_2019_2025_v3_1` (unchanged). Scope: `" + scope.scope_id + "` (D9), seasons " + ", ".join(scope.labels) + ". 2019/20 is excluded.", "",
             "Every table is a season filter of v3.1; each row is verified identical to v3.1. Totals and coverage were recomputed. Inherited verdict: CONDITIONAL_GO.", "",
             "| Season | Completed matches | Confirmed appeared | Unverified | Unknown player-matches |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {r['season_label']} | {r['completed_matches']} | {r['confirmed_appeared']} | {r['unverified']} | {r['unknown_player_matches']} |" for r in pop]
    lines += ["", "Files and hashes: `metadata/release_manifest.json`. Columns: `metadata/data_dictionary_rs5.csv`. Rebuild: `python -I src/research_scope/build_fotmob_rs5.py`."]
    (folder / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    fotmob = verify_fotmob_unchanged()
    temp = RELEASE.parent / f"_build_{uuid.uuid4().hex}"
    try:
        log = build(temp)
        write_readme(temp, log)
        if RELEASE.exists():
            if content_hashes(RELEASE) != content_hashes(temp):
                print(f"STOP: {RELEASE} exists with different content; not overwritten.")
                return 2
            print("Existing release has identical content; manifest kept.")
        else:
            write_manifest(temp, log, fotmob)
            shutil.move(str(temp), str(RELEASE))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    print(json.dumps(log["recalculated"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
