"""Immutable capture registry and historical-scope checks for Phase 2B.0."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import yaml

from src.audit.client import AuditClient
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import json_bytes


def load_hardening_config(path: Path | None = None) -> dict:
    config = yaml.safe_load((path or ROOT / "configs/hardening_config.yaml").read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not 0 <= config.get("lineup_request_budget", -1) <= 12:
        raise ValueError("Invalid bounded lineup request budget")
    for field in ("raw_dir", "report_dir", "log_path", "legacy_raw_dir"):
        value = Path(config[field])
        if value.is_absolute() or ".." in value.parts:
            raise ValueError(f"Unsafe {field}")
    if not 0 <= config.get("player_matches_probe_budget", -1) <= 2:
        raise ValueError("Invalid playerMatches probe budget")
    for field in ("player_matches_probe_dir", "player_matches_probe_log_path"):
        value = Path(config[field])
        if value.is_absolute() or ".." in value.parts:
            raise ValueError(f"Unsafe {field}")
    return config


def canonical_params(params: dict) -> dict:
    """Normalize a request's non-secret query values without losing their meaning."""
    def norm(value):
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, (list, tuple)):
            return [norm(v) for v in value]
        if isinstance(value, dict):
            return {str(k): norm(v) for k, v in sorted(value.items())}
        return str(value)
    return {str(k): norm(v) for k, v in sorted(params.items())}


def request_key(endpoint: str, params: dict, method: str = "GET",
                contract: str = "fotmob-data-v1", body: dict | None = None) -> str:
    if not endpoint or "/" in endpoint or endpoint.startswith("."):
        raise ValueError("Endpoint must be one canonical API path segment")
    identity = {"method": method.upper(), "path": "/api/data/" + endpoint,
                "params": canonical_params(params), "body": canonical_params(body or {}),
                "contract": contract}
    return "req_" + hashlib.sha256(json_bytes(identity)).hexdigest()


def validate_scope(endpoint: str, params: dict, season: str, season_id: int,
                   payload: dict) -> tuple[str, str]:
    """Validate only context explicitly returned by the endpoint."""
    if not isinstance(payload, dict):
        return "REJECTED", "Response is not a JSON object"
    if endpoint == "leagues":
        selected = (payload.get("details") or {}).get("selectedSeason")
        if selected is None:
            return "UNVERIFIED", "No returned selectedSeason"
        return ("ACCEPTED", "Selected season matches") if selected == season else (
            "HISTORICAL_SCOPE_MISMATCH", f"selectedSeason={selected}, expected={season}")
    if endpoint == "leagueseasondeepstats":
        returned = payload.get("currentSeasonId")
        if returned is None:
            return "UNVERIFIED", "No returned currentSeasonId"
        if str(returned) != str(season_id):
            return "HISTORICAL_SCOPE_MISMATCH", f"currentSeasonId={returned}, expected={season_id}"
        if payload.get("currentStatName") != params.get("stat"):
            return "HISTORICAL_SCOPE_MISMATCH", "Stat name differs from request"
        return "ACCEPTED", "Season ID and stat name match"
    if endpoint == "matchDetails":
        general = payload.get("general") or {}
        match_id = general.get("matchId")
        league_id = general.get("leagueId")
        if match_id is None or league_id is None:
            return "UNVERIFIED", "No returned match and league ID"
        if str(match_id) != str(params.get("matchId")) or str(league_id) != "47":
            return "HISTORICAL_SCOPE_MISMATCH", "Match or competition ID differs from request"
        # The fixture index provides the season; matchDetails itself does not.
        return "UNVERIFIED", "Match/league IDs match; response has no explicit season ID"
    if endpoint == "teams":
        details = payload.get("details") or {}
        if details.get("id") is not None and str(details["id"]) != str(params.get("id")):
            return "HISTORICAL_SCOPE_MISMATCH", "Returned team ID differs from request"
        returned_season = (payload.get("squad") or {}).get("season") or details.get("selectedSeason")
        if returned_season is None:
            return "UNVERIFIED", "No explicit historical squad season; latestSeason is not squad season"
        return ("ACCEPTED", "Squad season matches") if str(returned_season) == season else (
            "HISTORICAL_SCOPE_MISMATCH", f"squad season={returned_season}, expected={season}")
    if endpoint == "playerStats":
        return "UNVERIFIED", "Season association requires checked playerData statSeasons entry"
    return "UNVERIFIED", "Response has no explicit historical season context"


