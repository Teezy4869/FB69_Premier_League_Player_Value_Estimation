"""Holdout (D10) step 5: score the frozen final model on 2025/26 ONCE, exactly as pre-registered (incl. Amendment 1).

Before reading any holdout target it verifies:
  - the signed freeze manifest (all SHA-256), the final model SHA-256, the holdout input v2 SHA-256
  - that no lock exists; it then creates the lock exclusively, so a second run is impossible.
If the run crashes after the lock is created, the lock stays: re-running needs an explicit owner decision.

Primary  ΔMAE = MAE(persistence) - MAE(model), ln scale, rows with a previous value; paired player bootstrap
         2,000 draws, seed 0. PASS lower > 0, FAIL upper < 0, else INCONCLUSIVE.
Secondary share within ±20% (ratio in [0.8, 1.2]) for 900+ minute rows; bootstrap 2,000, seed 0.
         PASS lower >= 0.60, FAIL upper < 0.60, else INCONCLUSIVE.

Usage (owner-authorized only): python -I src/holdout/score_holdout.py --i-am-authorized
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase5 import features as fx  # noqa: E402
from src.phase5.final_model import verify_freeze  # noqa: E402
from src.phase5.train_eval import metrics  # noqa: E402

MODEL_DIR = ROOT / "data/phase_05/final_model/final_model_v1"
INPUT = ROOT / "data/holdout_2025_26/model_input/holdout_model_input_v2.parquet"
INPUT_MANIFEST = ROOT / "data/holdout_2025_26/model_input/build_manifest_v2.json"
OUT = ROOT / "data/holdout_2025_26/scoring"
REPORT = ROOT / "reports/phase_05/holdout/HOLDOUT_RESULT.md"
LOCK = ROOT / "reports/phase_05/holdout/HOLDOUT_SCORED.lock"
DRAWS, SEED, THRESHOLD, BAND = 2000, 0, 0.60, (0.8, 1.2)
GROUPS = ["position_group_season", "has_prev_value", "seen_in_development", "minutes_900_plus", "target_before_season_start"]


def three_level(lower: float, upper: float, bound: float, pass_inclusive: bool) -> str:
    if (lower >= bound) if pass_inclusive else (lower > bound):
        return "PASS"
    return "FAIL" if upper < bound else "INCONCLUSIVE"


def paired_delta(y: np.ndarray, pred: np.ndarray, prev: np.ndarray, groups: np.ndarray) -> dict:
    """ΔMAE persistence - model, with a paired bootstrap over players (both errors resampled together)."""
    em, ep = np.abs(pred - y), np.abs(prev - y)
    players, inv = np.unique(groups, return_inverse=True)
    sm, sp, n = np.bincount(inv, em), np.bincount(inv, ep), np.bincount(inv)
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(players), size=(DRAWS, len(players)))
    boot = (sp[draws].sum(1) - sm[draws].sum(1)) / n[draws].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"n_rows": int(len(y)), "n_players": int(len(players)), "mae_model": float(em.mean()), "mae_persistence": float(ep.mean()),
            "delta_mae": float(ep.mean() - em.mean()), "ci95": [float(lo), float(hi)], "verdict": three_level(lo, hi, 0.0, pass_inclusive=False)}


def within_band(y: np.ndarray, pred: np.ndarray, groups: np.ndarray) -> dict:
    ratio = np.exp(pred - y)
    hit = ((ratio >= BAND[0]) & (ratio <= BAND[1])).astype(float)
    players, inv = np.unique(groups, return_inverse=True)
    sh, n = np.bincount(inv, hit), np.bincount(inv)
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(players), size=(DRAWS, len(players)))
    boot = sh[draws].sum(1) / n[draws].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"n_rows": int(len(y)), "share_within_20pct": float(hit.mean()), "ci95": [float(lo), float(hi)], "threshold": THRESHOLD,
            "verdict": three_level(lo, hi, THRESHOLD, pass_inclusive=True)}


def verify_inputs() -> None:
    verify_freeze()
    fm = json.loads((MODEL_DIR / "manifest.json").read_text(encoding="utf-8"))
    if file_hash(MODEL_DIR / "final_model.txt") != fm["model_sha256"]:
        raise RuntimeError("Final model changed")
    if file_hash(INPUT) != json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))["model_input_sha256"]:
        raise RuntimeError("Holdout input changed")


def main() -> None:
    if "--i-am-authorized" not in sys.argv:
        raise SystemExit("Scoring needs explicit owner authorization: pass --i-am-authorized")
    verify_inputs()
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # fails if already scored
    os.write(fd, json.dumps({"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input_sha256": file_hash(INPUT)}).encode())
    os.close(fd)

    import lightgbm as lgb
    cfg = fx.load_config()
    feats = fx.feature_columns(cfg)
    booster = lgb.Booster(model_file=str(MODEL_DIR / "final_model.txt"))
    assert booster.feature_name() == feats
    h = pd.read_parquet(INPUT)
    assert h["canonical_player_id"].is_unique and (h["season"] == "2025/2026").all()
    X = h[feats].copy()
    X["has_prev_value"] = X["has_prev_value"].astype(int)
    h["pred_log"] = booster.predict(X)
    y, g = h["log_target"].to_numpy(), h["canonical_player_id"].to_numpy()

    hp = h[h["has_prev_value"]]
    primary = paired_delta(hp["log_target"].to_numpy(), hp["pred_log"].to_numpy(), hp["log_prev_value"].to_numpy(), hp["canonical_player_id"].to_numpy())
    h9 = h[h["minutes_900_plus"]]
    secondary = within_band(h9["log_target"].to_numpy(), h9["pred_log"].to_numpy(), h9["canonical_player_id"].to_numpy())

    def block(f: pd.DataFrame) -> dict:
        out = metrics(f["log_target"].to_numpy(), f["pred_log"].to_numpy())
        p = f[f["has_prev_value"]]
        if len(p):
            out["persistence"] = metrics(p["log_target"].to_numpy(), p["log_prev_value"].to_numpy())
            out["model_on_persistence_rows"] = metrics(p["log_target"].to_numpy(), p["pred_log"].to_numpy())
        return out

    res = {"overall": block(h), "primary_vs_persistence": primary, "secondary_within_20pct_900min": secondary,
           "groups": {c: {str(k): block(f) for k, f in h.groupby(c, observed=True)} for c in GROUPS}}
    OUT.mkdir(parents=True, exist_ok=True)
    h[fx.KEY + ["log_target", "pred_log", "log_prev_value", *GROUPS]].to_parquet(OUT / "holdout_predictions.parquet", index=False)
    write_json(OUT / "holdout_metrics.json", res)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    lock.update({"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "metrics_sha256": file_hash(OUT / "holdout_metrics.json"),
                 "predictions_sha256": file_hash(OUT / "holdout_predictions.parquet"), "primary_verdict": primary["verdict"], "secondary_verdict": secondary["verdict"]})
    LOCK.write_text(json.dumps(lock, indent=1), encoding="utf-8")
    o = res["overall"]
    REPORT.write_text(f"""# 2025/26 Holdout Result (scored once, {lock['finished_utc']})

