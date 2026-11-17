"""Holdout (D10) step 4b: build the 2025/26 holdout model input from raw FotMob + the existing Transfermarkt snapshot.

Same rules as development, reusing the frozen code:
  FotMob tables    src/holdout/fotmob_tables.py (reproduces release v3.1 2024/25 exactly)
  identity         src/phase3/entity_resolution.run (matching_v2_1); its TM season filter 2019-2024 is widened to
                   2019-2025 through a logged SQL substitution, nothing else changes; no automated adjudication
  target           src/phase3/season_targets.select_target, cutoff = verified 2025/26 season end
  previous value   src/phase5/season_start_prev_value.decide, first match = verified 2025/26 first match
  features         src/phase5/features.per90 / feature_columns, config phase5_model_v1
BLIND: this script prints and writes only counts, coverage, null rates and schema. It never prints a target
value, a previous value, a prediction or any distribution of them. It does not score anything (step 5).

Usage: python -I src/holdout/build_holdout.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.holdout import fotmob_tables as ft  # noqa: E402
from src.phase3 import entity_resolution as er  # noqa: E402
from src.phase3.season_targets import ELIGIBLE_CROSSWALK, HISTORY, select_target  # noqa: E402
from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase5 import features as fx  # noqa: E402
from src.phase5.final_model import verify_freeze  # noqa: E402
from src.phase5.season_start_prev_value import decide  # noqa: E402

SEASON, SEASON_ID = "2025/2026", "27110"
RAW = ROOT / "data/holdout_2025_26/fotmob/raw"
OUT = ROOT / "data/holdout_2025_26"
FM = OUT / "fotmob/release_v1"
DATES = yaml.safe_load((ROOT / "configs/phase_05_holdout_seasons.yaml").read_text(encoding="utf-8"))["seasons"][0]
assert DATES["verification_status"] == "VERIFIED" and DATES["season"] == SEASON
FIRST, END = date.fromisoformat(DATES["first_match_date"]), date.fromisoformat(DATES["season_end_date"])


def captures(endpoint: str) -> dict[str, tuple[dict, Path]]:
    out = {}
    for meta_path in (RAW / endpoint).glob("*/metadata.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body = meta_path.with_name("response.json")
        if file_hash(body) != meta["content_sha256"]:
            raise ValueError(f"RAW_CHECKSUM_MISMATCH {body}")
        out[json.dumps(meta["params"], sort_keys=True)] = (json.loads(body.read_text(encoding="utf-8")), body)
    return out


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def build_fotmob() -> dict:
    league = json.loads((RAW / "probe/leagues_2025_2026.json").read_text(encoding="utf-8"))
    details = {json.loads(k)["matchId"]: v for k, v in captures("matchDetails").items()}
    profiles = {json.loads(k)["id"]: v for k, v in captures("playerData").items()}
    stats = {json.loads(k)["playerId"]: v for k, v in captures("playerStats").items()}
    boards = {json.loads(k)["stat"]: v[0] for k, v in captures("leagueseasondeepstats").items()}
    pos_map, matches, teams, pma, pos = ft.position_map(), [], {}, [], []
    for f in league["fixtures"]["allMatches"]:
        fixture = {"match_id": str(f["id"]), "match_date_utc": f["status"]["utcTime"], "home_team_id": str(f["home"]["id"]), "away_team_id": str(f["away"]["id"]),
                   "competition_id": "47", "season_id": SEASON_ID, "season_label": SEASON}
        teams[fixture["home_team_id"]], teams[fixture["away_team_id"]] = f["home"]["name"], f["away"]["name"]
        payload, path = details[fixture["match_id"]]
        a, b, _ = ft.match_rows(payload, fixture, pos_map)
        pma += [{**r, "raw_path": rel(path)} for r in a]
        pos += b
        matches.append({**fixture, "match_status": "COMPLETED", "score": f["status"]["scoreStr"], "finished": True, "cancelled": False})
    assert len(matches) == 380
    population = ft.season_population(pma)
    modal, bv, rules = ft.modal_position(pos), ft.board_values(boards), ft.metric_rules()
    conf, players, pts, curated = [], [], [], []
    for pid in sorted(population, key=int):
        p = population[pid]
        prof, prof_path = profiles.get(pid, (None, None))
        st, st_path = stats.get(pid, (None, None))
        conf.append({"season_label": SEASON, "season_id": SEASON_ID, "player_id": pid, "player_name": p["player_name"], "confirmed_team_count": len(p["confirmed_team_ids"]),
                     "team_ids": "|".join(p["confirmed_team_ids"]), "team_names": "|".join(teams[t] for t in p["confirmed_team_ids"]),
                     "confirmed_appearance_count": p["confirmed_appearance_count"], "started_match_count": p["started_match_count"]})
        players.append({"player_id": pid, "lineup_name": p["player_name"], **ft.profile_fields(prof), "nationality_code": None,
                        "profile_raw_path": rel(prof_path) if prof_path else None})
        pts += [{"season_label": SEASON, "season_id": SEASON_ID, "player_id": pid, "team_id": t, "validation_status": "CONFIRMED"} for t in p["confirmed_team_ids"]]
        curated.append({"season_label": SEASON, "season_id": SEASON_ID, "player_id": pid, "confirmed_team_count": len(p["confirmed_team_ids"]),
                        "position_group_season": modal.get(pid, "UNKNOWN"), "stats_raw_path": rel(st_path) if st_path else None,
                        **ft.player_metrics(st, len(p["confirmed_team_ids"]), bv, pid, rules)})
    tables = {"normalized/matches": matches, "normalized/teams": [{"season_id": SEASON_ID, "season_label": SEASON, "team_id": t, "team_name": n} for t, n in sorted(teams.items())],
              "normalized/player_match_appearances": [{"season_label": SEASON, "season_id": SEASON_ID, **r} for r in pma],
              "normalized/historical_position_observations": [{"season_id": SEASON_ID, **r} for r in pos],
              "normalized/confirmed_appeared_player_seasons": conf, "normalized/players": players, "normalized/player_team_seasons": pts,
              "curated/confirmed_appeared_player_seasons": curated}
    hashes = {}
    for name, rows in tables.items():
        path = FM / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(path, index=False)
        hashes[f"{name}.parquet"] = file_hash(path)
    unmapped = Counter((r["source_field"], r["original_code"]) for r in pos if r["mapped_group"] == "UNMAPPED_NEW_CODE")
    summary = {"matches": len(matches), "player_matches": len(pma), "participation": dict(Counter(r["participation_status"] for r in pma)),
               "confirmed_appeared_player_seasons": len(conf), "profiles_missing": sum(pid not in profiles for pid in population),
               "stats_missing": sum(pid not in stats for pid in population), "boards": sorted(boards), "unmapped_position_codes": {f"{a}:{b}": n for (a, b), n in unmapped.items()},
               "position_group": dict(Counter(r["position_group_season"] for r in curated)), "multi_club": sum(r["confirmed_team_count"] > 1 for r in conf)}
    write_json(FM / "release_manifest.json", {"dataset_version": "fotmob_epl_2025_2026_holdout_v1", "season": SEASON, "season_id": SEASON_ID, "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "code_sha256": {rel(p): file_hash(p) for p in (ROOT / "src/holdout/fotmob_tables.py", ROOT / "src/holdout/build_holdout.py")}, "files": hashes, "summary": summary})
    return summary


class WidenedSeasons:
    """DuckDB connection whose SQL has the TM season range widened from 2019-2024 to 2019-2025. Logged."""
    def __init__(self, con):
        self.con, self.substitutions = con, 0

    def execute(self, sql, *args):
        if "BETWEEN 2019 AND 2024" in sql:
            self.substitutions += sql.count("BETWEEN 2019 AND 2024")
            sql = sql.replace("BETWEEN 2019 AND 2024", "BETWEEN 2019 AND 2025")
        return self.con.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self.con, name)


def match_identities() -> dict:
    config = yaml.safe_load(er.CONFIG_PATH.read_text(encoding="utf-8"))
    wrapped = {}
    er.FOTMOB_RELEASE = FM

    def connect(*a, **k):
        wrapped["con"] = WidenedSeasons(duckdb.connect(*a, **k))
        return wrapped["con"]
    er.duckdb = type("D", (), {"connect": staticmethod(connect), "__version__": duckdb.__version__})
    result = er.run(config, OUT / "entity_resolution", OUT / "review", adjudication_path=None)
    er.duckdb = duckdb
    return {"run_dir": rel(Path(result["run_dir"])), "sql_season_substitutions": wrapped["con"].substitutions,
            "status": dict(Counter(r["match_status"] for r in result["crosswalk"]))}


LABELS = ROOT / "reports/phase_05/holdout/iss01_holdout_labeling.csv"


def apply_labels(cw: pd.DataFrame, path: Path = LABELS) -> tuple[pd.DataFrame, dict]:
    """Owner-approved rule (2026-11-16): WRONG new AUTO_EXACT -> excluded; one CORRECT REVIEW_REQUIRED candidate -> MANUAL_CONFIRMED."""
    lab = pd.read_csv(path, dtype=str, keep_default_na=False)
    if not lab.human_label.isin(["CORRECT", "WRONG", "UNSURE"]).all() or (lab.labeler_name == "").any() or (lab.label_date == "").any():
        raise ValueError("Incomplete or invalid labels")
    cw = cw.copy()
    wrong = lab[(lab.sample_reason == "NEW_AUTO_EXACT") & (lab.human_label == "WRONG")]
    cw.loc[cw.index.isin(wrong.fotmob_player_id), "match_status"] = "OWNER_REJECTED"
    ok = lab[(lab.sample_reason == "REVIEW_REQUIRED") & (lab.human_label == "CORRECT")]
    if ok.fotmob_player_id.duplicated().any():
        raise ValueError("More than one CORRECT candidate for an identity")
    for r in ok.itertuples():
        if cw.loc[r.fotmob_player_id, "match_status"] not in ("REVIEW_REQUIRED", "AMBIGUOUS"):
            raise ValueError(f"{r.fotmob_player_id} is not a review identity")
        cw.loc[r.fotmob_player_id, ["transfermarkt_player_id", "match_status"]] = [r.candidate_tm_player_id, "MANUAL_CONFIRMED"]
    return cw, {"labels_sha256": file_hash(path), "owner_rejected": len(wrong), "manual_confirmed": len(ok),
                "unsure_new_auto_exact": int(((lab.sample_reason == "NEW_AUTO_EXACT") & (lab.human_label == "UNSURE")).sum())}


def build_model_input(run_dir: Path, labelled: bool = False) -> tuple[pd.DataFrame, dict]:
    cfg = fx.load_config()
    cw = pd.read_parquet(run_dir / "player_crosswalk.parquet").set_index("fotmob_player_id")
    label_info = None
    if labelled:
        cw, label_info = apply_labels(cw)
    cur = pd.read_parquet(FM / "curated/confirmed_appeared_player_seasons.parquet")
    players = pd.read_parquet(FM / "normalized/players.parquet").set_index("player_id")
    history = {}
    for tid, day, value, status, record in duckdb.sql(f"SELECT tm_player_id, valuation_date, market_value, quality_status, source_record_id FROM read_parquet('{HISTORY.as_posix()}')").fetchall():
        history.setdefault(tid, []).append({"valuation_date": day, "market_value": value, "quality_status": status, "source_record_id": record})
    rows = []
    for r in cur.to_dict("records"):
        c = cw.loc[r["player_id"]]
        tid = c["transfermarkt_player_id"] if c["match_status"] in ELIGIBLE_CROSSWALK else None
        t = select_target(history.get(tid, []), END, 90) if tid else {"market_value": None, "target_status": "TARGET_MISSING", "target_missing_reason": "NO_ELIGIBLE_MAPPING", "selected_valuation_date": None}
        p = decide(history.get(tid, []), FIRST) if tid else {"prev_market_value": None, "prev_status": "NO_TM_IDENTITY"}
        birth = players.loc[r["player_id"], "birth_date"]
        rows.append({**r, "canonical_player_id": c["canonical_player_id"], "season": SEASON, "transfermarkt_player_id": tid, "crosswalk_status": c["match_status"],
                     "target_market_value": t["market_value"], "target_status": t["target_status"], "target_missing_reason": t["target_missing_reason"], "target_valuation_date": t["selected_valuation_date"],
                     "prev_market_value": p["prev_market_value"], "prev_status": p["prev_status"],
                     "age_at_season_end_years": round((END - date.fromisoformat(birth)).days / 365.25, 2) if birth else None})
    df = pd.DataFrame(rows)
    pop = cfg["population"]
    m = df[df["position_group_season"].isin(pop["positions"]) & df["target_market_value"].notna()].copy()
    for name, total in cfg["features"]["derived_per90"].items():
        m[name] = fx.per90(m[total], m["m_minutes_played"])
    m["has_prev_value"] = m["prev_market_value"].notna()
    m["log_prev_value"] = np.log(m["prev_market_value"].astype("float64"))
    m["log_target"] = np.log(m["target_market_value"].astype("float64"))
    m["minutes_900_plus"] = m["m_minutes_played"] >= 900
    m["target_before_season_start"] = pd.to_datetime(m["target_valuation_date"]).dt.date < FIRST
    dev_players = set(pd.read_parquet(fx.OUTPUT / "model_input.parquet", columns=["canonical_player_id"])["canonical_player_id"])
    m["seen_in_development"] = m["canonical_player_id"].isin(dev_players)
    m["position_group_season"] = pd.Categorical(m["position_group_season"], categories=sorted(pop["positions"]))
    keep = fx.KEY + ["target_market_value", "log_target"] + fx.feature_columns(cfg) + ["minutes_900_plus", "target_before_season_start", "seen_in_development", "crosswalk_status", "transfermarkt_player_id"]
    out = m[keep].sort_values(fx.KEY).reset_index(drop=True)
    feats = fx.feature_columns(cfg)
    counts = {"player_seasons_total": len(df), "by_position": dict(Counter(df["position_group_season"])), "target_status_all_rows": dict(Counter(df["target_status"])),
              "goalkeepers_excluded": int((df["position_group_season"] == "GK").sum()), "unknown_position_excluded": int((df["position_group_season"] == "UNKNOWN").sum()),
              "outfield_without_usable_target": int((df["position_group_season"].isin(pop["positions"]) & df["target_market_value"].isna()).sum()),
              "model_rows": len(out), "model_players": int(out["canonical_player_id"].nunique()), "no_prev_value": int((~out["has_prev_value"]).sum()),
              "target_before_season_start": int(out["target_before_season_start"].sum()), "seen_in_development": int(out["seen_in_development"].sum()),
              "minutes_900_plus": int(out["minutes_900_plus"].sum()), "iss01_labels": label_info, "null_rate": {c: round(float(out[c].isna().mean()), 4) for c in feats if out[c].isna().any()}}
    return out, counts


def identity_consistency(run_dir: Path) -> dict:
    """Returning players: does the holdout mapping agree with the development crosswalk? Counts only."""
    dev = pd.read_parquet(ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet")[["fotmob_player_id", "transfermarkt_player_id", "match_status"]]
    new = pd.read_parquet(run_dir / "player_crosswalk.parquet")[["fotmob_player_id", "transfermarkt_player_id", "match_status"]]
    j = new.merge(dev, on="fotmob_player_id", suffixes=("", "_dev"))
    both = j[j["transfermarkt_player_id"].notna() & j["transfermarkt_player_id_dev"].notna()]
    return {"holdout_identities": len(new), "also_in_development_crosswalk": len(j), "both_mapped": len(both),
            "same_tm_id": int((both["transfermarkt_player_id"] == both["transfermarkt_player_id_dev"]).sum()),
            "different_tm_id": int((both["transfermarkt_player_id"] != both["transfermarkt_player_id_dev"]).sum())}


def main_labelled() -> None:
    """Rebuild the model input after ISS-01 labels; FotMob tables and the rule-based crosswalk are reused as built."""
    verify_freeze()
    run_dir = OUT / "entity_resolution/matching_v2_1__reviews_none"
    out, counts = build_model_input(run_dir, labelled=True)
    path = OUT / "model_input/holdout_model_input_v2.parquet"
    if path.exists():
        raise RuntimeError("v2 already built")
    out.to_parquet(path, index=False)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "supersedes": "holdout_model_input_v1.parquet", "model_input": counts,
              "model_input_sha256": file_hash(path), "freeze_manifest_sha256": file_hash(ROOT / "reports/phase_05/holdout/holdout_freeze_manifest.json")}
    write_json(OUT / "model_input/build_manifest_v2.json", report)
    print(json.dumps(report, indent=1, default=str))


def main() -> None:
    verify_freeze()
    fotmob = build_fotmob()
    identity = match_identities()
    run_dir = ROOT / identity["run_dir"]
    consistency = identity_consistency(run_dir)
    out, counts = build_model_input(run_dir)
    path = OUT / "model_input/holdout_model_input_v1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fotmob": fotmob, "identity": identity, "identity_consistency_with_development": consistency,
              "model_input": counts, "model_input_sha256": file_hash(path), "freeze_manifest_sha256": file_hash(ROOT / "reports/phase_05/holdout/holdout_freeze_manifest.json")}
    write_json(OUT / "model_input/build_manifest.json", report)
    print(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main_labelled() if "--labelled" in sys.argv else main()