class SourceRegistry:
    def __init__(self, hardening: dict, client: AuditClient | None = None, root: Path = ROOT):
        self.root = root
        self.hardening = hardening
        self.pilot = load_config()
        self.raw_dir = root / hardening["raw_dir"]
        self.legacy_dir = root / hardening["legacy_raw_dir"]
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[tuple[str, str], tuple[dict, Path]] | None = None
        self._request_index: dict[str, list[tuple[dict, Path]]] | None = None
        client_config = dict(self.pilot)
        client_config["request_budget"] = hardening["lineup_request_budget"]
        self.client = client or AuditClient(client_config, root / hardening["log_path"])

    def _metadata_entries(self):
        """Index capture metadata without retaining every decoded response in memory."""
        for meta_path in sorted(self.legacy_dir.glob("*.meta.json")):
            source = json.loads(meta_path.read_text(encoding="utf-8"))
            path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            identity = request_key(source["endpoint"], source["params"],
                                   contract=self.hardening["request_contract"])
            meta = {"request_key": identity, "capture_id": "legacy_" + hashlib.sha256(
                str(meta_path.relative_to(self.root)).encode()).hexdigest()[:24],
                "source_id": source["source_id"], "endpoint": source["endpoint"],
                "params": canonical_params(source["params"]), "season_label": source["season_label"],
                "season_id": source["fotmob_season_id"], "collected_at_utc": source["collected_at_utc"],
                "http_status": source["http_status"], "content_type": source["content_type"],
                "source_url": source.get("source_url", ""), "content_sha256": source["sha256"],
                "raw_path": path.relative_to(self.root).as_posix(),
                "metadata_path": meta_path.relative_to(self.root).as_posix(),
                "body_kind": source.get("stored_body_kind", "canonical_json"), "legacy": True}
            yield meta, path
        for meta_path in sorted(self.raw_dir.glob("*/*/*/metadata.json")):
            if meta_path.parent.name.startswith("."):
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            yield meta, meta_path.with_name("response.json")

    def captures(self):
        for meta_path in sorted(self.legacy_dir.glob("*.meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != meta["sha256"]:
                raise ValueError(f"Legacy checksum mismatch: {path}")
            identity = request_key(meta["endpoint"], meta["params"],
                                   contract=self.hardening["request_contract"])
            yield {"request_key": identity, "capture_id": "legacy_" + hashlib.sha256(
                str(meta_path.relative_to(self.root)).encode()).hexdigest()[:24],
                   "source_id": meta["source_id"], "endpoint": meta["endpoint"],
                   "params": canonical_params(meta["params"]), "season_label": meta["season_label"],
                   "season_id": meta["fotmob_season_id"], "collected_at_utc": meta["collected_at_utc"],
                   "http_status": meta["http_status"], "content_type": meta["content_type"],
                   "source_url": meta.get("source_url", ""),
                   "content_sha256": hashlib.sha256(body).hexdigest(),
                   "raw_path": path.relative_to(self.root).as_posix(),
                   "metadata_path": meta_path.relative_to(self.root).as_posix(),
                   "body_kind": meta.get("stored_body_kind", "canonical_json"),
                   "legacy": True}, json.loads(body)
        for meta_path in sorted(self.raw_dir.glob("*/*/*/metadata.json")):
            if meta_path.parent.name.startswith("."):
                continue  # Uncommitted directory from an interrupted atomic rename.
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            path = meta_path.with_name("response.json")
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != meta["content_sha256"]:
                raise ValueError(f"New checksum mismatch: {path}")
            yield meta, json.loads(body)

    def lookup(self, endpoint: str, params: dict, season: str) -> tuple[dict, dict] | None:
        key = request_key(endpoint, params, contract=self.hardening["request_contract"])
        if self._index is None:
            self._index = {}
            self._request_index = {}
            for meta, path in self._metadata_entries():
                identity = (meta["request_key"], meta["season_label"])
                previous = self._index.get(identity)
                if previous and previous[0]["content_sha256"] != meta["content_sha256"]:
                    raise ValueError(f"Conflicting cached captures for request {identity}")
                self._index.setdefault(identity, (meta, path))
                self._request_index.setdefault(meta["request_key"], []).append((meta, path))
        found = self._index.get((key, season))
        if found is not None:
            meta, path = found
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != meta["content_sha256"]:
                raise ValueError(f"Cached response checksum mismatch: {meta['raw_path']}")
            payload = json.loads(body)
            scope = meta.get("scope_status")
            if scope is None:
                scope, _ = validate_scope(endpoint, params, season, self.pilot["seasons"][season], payload)
            if scope in ("HISTORICAL_SCOPE_MISMATCH", "REJECTED"):
                raise ValueError(f"Cached response has invalid historical scope: {meta['raw_path']}")
            return meta, payload
        return None

    def lookup_any_season(self, endpoint: str, params: dict):
        """Yield same-request captures with original provenance; caller validates target scope."""
        key = request_key(endpoint, params, contract=self.hardening["request_contract"])
        if self._index is None:
            self.lookup(endpoint, params, "__index_only__")
        for meta, path in self._request_index.get(key, []):
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != meta["content_sha256"]:
                raise ValueError(f"Cached response checksum mismatch: {meta['raw_path']}")
            yield meta, json.loads(body)

    def capture(self, endpoint: str, params: dict, season: str, result: dict,
                expected_fixture: dict | None = None) -> tuple[dict, dict] | None:
        payload = result.get("payload")
        if payload is None:
            return None
        season_id = self.pilot["seasons"][season]
        key = request_key(endpoint, params, contract=self.hardening["request_contract"])
        prior = self.lookup(endpoint, params, season)
        if prior is not None:
            raise FileExistsError(f"Request already captured: {key}")
        record = result["record"]
        body = result.get("raw_body") or json_bytes(payload)
        status, note = validate_scope(endpoint, params, season, season_id, payload)
        if expected_fixture is not None:
            general = payload.get("general") or {}
            exp_date = expected_fixture.get("date")
            actual_date = (general.get("matchTimeUTCDate") or "")[:10]
            exp_teams = (str(expected_fixture["home_team_id"]), str(expected_fixture["away_team_id"]))
            actual_teams = (str((general.get("homeTeam") or {}).get("id")),
                            str((general.get("awayTeam") or {}).get("id")))
            if exp_date != actual_date or exp_teams != actual_teams:
                status, note = "HISTORICAL_SCOPE_MISMATCH", "Fixture date or teams differ from season index"
            elif status == "UNVERIFIED" and "Match/league IDs match" in note:
                status, note = "ACCEPTED", "Match, league, date and teams match season-scoped fixture index"
        capture_id = "cap_" + uuid.uuid4().hex
        directory = self.raw_dir / season.replace("/", "_") / endpoint / capture_id
        temp_dir = directory.with_name("." + capture_id + ".tmp")
        meta = {"request_key": key, "capture_id": capture_id, "source_id": key,
                "endpoint": endpoint, "method": "GET", "params": canonical_params(params),
                "season_label": season, "season_id": season_id,
                "collected_at_utc": record["timestamp_utc"], "http_status": record["http_status"],
                "content_type": record["content_type"], "content_sha256": hashlib.sha256(body).hexdigest(),
                "source_url": record.get("source_url", ""),
                "raw_path": (directory / "response.json").relative_to(self.root).as_posix(),
                "metadata_path": (directory / "metadata.json").relative_to(self.root).as_posix(),
                "scope_status": status, "scope_note": note,
                "body_kind": "wire_json" if result.get("raw_body") else "canonical_json",
                "legacy": False, "schema_version": self.hardening.get("schema_version", 1),
                "parser_version": self.hardening.get("parser_version", 1),
                "schema_status": "UNVERIFIED_AT_CAPTURE"}
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            for name, data in (("response.json", body), ("metadata.json", json_bytes(meta))):
                with (temp_dir / name).open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            if directory.exists():
                raise FileExistsError(directory)
            for rename_attempt in range(5):
                try:
                    os.rename(temp_dir, directory)
                    break
                except PermissionError:
                    # Windows scanners may briefly hold a just-written file open.
                    # Keep the checked temp capture for explicit recovery if all retries fail.
                    if rename_attempt == 4:
                        raise
                    time.sleep(0.5 * (rename_attempt + 1))
        except Exception:
            # A temporary directory is evidence of an interrupted write, never a cache hit.
            raise
        if self._index is not None:
            self._index[(key, season)] = (meta, directory / "response.json")
            self._request_index.setdefault(key, []).append((meta, directory / "response.json"))
        if status in ("HISTORICAL_SCOPE_MISMATCH", "REJECTED"):
            raise ValueError(f"Historical scope mismatch preserved as raw evidence: {meta['raw_path']}")
        return meta, payload

    def fetch(self, endpoint: str, params: dict, season: str,
              expected_fixture: dict | None = None) -> tuple[dict, dict] | None:
        if season not in self.pilot["seasons"]:
            raise ValueError("Season outside fixed scope")
        if endpoint != "matchDetails" or set(params) != {"matchId"} or not str(params["matchId"]).isdigit():
            raise ValueError("Phase 2B.0 live collection is limited to a bounded matchDetails ID")
        if expected_fixture is None:
            raise ValueError("A season-scoped fixture expectation is required before HTTP collection")
        cached = self.lookup(endpoint, params, season)
        if cached is not None:
            return cached
        result = self.client.get(endpoint, params)
        return self.capture(endpoint, params, season, result, expected_fixture)
