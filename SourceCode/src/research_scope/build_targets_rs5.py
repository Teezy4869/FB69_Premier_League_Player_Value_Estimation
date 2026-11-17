"""Prompt 02 Task B: rebuild the season-end market-value target for the five-season research population.

The approved rule is not re-implemented. `src.phase3.season_targets.build` (rule latest_valid_on_or_before_season_end_v1)
runs unchanged; only its FotMob input is pointed at the rs5 release. The temporal-alignment evidence reuses
`src.phase3.step4_1_audit` the same way. Cutoffs come from the approved config, through the central scope.

Identity input: the historical player-level crosswalk `matching_v2_1`, restricted to the rs5 universe. Step 3
revalidates it; if any in-scope mapping changes, this target must be rebuilt under a new version.

Usage: python -I src/research_scope/build_targets_rs5.py [--crosswalk <player_crosswalk.parquet> --matching-version <v>]
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.phase3 import season_targets, step4_1_audit  # noqa: E402
from src.phase3.tm_common import file_hash, verify_fotmob_unchanged, write_json  # noqa: E402
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.scope import ROOT, ScopeViolation, assert_seasons, load_scope  # noqa: E402

TARGET_VERSION = "target_rs5_v1"
HISTORICAL_CROSSWALK = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
HISTORICAL_TARGET = ROOT / "data/phase_03/targets/target_v1__matching_v2_1/player_season_target.parquet"
HISTORICAL_TEMPORAL = ROOT / "reports/phase_03/step_04/audit_4_1/evidence/temporal_alignment_by_player_season.parquet"
HISTORICAL_FLAGS = ROOT / "reports/phase_03/step_04/audit_4_1/evidence/target_quality_flags.parquet"
RAW_VALUATIONS = ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz"
TM_PLAYERS = ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_players.parquet"
OUT_ROOT = ROOT / "data/research_rs5/targets"
# Columns that describe the identity decision rather than the target value; they may change when identities are revalidated.
IDENTITY_COLUMNS = ("crosswalk_status", "crosswalk_method", "identity_evidence_tier", "matching_version")
AUDIT_SCHEMA = pa.schema([("canonical_player_id", pa.string()), ("fotmob_player_id", pa.string()), ("season", pa.string()), ("selected_valuation_date", pa.date32()), ("market_value", pa.int64()),
                          ("previous_value", pa.int64()), ("previous_valuation_date", pa.date32()), ("ratio_to_previous_value", pa.float64())])


DESCRIPTIONS = {
    "canonical_player_id": "fb69p_<fotmob_player_id>", "fotmob_player_id": "FotMob player id", "season": "Season label (official rs5 season)", "season_id": "FotMob season id",
    "transfermarkt_player_id": "Mapped Transfermarkt id; null when the identity is not eligible", "season_end_date": "Cutoff: official season end (configs/phase_03_seasons.yaml)",
    "selected_valuation_date": "Latest valid valuation date on or before the cutoff", "market_value": "Selected value, EUR as published; null if no usable target", "currency": "EUR when a value exists",
    "valuation_age_days": "season_end_date - selected_valuation_date", "staleness_bucket": "0-30 / 31-60 / 61-90 / 91-180 / >180 days", "target_status": "VALID (<=90 days), STALE_TARGET (>90; usable, label only), TARGET_MISSING, INVALID_VALUATION, AMBIGUOUS_VALUATION",
    "target_missing_reason": "Why no target: NO_ELIGIBLE_IDENTITY_MATCH, NO_VALUATION_HISTORY, ONLY_VALUATIONS_AFTER_CUTOFF, ...", "crosswalk_status": "Identity decision status", "crosswalk_method": "Identity decision method",
    "identity_evidence_tier": "Evidence tier of the identity mapping", "source_record_reference": "player_valuations:<tm id>:<date>", "source_file_sha256": "SHA-256 of player_valuations.csv.gz", "source_row_number": "Row in the raw CSV",
    "conflicting_record_references": "Same-date conflicting records, if any", "selection_rule_version": "latest_valid_on_or_before_season_end_v1", "matching_version": "Crosswalk version used",
    "player_games_in_season": "Confirmed appearances (STARTED or SUBSTITUTED_ON) that season", "player_games_after_valuation": "Of those, dated after the selected valuation", "league_games_in_season": "Completed league matches that season",
    "league_games_after_valuation": "Completed league matches after the selected valuation",
}


def write_dictionary(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column", "type", "role", "description"])
        for f in season_targets.SCHEMA:
            role = "TARGET" if f.name in ("market_value", "currency") else "KEY" if f.name in ("canonical_player_id", "fotmob_player_id", "season", "season_id") else "TEMPORAL_NOT_A_PREDICTOR" if "games" in f.name else "TARGET_METADATA"
            writer.writerow([f.name, str(f.type), role, DESCRIPTIONS[f.name]])


@contextlib.contextmanager
def patched(module, **values):
    """Point a frozen Phase 3 module at rs5 inputs for one call, then restore it."""
    old = {k: getattr(module, k) for k in values}
    try:
        for k, v in values.items():
            setattr(module, k, v)
        yield module
    finally:
        for k, v in old.items():
            setattr(module, k, v)


def verify_rs5_release() -> dict:
    manifest = json.loads((FOTMOB_RS5 / "metadata/release_manifest.json").read_text(encoding="utf-8"))
    bad = [f["path"] for f in manifest["files"] if file_hash(FOTMOB_RS5 / f["path"]) != f["sha256"]]
    if bad:
        raise RuntimeError(f"rs5 FotMob release changed: {bad}")
    return {"files_checked": len(manifest["files"]), "mismatches": 0, "manifest_sha256": file_hash(FOTMOB_RS5 / "metadata/release_manifest.json")}


def build_rows(crosswalk: Path, matching_version: str, validation: Path) -> tuple[list[dict], dict]:
    scope = load_scope()
    with patched(season_targets, FOTMOB_RELEASE=FOTMOB_RS5, RUN_DIR_CROSSWALK=crosswalk.parent, MATCHING_VERSION=matching_version, VALIDATION=validation):
        rows, summary = season_targets.build()
    assert_seasons({r["season"] for r in rows}, scope, "label", "target")
    assert_seasons({r["season_id"] for r in rows}, scope, "season_id", "target")
    for r in rows:
        if r["season_end_date"] != scope.by_label(r["season"]).season_end_date:
            raise ScopeViolation(f"Cutoff mismatch for {r['season']}")
        if r["selected_valuation_date"] is not None and r["selected_valuation_date"] > r["season_end_date"]:
            raise ScopeViolation("A selected valuation is after the cutoff")
    # The historical summary lists unresolved identities from the whole six-season crosswalk; keep only the rs5 universe.
    universe = {r["fotmob_player_id"] for r in rows}
    summary["unresolved_identities"] = [u for u in summary["unresolved_identities"] if u["fotmob_player_id"] in universe]
    for u in summary["unresolved_identities"]:
        u["rows"] = sum(r["fotmob_player_id"] == u["fotmob_player_id"] for r in rows)
    return rows, summary


def write_table(rows: list[dict], schema: pa.Schema, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({f.name: pa.array([r[f.name] for r in rows], f.type) for f in schema}), path, compression="zstd")


def temporal_evidence(target_path: Path, crosswalk: Path, out: Path) -> dict:
    """Per-match before/after split of minutes, goals, assists, xG and xA around the selected valuation date."""
    con = duckdb.connect(":memory:")
    with patched(step4_1_audit, FM=FOTMOB_RS5, TARGET=target_path, CROSSWALK=crosswalk):
        step4_1_audit.setup(con)
        per_game, match_info = step4_1_audit.parse_matches(con)
        agreement = step4_1_audit.temporal(con, per_game, match_info, out)
    return {"player_games_parsed": len(per_game), "match_level": agreement["match_level"], "season_metric_agreement": {k: v for k, v in agreement.items() if k not in ("match_level", "per_match_stat_keys_2023_24")}}


def previous_valuations(target_path: Path, out: Path) -> int:
    """Previous valid valuation before the selected one (audit only; same SQL chain as Step 4.1 follow-ups)."""
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW target AS SELECT * FROM read_parquet('{target_path.as_posix()}')")
    con.execute(f"CREATE TABLE raw_v AS SELECT row_number() OVER () rn, player_id, try_cast(date AS DATE) d, try_cast(market_value_in_eur AS BIGINT) m FROM read_csv('{RAW_VALUATIONS.as_posix()}', all_varchar=true, header=true)")
    con.execute("CREATE TEMP TABLE chain AS SELECT player_id, d, m, lag(m) OVER w prev_m, lag(d) OVER w prev_d FROM raw_v WHERE m>0 WINDOW w AS (PARTITION BY player_id ORDER BY d)")
    rows = con.execute("""SELECT t.canonical_player_id, t.fotmob_player_id, t.season, t.selected_valuation_date, t.market_value, c.prev_m, c.prev_d
                          FROM target t LEFT JOIN chain c ON c.player_id=t.transfermarkt_player_id AND c.d=t.selected_valuation_date ORDER BY t.season, t.canonical_player_id""").fetchall()
    records = [dict(zip(AUDIT_SCHEMA.names[:-1], r)) for r in rows]
    for r in records:
        # Python round(), as in Step 4.1: DuckDB rounds ties (0.78125) differently.
        r["ratio_to_previous_value"] = round(r["market_value"] / r["previous_value"], 4) if r["market_value"] and r["previous_value"] else None
    write_table(records, AUDIT_SCHEMA, out / "target_previous_valuation_audit.parquet")
    return len(records)


def positions() -> dict:
    """Modal known lineup position per player-season, same rule as integrate.py (ties broken by group name)."""
    con = duckdb.connect()
    return {(p, s): g for p, s, g in con.execute(f"""SELECT player_id, season_id, mapped_group FROM (SELECT player_id, season_id, mapped_group, row_number() OVER (PARTITION BY player_id, season_id ORDER BY count(*) DESC, mapped_group) rk
                                                FROM read_parquet('{(FOTMOB_RS5 / 'normalized/historical_position_observations.parquet').as_posix()}') WHERE mapped_group<>'UNKNOWN' GROUP BY 1,2,3) WHERE rk=1""").fetchall()}


def quantiles(values: list[int]) -> dict:
    if not values:
        return {}
    v = sorted(values)
    pick = lambda q: v[min(len(v) - 1, int(round(q * (len(v) - 1))))]  # noqa: E731
    return {"n": len(v), "min": v[0], "p10": pick(0.10), "p25": pick(0.25), "median": median(v), "mean": round(mean(v), 1), "p75": pick(0.75), "p90": pick(0.90), "max": v[-1]}


def report_statistics(rows: list[dict], history_rows: int) -> dict:
    scope = load_scope()
    usable = lambda items: [r for r in items if r["target_status"] in ("VALID", "STALE_TARGET")]  # noqa: E731
    pos = positions()
    for r in rows:
        r["_position"] = pos.get((r["fotmob_player_id"], r["season_id"]), "UNKNOWN")

    def block(items):
        u = usable(items)
        ages = [r["valuation_age_days"] for r in u]
        games = sum(r["player_games_in_season"] for r in u)
        after = sum(r["player_games_after_valuation"] for r in u)
        return {"rows": len(items), "usable": len(u), "missing": len(items) - len(u), "coverage_pct": round(100 * len(u) / len(items), 2) if items else None,
                "status": dict(Counter(r["target_status"] for r in items)), "missing_reasons": dict(Counter(r["target_missing_reason"] for r in items if r["target_missing_reason"])),
                "market_value_eur": quantiles([r["market_value"] for r in u]), "valuation_age_days": quantiles(ages),
                "staleness_bins": dict(Counter(r["staleness_bucket"] for r in u)), "pct_targets_older_than_90_days": round(100 * sum(a > 90 for a in ages) / len(ages), 2) if ages else None,
                "pct_appearances_after_valuation": round(100 * after / games, 2) if games else None}

    stats = {"definitions": {"usable": "target_status in (VALID, STALE_TARGET); missing = all other statuses",
                             "pct_targets_older_than_90_days": "usable rows with valuation_age_days > 90 / usable rows",
                             "pct_appearances_after_valuation": "sum over usable rows of confirmed appearances (STARTED or SUBSTITUTED_ON) dated after the selected valuation date / sum of their confirmed appearances",
                             "valuation_age_days": "season_end_date - selected_valuation_date"},
             "overall": block(rows), "by_season": {s: block([r for r in rows if r["season"] == s]) for s in scope.labels},
             "by_position_group_season": {p: block([r for r in rows if r["_position"] == p]) for p in sorted({r["_position"] for r in rows})},
             "by_identity_tier": {t: block([r for r in rows if r["identity_evidence_tier"] == t]) for t in sorted({r["identity_evidence_tier"] for r in rows})},
             "valuation_date_distribution": {s: [{"date": d.isoformat(), "targets": n} for d, n in Counter(r["selected_valuation_date"] for r in usable(rows) if r["season"] == s).most_common(8)] for s in scope.labels},
             "valuation_month_distribution": dict(sorted(Counter(r["selected_valuation_date"].strftime("%Y-%m") for r in usable(rows)).items())),
             "valid_valuation_records_for_in_scope_players": history_rows}
    for r in rows:
        r.pop("_position")
    return stats


def validate(rows: list[dict], target_path: Path) -> list[dict]:
    """Target-level checks. Each returns PASS or FAIL with the observed value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{target_path.as_posix()}')")
    con.execute(f"CREATE VIEW h AS SELECT * FROM read_parquet('{season_targets.HISTORY.as_posix()}')")
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{TM_PLAYERS.as_posix()}')")
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{(FOTMOB_RS5 / 'normalized/confirmed_appeared_player_seasons.parquet').as_posix()}')")
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    checks = [
        ("one row per population player-season", one("SELECT count(*) FROM t") == one("SELECT count(*) FROM c") and one("SELECT count(*) FROM (SELECT DISTINCT fotmob_player_id, season FROM t)") == one("SELECT count(*) FROM t"), one("SELECT count(*) FROM t")),
        ("no duplicate canonical player-season", one("SELECT count(*) FROM (SELECT canonical_player_id, season FROM t GROUP BY ALL HAVING count(*)>1)") == 0, 0),
        ("population matches rs5 Confirmed set", one("SELECT count(*) FROM (SELECT player_id, season_label FROM c EXCEPT SELECT fotmob_player_id, season FROM t)") == 0, None),
        ("currency is EUR whenever a value exists", one("SELECT count(*) FROM t WHERE market_value IS NOT NULL AND currency IS DISTINCT FROM 'EUR'") == 0, one("SELECT count(DISTINCT currency) FROM t WHERE currency IS NOT NULL")),
        ("no value without currency, and none with a missing target", one("SELECT count(*) FROM t WHERE (market_value IS NULL) <> (currency IS NULL) OR (market_value IS NOT NULL AND target_status NOT IN ('VALID','STALE_TARGET'))") == 0, None),
        ("selected valuation on or before cutoff", one("SELECT count(*) FROM t WHERE selected_valuation_date > season_end_date") == 0, one("SELECT max(season_end_date - selected_valuation_date) FROM t")),
        ("age equals cutoff minus valuation date", one("SELECT count(*) FROM t WHERE valuation_age_days IS DISTINCT FROM (season_end_date - selected_valuation_date)") == 0, None),
        ("Transfermarkt id exists in tm_players", one("SELECT count(*) FROM t ANTI JOIN p ON p.tm_player_id=t.transfermarkt_player_id WHERE t.transfermarkt_player_id IS NOT NULL") == 0, None),
        ("selected record exists in valuation history with same value and date", one("""SELECT count(*) FROM t LEFT JOIN h ON h.source_record_id=t.source_record_reference
            WHERE t.source_record_reference IS NOT NULL AND (h.source_record_id IS NULL OR h.market_value<>t.market_value OR h.valuation_date<>t.selected_valuation_date OR h.tm_player_id<>t.transfermarkt_player_id
            OR h._source_row_number<>t.source_row_number OR h._source_sha256<>t.source_file_sha256)""") == 0, None),
        ("provenance present for every usable target", one("SELECT count(*) FROM t WHERE market_value IS NOT NULL AND (source_record_reference IS NULL OR source_file_sha256 IS NULL OR source_row_number IS NULL)") == 0, None),
        ("no later eligible valuation was skipped", one("""SELECT count(*) FROM t JOIN h ON h.tm_player_id=t.transfermarkt_player_id WHERE h.quality_status IN ('VALID','DUPLICATE_EXACT','CONFLICT_SAME_DATE') AND h.market_value>0
            AND h.valuation_date<=t.season_end_date AND (t.selected_valuation_date IS NULL OR h.valuation_date>t.selected_valuation_date)""") == 0, None),
        ("selection rule version", one("SELECT count(DISTINCT selection_rule_version) FROM t") == 1 and one("SELECT any_value(selection_rule_version) FROM t") == load_scope().selection_rule_version, None),
        ("statuses within the approved vocabulary", one(f"SELECT count(*) FROM t WHERE target_status NOT IN {season_targets.TARGET_STATUSES}") == 0, None),
        ("missing target has a reason", one("SELECT count(*) FROM t WHERE market_value IS NULL AND target_missing_reason IS NULL") == 0, None),
    ]
    return [{"check": name, "status": "PASS" if ok else "FAIL", "observed": observed} for name, ok, observed in checks]


