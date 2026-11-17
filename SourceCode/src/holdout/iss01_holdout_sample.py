"""Holdout (D10) ISS-01: owner labelling file for 2025/26 identity mappings. Contains NO value or target column.

Rows:
  NEW_AUTO_EXACT   every AUTO_EXACT mapping not already in the development crosswalk with the same TM id (census)
  REVIEW_REQUIRED  every identity the rules left unresolved; top candidates for the owner to confirm or reject
Same evidence columns as the development labelling files. Shuffled with a fixed seed.

Usage: python -I src/holdout/iss01_holdout_sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402

RUN = ROOT / "data/holdout_2025_26/entity_resolution/matching_v2_1__reviews_none"
DEV = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
OUT = ROOT / "reports/phase_05/holdout/iss01_holdout_labeling.csv"
COLS = ["fotmob_player_id", "candidate_tm_player_id", "fotmob_names", "fotmob_dob", "fotmob_nationality", "fotmob_club_seasons",
        "candidate_name", "candidate_dob", "candidate_nationality", "candidate_club_seasons", "candidate_url"]
BANNED = ("value", "market", "target", "price", "eur")


def build() -> pd.DataFrame:
    cw = pd.read_parquet(RUN / "player_crosswalk.parquet")
    cand = pd.read_parquet(RUN / "matching_candidates.parquet").rename(columns={"tm_player_id": "candidate_tm_player_id", "tm_name": "candidate_name", "tm_dob": "candidate_dob",
                                                                                "tm_nationality": "candidate_nationality", "tm_club_season_labels": "candidate_club_seasons", "tm_url": "candidate_url"})
    dev = pd.read_parquet(DEV)[["fotmob_player_id", "transfermarkt_player_id"]]
    j = cw.merge(dev, on="fotmob_player_id", how="left", suffixes=("", "_dev"))
    new = j[(j.match_status == "AUTO_EXACT") & (j.transfermarkt_player_id != j.transfermarkt_player_id_dev)]
    a = cand.merge(new[["fotmob_player_id", "transfermarkt_player_id"]], left_on=["fotmob_player_id", "candidate_tm_player_id"], right_on=["fotmob_player_id", "transfermarkt_player_id"])
    a = a.assign(sample_reason="NEW_AUTO_EXACT", decision_field="human_label")
    review_ids = cw.loc[cw.match_status.isin(["REVIEW_REQUIRED", "AMBIGUOUS"]), "fotmob_player_id"]
    b = cand[cand.fotmob_player_id.isin(review_ids) & (cand.candidate_rank <= 3)].assign(sample_reason="REVIEW_REQUIRED", decision_field="human_label")
    out = pd.concat([a[COLS + ["sample_reason"]], b[COLS + ["sample_reason", "candidate_rank"]]], ignore_index=True)
    out["sample_id"] = out.sample_reason + ":" + out.fotmob_player_id + ":" + out.candidate_tm_player_id
    for c in ("human_label", "labeler_name", "label_date", "label_notes"):
        out[c] = ""
    out = out.sample(frac=1, random_state=0).reset_index(drop=True)
    assert out.sample_id.is_unique and len(a) == len(new)
    assert not [c for c in out.columns if any(w in c.lower() for w in BANNED)], "value column in labelling file"
    return out[["sample_id", "sample_reason", "candidate_rank", *COLS, "human_label", "labeler_name", "label_date", "label_notes"]]


def main() -> None:
    out = build()
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    write_json(OUT.with_suffix(".manifest.json"), {"rows": len(out), "by_reason": out.sample_reason.value_counts().to_dict(),
               "identities": int(out.fotmob_player_id.nunique()), "source_run": RUN.relative_to(ROOT).as_posix(), "output_sha256": file_hash(OUT)})
    print(len(out), out.sample_reason.value_counts().to_dict(), out.fotmob_player_id.nunique())


if __name__ == "__main__":
    main()
