"""Prompt 03 Task D: validation and reconciliation of the rs5 crosswalk and integrated dataset. Read-only.

`integration_checks()` returns PASS/FAIL rows with observed values; tests and reports both call it.
`integration_statistics()` returns the counts the reports quote.

Usage: python -I src/research_scope/validate_rs5.py <out.json>
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402

from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.integrate_rs5 import CROSSWALK, DATASET_VERSION, RELEASE, TARGET, column_role  # noqa: E402
from src.research_scope.scope import ROOT, ScopeViolation, check_table, load_scope  # noqa: E402

DATASET = RELEASE / f"{DATASET_VERSION}.parquet"
EVIDENCE = RELEASE / "player_team_season_evidence.parquet"
V1 = ROOT / "data/releases/fb69_player_season_integrated_v1/player_season_integrated_v1.parquet"
TM_PLAYERS = ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_players.parquet"
IDENTITY_OR_PROVENANCE = ("identity_evidence_tier", "crosswalk_method", "matching_version", "dataset_version", "fotmob_source_version")


def connect():
    con = duckdb.connect()
    for alias, path in {"d": DATASET, "e": EVIDENCE, "cw": CROSSWALK, "t": TARGET, "tp": TM_PLAYERS, "cur": FOTMOB_RS5 / "curated/confirmed_appeared_player_seasons.parquet",
                        "pts": FOTMOB_RS5 / "normalized/player_team_seasons.parquet", "v1": V1}.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    return con


def integration_checks(con=None) -> list[dict]:
    con = con or connect()
    scope = load_scope()
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    checks = []

    def add(name, ok, observed=None):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "observed": observed})

    try:
        per_season = check_table(con, "d", scope, "season", "season_id", where="integrated")["season"]
        add("five-season whitelist (all official seasons present, nothing else)", True, per_season)
    except ScopeViolation as error:
        add("five-season whitelist (all official seasons present, nothing else)", False, str(error))
    excluded = " OR ".join([f"season='{s}'" for s in scope.excluded_labels] + [f"season_id='{s}'" for s in scope.excluded_ids])
    add("excluded season rejected (0 rows by label or id)", one(f"SELECT count(*) FROM d WHERE {excluded}") == 0, one(f"SELECT count(*) FROM d WHERE {excluded}"))
    add("excluded season absent from club evidence", one(f"SELECT count(*) FROM e WHERE season IN ({', '.join(repr(s) for s in scope.excluded_labels)})") == 0)
    add("no 2019/20 flag columns remain", not ({"sensitivity_season_2019_20", "xg_xa_unavailable_for_comparison", "target_on_2020_04_08_batch"} & {r[0] for r in con.execute("DESCRIBE d").fetchall()}))
    add("player-season uniqueness", one("SELECT count(*) FROM (SELECT canonical_player_id, season FROM d GROUP BY ALL HAVING count(*)>1)") == 0)
    add("record count reconciles with rs5 Confirmed population", one("SELECT count(*) FROM d") == one("SELECT count(*) FROM cur") and one("SELECT count(*) FROM (SELECT player_id, season_id FROM cur EXCEPT SELECT fotmob_player_id, season_id FROM d)") == 0, one("SELECT count(*) FROM d"))
    add("per-season counts reconcile", con.execute("SELECT season, count(*) FROM d GROUP BY 1 ORDER BY 1").fetchall() == con.execute("SELECT season_label, count(*) FROM cur GROUP BY 1 ORDER BY 1").fetchall())
    add("canonical id derives from FotMob id", one("SELECT count(*) FROM d WHERE canonical_player_id <> 'fb69p_' || fotmob_player_id") == 0)
    add("one Transfermarkt id per player across seasons", one("SELECT count(*) FROM (SELECT canonical_player_id FROM d GROUP BY 1 HAVING count(DISTINCT transfermarkt_player_id) > 1)") == 0)
    add("one player per Transfermarkt id (no many-to-one)", one("SELECT count(*) FROM (SELECT transfermarkt_player_id FROM d WHERE transfermarkt_player_id IS NOT NULL GROUP BY 1 HAVING count(DISTINCT canonical_player_id) > 1)") == 0)
    add("dataset identity equals crosswalk", one("SELECT count(*) FROM d JOIN cw ON cw.fotmob_player_id=d.fotmob_player_id WHERE d.transfermarkt_player_id IS DISTINCT FROM cw.transfermarkt_player_id OR d.crosswalk_status<>cw.match_status OR d.canonical_player_id<>cw.canonical_player_id") == 0)
    add("every crosswalk identity appears in the dataset", one("SELECT count(*) FROM cw ANTI JOIN d USING (fotmob_player_id)") == 0)
    add("Transfermarkt ids exist (referential integrity)", one("SELECT count(*) FROM d ANTI JOIN tp ON tp.tm_player_id=d.transfermarkt_player_id WHERE d.transfermarkt_player_id IS NOT NULL") == 0)
    add("unmapped rows carry an unresolved status", one("SELECT count(*) FROM d WHERE transfermarkt_player_id IS NULL AND (crosswalk_status IN ('AUTO_EXACT','AUTO_ADJUDICATED','MANUAL_CONFIRMED') OR identity_match_status<>'UNRESOLVED_NO_MAPPING')") == 0)
    target_cols = {"target_market_value": "market_value", "target_currency": "currency", "target_valuation_date": "selected_valuation_date", "target_season_end_date": "season_end_date", "target_valuation_age_days": "valuation_age_days",
                   "target_status": "target_status", "target_missing_reason": "target_missing_reason", "target_source_record_reference": "source_record_reference", "identity_evidence_tier": "identity_evidence_tier"}
    cond = " OR ".join(f"d.{a} IS DISTINCT FROM t.{b}" for a, b in target_cols.items())
    add("target uniqueness and equality with the target table", one("SELECT count(*) FROM (SELECT fotmob_player_id, season FROM t GROUP BY ALL HAVING count(*)>1)") == 0 and one(f"SELECT count(*) FROM d JOIN t ON t.fotmob_player_id=d.fotmob_player_id AND t.season=d.season WHERE {cond}") == 0)
    add("missing target handling: null value iff not usable, with a reason", one("SELECT count(*) FROM d WHERE (target_market_value IS NULL) <> (NOT target_usable) OR (NOT target_usable AND target_missing_reason IS NULL)") == 0, one("SELECT count(*) FROM d WHERE NOT target_usable"))
    add("no valuation after cutoff", one("SELECT count(*) FROM d WHERE target_valuation_date > target_season_end_date") == 0)
    cols = [r[0] for r in con.execute("DESCRIBE d").fetchall()]
    metric = [c for c in cols if c.startswith("m_") or c.startswith("s_")]
    sel = ", ".join(f'"{c}"' for c in metric)
    add("features unchanged from FotMob rs5 (feature-target separation)", one(f"SELECT count(*) FROM (SELECT player_id, season_id, {sel} FROM cur EXCEPT ALL SELECT fotmob_player_id, season_id, {sel} FROM d)") == 0, len(metric))
    add("missingness preserved: null metric cells equal source", one(" + ".join(f'count(*) FILTER (WHERE "{c}" IS NULL)' for c in metric if c.startswith("m_")).join(("SELECT ", " FROM d"))) == one(" + ".join(f'count(*) FILTER (WHERE "{c}" IS NULL)' for c in metric if c.startswith("m_")).join(("SELECT ", " FROM cur"))))
    add("missing_feature_count equals null m_* count", one("SELECT count(*) FROM d WHERE missing_feature_count <> (" + " + ".join(f'CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END' for c in metric if c.startswith("m_")) + ")") == 0)
    roles = {}
    try:
        roles = {c: column_role(c) for c in cols}
        add("schema: every column has a role", True, len(roles))
    except Exception as error:  # noqa: BLE001
        add("schema: every column has a role", False, str(error))
    leaky = [c for c, r in roles.items() if (c.startswith(("target_", "temporal_", "identity_")) and (r.startswith("FEATURE") or r == "CONTEXT_FEATURE"))]
    add("no target/temporal/identity column is a candidate predictor", not leaky, leaky)
    with (RELEASE / "data_dictionary.csv").open(encoding="utf-8-sig", newline="") as handle:
        dictionary = {r["column"]: r for r in csv.DictReader(handle)}
    add("data dictionary covers every column with its type", set(dictionary) == set(cols) and all(dictionary[c]["type"] == str(t) for c, t in zip(cols, [f.type for f in __import__("pyarrow.parquet", fromlist=["x"]).read_schema(DATASET)])))
    add("provenance columns populated", one("SELECT count(*) FROM d WHERE dataset_version IS NULL OR research_scope_id IS NULL OR fotmob_source_version IS NULL OR transfermarkt_source_version IS NULL OR provenance_profile_raw_path IS NULL") == 0)
    add("usable targets carry source lineage", one("SELECT count(*) FROM d WHERE target_usable AND (target_source_record_reference IS NULL OR target_source_file_sha256 IS NULL OR target_source_row_number IS NULL)") == 0)
    add("multi-club players stay one row; club evidence covers every row", one("SELECT count(*) FROM d ANTI JOIN e USING (canonical_player_id, season)") == 0 and one("SELECT count(*) FROM e") == one(f"SELECT count(*) FROM pts WHERE season_id IN ({scope.sql_ids()}) AND (player_id, season_id) IN (SELECT fotmob_player_id, season_id FROM d)"))
    common = [c for c in cols if c in {r[0] for r in con.execute("DESCRIBE v1").fetchall()} and c not in IDENTITY_OR_PROVENANCE]
    sel = ", ".join(f'"{c}"' for c in common)
    v1 = f"(SELECT {sel} FROM v1 WHERE season IN ({scope.sql_labels()}))"
    diff = one(f"SELECT count(*) FROM (SELECT {sel} FROM d EXCEPT ALL SELECT * FROM {v1})") + one(f"SELECT count(*) FROM (SELECT * FROM {v1} EXCEPT ALL SELECT {sel} FROM d)")
    add("reconciles with historical v1 in-scope rows on all shared non-identity columns", diff == 0, {"shared_columns_compared": len(common), "differing_rows": diff})
    return checks


def integration_statistics(con=None) -> dict:
    con = con or connect()
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    cols = [r[0] for r in con.execute("DESCRIBE d").fetchall()]
    metric = [c for c in cols if c.startswith("m_")]
    total_cells = one("SELECT count(*) FROM d") * len(metric)
    null_cells = one("SELECT sum(missing_feature_count) FROM d")
    return {
        "rows": one("SELECT count(*) FROM d"), "unique_players": one("SELECT count(DISTINCT canonical_player_id) FROM d"), "columns": len(cols),
        "rows_by_season": dict(q("SELECT season, count(*) FROM d GROUP BY 1 ORDER BY 1")),
        "mapped_rows": one("SELECT count(*) FROM d WHERE transfermarkt_player_id IS NOT NULL"), "unmapped_rows": one("SELECT count(*) FROM d WHERE transfermarkt_player_id IS NULL"),
        "usable_targets": one("SELECT count(*) FROM d WHERE target_usable"), "missing_targets": one("SELECT count(*) FROM d WHERE NOT target_usable"),
        "missing_target_reasons": dict(q("SELECT target_missing_reason, count(*) FROM d WHERE NOT target_usable GROUP BY 1 ORDER BY 2 DESC")),
        "duplicate_player_season_rows": one("SELECT count(*) - count(DISTINCT (canonical_player_id, season)) FROM d"),
        "integration_coverage_pct": round(100 * one("SELECT count(*) FROM d WHERE target_usable") / one("SELECT count(*) FROM d"), 2),
        "mapping_coverage_rows_pct": round(100 * one("SELECT count(*) FROM d WHERE transfermarkt_player_id IS NOT NULL") / one("SELECT count(*) FROM d"), 2),
        "metric_cells": total_cells, "null_metric_cells": null_cells, "null_metric_cell_pct": round(100 * null_cells / total_cells, 2),
        "mean_null_metrics_with_target": round(one("SELECT avg(missing_feature_count) FROM d WHERE target_usable"), 2), "mean_null_metrics_without_target": round(one("SELECT avg(missing_feature_count) FROM d WHERE NOT target_usable"), 2),
        "by_season": [dict(zip(("season", "rows", "players", "mapped", "usable", "missing", "multi_club_confirmed"), r)) for r in q("""SELECT season, count(*), count(DISTINCT canonical_player_id), count(transfermarkt_player_id), count(*) FILTER (WHERE target_usable),
            count(*) FILTER (WHERE NOT target_usable), count(*) FILTER (WHERE multi_club_class='MULTI_CLUB_CONFIRMED_APPEARANCES') FROM d GROUP BY 1 ORDER BY 1""")],
        "multi_club_class": dict(q("SELECT multi_club_class, count(*) FROM d GROUP BY 1 ORDER BY 1")),
        "crosswalk_status_rows": dict(q("SELECT crosswalk_status, count(*) FROM d GROUP BY 1 ORDER BY 1")), "crosswalk_status_players": dict(q("SELECT crosswalk_status, count(DISTINCT canonical_player_id) FROM d GROUP BY 1 ORDER BY 1")),
        "identity_evidence_tier_rows": dict(q("SELECT identity_evidence_tier, count(*) FROM d GROUP BY 1 ORDER BY 1")),
        "identity_rs5_validation_label_rows": dict(q("SELECT coalesce(identity_rs5_validation_label, 'NOT_VALIDATED'), count(*) FROM d GROUP BY 1 ORDER BY 1")),
        "club_evidence_rows": one("SELECT count(*) FROM e"),
    }


def main() -> int:
    con = connect()
    checks = integration_checks(con)
    stats = integration_statistics(con)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"checks": checks, "passed": sum(c["status"] == "PASS" for c in checks), "total": len(checks), "statistics": stats}, indent=1, default=str) + "\n", encoding="utf-8")
    for c in checks:
        print(c["status"], c["check"], "" if c["observed"] is None else c["observed"])
    print(json.dumps(stats, indent=1, default=str))
    return 0 if all(c["status"] == "PASS" for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
