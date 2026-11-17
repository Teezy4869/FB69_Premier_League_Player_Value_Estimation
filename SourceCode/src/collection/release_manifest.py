"""Physical release inventory and verification, shared by versioned release builders."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.foundation import atomic_write

MANIFEST_PATH = "metadata/release_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def physical_inventory(release_dir: Path) -> list[dict]:
    """Every regular release file except the self-referential manifest is inventoried."""
    rows = []
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(release_dir).as_posix()
        if rel == MANIFEST_PATH:
            continue
        row = {"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path),
               "file_type": path.suffix.lower() or "none"}
        if path.suffix.lower() == ".parquet":
            meta = pq.read_metadata(path)
            row.update({"physical_rows": meta.num_rows,
                        "schema_sha256": hashlib.sha256(meta.schema.to_arrow_schema().serialize().to_pybytes()).hexdigest(),
                        "schema_columns": meta.schema.names,
                        "schema_version": "3.1"})
        rows.append(row)
    return rows


def build_manifest(release_dir: Path, *, version: str, parent_version: str,
                   seasons: list[str], quality_status: str, known_limitations: list[str],
                   reproduction_commands: list[str], created_at: str | None = None) -> dict:
    files = physical_inventory(release_dir)
    tables = [{"table": Path(row["path"]).stem, "path": row["path"],
               "physical_rows": row["physical_rows"], "rows": row["physical_rows"],
               "bytes": row["bytes"], "sha256": row["sha256"],
               "schema_version": row["schema_version"], "schema_sha256": row["schema_sha256"]}
              for row in files if row["file_type"] == ".parquet"]
    return {"dataset_version": version, "parent_release_version": parent_version,
            "created_at_utc": created_at or datetime.now(timezone.utc).isoformat(),
            "source": "FotMob saved historical responses; offline rebuild",
            "competition": "English Premier League", "competition_id": "47",
            "seasons": seasons, "quality_status": quality_status,
            "release_validation_status": quality_status,
            "known_limitations": known_limitations,
            "reproduction_commands": reproduction_commands,
            "inventory_policy": "All regular release files are checksummed except metadata/release_manifest.json, whose self-hash would be circular.",
            "inventory_exclusions": [MANIFEST_PATH],
            "total_files": len(files) + 1, "checksummed_files": len(files),
            "parquet_tables": len(tables), "files": files, "tables": tables}


def write_manifest(release_dir: Path, **kwargs) -> dict:
    manifest = build_manifest(release_dir, **kwargs)
    path = release_dir / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    verify_manifest(release_dir)
    return manifest


def verify_manifest(release_dir: Path) -> dict:
    path = release_dir / MANIFEST_PATH
    manifest = json.loads(path.read_text(encoding="utf-8"))
    actual = {r["path"]: r for r in physical_inventory(release_dir)}
    declared = {r["path"]: r for r in manifest["files"]}
    if set(actual) != set(declared):
        raise ValueError(f"RELEASE_INVENTORY_MISMATCH missing={sorted(set(actual)-set(declared))} stale={sorted(set(declared)-set(actual))}")
    if manifest["total_files"] != len(actual) + 1 or manifest["checksummed_files"] != len(actual):
        raise ValueError("RELEASE_FILE_COUNT_MISMATCH")
    for rel, row in actual.items():
        stored = declared[rel]
        if row["sha256"] != stored["sha256"] or row["bytes"] != stored["bytes"]:
            raise ValueError(f"RELEASE_CHECKSUM_MISMATCH:{rel}")
        if row.get("physical_rows") != stored.get("physical_rows"):
            raise ValueError(f"RELEASE_ROW_COUNT_MISMATCH:{rel}")
        if row.get("schema_sha256") != stored.get("schema_sha256"):
            raise ValueError(f"RELEASE_SCHEMA_MISMATCH:{rel}")
    actual_tables = {rel: row for rel, row in actual.items() if row["file_type"] == ".parquet"}
    declared_tables = {r["path"]: r for r in manifest["tables"]}
    if set(actual_tables) != set(declared_tables) or manifest["parquet_tables"] != len(actual_tables):
        raise ValueError("RELEASE_PARQUET_INVENTORY_MISMATCH")
    for rel, row in actual_tables.items():
        if declared_tables[rel]["rows"] != row["physical_rows"] or declared_tables[rel]["sha256"] != row["sha256"]:
            raise ValueError(f"RELEASE_TABLE_MISMATCH:{rel}")
    return manifest
