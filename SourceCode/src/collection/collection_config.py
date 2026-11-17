"""Load and validate the bounded pilot configuration."""
from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SEASONS = (
    "2019/2020", "2020/2021", "2021/2022",
    "2022/2023", "2023/2024", "2024/2025",
)


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "configs/pilot_config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Pilot config must be a mapping")
    config["seasons"] = {str(k): int(v) for k, v in config["seasons"].items()}
    if tuple(config["seasons"]) != EXPECTED_SEASONS or config["league_id"] != 47:
        raise ValueError("Competition or six-season scope changed")
    if set(config["deep_seasons"]) | set(config["light_seasons"]) != set(EXPECTED_SEASONS):
        raise ValueError("Sampling seasons do not cover the six-season scope")
    if set(config["deep_seasons"]) & set(config["light_seasons"]):
        raise ValueError("Deep and light seasons overlap")
    if not 0 < config["request_budget"] <= 40 or not 0 < config["pilot_execution_limit"] <= 12:
        raise ValueError("Pilot request limits exceeded")
    for key in ("raw_dir", "normalized_dir", "report_dir", "log_path"):
        p = Path(config[key])
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"{key} must be a relative path within the project")
    return config
