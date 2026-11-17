"""Step 3 QA: measure candidate-generation coverage and ranking stability (read-only).

Usage: python -I src/phase3/step3_qa_architecture.py <run_dir> <evidence_dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3.entity_resolution import CONFIG_PATH, score_candidate  # noqa: E402
from src.phase3.tm_common import write_json  # noqa: E402


def main() -> None:
    run_dir, evidence = Path(sys.argv[1]), Path(sys.argv[2])
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    crosswalk = pq.read_table(run_dir / "player_crosswalk.parquet").to_pylist()
    candidates = pq.read_table(run_dir / "matching_candidates.parquet").to_pylist()
    mapped = {r["fotmob_player_id"]: r["transfermarkt_player_id"] for r in crosswalk if r["transfermarkt_player_id"]}
    true_pairs = [c for c in candidates if mapped.get(c["fotmob_player_id"]) == c["tm_player_id"]]
    blocks = ("EXACT_NAME", "DOB_EXACT", "DOB_NEAR", "BIRTH_YEAR_NAME", "ROSTER_NAME", "GAME_SET")
    out: dict = {
        "identities_processed": len(crosswalk), "identities_without_candidates": sum(r["candidate_count"] == 0 for r in crosswalk),
        "mapped_pairs_found_in_candidates": len(true_pairs), "mapped_identities": len(mapped),
        "mapped_pairs_with_block": {b: sum(b in c["blocks"].split("|") for c in true_pairs) for b in blocks},
        "mapped_pairs_lost_if_block_removed": {b: sum(c["blocks"].split("|") == [b] for c in true_pairs) for b in blocks},
        "mapped_pairs_by_block_count": dict(Counter(len(c["blocks"].split("|")) for c in true_pairs)),
        "lowest_name_similarity_of_mapped_pairs": sorted((round(c["name_similarity"], 1), c["fotmob_names"], c["tm_name"]) for c in true_pairs)[:8],
        "mapped_pairs_rank_1": sum(c["candidate_rank"] == 1 for c in true_pairs),
        "mapped_pairs_not_rank_1": [(c["fotmob_names"], c["tm_name"], c["candidate_rank"]) for c in true_pairs if c["candidate_rank"] != 1],
        "false_dob_near_flags_on_exact_dates": sum("DOB_NEAR" in c["blocks"] and c["dob_relation"] == "EXACT" for c in candidates),
    }
    # Blocking exposure: pairs that depend on the fixed similarity floors.
    floors = config["blocking"]
    out["mapped_pairs_near_blocking_floor"] = {
        "dob_exact_within_10_of_floor": sum("DOB_EXACT" in c["blocks"] and c["name_similarity"] < floors["dob_exact_min_name_similarity"] + 10 for c in true_pairs),
        "without_game_set_block": sum("GAME_SET" not in c["blocks"] for c in true_pairs),
        "with_under_3_fotmob_games": sum(c["fm_games"] < floors["game_set_min_shared_games"] for c in true_pairs),
    }
    # Ranking stability: does the mapped pair stay first if each weight changes?
    groups: dict[str, list] = {}
    for c in candidates:
        groups.setdefault(c["fotmob_player_id"], []).append(c)
    base = config["scoring"]
    scenarios = {"baseline": base}
    for key in base:
        for factor, label in ((0.5, "half"), (1.5, "x1.5"), (0.0, "zero")):
            scenarios[f"{key}_{label}"] = {**base, key: base[key] * factor}
    stability = {}
    for name, weights in scenarios.items():
        kept = 0
        for fid, group in groups.items():
            if fid not in mapped:
                continue
            best = max(group, key=lambda c: (score_candidate(c, weights)[0], c["tm_player_id"] == mapped[fid]))
            kept += best["tm_player_id"] == mapped[fid]
        stability[name] = kept
    out["mapped_pair_stays_rank_1_of_%d" % len(mapped)] = stability
    similarity_when_subset = [c["name_similarity"] for c in true_pairs if c["name_subset"]]
    out["double_counting"] = {
        "subset_true_among_mapped": len(similarity_when_subset), "mean_similarity_when_subset": round(sum(similarity_when_subset) / len(similarity_when_subset), 2) if similarity_when_subset else None,
        "note": "name_subset and name_similarity both read names, so names can earn up to 40 points. Game Jaccard, birth date, nationality and position read other fields.",
        "score_max_points": sum(v for k, v in base.items() if k not in ("dob_near", "dob_same_year")),
    }
    write_json(evidence / "architecture_review.json", out)
    print(json.dumps(out, default=str, ensure_ascii=False, indent=0)[:5000])


if __name__ == "__main__":
    main()
