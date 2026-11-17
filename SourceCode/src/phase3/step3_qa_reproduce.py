"""Step 3 QA: reproduce matching_v1 from documented inputs and verify every checksum (read-only on sources).

Compares a fresh run in a temporary folder with the stored v1 outputs, then re-derives birth dates for
all automatic mappings directly from the raw FotMob JSON and the original Transfermarkt CSV.

This ran against the v1 code before v2 changes; its result is evidence/reproduction_audit.json. To repeat it,
use the code in matching_v1__reviews_none/code_snapshot.

Usage: python -I src/phase3/step3_qa_reproduce.py <evidence_dir>
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.entity_resolution import CONFIG_PATH, REVIEW_DIR, run  # noqa: E402
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash, verify_fotmob_unchanged, write_json  # noqa: E402

V1 = ROOT / "data/phase_03/entity_resolution/matching_v1__reviews_none"
TM_SOURCE = ROOT / "data/transfermarkt/source/tm_r2_20260905"


def main() -> None:
    evidence = Path(sys.argv[1])
    out: dict = {"fotmob_release": verify_fotmob_unchanged()}
    manifest = json.loads((ROOT / "data/transfermarkt/metadata/tm_r2_20260905/source_manifest.json").read_text(encoding="utf-8"))
    out["tm_raw_mismatches"] = [f["file"] for f in manifest["files"] if file_hash(TM_SOURCE / f["file"]) != f["sha256"]]
    normalized = json.loads((ROOT / "data/transfermarkt/metadata/tm_r2_20260905/normalization_manifest.json").read_text(encoding="utf-8"))
    out["tm_normalized_mismatches"] = [k for k, v in normalized["output_sha256"].items() if file_hash(ROOT / "data/transfermarkt" / k.split("/")[0] / "tm_r2_20260905" / k.split("/")[1]) != v]
    run_manifest = json.loads((V1 / "run_manifest.json").read_text(encoding="utf-8"))
    out["v1_output_mismatches"] = [k for k, v in run_manifest["output_sha256"].items() if file_hash(V1 / k) != v]
    out["v1_input_mismatches"] = [k for k, v in run_manifest["input_sha256"].items() if file_hash(ROOT / k) != v]
    out["v1_code_mismatches"] = [k for k, v in run_manifest["code_sha256"].items() if file_hash(ROOT / k) != v]

    # Preserve v1's review files inside the v1 folder before any later version regenerates them.
    snapshot = V1 / "review_snapshot"
    snapshot.mkdir(exist_ok=True)
    for name in ("matching_review_queue.csv", "validation_sample_for_labeling.csv"):
        if not (snapshot / name).exists():
            shutil.copy2(REVIEW_DIR / name, snapshot / name)
    out["v1_review_snapshot_sha256"] = {p.name: file_hash(p) for p in sorted(snapshot.iterdir())}

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as folder:
        fresh = run(config, Path(folder) / "out", Path(folder) / "review")
        fresh_dir = Path(fresh["run_dir"])
        con = duckdb.connect()
        out["fresh_run_identical"] = {}
        for name in ("player_crosswalk.parquet", "matching_candidates.parquet"):
            a = con.execute(f"SELECT * FROM read_parquet('{(fresh_dir / name).as_posix()}')").fetchall()
            b = con.execute(f"SELECT * FROM read_parquet('{(V1 / name).as_posix()}')").fetchall()
            out["fresh_run_identical"][name] = {"rows": len(a), "identical_rows": a == b, "identical_bytes": file_hash(fresh_dir / name) == file_hash(V1 / name)}
        for name in ("matching_review_queue.csv", "validation_sample_for_labeling.csv"):
            out["fresh_run_identical"][name] = (Path(folder) / "review" / name).read_bytes() == (snapshot / name).read_bytes()
        out["fresh_run_identical"]["unresolved_identities.csv"] = (fresh_dir / "unresolved_identities.csv").read_bytes() == (V1 / "unresolved_identities.csv").read_bytes()

    rows = pq.read_table(V1 / "player_crosswalk.parquet").to_pylist()
    conf = pq.read_table(FOTMOB_RELEASE / "normalized/confirmed_appeared_player_seasons.parquet", columns=["player_id", "season_id"]).to_pylist()
    out["counts"] = {
        "identities": len(rows), "distinct_confirmed_players": len({r["player_id"] for r in conf}), "confirmed_rows": len(conf),
        "auto_exact": sum(r["match_status"] == "AUTO_EXACT" for r in rows), "unresolved": sum(r["transfermarkt_player_id"] is None for r in rows),
        "mapped_rows": sum(r["player_season_rows"] for r in rows if r["transfermarkt_player_id"]), "unresolved_rows": sum(r["player_season_rows"] for r in rows if not r["transfermarkt_player_id"]),
        "duplicate_fotmob": len(rows) - len({r["fotmob_player_id"] for r in rows}), "duplicate_canonical": len(rows) - len({r["canonical_player_id"] for r in rows}),
    }
    tm_ids = [r["transfermarkt_player_id"] for r in rows if r["transfermarkt_player_id"]]
    out["counts"]["duplicate_tm"] = len(tm_ids) - len(set(tm_ids))
    per_player = {}
    for r in conf:
        per_player[r["player_id"]] = per_player.get(r["player_id"], 0) + 1
    out["counts"]["season_row_mismatches"] = sum(per_player[r["fotmob_player_id"]] != r["player_season_rows"] for r in rows)

    with (REVIEW_DIR / "matching_review_queue.csv").open(encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))
    unresolved = {r["fotmob_player_id"]: r for r in rows if not r["transfermarkt_player_id"]}
    per_identity: dict[str, int] = {}
    for q in queue:
        per_identity[q["fotmob_player_id"]] = per_identity.get(q["fotmob_player_id"], 0) + 1
    out["queue_reconciliation"] = {
        "queue_rows": len(queue), "queue_identities": len(per_identity), "unresolved_identities": len(unresolved), "identity_sets_equal": set(per_identity) == set(unresolved),
        "duplicate_queue_ids": len(queue) - len({q["queue_id"] for q in queue}), "rows_per_identity_distribution": {str(k): sum(1 for v in per_identity.values() if v == k) for k in sorted(set(per_identity.values()))},
        "player_season_rows_from_crosswalk": sum(r["player_season_rows"] for r in unresolved.values()),
        "candidates_hidden_by_top5_cap": sum(max(0, r["candidate_count"] - 5) for r in unresolved.values()),
    }

    # Birth dates re-derived from original sources, bypassing normalized tables.
    fm_paths = dict(duckdb.connect().execute(f"SELECT player_id, profile_raw_path FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/players.parquet').as_posix()}')").fetchall())
    with gzip.open(TM_SOURCE / "players.csv.gz", "rb") as handle:
        tm_raw = {r["player_id"]: r["date_of_birth"] for r in csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))}
    mismatch, utc_flags, raw_vs_normalized = [], 0, 0
    players = dict(duckdb.connect().execute(f"SELECT player_id, birth_date FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/players.parquet').as_posix()}')").fetchall())
    for row in rows:
        fid = row["fotmob_player_id"]
        raw = json.loads((ROOT / fm_paths[fid]).read_text(encoding="utf-8"))["birthDate"]
        day = raw["utcTime"][:10]
        utc_flags += not raw["utcTime"].endswith("T00:00:00.000Z")
        raw_vs_normalized += day != players[fid]
        if row["match_status"] == "AUTO_EXACT" and day != tm_raw[row["transfermarkt_player_id"]][:10]:
            mismatch.append(fid)
    out["birth_dates_from_raw"] = {"auto_exact_raw_dob_mismatches": mismatch, "fotmob_raw_time_not_midnight_utc": utc_flags, "fotmob_raw_vs_normalized_differences": raw_vs_normalized}
    write_json(evidence / "reproduction_audit.json", out)
    print(json.dumps(out, indent=0, default=str)[:3500])


if __name__ == "__main__":
    main()
