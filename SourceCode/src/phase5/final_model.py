"""Holdout step 2: fit the final model once on all development rows, exactly as pre-registered.

Verifies the signed freeze manifest first, then reuses the frozen `prepare` and `tuned_fit_predict` logic
(GridSearchCV + GroupKFold by player). Writes the model and its SHA-256. Refuses to overwrite an existing model.

Usage: python -I src/phase5/final_model.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from lightgbm import LGBMRegressor  # noqa: E402
from sklearn.model_selection import GridSearchCV, GroupKFold  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase5 import features as fx  # noqa: E402
from src.phase5 import train_eval as te  # noqa: E402

MANIFEST = ROOT / "reports/phase_05/holdout/holdout_freeze_manifest.json"
OUTPUT = ROOT / "data/phase_05/final_model/final_model_v1"


def verify_freeze(path: Path = MANIFEST) -> dict:
    m = json.loads(path.read_text(encoding="utf-8"))
    if m["status"] != "FROZEN_OWNER_SIGNED":
        raise RuntimeError("Pre-registration not signed")
    bad = [f for f, h in m["files"].items() if file_hash(ROOT / f) != h]
    if bad:
        raise RuntimeError(f"Frozen files changed: {bad}")
    return m


def main() -> None:
    verify_freeze()
    model_path = OUTPUT / "final_model.txt"
    if model_path.exists():
        raise RuntimeError("Final model already exists; it is fitted once")
    cfg = fx.load_config()
    df = pd.read_parquet(te.INPUT).sort_values(fx.KEY).reset_index(drop=True)
    X, y, g = te.prepare(df, cfg), df["log_target"].to_numpy(), df["canonical_player_id"].to_numpy()
    t = cfg["evaluation"]["tuning"]
    search = GridSearchCV(LGBMRegressor(**t["fixed"]), t["grid"], cv=GroupKFold(n_splits=t["inner_n_splits"]),
                          scoring="neg_mean_absolute_error", n_jobs=-1, refit=True).fit(X, y, groups=g)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    search.best_estimator_.booster_.save_model(str(model_path))
    write_json(OUTPUT / "manifest.json", {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code": "src/phase5/final_model.py",
                                          "freeze_manifest_sha256": file_hash(MANIFEST), "training_rows": len(df), "training_players": int(df.canonical_player_id.nunique()),
                                          "feature_order": list(X.columns), "best_params": search.best_params_, "inner_cv_mae_log": -float(search.best_score_),
                                          "model_sha256": file_hash(model_path)})
    print(search.best_params_, round(-search.best_score_, 4))


if __name__ == "__main__":
    main()
