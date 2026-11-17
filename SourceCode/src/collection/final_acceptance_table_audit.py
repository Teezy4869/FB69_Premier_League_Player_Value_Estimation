"""Independent physical grain and source-path audit of every v3.1 Parquet table."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.final_acceptance_release import VERSION
from src.collection.release_manifest import verify_manifest
from src.collection.remediation_release_v3 import write_csv

GRAINS = {
    "players": ("player_id",), "teams": ("season_id", "team_id"),
    "seasons": ("season_id",), "matches": ("match_id",),
    "player_seasons": ("season_id", "player_id"),
    "player_team_seasons": ("season_id", "player_id", "team_id"),
    "player_match_appearances": ("match_id", "player_id"),
    "metric_observations": ("season_id", "player_id", "metric_name", "source_endpoint", "original_source_field", "raw_path"),
    "historical_position_observations": ("match_id", "player_id", "source_field"),
    "substitution_evidence_registry": ("match_id", "player_id"),
    "complete_player_season_classification": ("season_id", "player_id"),
    "confirmed_appeared_player_seasons": ("season_id", "player_id"),
    "unverified_player_seasons": ("season_id", "player_id"),
    "confirmed_non_appeared_player_seasons": ("season_id", "player_id"),
    "player_season_metrics_wide": ("season_id", "player_id"),
}


def run(root: Path = ROOT) -> dict:
    release = root / "data/releases" / VERSION
    manifest = verify_manifest(release)
    rows = []
    for table in manifest["tables"]:
        rel = table["path"]
        name = Path(rel).stem
        if name not in GRAINS:
            raise ValueError(f"UNDEFINED_TABLE_GRAIN:{rel}")
        path = release / rel
        schema = pq.read_schema(path)
        keys = GRAINS[name]
        if any(k not in schema.names for k in keys):
            raise ValueError(f"MISSING_GRAIN_FIELD:{rel}")
        data = pq.read_table(path, columns=list(keys)).to_pylist()
        tuples = [tuple(r[k] for k in keys) for r in data]
        duplicates = len(tuples) - len(set(tuples))
        identifiers = [k for k in keys if k.endswith("_id") or k == "match_id"]
        null_ids = sum(any(r[k] in (None, "") for k in identifiers) for r in data)
        id_type_errors = sum(not str(schema.field(k).type).startswith("string") for k in identifiers)
        path_refs = {str(r["raw_path"]) for r in data if r.get("raw_path")}
        missing_paths = sum(not (root / p).is_file() for p in path_refs)
        status = "PASS" if not (duplicates or null_ids or id_type_errors or missing_paths or len(data) != table["rows"]) else "FAIL"
        rows.append({"path": rel, "table": name, "grain": "|".join(keys),
                     "physical_rows": len(data), "manifest_rows": table["rows"],
                     "duplicate_grain_keys": duplicates, "null_identifier_rows": null_ids,
                     "identifier_type_errors": id_type_errors,
                     "distinct_raw_paths": len(path_refs), "missing_raw_paths": missing_paths,
                     "status": status})
    output = root / "reports/final_acceptance_fix/parquet_table_contract_audit.csv"
    write_csv(output, rows, list(rows[0]))
    result = {"tables": len(rows), "passed": sum(r["status"] == "PASS" for r in rows),
              "failed": sum(r["status"] == "FAIL" for r in rows), "output": str(output)}
    if result["failed"]:
        raise ValueError(f"PARQUET_TABLE_CONTRACT_FAILED:{result}")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