def compare_with_historical(target_path: Path, temporal_path: Path, audit_path: Path) -> dict:
    """The approved rule is row-local, so in-scope historical rows must be identical. Any difference is reported."""
    con = duckdb.connect()
    labels = load_scope().sql_labels()
    out = {}
    for name, fresh, old, key in (("target", target_path, HISTORICAL_TARGET, "fotmob_player_id, season"), ("temporal_alignment", temporal_path, HISTORICAL_TEMPORAL, "fotmob_player_id, season")):
        a, b = f"read_parquet('{fresh.as_posix()}')", f"(SELECT * FROM read_parquet('{old.as_posix()}') WHERE season IN ({labels}))"
        out[name] = {"rs5_rows": con.execute(f"SELECT count(*) FROM {a}").fetchone()[0], "historical_in_scope_rows": con.execute(f"SELECT count(*) FROM {b}").fetchone()[0],
                     "rows_only_in_rs5": con.execute(f"SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})").fetchone()[0],
                     "rows_only_in_historical": con.execute(f"SELECT count(*) FROM (SELECT * FROM {b} EXCEPT ALL SELECT * FROM {a})").fetchone()[0]}
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {a}").fetchall()]
        identity = [c for c in IDENTITY_COLUMNS if c in cols]
        if identity:
            rest = ", ".join(c for c in cols if c not in identity)
            out[name]["rows_differing_outside_identity_columns"] = con.execute(f"SELECT count(*) FROM (SELECT {rest} FROM {a} EXCEPT ALL SELECT {rest} FROM {b})").fetchone()[0]
            out[name]["rows_differing_by_identity_column"] = {c: con.execute(f"SELECT count(*) FROM {a} x JOIN {b} y USING ({key}) WHERE x.{c} IS DISTINCT FROM y.{c}").fetchone()[0] for c in identity}
    a = f"read_parquet('{audit_path.as_posix()}')"
    b = f"(SELECT canonical_player_id, fotmob_player_id, season, selected_valuation_date, market_value, previous_value, previous_valuation_date, ratio_to_previous_value FROM read_parquet('{HISTORICAL_FLAGS.as_posix()}') WHERE season IN ({labels}))"
    out["previous_valuation_audit"] = {"rows_only_in_rs5": con.execute(f"SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})").fetchone()[0],
                                       "rows_only_in_historical": con.execute(f"SELECT count(*) FROM (SELECT * FROM {b} EXCEPT ALL SELECT * FROM {a})").fetchone()[0],
                                       "historical_batch_rows_in_scope": con.execute(f"SELECT count(*) FROM read_parquet('{HISTORICAL_FLAGS.as_posix()}') WHERE season IN ({labels}) AND on_2020_04_08_batch").fetchone()[0],
                                       "historical_non_batch_age_differs_in_scope": con.execute(f"SELECT count(*) FROM read_parquet('{HISTORICAL_FLAGS.as_posix()}') WHERE season IN ({labels}) AND age_days_from_last_non_batch_valuation IS DISTINCT FROM valuation_age_days").fetchone()[0]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crosswalk", type=Path, default=HISTORICAL_CROSSWALK)
    parser.add_argument("--matching-version", default="matching_v2_1")
    parser.add_argument("--validation", type=Path, default=season_targets.VALIDATION, help="identity validation labels (fotmob_player_id, label)")
    args = parser.parse_args()
    args.crosswalk, args.validation = args.crosswalk.resolve(), args.validation.resolve()
    fotmob = verify_fotmob_unchanged()
    rs5 = verify_rs5_release()
    scope = load_scope()
    final = OUT_ROOT / f"{TARGET_VERSION}__{args.matching_version}"
    temp = OUT_ROOT / f"_build_{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    try:
        rows, summary = build_rows(args.crosswalk, args.matching_version, args.validation)
        target_path = temp / "player_season_target.parquet"
        write_table(rows, season_targets.SCHEMA, target_path)
        conflicts = [r for r in rows if r["target_status"] == "AMBIGUOUS_VALUATION"]
        with (temp / "same_date_valuation_conflicts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["canonical_player_id", "season", "transfermarkt_player_id", "selected_valuation_date", "conflicting_record_references"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(conflicts)
        write_dictionary(temp / "target_data_dictionary.csv")
        temporal = temporal_evidence(target_path, args.crosswalk, temp)
        previous_valuations(target_path, temp)
        con = duckdb.connect()
        mapped = sorted({r["transfermarkt_player_id"] for r in rows if r["transfermarkt_player_id"]})
        con.execute("CREATE TABLE ids(tm_player_id VARCHAR)")
        con.executemany("INSERT INTO ids VALUES (?)", [(i,) for i in mapped])
        max_cut = max(s.season_end_date for s in scope.seasons)
        history_rows = con.execute(f"SELECT count(*) FROM read_parquet('{season_targets.HISTORY.as_posix()}') h SEMI JOIN ids USING (tm_player_id) WHERE quality_status='VALID' AND valuation_date <= DATE '{max_cut}'").fetchone()[0]
        stats = report_statistics(rows, history_rows)
        checks = validate(rows, target_path)
        comparison = compare_with_historical(target_path, temp / "temporal_alignment_by_player_season.parquet", temp / "target_previous_valuation_audit.parquet")
        failed = [c for c in checks if c["status"] == "FAIL"]
        if failed:
            raise ScopeViolation(f"Target validation failed: {failed}")
        outputs = {p.name: file_hash(p) for p in sorted(temp.iterdir()) if p.is_file()}
        if final.exists():
            existing = {p.name: file_hash(p) for p in sorted(final.iterdir()) if p.is_file() and p.name != "target_manifest.json"}
            if existing != outputs:
                print(f"STOP: {final} exists with different content; not overwritten.")
                return 2
            print("Existing target has identical content; manifest kept.")
            return 0
        inputs = [ROOT / "configs/research_scope.yaml", season_targets.SEASONS_PATH, args.crosswalk, season_targets.HISTORY, args.validation, RAW_VALUATIONS, TM_PLAYERS,
                  *[FOTMOB_RS5 / f"normalized/{n}.parquet" for n in ("confirmed_appeared_player_seasons", "matches", "player_match_appearances", "historical_position_observations")], FOTMOB_RS5 / "curated/confirmed_appeared_player_seasons.parquet"]
        write_json(temp / "target_manifest.json", {
            "target_version": TARGET_VERSION, "matching_version": args.matching_version, "scope_id": scope.scope_id, "seasons": list(scope.labels), "excluded_seasons": list(scope.excluded_labels),
            "research_objective": "A (D6)", "selection_rule_version": scope.selection_rule_version, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": "src.phase3.season_targets.build run unchanged on the rs5 FotMob population; temporal evidence from src.phase3.step4_1_audit run unchanged on rs5 inputs",
            "identity_note": "Crosswalk is the historical player-level mapping restricted to the rs5 universe until Step 3 revalidates it" if args.matching_version == "matching_v2_1" else "Crosswalk and validation labels revalidated on in-scope evidence (Step 3)",
            "identity_validation_labels": args.validation.relative_to(ROOT).as_posix(),
            "code_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in (ROOT / "src/research_scope/build_targets_rs5.py", ROOT / "src/phase3/season_targets.py", ROOT / "src/phase3/step4_1_audit.py", ROOT / "src/research_scope/scope.py")},
            "input_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in inputs}, "output_sha256": outputs, "fotmob_v3_1_preflight": fotmob, "fotmob_rs5_preflight": rs5,
            "row_count": len(rows), "validation": checks, "comparison_with_historical_in_scope_rows": comparison, "statistics": stats, "temporal_evidence": temporal,
            "season_targets_summary": summary, "environment": {"python": sys.version.split()[0], "duckdb": duckdb.__version__, "pyarrow": pa.__version__},
        })
        shutil.move(str(temp), str(final))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    print(json.dumps({"final": str(final), "rows": len(rows), "overall": stats["overall"], "comparison": comparison, "checks_failed": len(failed)}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
