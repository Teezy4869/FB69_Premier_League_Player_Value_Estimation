"""Phase 5 step 01: previous market value at season start.

Rule (owner decision 2026-11-15): for each player-season, the latest usable Transfermarkt valuation dated
strictly before the official EPL first match date of that season. It reuses the Phase 3 target selection rule
(`select_target`) with cutoff = first_match_date - 1 day, so usable statuses and same-date conflicts are treated
exactly as for the target. Nothing is imputed. The release dataset is read only.

Usage: python -I src/phase5/season_start_prev_value.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.season_targets import HISTORY, SEASONS_PATH, select_target  # noqa: E402
from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase4 import profiling  # noqa: E402

RULE_VERSION = "latest_valid_strictly_before_first_match_v1"
OUTPUT = ROOT / "data/phase_05/previous_value/season_start_prev_value_v1"
KEY = ["canonical_player_id", "season"]

SCHEMA = pa.schema([("canonical_player_id", pa.string()), ("season", pa.string()), ("transfermarkt_player_id", pa.string()),
                    ("first_match_date", pa.date32()), ("prev_cutoff_date", pa.date32()), ("target_valuation_date", pa.date32()),
                    ("prev_valuation_date", pa.date32()), ("prev_market_value", pa.int64()), ("prev_age_days_at_first_match", pa.int32()),
                    ("prev_status", pa.string()), ("prev_missing_reason", pa.string()), ("prev_source_record_reference", pa.string()),
                    ("prev_conflicting_record_references", pa.string()), ("target_before_season_start", pa.bool_()), ("prev_rule_version", pa.string())])


def season_starts(path: Path = SEASONS_PATH) -> dict[str, date]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if any(s["verification_status"] != "VERIFIED" for s in config["seasons"]):
        raise RuntimeError("A season date is not verified")
    return {s["season"]: date.fromisoformat(s["first_match_date"]) for s in config["seasons"]}


def decide(observations: list[dict], first_match: date) -> dict:
    """Previous-value decision for one player-season. Only valuations dated before first_match are eligible."""
    d = select_target(observations, first_match - timedelta(days=1), stale_days=10**9)
    usable = d["target_status"] == "VALID"
    return {"prev_valuation_date": d["selected_valuation_date"], "prev_market_value": d["market_value"] if usable else None,
            "prev_age_days_at_first_match": (first_match - d["selected_valuation_date"]).days if d["selected_valuation_date"] else None,
            "prev_status": "AVAILABLE" if usable else d["target_status"], "prev_missing_reason": d["target_missing_reason"],
            "prev_source_record_reference": d["source_record_reference"], "prev_conflicting_record_references": d["conflicting_record_references"]}


def build() -> tuple[list[dict], dict]:
    df, _, _, verification = profiling.load_verified()
    starts = season_starts()
    history = defaultdict(list)
    for tid, day, value, status, record in duckdb.sql(f"SELECT tm_player_id, valuation_date, market_value, quality_status, source_record_id FROM read_parquet('{HISTORY.as_posix()}')").fetchall():
        history[tid].append({"valuation_date": day, "market_value": value, "quality_status": status, "source_record_id": record})
    rows = []
    for r in df[KEY + ["transfermarkt_player_id", "target_valuation_date"]].sort_values(KEY).itertuples(index=False):
        start = starts[r.season]
        tid = r.transfermarkt_player_id if isinstance(r.transfermarkt_player_id, str) else None
        target_date = r.target_valuation_date if isinstance(r.target_valuation_date, date) else None
        if tid is None:
            decision = {k: None for k in ("prev_valuation_date", "prev_market_value", "prev_age_days_at_first_match", "prev_source_record_reference", "prev_conflicting_record_references")}
            decision |= {"prev_status": "NO_TM_IDENTITY", "prev_missing_reason": "NO_TRANSFERMARKT_PLAYER_ID"}
        else:
            decision = decide(history.get(tid, []), start)
        rows.append({"canonical_player_id": r.canonical_player_id, "season": r.season, "transfermarkt_player_id": tid, "first_match_date": start,
                     "prev_cutoff_date": start - timedelta(days=1), "target_valuation_date": target_date, **decision,
                     "target_before_season_start": None if target_date is None else target_date < start, "prev_rule_version": RULE_VERSION})
    meta = {"release_sha256": verification["sha256"], "history_sha256": file_hash(HISTORY), "seasons_config_sha256": file_hash(SEASONS_PATH)}
    return rows, meta


def check(rows: list[dict]) -> dict:
    """Invariants. Raises on any violation."""
    keys = Counter((r["canonical_player_id"], r["season"]) for r in rows)
    assert max(keys.values()) == 1, "duplicate player-season"
    for r in rows:
        if r["prev_valuation_date"] is not None:
            assert r["prev_valuation_date"] < r["first_match_date"], f"valuation not before season start: {r}"
            if r["target_valuation_date"] is not None:
                # equal dates are possible: the target valuation itself predates the season (flagged)
                assert r["prev_valuation_date"] <= r["target_valuation_date"], f"previous value after target: {r}"
                assert (r["prev_valuation_date"] == r["target_valuation_date"]) <= r["target_before_season_start"], f"same date without flag: {r}"
        assert (r["prev_market_value"] is not None) == (r["prev_status"] == "AVAILABLE"), f"value/status mismatch: {r}"
        if r["prev_market_value"] is not None:
            assert r["prev_market_value"] > 0
    return {"rows": len(rows), "status_counts": dict(Counter(r["prev_status"] for r in rows)),
            "target_before_season_start": sum(bool(r["target_before_season_start"]) for r in rows)}


def main() -> None:
    rows, meta = build()
    checks = check(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "season_start_prev_value.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), out)
    write_json(OUTPUT / "manifest.json", {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rule_version": RULE_VERSION,
                                          "code": "src/phase5/season_start_prev_value.py", "inputs": meta, "output_sha256": file_hash(out), "checks": checks})
    print(checks)


if __name__ == "__main__":
    main()
