"""Construct the season-end market-value target (Phase 3, Step 4).

Rule: for each canonical player-season, select the latest valid Transfermarkt valuation with
valuation_date <= official season_end_date. Only tm_valuation_history is read for values, so
current or career-high profile values can't reach a target. Nothing is imputed.

Usage: python -I src/phase3/season_targets.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash, verify_fotmob_unchanged, write_json  # noqa: E402

SEASONS_PATH = ROOT / "configs/phase_03_seasons.yaml"
MATCHING_VERSION = "matching_v2_1"
RUN_DIR_CROSSWALK = ROOT / "data/phase_03/entity_resolution" / f"{MATCHING_VERSION}__reviews_none"
HISTORY = ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_valuation_history.parquet"
VALIDATION = ROOT / "reports/phase_03/step_03_qa/evidence/auto_match_validation_all_1299.csv"
OUTPUT = ROOT / "data/phase_03/targets" / f"target_v1__{MATCHING_VERSION}"
ELIGIBLE_CROSSWALK = ("AUTO_EXACT", "AUTO_ADJUDICATED", "MANUAL_CONFIRMED")
USABLE_HISTORY_STATUS = ("VALID", "DUPLICATE_EXACT", "CONFLICT_SAME_DATE")
TARGET_STATUSES = ("VALID", "STALE_TARGET", "TARGET_MISSING", "INVALID_VALUATION", "AMBIGUOUS_VALUATION")
BINS = (("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("91-180", 91, 180), (">180", 181, 10**9))


def staleness_bucket(age: int | None) -> str | None:
    if age is None:
        return None
    if age < 0:
        raise ValueError(f"Negative valuation age: {age}")
    return next(label for label, low, high in BINS if low <= age <= high)


def select_target(observations: list[dict], cutoff: date, stale_days: int) -> dict:
    """Choose one target decision. Observations need valuation_date, market_value, quality_status, source_record_id.

    A valuation after the cutoff is never selectable. Conflicting values on the latest eligible date are
    flagged and not resolved. Missing stays None; there is no fallback of any kind.
    """
    on_or_before = [o for o in observations if o["valuation_date"] is not None and o["valuation_date"] <= cutoff]
    usable = [o for o in on_or_before if o["quality_status"] in USABLE_HISTORY_STATUS and o["market_value"] is not None and o["market_value"] > 0]
    empty = {"selected_valuation_date": None, "market_value": None, "valuation_age_days": None, "staleness_bucket": None, "source_record_reference": None, "selected": None, "conflicting_record_references": None}
    if not usable:
        if on_or_before:
            return {**empty, "target_status": "INVALID_VALUATION", "target_missing_reason": "ONLY_INVALID_VALUATIONS_ON_OR_BEFORE_CUTOFF"}
        reason = "ONLY_VALUATIONS_AFTER_CUTOFF" if observations else "NO_VALUATION_HISTORY"
        return {**empty, "target_status": "TARGET_MISSING", "target_missing_reason": reason}
    latest = max(o["valuation_date"] for o in usable)
    same_day = sorted((o for o in usable if o["valuation_date"] == latest), key=lambda o: o["source_record_id"])
    age = (cutoff - latest).days
    values = {o["market_value"] for o in same_day}
    if len(values) > 1:
        return {**empty, "selected_valuation_date": latest, "valuation_age_days": age, "staleness_bucket": staleness_bucket(age), "target_status": "AMBIGUOUS_VALUATION", "target_missing_reason": "SAME_DATE_CONFLICT",
                "conflicting_record_references": "|".join(o["source_record_id"] for o in same_day)}
    chosen = same_day[0]
    return {"selected_valuation_date": latest, "market_value": chosen["market_value"], "valuation_age_days": age, "staleness_bucket": staleness_bucket(age), "source_record_reference": chosen["source_record_id"], "selected": chosen,
            "conflicting_record_references": None, "target_status": "STALE_TARGET" if age > stale_days else "VALID", "target_missing_reason": None}


SCHEMA = pa.schema([("canonical_player_id", pa.string()), ("fotmob_player_id", pa.string()), ("season", pa.string()), ("season_id", pa.string()), ("transfermarkt_player_id", pa.string()), ("season_end_date", pa.date32()), ("selected_valuation_date", pa.date32()), ("market_value", pa.int64()), ("currency", pa.string()),
                    ("valuation_age_days", pa.int32()), ("staleness_bucket", pa.string()), ("target_status", pa.string()), ("target_missing_reason", pa.string()), ("crosswalk_status", pa.string()), ("crosswalk_method", pa.string()), ("identity_evidence_tier", pa.string()),
                    ("source_record_reference", pa.string()), ("source_file_sha256", pa.string()), ("source_row_number", pa.int64()), ("conflicting_record_references", pa.string()), ("selection_rule_version", pa.string()), ("matching_version", pa.string()),
                    ("player_games_in_season", pa.int32()), ("player_games_after_valuation", pa.int32()), ("league_games_in_season", pa.int32()), ("league_games_after_valuation", pa.int32())])


def identity_tier(row: dict, validation: dict) -> str:
    if row["match_status"] == "AUTO_EXACT":
        return "AUTO_EXACT_VALIDATED" if validation.get(row["fotmob_player_id"]) == "CONFIRMED_MATCH" else "AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED"
    if row["match_status"] == "AUTO_ADJUDICATED":
        return "AUTO_ADJUDICATED_INDEPENDENT_RULE" if "RULE" in (row["adjudication_basis"] or "") else "AUTO_ADJUDICATED_EXTERNAL"
    if row["match_status"] == "MANUAL_CONFIRMED":
        return "HUMAN_CONFIRMED"
    return "UNRESOLVED"


def build() -> tuple[list[dict], dict]:
    config = yaml.safe_load(SEASONS_PATH.read_text(encoding="utf-8"))
    if any(s["verification_status"] != "VERIFIED" for s in config["seasons"]):
        raise RuntimeError("A season cutoff is not verified")
    seasons = {s["season"]: {**s, "end": date.fromisoformat(s["season_end_date"])} for s in config["seasons"]}
    con = duckdb.connect()
    fm = FOTMOB_RELEASE / "normalized"
    crosswalk = {r["fotmob_player_id"]: r for r in pq.read_table(RUN_DIR_CROSSWALK / "player_crosswalk.parquet").to_pylist()}
    with VALIDATION.open(encoding="utf-8-sig", newline="") as handle:
        validation = {r["fotmob_player_id"]: r["label"] for r in csv.DictReader(handle)}
    population = con.execute(f"SELECT player_id, season_label, season_id FROM read_parquet('{(fm / 'confirmed_appeared_player_seasons.parquet').as_posix()}') ORDER BY season_label, player_id").fetchall()
    history = defaultdict(list)
    for tid, day, value, status, record, sha, number in con.execute(f"SELECT tm_player_id, valuation_date, market_value, quality_status, source_record_id, _source_sha256, _source_row_number FROM read_parquet('{HISTORY.as_posix()}')").fetchall():
        history[tid].append({"valuation_date": day, "market_value": value, "quality_status": status, "source_record_id": record, "_source_sha256": sha, "_source_row_number": number})
    league_dates = defaultdict(list)
    for season, day in con.execute(f"SELECT season_label, substr(match_date_utc,1,10) FROM read_parquet('{(fm / 'matches.parquet').as_posix()}') WHERE match_status='COMPLETED'").fetchall():
        league_dates[season].append(date.fromisoformat(day))
    player_dates = defaultdict(list)
    for fid, season, day in con.execute(f"SELECT player_id, season_label, substr(match_date_utc,1,10) FROM read_parquet('{(fm / 'player_match_appearances.parquet').as_posix()}') WHERE participation_status IN ('STARTED','SUBSTITUTED_ON')").fetchall():
        player_dates[(fid, season)].append(date.fromisoformat(day))
    rows = []
    next_gap = defaultdict(list)
    for fid, season_label, season_id in population:
        cw = crosswalk[fid]
        season = seasons[season_label]
        tid = cw["transfermarkt_player_id"] if cw["match_status"] in ELIGIBLE_CROSSWALK else None
        if tid is None:
            decision = {"selected_valuation_date": None, "market_value": None, "valuation_age_days": None, "staleness_bucket": None, "source_record_reference": None, "selected": None, "conflicting_record_references": None, "target_status": "TARGET_MISSING", "target_missing_reason": "NO_ELIGIBLE_IDENTITY_MATCH"}
        else:
            decision = select_target(history.get(tid, []), season["end"], config["stale_label_days"])
            later = [o["valuation_date"] for o in history.get(tid, []) if o["valuation_date"] and o["valuation_date"] > season["end"]]
            if later:
                next_gap[season_label].append((min(later) - season["end"]).days)
        selected = decision["selected"]
        chosen_date = decision["selected_valuation_date"]
        games, league = player_dates[(fid, season_label)], league_dates[season_label]
        rows.append({"canonical_player_id": cw["canonical_player_id"], "fotmob_player_id": fid, "season": season_label, "season_id": season_id, "transfermarkt_player_id": tid, "season_end_date": season["end"], "selected_valuation_date": chosen_date,
                     "market_value": decision["market_value"], "currency": "EUR" if decision["market_value"] is not None else None, "valuation_age_days": decision["valuation_age_days"], "staleness_bucket": decision["staleness_bucket"],
                     "target_status": decision["target_status"], "target_missing_reason": decision["target_missing_reason"], "crosswalk_status": cw["match_status"], "crosswalk_method": cw["match_method"], "identity_evidence_tier": identity_tier(cw, validation),
                     "source_record_reference": decision["source_record_reference"], "source_file_sha256": selected["_source_sha256"] if selected else None, "source_row_number": selected["_source_row_number"] if selected else None, "conflicting_record_references": decision["conflicting_record_references"],
                     "selection_rule_version": config["selection_rule_version"], "matching_version": MATCHING_VERSION, "player_games_in_season": len(games), "player_games_after_valuation": sum(d > chosen_date for d in games) if chosen_date else None,
                     "league_games_in_season": len(league), "league_games_after_valuation": sum(d > chosen_date for d in league) if chosen_date else None})
    return rows, summarize(rows, next_gap, config, crosswalk)


def summarize(rows: list[dict], next_gap: dict, config: dict, crosswalk: dict) -> dict:
    by_season = {}
    usable_status = ("VALID", "STALE_TARGET")

    def block(items):
        usable = [r for r in items if r["target_status"] in usable_status]
        ages = [r["valuation_age_days"] for r in usable]
        player_total = sum(r["player_games_in_season"] for r in usable)
        player_after = sum(r["player_games_after_valuation"] for r in usable)
        shares = [r["player_games_after_valuation"] / r["player_games_in_season"] for r in usable if r["player_games_in_season"]]
        league_shares = [r["league_games_after_valuation"] / r["league_games_in_season"] for r in usable]
        status = Counter(r["target_status"] for r in items)
        reasons = Counter(r["target_missing_reason"] for r in items if r["target_missing_reason"])
        return {
            "player_seasons": len(items), "distinct_players": len({r["canonical_player_id"] for r in items}), "identity_matched": sum(r["transfermarkt_player_id"] is not None for r in items),
            "with_eligible_valuation": sum(r["selected_valuation_date"] is not None for r in items), "VALID": status["VALID"], "STALE_TARGET": status["STALE_TARGET"], "TARGET_MISSING": status["TARGET_MISSING"], "INVALID_VALUATION": status["INVALID_VALUATION"], "AMBIGUOUS_VALUATION": status["AMBIGUOUS_VALUATION"],
            "missing_reasons": dict(reasons), "usable": len(usable), "usable_pct": round(100 * len(usable) / len(items), 2) if items else None,
            "bins": {label: sum(low <= a <= high for a in ages) for label, low, high in BINS},
            "median_age_days": median(ages) if ages else None, "max_age_days": max(ages) if ages else None, "pct_older_than_90_days": round(100 * sum(a > 90 for a in ages) / len(ages), 2) if ages else None,
            "pct_player_games_after_valuation": round(100 * player_after / player_total, 2) if player_total else None, "mean_pct_of_each_players_games_after_valuation": round(100 * sum(shares) / len(shares), 2) if shares else None,
            "mean_pct_league_games_after_valuation": round(100 * sum(league_shares) / len(league_shares), 2) if league_shares else None,
            "selected_on_most_common_date": Counter(r["selected_valuation_date"].isoformat() for r in usable).most_common(1)[0] if usable else None,
            "market_value_min": min((r["market_value"] for r in usable), default=None), "market_value_median": median([r["market_value"] for r in usable]) if usable else None, "market_value_max": max((r["market_value"] for r in usable), default=None),
        }

    for season in sorted({r["season"] for r in rows}):
        items = [r for r in rows if r["season"] == season]
        by_season[season] = block(items)
        gaps = next_gap.get(season, [])
        by_season[season]["median_days_to_next_valuation_after_cutoff_not_used"] = median(gaps) if gaps else None
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "selection_rule_version": config["selection_rule_version"], "stale_label_days": config["stale_label_days"], "overall": block(rows), "by_season": by_season,
        "by_identity_tier": {t: block([r for r in rows if r["identity_evidence_tier"] == t]) for t in sorted({r["identity_evidence_tier"] for r in rows})},
        "unresolved_identities": [{"fotmob_player_id": fid, "names": r["fotmob_names_raw"], "status": r["match_status"], "rows": r["player_season_rows"]} for fid, r in sorted(crosswalk.items()) if r["match_status"] not in ELIGIBLE_CROSSWALK],
    }


def main() -> int:
    fotmob = verify_fotmob_unchanged()
    rows, summary = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target_path = OUTPUT / "player_season_target.parquet"
    temp = OUTPUT / "_tmp.parquet"
    pq.write_table(pa.table({f.name: pa.array([r[f.name] for r in rows], f.type) for f in SCHEMA}), temp, compression="zstd")
    if target_path.exists() and file_hash(target_path) != file_hash(temp):
        temp.unlink()
        print(f"STOP: {target_path} exists with different content; not overwritten.")
        return 2
    temp.replace(target_path)
    conflicts = [r for r in rows if r["target_status"] == "AMBIGUOUS_VALUATION"]
    with (OUTPUT / "same_date_valuation_conflicts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical_player_id", "season", "transfermarkt_player_id", "selected_valuation_date", "conflicting_record_references"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(conflicts)
    inputs = [SEASONS_PATH, RUN_DIR_CROSSWALK / "player_crosswalk.parquet", HISTORY, VALIDATION, FOTMOB_RELEASE / "normalized/confirmed_appeared_player_seasons.parquet", FOTMOB_RELEASE / "normalized/matches.parquet", FOTMOB_RELEASE / "normalized/player_match_appearances.parquet"]
    write_json(OUTPUT / "target_manifest.json", {
        "code_version": None, "code_version_note": "No git (D5); script hashes recorded instead.", "code_sha256": {"src/phase3/season_targets.py": file_hash(ROOT / "src/phase3/season_targets.py")},
        "input_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in inputs}, "output_sha256": {"player_season_target.parquet": file_hash(target_path), "same_date_valuation_conflicts.csv": file_hash(OUTPUT / "same_date_valuation_conflicts.csv")},
        "fotmob_preflight": fotmob, "row_count": len(rows), "summary": summary,
    })
    print(json.dumps(summary, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
