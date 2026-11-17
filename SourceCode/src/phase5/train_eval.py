"""Phase 5 step 03: nested-CV training and evaluation of the single main model (LightGBM, ln target).

Runs, all from configs/phase_05_model.yaml:
  primary       Repeated StratifiedGroupKFold by player, stratified on log-target quantile bins
  forward       forward chaining by season (train on earlier seasons only)
  sensitivity   primary design re-run without the P4-B01 identity-sensitive rows (ODR-08)
Every fold tunes on its own training rows only (inner GroupKFold by player). Persistence is the untrained reference.

Usage: python -I src/phase5/train_eval.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from lightgbm import LGBMRegressor  # noqa: E402
from sklearn.model_selection import GridSearchCV, GroupKFold, StratifiedGroupKFold  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase5 import features as fx  # noqa: E402

INPUT = fx.OUTPUT / "model_input.parquet"
OUTPUT = ROOT / "data/phase_05/results/run_v1"


def metrics(y_log: np.ndarray, p_log: np.ndarray) -> dict:
    """mae_log, rmse_log (ln scale) and mdape_eur (%, back-transformed)."""
    e = p_log - y_log
    y, p = np.exp(y_log), np.exp(p_log)
    return {"n": int(len(e)), "mae_log": float(np.mean(np.abs(e))), "rmse_log": float(np.sqrt(np.mean(e ** 2))),
            "mdape_eur": float(np.median(np.abs(p - y) / y) * 100)}


def prepare(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    X = df[fx.feature_columns(cfg)].copy()
    X["has_prev_value"] = X["has_prev_value"].astype(int)
    return X


def tuned_fit_predict(X_tr, y_tr, g_tr, X_te, cfg: dict) -> tuple[np.ndarray, dict]:
    t = cfg["evaluation"]["tuning"]
    search = GridSearchCV(LGBMRegressor(**t["fixed"]), t["grid"], cv=GroupKFold(n_splits=t["inner_n_splits"]),
                          scoring="neg_mean_absolute_error", n_jobs=-1, refit=True)
    search.fit(X_tr, y_tr, groups=g_tr)
    return search.predict(X_te), search.best_params_


def run_primary(df: pd.DataFrame, cfg: dict, label: str) -> tuple[pd.DataFrame, list[dict]]:
    ev = cfg["evaluation"]["primary"]
    X, y, g = prepare(df, cfg), df["log_target"].to_numpy(), df["canonical_player_id"].to_numpy()
    bins = pd.qcut(df["log_target"], ev["n_bins"], labels=False).to_numpy()
    preds, params = [], []
    for repeat, seed in enumerate(ev["seeds"][: ev["n_repeats"]]):
        cv = StratifiedGroupKFold(n_splits=ev["n_splits"], shuffle=True, random_state=seed)
        for fold, (tr, te) in enumerate(cv.split(X, bins, g)):
            assert not set(g[tr]) & set(g[te]), "player in train and test"
            p, best = tuned_fit_predict(X.iloc[tr], y[tr], g[tr], X.iloc[te], cfg)
            preds.append(pd.DataFrame({"row": te, "repeat": repeat, "fold": fold, "pred_log": p}))
            params.append({"run": label, "repeat": repeat, "fold": fold, **best})
            print(f"{label} repeat {repeat} fold {fold} done {datetime.now(timezone.utc):%H:%M:%S}", flush=True)
    out = pd.concat(preds, ignore_index=True)
    assert (out.groupby("repeat")["row"].nunique() == len(df)).all(), "a row was not predicted exactly once per repeat"
    return out, params


def run_forward(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, list[dict]]:
    X, y, g = prepare(df, cfg), df["log_target"].to_numpy(), df["canonical_player_id"].to_numpy()
    preds, params = [], []
    for test_season in cfg["evaluation"]["supplementary"]["test_seasons"]:
        tr, te = np.where(df["season"] < test_season)[0], np.where(df["season"] == test_season)[0]
        p, best = tuned_fit_predict(X.iloc[tr], y[tr], g[tr], X.iloc[te], cfg)
        preds.append(pd.DataFrame({"row": te, "repeat": 0, "fold": test_season, "pred_log": p}))
        params.append({"run": "forward", "fold": test_season, "train_rows": len(tr), **best})
        print(f"forward {test_season} done {datetime.now(timezone.utc):%H:%M:%S}", flush=True)
    return pd.concat(preds, ignore_index=True), params


def summarize(df: pd.DataFrame, preds: pd.DataFrame, cfg: dict) -> dict:
    """Metrics per repeat (mean, sd across repeats), overall and per report group, with persistence on rows that have it."""
    p = preds.merge(df.reset_index(drop=True).rename_axis("row").reset_index(), on="row")
    groups = cfg["report_groups"]

    def block(frame: pd.DataFrame) -> dict:
        per = [metrics(f["log_target"].to_numpy(), f["pred_log"].to_numpy()) for _, f in frame.groupby("repeat")]
        out = {k: float(np.mean([m[k] for m in per])) for k in ("mae_log", "rmse_log", "mdape_eur")}
        out |= {f"{k}_sd": float(np.std([m[k] for m in per])) for k in ("mae_log", "rmse_log", "mdape_eur")} if len(per) > 1 else {}
        out["n"] = per[0]["n"]
        has = frame[frame["has_prev_value"]]
        if len(has):
            r0 = has[has["repeat"] == has["repeat"].min()]
            out["persistence"] = metrics(r0["log_target"].to_numpy(), r0["log_prev_value"].to_numpy())
            out["model_on_persistence_rows"] = {k: float(np.mean([metrics(f["log_target"].to_numpy(), f["pred_log"].to_numpy())[k] for _, f in has.groupby("repeat")])) for k in ("mae_log", "rmse_log", "mdape_eur")}
        return out

    res = {"overall": block(p)}
    for gcol in groups:
        res[gcol] = {str(k): block(f) for k, f in p.groupby(gcol, observed=True)}
    return res


def main() -> None:
    cfg = fx.load_config()
    df = pd.read_parquet(INPUT).sort_values(fx.KEY).reset_index(drop=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results, all_params = {}, []
    for label, frame in (("primary", df), ("sensitivity_without_identity_rows", df[~df["identity_sensitive"]].reset_index(drop=True))):
        preds, params = run_primary(frame, cfg, label)
        all_params += params
        results[label] = summarize(frame, preds, cfg)
        if label == "primary":
            preds.merge(frame[fx.KEY].rename_axis("row").reset_index(), on="row").to_parquet(OUTPUT / "oof_predictions_primary.parquet", index=False)
    preds, params = run_forward(df, cfg)
    all_params += params
    results["forward"] = summarize(df, preds, cfg)
    results["forward_by_test_season"] = {s: metrics(f["log_target"].to_numpy(), f["pred_log"].to_numpy()) for s, f in preds.merge(df.rename_axis("row").reset_index(), on="row").groupby("season")}
    preds.merge(df[fx.KEY].rename_axis("row").reset_index(), on="row").to_parquet(OUTPUT / "predictions_forward.parquet", index=False)
    pd.DataFrame(all_params).to_csv(OUTPUT / "best_params.csv", index=False)
    write_json(OUTPUT / "metrics.json", results)
    write_json(OUTPUT / "manifest.json", {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "config_version": cfg["config_version"],
                                          "code": "src/phase5/train_eval.py", "input_sha256": file_hash(INPUT), "config_sha256": file_hash(fx.CONFIG)})
    o = results["primary"]["overall"]
    print({k: round(v, 4) if isinstance(v, float) else v for k, v in o.items()})


if __name__ == "__main__":
    main()
