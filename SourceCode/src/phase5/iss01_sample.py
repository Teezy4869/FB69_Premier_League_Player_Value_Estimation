"""Phase 5: owner labelling sample for ISS-01 (identity mapping precision).

Draws from the existing, unlabelled Phase 3/rs5 sample `data/research_rs5/review/validation_sample_for_labeling.csv`,
stratum AUTO_EXACT_RANDOM only (a random draw of automatic matches), so every evidence column is reused unchanged:
  - all pairs in that stratum that belong to the P4-B01 identity-sensitive subset
  - a seeded random draw of the other pairs, to make 100 rows in total
Plus the identity-sensitive worst-error players from the step 03 error analysis that the source sample covers.
The source file is read only. Labels go in `human_label`: CORRECT, WRONG or UNSURE.

Usage: python -I src/phase5/iss01_sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase4 import profiling  # noqa: E402
from src.phase4.bivariate import identity_sensitivity_mask  # noqa: E402

SOURCE = ROOT / "data/research_rs5/review/validation_sample_for_labeling.csv"
OUTPUT = ROOT / "reports/phase_05/step_04"
TOTAL, SEED = 100, 0
WORST_ERROR_SENSITIVE = ["1086647", "1113790", "1324871"]  # fotmob ids, step 03 error analysis section 4


def build() -> pd.DataFrame:
    src = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    df = profiling.load_verified()[0]
    pairs = df[identity_sensitivity_mask(df)][["fotmob_player_id", "transfermarkt_player_id"]].drop_duplicates()
    key = set(zip(pairs.fotmob_player_id, pairs.transfermarkt_player_id))
    rnd = src[src.stratum == "AUTO_EXACT_RANDOM"].copy()
    rnd["identity_sensitive"] = [(f, t) in key for f, t in zip(rnd.fotmob_player_id, rnd.candidate_tm_player_id)]
    sens, other = rnd[rnd.identity_sensitive], rnd[~rnd.identity_sensitive]
    picked = pd.concat([sens, other.sample(TOTAL - len(sens), random_state=SEED)])
    picked["sample_reason"] = "RANDOM_AUTO_EXACT"
    worst = src[src.fotmob_player_id.isin(WORST_ERROR_SENSITIVE) & ~src.sample_id.isin(picked.sample_id)].drop_duplicates("fotmob_player_id").copy()
    worst["identity_sensitive"], worst["sample_reason"] = True, "WORST_ERROR_STEP03"
    out = pd.concat([picked, worst]).sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle so the labeller can't see the stratum order
    assert out.sample_id.is_unique and out.human_label.eq("").all()
    return out


def main() -> None:
    out = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "iss01_identity_labeling_sample.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")
    write_json(OUTPUT / "iss01_identity_labeling_sample_manifest.json", {"source": str(SOURCE.relative_to(ROOT)), "source_sha256": file_hash(SOURCE), "seed": SEED,
               "rows": len(out), "by_reason": out.sample_reason.value_counts().to_dict(), "identity_sensitive": int(out.identity_sensitive.sum()), "output_sha256": file_hash(path)})
    print(len(out), out.sample_reason.value_counts().to_dict(), int(out.identity_sensitive.sum()))


if __name__ == "__main__":
    main()
