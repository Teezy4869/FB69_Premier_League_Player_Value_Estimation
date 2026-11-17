"""Prompt 01 evidence: measure how every relevant historical artifact depends on seasons. Read-only.

Writes, under <out_dir>:
  artifact_season_profile.csv   one row per data artifact: rows, season columns, rows per season, 2019/20 rows
  hardcoded_season_scan.csv     every line in src/, configs/, tests/ that hard-codes a season or a six-season assumption
  population_preview.json       what the five-season population will contain (counts only, no data written)

Usage: python -I src/research_scope/audit_baseline.py <out_dir>
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402

from src.research_scope.scope import ROOT, load_scope  # noqa: E402

ARTIFACT_ROOTS = ["data/releases/fotmob_epl_2019_2025_v3_1", "data/transfermarkt/curated/tm_r2_20260905", "data/transfermarkt/staging/tm_r2_20260905",
                  "data/phase_03/entity_resolution/matching_v2_1__reviews_none", "data/phase_03/targets/target_v1__matching_v2_1",
                  "reports/phase_03/step_04/audit_4_1/evidence", "data/releases/fb69_player_season_integrated_v1"]
SEASON_COLUMNS = ("season_label", "season", "season_id", "season_start_year")
SCAN_DIRS = ("src", "configs", "tests")
PATTERNS = [
    ("season_2019_label", re.compile(r"2019/(20)?20|2019_2020|2019/20\b")),
    ("hardcoded_tm_year_range", re.compile(r"BETWEEN 20\d\d AND 20\d\d")),
    ("research_window_date_2019", re.compile(r"'2019-0[78]-\d\d'|\"2019-0[78]-\d\d\"")),
    ("six_season_count", re.compile(r"\b(EXPECTED_ROWS|EXPECTED_PLAYERS)\s*=|== *(3262|1343|3195|67)\b|\b(3262|3195|1343)\b")),
    ("release_name_2019_2025", re.compile(r"fotmob_epl_2019_2025")),
    ("batch_2020_04_08", re.compile(r"2020[-_]04[-_]08")),
]


def profile_artifacts(con, scope) -> list[dict]:
    excluded_keys = {*scope.excluded_labels, *scope.excluded_ids, *map(str, scope.excluded_tm_years)}
    rows = []
    for root in ARTIFACT_ROOTS:
        for path in sorted((ROOT / root).rglob("*.parquet")):
            rel = path.relative_to(ROOT).as_posix()
            relation = f"read_parquet('{path.as_posix()}')"
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()]
            n = con.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]
            season_cols = [c for c in SEASON_COLUMNS if c in cols]
            by_season, excluded_rows = {}, None
            if season_cols:
                col = season_cols[0]
                by_season = {str(k): v for k, v in con.execute(f'SELECT "{col}", count(*) FROM {relation} GROUP BY 1 ORDER BY 1').fetchall()}
                excluded_rows = sum(v for k, v in by_season.items() if k in excluded_keys)
            rows.append({"artifact": rel, "rows": n, "columns": len(cols), "season_columns": "|".join(season_cols), "rows_by_season": json.dumps(by_season, ensure_ascii=False),
                         "rows_in_excluded_seasons": excluded_rows if season_cols else "", "season_dependency": "SEASON_GRAIN" if season_cols else "NO_SEASON_COLUMN"})
    return rows


def scan_code(scope) -> list[dict]:
    found = []
    patterns = PATTERNS + [("excluded_season_id", re.compile("|".join(f"(?<![0-9]){i}(?![0-9])" for i in scope.excluded_ids)))]
    for folder in SCAN_DIRS:
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix not in (".py", ".yaml", ".yml", ".json"):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(("src/research_scope/", "tests/research_scope/")) or rel == "configs/research_scope.yaml":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for name, pattern in patterns:
                    if pattern.search(line):
                        found.append({"file": rel, "line": number, "pattern": name, "area": rel.split("/")[1] if rel.startswith(("src/", "tests/")) else "configs", "text": line.strip()[:200]})
    return found


def population_preview(con, scope) -> dict:
    fm = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1/normalized"
    integrated = ROOT / "data/releases/fb69_player_season_integrated_v1/player_season_integrated_v1.parquet"
    conf = f"read_parquet('{(fm / 'confirmed_appeared_player_seasons.parquet').as_posix()}')"
    data = f"read_parquet('{integrated.as_posix()}')"
    labels = scope.sql_labels()
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    return {
        "scope_id": scope.scope_id, "official_seasons": list(scope.labels), "excluded_seasons": list(scope.excluded_labels),
        "confirmed_rows_by_season_in_scope": dict(q(f"SELECT season_label, count(*) FROM {conf} WHERE season_label IN ({labels}) GROUP BY 1 ORDER BY 1")),
        "confirmed_rows_in_scope": q(f"SELECT count(*) FROM {conf} WHERE season_label IN ({labels})")[0][0],
        "players_in_scope": q(f"SELECT count(DISTINCT player_id) FROM {conf} WHERE season_label IN ({labels})")[0][0],
        "players_only_in_excluded_seasons": q(f"SELECT count(DISTINCT player_id) FROM {conf} WHERE player_id NOT IN (SELECT player_id FROM {conf} WHERE season_label IN ({labels}))")[0][0],
        "players_in_both": q(f"SELECT count(DISTINCT player_id) FROM {conf} WHERE season_label NOT IN ({labels}) AND player_id IN (SELECT player_id FROM {conf} WHERE season_label IN ({labels}))")[0][0],
        "historical_integrated_in_scope_preview": {
            "rows": q(f"SELECT count(*) FROM {data} WHERE season IN ({labels})")[0][0],
            "usable_targets": q(f"SELECT count(*) FROM {data} WHERE season IN ({labels}) AND target_usable")[0][0],
            "missing_targets": q(f"SELECT count(*) FROM {data} WHERE season IN ({labels}) AND NOT target_usable")[0][0],
            "unmapped_rows": q(f"SELECT count(*) FROM {data} WHERE season IN ({labels}) AND transfermarkt_player_id IS NULL")[0][0],
            "players_by_crosswalk_status": dict(q(f"SELECT crosswalk_status, count(DISTINCT canonical_player_id) FROM {data} WHERE season IN ({labels}) GROUP BY 1 ORDER BY 1")),
            "batch_2020_04_08_rows_in_scope": q(f"SELECT count(*) FROM {data} WHERE season IN ({labels}) AND target_on_2020_04_08_batch")[0][0],
        },
        "note": "Preview from historical files filtered in memory. It is a reconciliation expectation, not a research output.",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    scope = load_scope()
    con = duckdb.connect()
    artifacts = profile_artifacts(con, scope)
    write_csv(out / "artifact_season_profile.csv", artifacts)
    scan = scan_code(scope)
    write_csv(out / "hardcoded_season_scan.csv", scan)
    preview = population_preview(con, scope)
    (out / "population_preview.json").write_text(json.dumps(preview, indent=1, default=str) + "\n", encoding="utf-8")
    by_file: dict[str, int] = {}
    for r in scan:
        by_file[r["file"]] = by_file.get(r["file"], 0) + 1
    print(json.dumps({"artifacts_profiled": len(artifacts), "hardcoded_hits": len(scan), "files_with_hits": len(by_file), "preview": preview}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
