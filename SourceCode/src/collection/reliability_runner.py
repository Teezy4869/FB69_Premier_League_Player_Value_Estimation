"""Bounded, resumable Phase 2B.0 Step 05 live evidence collection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import uuid
from collections import Counter
from pathlib import Path

import yaml

from src.audit.client import AuditClient, BudgetExceeded
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write, json_bytes
from src.collection.source_registry import SourceRegistry, load_hardening_config, request_key, validate_scope


def load_reliability_config(path: Path | None = None) -> dict:
    cfg = yaml.safe_load((path or ROOT / "configs/reliability_config.yaml").read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or cfg.get("workers") != 1:
        raise ValueError("Reliability runner requires one worker")
    if not 0 < cfg.get("max_live_http_attempts", 0) <= cfg.get("absolute_step_attempt_ceiling", 0) <= 150:
        raise ValueError("Invalid live HTTP attempt limit")
    if cfg.get("min_request_interval_seconds", 0) < 1 or cfg.get("max_retries", -1) not in (0, 1):
        raise ValueError("Unsafe reliability request rate or retry count")
    for field in ("run_dir", "log_path"):
        p = Path(cfg[field])
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"Unsafe {field}")
    pilot = load_config()
    if set(cfg["profile_seasons"]) - set(pilot["seasons"]) or set(cfg["match_seasons"]) - set(pilot["seasons"]):
        raise ValueError("Test season outside fixed EPL scope")
    if len(cfg["profile_seasons"]) != len(cfg["profile_player_ids"]):
        raise ValueError("Profile season/player plan mismatch")
    return cfg


def schema_state(endpoint: str, payload: object, params: dict) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return "SCHEMA_ERROR", "JSON root is not an object"
    if endpoint == "leagues":
        details, fixtures = payload.get("details"), payload.get("fixtures")
        if not isinstance(details, dict) or not isinstance(fixtures, dict) or not isinstance(fixtures.get("allMatches"), list):
            return "SCHEMA_ERROR", "Missing league details or fixture list"
        return ("EMPTY_DATA", "Fixture list empty") if not fixtures["allMatches"] else ("VALID_DATA", "Fixture list present")
    if endpoint == "leagueseasondeepstats":
        rows = payload.get("statsData")
        if not isinstance(rows, list) or payload.get("currentSeasonId") is None or payload.get("currentStatName") is None:
            return "SCHEMA_ERROR", "Missing leaderboard season, metric or rows"
        return ("EMPTY_DATA", "Leaderboard empty") if not rows else ("VALID_DATA", "Leaderboard rows present")
    if endpoint == "playerData":
        if str(payload.get("id")) != str(params["id"]) or not isinstance(payload.get("statSeasons"), list):
            return "SCHEMA_ERROR", "Player ID or statSeasons invalid"
        return "VALID_DATA", "Player ID and statSeasons present"
    if endpoint == "playerStats":
        section = payload.get("statsSection")
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            card = payload.get("topStatCard")
            if isinstance(card, dict) and isinstance(card.get("items"), list) and card["items"]:
                return "SPARSE_DATA", "Top card items present; stats section absent"
            return "SCHEMA_ERROR", "Missing statsSection.items and topStatCard.items"
        return ("EMPTY_DATA", "Stats items empty") if not section["items"] else ("VALID_DATA", "Stats items present")
    if endpoint == "matchDetails":
        general, content = payload.get("general"), payload.get("content")
        if not isinstance(general, dict) or not isinstance(content, dict) or not isinstance(content.get("lineup"), dict):
            return "SCHEMA_ERROR", "Missing match general or lineup"
        if not any((content["lineup"].get(side) or {}).get("starters") for side in ("homeTeam", "awayTeam")):
            return "EMPTY_DATA", "No starter lineup"
        return "VALID_DATA", "Match lineup present"
    if endpoint == "teams":
        details, squad = payload.get("details"), payload.get("squad")
        if not isinstance(details, dict) or str(details.get("id")) != str(params["id"]) or not isinstance(squad, dict):
            return "SCHEMA_ERROR", "Team ID or squad invalid"
        return "VALID_DATA", "Team response shape present; historical squad scope separate"
    return "SCHEMA_ERROR", "Endpoint outside reliability allowlist"


def profile_entry(profile: dict, season: str) -> str | None:
    for season_row in profile.get("statSeasons") or []:
        if not isinstance(season_row, dict) or season_row.get("seasonName") != season:
            continue
        for tournament in season_row.get("tournaments") or []:
            if isinstance(tournament, dict) and str(tournament.get("tournamentId")) == "47":
                entry = tournament.get("entryId")
                if isinstance(entry, str) and entry:
                    return entry
    return None


def classify_failure(record: dict) -> str:
    status = record.get("http_status")
    if status == 400:
        return "PARAMETER_ERROR"
    if status == 403:
        return "ACCESS_DENIED"
    if status == 429:
        return "RATE_LIMITED"
    if isinstance(status, int) and status >= 500:
        return "SERVER_ERROR"
    if status == 200:
        return "SCHEMA_ERROR"
    if status is None:
        return "NETWORK_ERROR"
    return "HTTP_ERROR"


def classify_empty_stats_payload(endpoint: str, record: dict, raw_body: bytes | None) -> str:
    """A JSON null playerStats response is source absence, not a parser regression."""
    if (endpoint == "playerStats" and record.get("http_status") == 200 and
            record.get("json_parse_success") and (raw_body or b"").strip() == b"null"):
        return "NO_STATS_PAYLOAD"
    return classify_failure(record)


def load_observations(directory: Path) -> list[dict]:
    rows = []
    for path in sorted(directory.glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        raw = row.get("raw_evidence_path")
        if raw:
            body = (ROOT / raw).read_bytes()
            if hashlib.sha256(body).hexdigest() != row["content_sha256"]:
                raise ValueError(f"Reliability raw checksum mismatch: {raw}")
        rows.append(row)
    return rows


class ReliabilityRunner:
    def __init__(self, cfg: dict | None = None, client: AuditClient | None = None):
        self.cfg = cfg or load_reliability_config()
        self.pilot = load_config()
        self.run_dir = ROOT / self.cfg["run_dir"]
        self.observation_dir = self.run_dir / "observations"
        self.observation_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = ROOT / self.cfg["log_path"]
        existing_attempts = len(self.log_path.read_text(encoding="utf-8").splitlines()) if self.log_path.exists() else 0
        remaining = self.cfg["max_live_http_attempts"] - existing_attempts
        if remaining < 0:
            raise BudgetExceeded("Existing reliability log exceeds configured ceiling")
        client_cfg = dict(self.pilot)
        client_cfg.update({"request_budget": remaining,
                           "min_request_interval_seconds": self.cfg["min_request_interval_seconds"],
                           "max_retries": self.cfg["max_retries"],
                           "backoff_seconds": self.cfg["backoff_seconds"],
                           "max_retry_after_seconds": self.cfg["max_retry_after_seconds"]})
        self.client = client or AuditClient(client_cfg, self.log_path)
        hardening = dict(load_hardening_config())
        hardening.update({"raw_dir": (Path(self.cfg["run_dir"]) / "raw").as_posix(),
                          "legacy_raw_dir": (Path(self.cfg["run_dir"]) / "legacy_empty").as_posix(),
                          "log_path": self.cfg["log_path"], "lineup_request_budget": 0})
        self.registry = SourceRegistry(hardening, client=self.client)
        self.cache_hits = 0
        self.new_logical_requests = 0
        self.stopped = False

    def _failure_raw(self, key: str, body: bytes) -> str:
        directory = self.run_dir / "failed" / ("failure_" + uuid.uuid4().hex)
        directory.mkdir(parents=True, exist_ok=False)
        path = directory / "response.bin"
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        return path.relative_to(ROOT).as_posix()

    def request(self, endpoint: str, params: dict, season: str, fixture: dict | None = None) -> dict:
        if season not in self.pilot["seasons"]:
            raise ValueError("Season outside fixed scope")
        key = request_key(endpoint, params)
        checkpoint = self.observation_dir / (key + ".json")
        if checkpoint.exists():
            row = next(r for r in load_observations(self.observation_dir) if r["request_key"] == key)
            if row["season_label"] != season:
                raise ValueError("Request identity reused across seasons")
            self.cache_hits += 1
            return row
        try:
            result = self.client.get(endpoint, params)
        except BudgetExceeded:
            self.stopped = True
            raise
        record = result["record"]
        payload = result.get("payload")
        status, note = (schema_state(endpoint, payload, params) if payload is not None else
                        (classify_failure(record), record.get("error", "HTTP or network failure")))
        scope, scope_note = (validate_scope(endpoint, params, season, self.pilot["seasons"][season], payload)
                             if isinstance(payload, dict) else ("NOT_EVALUATED", "No JSON object"))
        if fixture is not None and isinstance(payload, dict):
            from src.collection.historical_lineup_validator import verify_detail
            scope, scope_note = verify_detail(payload, fixture)
        if scope in ("HISTORICAL_SCOPE_MISMATCH", "REJECTED"):
            status = "HISTORICAL_SCOPE_MISMATCH"
        if status == "VALID_DATA" and scope == "UNVERIFIED" and endpoint == "teams":
            status = "HISTORICAL_SCOPE_UNVERIFIED"
        raw_path = ""
        capture_id = ""
        body = result.get("raw_body")
        if body is not None:
            if status in ("VALID_DATA", "EMPTY_DATA"):
                meta, _ = self.registry.capture(endpoint, params, season, result, fixture)
                raw_path, capture_id = meta["raw_path"], meta["capture_id"]
            else:
                raw_path = self._failure_raw(key, body)
        row = {"request_key": key, "capture_id": capture_id, "endpoint": endpoint,
               "season_label": season, "season_id": self.pilot["seasons"][season],
               "params": params, "http_status": record.get("http_status"),
               "content_type": record.get("content_type", ""),
               "json_parse_success": record.get("json_parse_success", False),
               "schema_status": status, "scope_status": scope, "scope_note": scope_note,
               "error_classification": status if status not in ("VALID_DATA", "EMPTY_DATA") else "",
               "response_latency_seconds": record.get("elapsed_seconds"),
               "retry_count": record.get("retry_index", 0),
               "raw_evidence_path": raw_path,
               "content_sha256": hashlib.sha256(body).hexdigest() if body is not None else "",
               "source_url": record.get("source_url", ""),
               "timestamp_utc": record["timestamp_utc"], "note": note}
        atomic_write(checkpoint, json_bytes(row))
        self.new_logical_requests += 1
        if status in ("RATE_LIMITED", "ACCESS_DENIED"):
            self.stopped = True
        return row

    def plan_and_run(self) -> dict:
        # Smoke: each historical league index has explicit selectedSeason and fixtures.
        for season in self.pilot["seasons"]:
            row = self.request("leagues", {"id": 47, "season": season}, season)
            if self.stopped or row["schema_status"] not in ("VALID_DATA", "EMPTY_DATA"):
                return self.summary("SMOKE_STOP")
        # One verified leaderboard metric for every season, then targeted dependent probes.
        for season, season_id in self.pilot["seasons"].items():
            self.request("leagueseasondeepstats", {"id": 47, "season": season_id,
                         "type": "players", "stat": "mins_played"}, season)
            if self.stopped:
                return self.summary("ACCESS_STOP")
        for season, pid in zip(self.cfg["profile_seasons"], self.cfg["profile_player_ids"]):
            profile_row = self.request("playerData", {"id": pid}, season)
            if self.stopped:
                return self.summary("ACCESS_STOP")
            if profile_row["schema_status"] != "VALID_DATA":
                continue
            profile = json.loads((ROOT / profile_row["raw_evidence_path"]).read_text(encoding="utf-8"))
            entry = profile_entry(profile, season)
            if entry is None:
                continue  # Do not guess a positional seasonId from old cached profiles.
            self.request("playerStats", {"playerId": pid, "seasonId": entry}, season)
            if self.stopped:
                return self.summary("ACCESS_STOP")
        with (ROOT / "reports/phase_02b0/historical_match_sample.csv").open(encoding="utf-8", newline="") as handle:
            fixtures = list(csv.DictReader(handle))
        for season in self.cfg["match_seasons"]:
            fixture = next(r for r in fixtures if r["season_label"] == season and r["detail_scope_status"] == "ACCEPTED")
            expectation = {"match_id": fixture["match_id"], "season_label": season,
                           "match_date_utc": fixture["match_date_utc"],
                           "date": fixture["match_date_utc"][:10],
                           "home_team_id": fixture["home_team_id"], "away_team_id": fixture["away_team_id"]}
            self.request("matchDetails", {"matchId": int(fixture["match_id"])}, season, expectation)
            if self.stopped:
                return self.summary("ACCESS_STOP")
        for season in self.cfg["team_probe_seasons"]:
            self.request("teams", {"id": 8650, "season": season}, season)
            if self.stopped:
                return self.summary("ACCESS_STOP")
        return self.summary("COMPLETE")

    def summary(self, state: str) -> dict:
        rows = load_observations(self.observation_dir)
        return {"state": state, "new_logical_requests": self.new_logical_requests,
                "new_http_attempts": self.client.attempts,
                "cache_hits": self.cache_hits,
                "observed_requests": len(rows),
                "outcomes": dict(Counter(r["schema_status"] for r in rows))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Execute the bounded live plan")
    args = parser.parse_args()
    runner = ReliabilityRunner()
    result = runner.plan_and_run() if args.live else runner.summary("REPORT_ONLY")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
