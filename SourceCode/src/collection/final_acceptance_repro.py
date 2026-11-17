"""Independent logical rebuild of metric curation and coverage from saved inputs."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.final_acceptance_release import VERSION, csv_read
from src.collection.remediation_conflicts import build_conflict_inventory
from src.collection.remediation_recovery import generate_provisional_curated_wide
from src.collection.statistics_semantics import compute_metric_eligibility_registry


def run(root: Path = ROOT) -> dict:
    release = root / "data/releases" / VERSION
    report = root / "reports/final_acceptance_fix"
    rebuilt = generate_provisional_curated_wide(root)
    actual = pq.read_table(release / "curated/player_season_metrics_wide.parquet").to_pylist()
    index = {(r["season_id"], r["player_id"]): r for r in actual}
    if len(rebuilt) != len(actual) or len(index) != len(actual):
        raise ValueError("METRIC_REBUILD_GRAIN_MISMATCH")
    differences = []
    for r in rebuilt:
        key = (r["season_id"], r["player_id"])
        saved = index.get(key)
        if saved is None:
            differences.append((key, "missing_player"))
            continue
        for field, value in r.items():
            if field.startswith(("m_", "s_")) and saved.get(field) != value:
                differences.append((key, field))
    conflict_rebuilt = build_conflict_inventory(root)["inventory_rows"]
    conflict_saved = csv_read(release / "quality_reports/metric_reconciliation_report.csv")
    def conflict_key(r):
        return (r["conflict_id"], r["season_label"], r["player_id"], r["canonical_metric"],
                r["resolution_action"], r["curated_resolved_status"], str(r["curated_resolved_value"]))
    conflict_match = [conflict_key(r) for r in conflict_rebuilt] == [conflict_key(r) for r in conflict_saved]
    rules = csv_read(release / "manifests/metric_dictionary_v3.csv")
    positions = pq.read_table(release / "normalized/historical_position_observations.parquet").to_pylist()
    seasons = pq.read_table(release / "normalized/seasons.parquet").to_pylist()
    registry, coverage = compute_metric_eligibility_registry(actual, [r["normalized_field"] for r in rules], rules, positions, seasons)
    for r in coverage:
        if r["eligible_players"] == 0:
            r["coverage_fraction"] = ""
            r["coverage_status"] = "UNDEFINED"
    saved_coverage = csv_read(release / "quality_reports/cross_season_feature_coverage.csv")
    def normalize(rows):
        return [{k: str(v) for k, v in r.items()} for r in rows]
    coverage_match = normalize(coverage) == normalize(saved_coverage)
    result = {"metric_rebuilt_player_seasons": len(rebuilt),
              "metric_value_status_mismatches": len(differences), "metric_mismatch_samples": differences[:10],
              "conflict_inventory_rows": len(conflict_rebuilt), "conflict_inventory_match": conflict_match,
              "coverage_rows": len(coverage), "coverage_matrix_match": coverage_match,
              "data_content_reproducible": not differences and conflict_match and coverage_match,
              "comparison_contract": "Canonical m_*/s_* values and statuses by (season_id, player_id); conflict action keys; all coverage rows. Population labels are rebuilt separately from Part 1 evidence."}
    (report / "metric_rebuild_verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not result["data_content_reproducible"]:
        raise ValueError("METRIC_OR_COVERAGE_REBUILD_DIFFERS")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
