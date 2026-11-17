"""Evaluate the crosswalk against human labels. Reports NOT_EVALUATED until a person has labeled pairs.

Usage: python -I src/phase3/evaluate_matching.py <crosswalk.parquet>
"""
from __future__ import annotations

import csv
import json
import sys
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pyarrow.parquet as pq  # noqa: E402

from src.phase3.tm_common import ROOT  # noqa: E402

LABELS = ("MATCH", "NON_MATCH", "UNSURE")
RANDOM_STRATUM = "AUTO_EXACT_RANDOM"


def lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """One-sided exact binomial (Clopper-Pearson) lower bound on a proportion."""
    if trials == 0 or successes == 0:
        return 0.0
    alpha = 1 - confidence
    tail = lambda p: sum(comb(trials, k) * p**k * (1 - p) ** (trials - k) for k in range(successes, trials + 1))  # noqa: E731
    low, high = 0.0, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if tail(mid) < alpha:
            low = mid
        else:
            high = mid
    return low


def evaluate(labels: list[dict], mapped: dict[str, str]) -> dict:
    """Score human labels. Each pair needs one consistent label; conflicting labels stop the run."""
    pairs: dict[tuple, str] = {}
    random_pairs = set()
    for row in labels:
        label = (row.get("human_label") or "").strip()
        if not label:
            continue
        if label not in LABELS:
            raise ValueError(f"Invalid label '{label}' in {row.get('sample_id')}")
        if not (row.get("labeler_name") or "").strip() or not (row.get("label_date") or "").strip():
            raise ValueError(f"{row.get('sample_id')} needs labeler_name and label_date")
        key = (row["fotmob_player_id"], row["candidate_tm_player_id"])
        if pairs.get(key, label) != label:
            raise ValueError(f"Conflicting labels for pair {key}")
        pairs[key] = label
        if row.get("stratum") == RANDOM_STRATUM:
            random_pairs.add(key)
    if not pairs:
        return {"status": "NOT_EVALUATED", "reason": "No human labels yet. No precision or recall can be claimed.", "labeled_pairs": 0}
    decided = {k: v for k, v in pairs.items() if v != "UNSURE"}
    predicted_match = lambda k: mapped.get(k[0]) == k[1]  # noqa: E731
    tp = sum(1 for k, v in decided.items() if v == "MATCH" and predicted_match(k))
    fp = sum(1 for k, v in decided.items() if v == "NON_MATCH" and predicted_match(k))
    fn = sum(1 for k, v in decided.items() if v == "MATCH" and not predicted_match(k))
    tn = sum(1 for k, v in decided.items() if v == "NON_MATCH" and not predicted_match(k))
    random_decided = {k: decided[k] for k in random_pairs if k in decided and predicted_match(k)}
    random_ok = sum(1 for v in random_decided.values() if v == "MATCH")
    return {
        "status": "EVALUATED", "labeled_pairs": len(pairs), "unsure_excluded": len(pairs) - len(decided),
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "sample_precision": tp / (tp + fp) if tp + fp else None, "sample_recall": tp / (tp + fn) if tp + fn else None,
        "metric_note": "Sample precision and recall mix deliberately hard strata, so they do not describe the population. Use the random-stratum estimate for automatic mappings.",
        "auto_exact_random": {
            "decided": len(random_decided), "correct": random_ok,
            "precision": random_ok / len(random_decided) if random_decided else None,
            "precision_95pct_lower_bound": round(lower_bound(random_ok, len(random_decided)), 5),
        },
        "false_positive_pairs": sorted(f"{k[0]}:{k[1]}" for k, v in decided.items() if v == "NON_MATCH" and predicted_match(k)),
    }


def main() -> None:
    crosswalk = pq.read_table(sys.argv[1], columns=["fotmob_player_id", "transfermarkt_player_id"]).to_pylist()
    mapped = {r["fotmob_player_id"]: r["transfermarkt_player_id"] for r in crosswalk if r["transfermarkt_player_id"]}
    path = ROOT / "data/phase_03/review/validation_sample_for_labeling.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        result = evaluate(list(csv.DictReader(handle)), mapped)
    output = Path(sys.argv[1]).parent / "matching_evaluation.json"
    output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
