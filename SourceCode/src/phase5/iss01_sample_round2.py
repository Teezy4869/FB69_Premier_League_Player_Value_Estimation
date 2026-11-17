"""Phase 5: ISS-01 round 2 labelling sample. Every adjudicated mapping (AUTO_ADJUDICATED_*, 36 pairs) plus the two
worst-error identity-sensitive players not covered by round 1.

Evidence is reused from the existing sample where present; otherwise it is built from the verified release (FotMob
side) and the curated Transfermarkt tables (candidate side), in the same columns. Read-only on all sources.

Usage: python -I src/phase5/iss01_sample_round2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase4 import profiling  # noqa: E402
from src.phase5.iss01_sample import OUTPUT, SEED, SOURCE  # noqa: E402

TM = ROOT / "data/transfermarkt/curated/tm_r2_20260905"
ADJUDICATIONS = ROOT / "data/research_rs5/review/automated_adjudications_in_scope.csv"
EXTRA = ["1113790", "1324871"]  # step 03 worst-error identity-sensitive players missing from round 1


def built_rows(pairs: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Evidence rows for pairs absent from the existing sample. FotMob nationality is the present-day profile value."""
    tm = pd.read_parquet(TM / "tm_players.parquet").set_index("tm_player_id")
    tcs = pd.read_parquet(TM / "tm_player_club_seasons.parquet")
    rows = []
    for f, t, reason in pairs.itertuples(index=False):
        mine = df[df.fotmob_player_id == f].sort_values("season")
        seasons = set(mine.season)
        cand = tcs[(tcs.tm_player_id == t) & tcs.season_label.isin(seasons)].sort_values("season_label")
        p = tm.loc[t] if t in tm.index else None
        rows.append({"sample_id": f"{reason}:{f}:{t}", "stratum": reason, "already_in_another_stratum": "False", "fotmob_player_id": f, "candidate_tm_player_id": t,
                     "fotmob_names": " | ".join(dict.fromkeys(mine[["fotmob_player_name", "fotmob_profile_name"]].stack().dropna())),
                     "fotmob_dob": str(mine.fotmob_birth_date.iloc[0] or ""), "fotmob_nationality": str(mine.nationality_profile_present_day.iloc[0] or ""),
                     "fotmob_club_seasons": " | ".join(f"{r.season}:{r.associated_team_names}" for r in mine.itertuples()),
                     "candidate_name": "" if p is None else p.player_name_raw, "candidate_dob": "" if p is None else str(p.date_of_birth or ""),
                     "candidate_nationality": "" if p is None else str(p.nationality or ""),
                     "candidate_club_seasons": " | ".join(f"{r.season_label}:{r.club_name}" for r in cand.itertuples()),
                     "candidate_url": "" if p is None else str(p.source_profile_url or "")})
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    src = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    df = profiling.load_verified()[0]
    adj = df[df.identity_evidence_tier.str.startswith("AUTO_ADJUDICATED")][["fotmob_player_id", "transfermarkt_player_id"]].drop_duplicates().assign(reason="ADJUDICATED_ALL")
    extra = df[df.fotmob_player_id.isin(EXTRA)][["fotmob_player_id", "transfermarkt_player_id"]].drop_duplicates().assign(reason="WORST_ERROR_STEP03")
    pairs = pd.concat([adj, extra]).drop_duplicates(["fotmob_player_id", "transfermarkt_player_id"])
    have = src.drop_duplicates(["fotmob_player_id", "candidate_tm_player_id"]).merge(pairs, left_on=["fotmob_player_id", "candidate_tm_player_id"], right_on=["fotmob_player_id", "transfermarkt_player_id"])
    missing = pairs[~pairs.set_index(["fotmob_player_id", "transfermarkt_player_id"]).index.isin(have.set_index(["fotmob_player_id", "candidate_tm_player_id"]).index)]
    out = pd.concat([have.drop(columns="transfermarkt_player_id"), built_rows(missing, df).assign(reason=missing.reason.to_numpy())], ignore_index=True)
    out = out.rename(columns={"reason": "sample_reason"}).assign(evidence_source=lambda x: x.sample_id.isin(src.sample_id).map({True: "EXISTING_SAMPLE", False: "BUILT_PHASE5"}))
    for c in ("human_label", "labeler_name", "label_date", "label_notes"):
        out[c] = ""
    out = out[list(src.columns) + ["sample_reason", "evidence_source"]].sample(frac=1, random_state=SEED).reset_index(drop=True)
    assert out.sample_id.is_unique and len(out) == len(pairs)
    return out


def main() -> None:
    out = build()
    path = OUTPUT / "iss01_identity_labeling_sample_round2.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")
    write_json(OUTPUT / "iss01_identity_labeling_sample_round2_manifest.json", {"sources": [str(p.relative_to(ROOT)) for p in (SOURCE, TM / "tm_players.parquet", TM / "tm_player_club_seasons.parquet")],
               "source_sha256": file_hash(SOURCE), "rows": len(out), "by_reason": out.sample_reason.value_counts().to_dict(),
               "by_evidence_source": out.evidence_source.value_counts().to_dict(), "output_sha256": file_hash(path)})
    print(len(out), out.sample_reason.value_counts().to_dict(), out.evidence_source.value_counts().to_dict())


if __name__ == "__main__":
    main()
