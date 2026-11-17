"""Holdout (D10) step 4a: collect FotMob EPL 2025/26 raw responses, owner-authorized 2026-11-16.

Same endpoints, parameters, user agent and pacing as the Phase 2 pipeline (configs/full_collection.yaml,
configs/pilot_config.yaml). Every response is stored immutably as response.json + metadata.json (SHA-256).
Resumable: a request whose capture already exists is skipped. Stops on HTTP 403/429 or repeated errors.
Collects only raw data; it never parses targets or values beyond what is needed to plan the next requests.

Order: league fixtures (already probed) -> season leaderboards -> matchDetails (380) -> playerData for every
lineup player -> playerStats for every player with an EPL 2025/26 entry.

Usage: python -I src/holdout/collect_fotmob.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402
import yaml  # noqa: E402

from src.collection.reliability_runner import profile_entry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SEASON, SEASON_ID, LEAGUE = "2025/2026", "27110", "47"
RAW = ROOT / "data/holdout_2025_26/fotmob/raw"
PROBE = RAW / "probe/leagues_2025_2026.json"
LOG = ROOT / "logs/holdout_2025_26_fotmob_requests.jsonl"
PILOT = yaml.safe_load((ROOT / "configs/pilot_config.yaml").read_text(encoding="utf-8"))
FULL = yaml.safe_load((ROOT / "configs/full_collection.yaml").read_text(encoding="utf-8"))
STATS = yaml.safe_load((ROOT / "configs/statistics_collection.yaml").read_text(encoding="utf-8"))
INTERVAL = float(FULL["min_request_interval_seconds"])
STOP = set(FULL["quality"]["stop_http_statuses"])


def key(endpoint: str, params: dict) -> str:
    return hashlib.sha256(json.dumps([endpoint, sorted((k, str(v)) for k, v in params.items())]).encode()).hexdigest()[:24]


class Collector:
    def __init__(self):
        self.session, self.last, self.errors, self.requests = requests.Session(), 0.0, 0, 0

    def get(self, endpoint: str, params: dict) -> dict | None:
        out = RAW / endpoint / key(endpoint, params)
        if (out / "response.json").exists():
            return json.loads((out / "response.json").read_text(encoding="utf-8"))
        for attempt in range(FULL["max_retries"] + 1):
            time.sleep(max(0.0, INTERVAL - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            self.requests += 1
            rec = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "endpoint": endpoint, "params": params, "attempt": attempt}
            try:
                r = self.session.get(f"{PILOT['api_base_url']}/{endpoint}", params=params, timeout=FULL["request_timeout_seconds"],
                                     headers={"User-Agent": PILOT["user_agent"], "Accept": "application/json"})
                rec.update({"http_status": r.status_code, "bytes": len(r.content), "url": r.url})
            except requests.RequestException as exc:
                rec["error"] = type(exc).__name__
                r = None
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            if r is not None and r.status_code in STOP:
                raise SystemExit(f"STOP: HTTP {r.status_code} on {endpoint} {params}")
            if r is not None and r.status_code == 200 and len(r.content) <= FULL["max_response_bytes"]:
                try:
                    payload = r.json()
                except ValueError:
                    payload = None
                if payload is not None:
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "response.json").write_bytes(r.content)
                    (out / "metadata.json").write_text(json.dumps({"endpoint": endpoint, "params": params, "season_label": SEASON, "season_id": SEASON_ID,
                        "source_url": r.url, "http_status": 200, "content_type": r.headers.get("Content-Type"), "collected_at_utc": rec["timestamp_utc"],
                        "content_sha256": hashlib.sha256(r.content).hexdigest(), "response_bytes": len(r.content), "user_agent": PILOT["user_agent"]}), encoding="utf-8")
                    self.errors = 0
                    return payload
            time.sleep(FULL["backoff_seconds"] * (2 ** attempt))
        self.errors += 1
        if self.errors >= FULL["quality"]["max_consecutive_server_errors"] + 1:
            raise SystemExit(f"STOP: {self.errors} consecutive failures, last {endpoint} {params}")
        return None


def main() -> None:
    c = Collector()
    fixtures = json.loads(PROBE.read_text(encoding="utf-8"))["fixtures"]["allMatches"]
    assert len(fixtures) == 380 and all(f["status"]["finished"] and not f["status"]["cancelled"] for f in fixtures)
    for spec in STATS["leaderboard_specs"]:
        c.get("leagueseasondeepstats", {"id": LEAGUE, "season": SEASON_ID, "stat": spec["stat"], "type": "players"})
    print("boards done", c.requests, flush=True)
    players = set()
    for i, f in enumerate(fixtures):
        d = c.get("matchDetails", {"matchId": str(f["id"])})
        lineup = ((d or {}).get("content") or {}).get("lineup") or {}
        for side in (lineup.get("homeTeam") or {}, lineup.get("awayTeam") or {}):
            players |= {str(m.get("id")) for m in (side.get("starters") or []) + (side.get("subs") or []) if isinstance(m, dict) and m.get("id")}
        if i % 50 == 0:
            print("matches", i, c.requests, flush=True)
    print("lineup players", len(players), flush=True)
    missing_entry = 0
    for i, pid in enumerate(sorted(players, key=int)):
        profile = c.get("playerData", {"id": pid})
        entry = profile_entry(profile or {}, SEASON)
        if entry is None:
            missing_entry += 1
            continue
        c.get("playerStats", {"playerId": pid, "seasonId": entry})
        if i % 100 == 0:
            print("players", i, c.requests, flush=True)
    print({"requests_this_run": c.requests, "lineup_players": len(players), "profiles_without_epl_entry": missing_entry}, flush=True)


if __name__ == "__main__":
    main()
