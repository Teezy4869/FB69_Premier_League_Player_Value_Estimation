"""Phase 5 step 02: model input table. One row per modeling player-season (DEF/MID/FWD, usable target).

Reads the verified release and the season-start previous value; writes features, target, keys and report-group
columns. No imputation: nulls stay null. The release is read only.

Usage: python -I src/phase5/features.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, write_json  # noqa: E402
from src.phase4 import profiling  # noqa: E402
from src.phase4.bivariate import identity_sensitivity_mask  # noqa: E402

CONFIG = ROOT / "configs/phase_05_model.yaml"
OUTPUT = ROOT / "data/phase_05/features/model_input_v1"
KEY = ["canonical_player_id", "season"]


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def per90(total: pd.Series, minutes: pd.Series) -> pd.Series:
    """total * 90 / minutes; null when either is null or minutes is 0."""
    m = minutes.where(minutes > 0)
    return total.astype("float64") * 90.0 / m.astype("float64")


def feature_columns(cfg: dict) -> list[str]:
    f = cfg["features"]
    return f["categorical"] + f["numeric_from_release"] + list(f["derived_per90"]) + f["previous_value"]


def build(cfg: dict) -> tuple[pd.DataFrame, dict]:
    df, _, _, verification = profiling.load_verified()
    prev = pd.read_parquet(ROOT / cfg["previous_value"]["source"])
    assert set(prev["prev_rule_version"]) == {cfg["previous_value"]["rule_version"]}
    pop = cfg["population"]
    df = df.assign(identity_sensitive=identity_sensitivity_mask(df).astype(bool))
    m = df[df["position_group_season"].isin(pop["positions"]) & df["target_usable"].astype(bool)].copy()
    before = len(m)
    m = m.merge(prev[KEY + ["prev_market_value", "prev_valuation_date", "target_before_season_start"]], on=KEY, how="left", validate="one_to_one")
    assert len(m) == before, "join changed row count"
    for name, total in cfg["features"]["derived_per90"].items():
        m[name] = per90(m[total], m["m_minutes_played"])
    m["has_prev_value"] = m["prev_market_value"].notna()
    m["log_prev_value"] = np.log(m["prev_market_value"].astype("float64"))
    m["log_target"] = np.log(m[cfg["target"]["column"]].astype("float64"))
    m["minutes_900_plus"] = m["m_minutes_played"] >= 900
    m["target_before_season_start"] = m["target_before_season_start"].astype(bool)
    m["position_group_season"] = m["position_group_season"].astype("category")
    cols = KEY + [cfg["target"]["column"], "log_target"] + feature_columns(cfg) + [g for g in cfg["report_groups"] if g not in ("position_group_season", "has_prev_value")]
    out = m[list(dict.fromkeys(cols))].sort_values(KEY).reset_index(drop=True)
    return out, {"release_sha256": verification["sha256"], "previous_value_sha256": file_hash(ROOT / cfg["previous_value"]["source"]), "config_sha256": file_hash(CONFIG)}


def check(out: pd.DataFrame, cfg: dict) -> dict:
    assert not out.duplicated(KEY).any(), "duplicate player-season"
    assert out["log_target"].notna().all() and np.isfinite(out["log_target"]).all()
    assert set(out["position_group_season"].astype(str)) <= set(cfg["population"]["positions"])
    assert (out["has_prev_value"] == out["log_prev_value"].notna()).all()
    for c in feature_columns(cfg):
        assert c in out, f"missing feature {c}"
    banned = [c for c in out if c.startswith("s_") or c.startswith("target_audit") or c in ("season_id",)]
    assert not banned, f"banned columns present: {banned}"
    feats = feature_columns(cfg)
    return {"rows": len(out), "players": int(out["canonical_player_id"].nunique()), "features": len(feats),
            "no_prev_value": int((~out["has_prev_value"]).sum()), "target_before_season_start": int(out["target_before_season_start"].sum()),
            "identity_sensitive": int(out["identity_sensitive"].sum()),
            "null_rate": {c: round(float(out[c].isna().mean()), 4) for c in feats if out[c].isna().any()}}


def main() -> None:
    cfg = load_config()
    out, meta = build(cfg)
    checks = check(out, cfg)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "model_input.parquet"
    out.to_parquet(path, index=False)
    write_json(OUTPUT / "manifest.json", {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "config_version": cfg["config_version"],
                                          "code": "src/phase5/features.py", "inputs": meta, "output_sha256": file_hash(path), "checks": checks})
    print(checks)


if __name__ == "__main__":
    main()