Pre-registration: `HOLDOUT_PREREGISTRATION.md` with Amendment 1. Freeze, model and input SHA-256 were verified before scoring. Lock: `HOLDOUT_SCORED.lock`.

## Primary: model vs persistence ({primary['n_rows']} rows with a previous value)

| MAE model | MAE persistence | ΔMAE | 95% CI | Verdict |
|---:|---:|---:|---|---|
| {primary['mae_model']:.3f} | {primary['mae_persistence']:.3f} | {primary['delta_mae']:.3f} | {primary['ci95'][0]:.3f} to {primary['ci95'][1]:.3f} | **{primary['verdict']}** |

## Secondary: within ±20%, 900+ minutes ({secondary['n_rows']} rows)

| Share | 95% CI | Threshold | Verdict |
|---:|---|---:|---|
| {secondary['share_within_20pct']:.1%} | {secondary['ci95'][0]:.1%} to {secondary['ci95'][1]:.1%} | 60% | **{secondary['verdict']}** |

## Overall ({o['n']} rows)

MAE log {o['mae_log']:.3f}, RMSE log {o['rmse_log']:.3f}, MdAPE {o['mdape_eur']:.1f}%. Group results: `data/holdout_2025_26/scoring/holdout_metrics.json`.

Reported as computed. Nothing may be changed in response to these results (pre-registration section 6).
""", encoding="utf-8")
    print(json.dumps({"primary": primary, "secondary": secondary}, indent=1))


if __name__ == "__main__":
    main()
