"""Shared helpers for Phase 3 Transfermarkt scripts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/phase_03_tm_source.yaml"
FOTMOB_RELEASE = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
EXPECTED_FOTMOB_MANIFEST_SHA256 = "9aa00b227b2dbf9a6004258ff94c25e825d7c5cfd45a365cb94f5f98863fbf93"


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def verify_fotmob_unchanged(release: Path = FOTMOB_RELEASE) -> dict:
    """Recompute every manifest hash. Raises if the frozen FotMob release has changed."""
    manifest_path = release / "metadata/release_manifest.json"
    manifest_sha = file_hash(manifest_path)
    if manifest_sha != EXPECTED_FOTMOB_MANIFEST_SHA256:
        raise RuntimeError(f"FotMob manifest changed: {manifest_sha}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = [e["path"] for e in manifest["files"] if file_hash(release / e["path"]) != e["sha256"]]
    if bad:
        raise RuntimeError(f"FotMob files changed: {bad}")
    return {"files_checked": len(manifest["files"]), "mismatches": 0, "manifest_sha256": manifest_sha}
