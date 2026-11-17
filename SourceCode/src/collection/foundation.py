"""Full-response cache and integrity manifest around the Phase 1 HTTP client."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from src.audit.client import AuditClient, BudgetExceeded
from src.collection.collection_config import ROOT


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class PilotStore:
    def __init__(self, config: dict, client: AuditClient | None = None, root: Path = ROOT):
        self.config = config
        self.root = root
        self.raw_dir = root / config["raw_dir"]
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or AuditClient(config, root / config["log_path"])
        self.events = []

    def fetch(self, endpoint: str, params: dict, season: str, source_id: str) -> dict | None:
        if endpoint not in {"leagues", "teams", "leagueseasondeepstats", "matchDetails", "playerData", "playerStats"}:
            raise ValueError("Endpoint not allowed in controlled pilot")
        if season not in self.config["seasons"]:
            raise ValueError("Season outside scope")
        allowed_keys = {
            "leagues": {"id", "season"},
            "leagueseasondeepstats": {"id", "season", "type", "stat"},
            "teams": {"id", "season"},
            "matchDetails": {"matchId"},
            "playerData": {"id"},
            "playerStats": {"playerId", "seasonId"},
        }
        if set(params) != allowed_keys[endpoint]:
            raise ValueError("Unexpected request parameters; refusing to send or log them")
        if endpoint == "leagues" and (params["id"] != 47 or params["season"] != season):
            raise ValueError("League request is outside fixed scope")
        if endpoint == "leagueseasondeepstats" and (
                params["id"] != 47 or params["season"] != self.config["seasons"][season] or
                params["type"] != "players" or params["stat"] not in self.config["reference_metrics"]):
            raise ValueError("Stats request is outside fixed scope")
        if endpoint == "teams" and (params["season"] != season or not str(params["id"]).isdigit()):
            raise ValueError("Team request is outside fixed scope")
        if endpoint in ("matchDetails", "playerData") and not str(next(iter(params.values()))).isdigit():
            raise ValueError("Invalid numeric FotMob identifier")
        if endpoint == "playerStats" and (not str(params["playerId"]).isdigit() or
                                          not re.fullmatch(r"\d+-\d+", str(params["seasonId"]))):
            raise ValueError("Invalid playerStats identifier or season entry")
        key = hashlib.sha256(json_bytes([endpoint, params, season, source_id])).hexdigest()[:20]
        stem = f"{season.replace('/', '_')}_{endpoint}_{key}"
        payload_path = self.raw_dir / (stem + ".json")
        meta_path = self.raw_dir / (stem + ".meta.json")
        if payload_path.exists() and meta_path.exists():
            data = payload_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise ValueError(f"Cached response checksum mismatch: {payload_path}")
            payload = json.loads(data)
            self.events.append({"source_id": source_id, "outcome": "CACHE_HIT", "season": season})
            return payload
        if payload_path.exists() or meta_path.exists():
            raise ValueError(f"Incomplete cache entry: {stem}")
        try:
            result = self.client.get(endpoint, params)
        except BudgetExceeded:
            self.events.append({"source_id": source_id, "outcome": "BUDGET_EXCEEDED", "season": season,
                                "error": "HTTP attempt budget exhausted during retry"})
            raise
        record = result["record"]
        payload = result["payload"]
        self.events.append({"source_id": source_id, "outcome": record["outcome"], "season": season,
                            "http_status": record.get("http_status"), "error": record.get("error")})
        if payload is None:
            return None
        data = result.get("raw_body") or json_bytes(payload)
        meta = {"endpoint": endpoint, "params": params, "competition": self.config["competition"],
                "league_id": self.config["league_id"], "season_label": season,
                "fotmob_season_id": self.config["seasons"][season],
                "collected_at_utc": record["timestamp_utc"], "http_status": record["http_status"],
                "content_type": record["content_type"], "source_id": source_id,
                "source_url": record["source_url"], "response_bytes_wire": record.get("response_bytes"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "stored_body_kind": "wire_json" if result.get("raw_body") else "canonical_json",
                "cache_schema_version": 1}
        atomic_write(payload_path, data)
        atomic_write(meta_path, json_bytes(meta))
        return payload

    def cached_payloads(self, endpoint: str | None = None):
        for meta_path in sorted(self.raw_dir.glob("*.meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if endpoint and meta["endpoint"] != endpoint:
                continue
            payload_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            data = payload_path.read_bytes()
            if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise ValueError(f"Cached response checksum mismatch: {payload_path}")
            yield meta, json.loads(data)
