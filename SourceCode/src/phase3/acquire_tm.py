"""Acquire the owner-approved Transfermarkt CSV snapshot. Never scrapes; downloads only the pinned files.

All files are downloaded to a new incoming folder and verified. The snapshot folder is created only
if every file passes. Any mismatch stops the run, and an existing snapshot is never overwritten.

Usage: python -I src/phase3/acquire_tm.py
"""
from __future__ import annotations

import os
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, load_config, verify_fotmob_unchanged, write_json  # noqa: E402


class PinMismatch(RuntimeError):
    pass


def check_pin(path: Path, pin: dict, response_etag: str | None = None) -> dict:
    """Return pin evidence for one file. Raises PinMismatch on any disagreement."""
    size = path.stat().st_size
    sha256 = file_hash(path)
    md5 = file_hash(path, "md5")
    if size != pin["bytes"]:
        raise PinMismatch(f"{pin['name']}: size {size} != pinned {pin['bytes']}")
    if response_etag is not None and response_etag != pin["etag"]:
        raise PinMismatch(f"{pin['name']}: ETag {response_etag} != pinned {pin['etag']}")
    if pin["sha256"] is not None:
        if sha256 != pin["sha256"]:
            raise PinMismatch(f"{pin['name']}: SHA-256 {sha256} != pinned {pin['sha256']}")
        basis = "APPROVED_SHA256"
    else:
        if md5 != pin["etag"]:
            raise PinMismatch(f"{pin['name']}: MD5 {md5} != pinned ETag {pin['etag']}")
        basis = "SIZE_AND_MD5_ETAG_SHA256_RECORDED_AT_FIRST_ACQUISITION"
    return {"sha256": sha256, "md5": md5, "pin_basis": basis}


def main() -> int:
    config = load_config()
    snapshot_id = config["snapshot_id"]
    source_root = ROOT / "data/transfermarkt/source"
    snapshot = source_root / snapshot_id
    manifest_path = ROOT / "data/transfermarkt/metadata" / snapshot_id / "source_manifest.json"
    if snapshot.exists():
        print(f"STOP: snapshot already exists and will not be overwritten: {snapshot}")
        return 2
    fotmob = verify_fotmob_unchanged()
    incoming = source_root / f"_incoming_{uuid.uuid4().hex}"
    incoming.mkdir(parents=True)
    session = requests.Session()
    session.headers["User-Agent"] = "fb69-research-acquisition"
    records = []
    for pin in config["files"]:
        url = config["source"]["base_url"] + pin["name"]
        path = incoming / pin["name"]
        started = datetime.now(timezone.utc).isoformat()
        with session.get(url, stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for chunk in response.iter_content(1 << 20):
                    handle.write(chunk)
            etag = response.headers.get("ETag", "").strip('"') or None
            last_modified = response.headers.get("Last-Modified")
        try:
            evidence = check_pin(path, pin, etag)
        except PinMismatch as error:
            print(f"STOP: {error}\nDownloaded files kept for inspection in {incoming}; no snapshot was created.")
            return 3
        records.append({
            "file": pin["name"], "source_url": url, "downloaded_at_utc": started, "bytes": pin["bytes"],
            "etag": etag, "last_modified": last_modified, "approved_sha256": pin["sha256"], **evidence,
        })
        print("verified", pin["name"], evidence["sha256"])
    incoming.rename(snapshot)
    for path in snapshot.iterdir():
        os.chmod(path, stat.S_IREAD)
    write_json(manifest_path, {
        "snapshot_id": snapshot_id,
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_method": "HTTP GET of pinned published files; no scraping or crawling",
        "local_path": snapshot.relative_to(ROOT).as_posix(),
        "source": config["source"], "rights": config["rights"], "owner_approval": config["owner_approval"],
        "extraction_or_conversion": "None on disk. Originals stay gzipped; later steps read them as streams.",
        "preservation": "Files set read-only after verification.",
        "fotmob_preflight": fotmob, "files": records,
    })
    print("snapshot", snapshot, "\nmanifest", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
