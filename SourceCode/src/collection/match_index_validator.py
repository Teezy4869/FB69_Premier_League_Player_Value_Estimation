"""Status-aware fixture audit and two-request playerMatches investigation."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone

import pyarrow.parquet as pq

from src.audit.client import AuditClient, BudgetExceeded
from src.collection.collection_config import ROOT, load_config
from src.collection.foundation import atomic_write, json_bytes
from src.collection.historical_identity import read_csv
from src.collection.source_registry import load_hardening_config, request_key, canonical_params

WRAPPER_SOURCE = "https://github.com/ccdejene/fotmob-mcp/blob/main/fotmob_mcp/server.py"
WRAPPER_REFERENCE = "https://github.com/ccdejene/fotmob-mcp/blob/main/docs/fotmob-api.md"
PROBES = [
    ("2019/2020", 108038, 1596240000),  # 2020-08-01 UTC, after season completion
    ("2024/2025", 831489, 1748736000),  # 2025-06-01 UTC, after season completion
]


def probe_records() -> list[dict]:
    hardening = load_hardening_config()
    base = ROOT / hardening["player_matches_probe_dir"]
    records = []
    for meta_path in sorted(base.glob("*/metadata.json")):
        if meta_path.parent.name.startswith("."):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body_path = meta_path.with_name("response.json")
        body = body_path.read_bytes()
        if hashlib.sha256(body).hexdigest() != meta["content_sha256"]:
            raise ValueError(f"playerMatches probe checksum mismatch: {body_path}")
        records.append(meta)
    return records


def persist_probe(season: str, params: dict, result: dict) -> dict:
    hardening = load_hardening_config()
    directory = ROOT / hardening["player_matches_probe_dir"]
    directory.mkdir(parents=True, exist_ok=True)
    key = request_key("playerMatches", params, contract=hardening["request_contract"])
    if any(r["request_key"] == key and r["season_label"] == season for r in probe_records()):
        raise FileExistsError(f"Probe already retained: {key}")
    capture_id = "probe_" + uuid.uuid4().hex
    target = directory / capture_id
    temporary = directory / ("." + capture_id + ".tmp")
    record = result["record"]
    body = result.get("raw_body") or json_bytes(result.get("payload") or result.get("error_payload") or {})
    meta = {"request_key": key, "capture_id": capture_id,
            "endpoint": "playerMatches", "method": "GET", "params": canonical_params(params),
            "season_label": season, "collected_at_utc": record["timestamp_utc"],
            "http_status": record.get("http_status"), "content_type": record.get("content_type", ""),
            "source_url": record.get("source_url", ""), "content_sha256": hashlib.sha256(body).hexdigest(),
            "response_error": record.get("response_error", ""), "outcome": record.get("outcome"),
            "raw_path": (target / "response.json").relative_to(ROOT).as_posix(),
            "metadata_path": (target / "metadata.json").relative_to(ROOT).as_posix(),
            "evidence_status": "HTTP_RESPONSE_RETAINED"}
    temporary.mkdir(exist_ok=False)
    for filename, content in (("response.json", body), ("metadata.json", json_bytes(meta))):
        with (temporary / filename).open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    if target.exists():
        raise FileExistsError(target)
    os.rename(temporary, target)
    return meta


def probe_player_matches(allow_http: bool = False) -> dict:
    hardening = load_hardening_config()
    config = dict(load_config())
    config["request_budget"] = hardening["player_matches_probe_budget"]
    config["max_retries"] = 0  # exactly two distinct documented-pattern attempts at most
    client = AuditClient(config, ROOT / hardening["player_matches_probe_log_path"])
    attempted = 0
    for season, player_id, before in PROBES:
        params = {"playerId": player_id, "before": before, "parentLeagueId": 47}
        key = request_key("playerMatches", params, contract=hardening["request_contract"])
        if any(r["request_key"] == key and r["season_label"] == season for r in probe_records()):
            continue
        if not allow_http or attempted >= hardening["player_matches_probe_budget"]:
            continue
        try:
            result = client.get("playerMatches", params)
        except BudgetExceeded:
            break
        attempted += 1
        persist_probe(season, params, result)
        if result["record"].get("http_status") in (403, 429):
            break  # stop on access restriction or rate limit
    return {"planned": len(PROBES), "retained": len(probe_records()),
            "new_http_attempts": attempted,
            "statuses": dict(Counter(r["http_status"] for r in probe_records()))}


def fixture_facts() -> dict:
    table = pq.read_table(ROOT / load_config()["normalized_dir"] / "matches.parquet").to_pylist()
    ids = [r["match_id"] for r in table]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate FotMob match ID")
    seasons = {}
    for season in load_config()["seasons"]:
        rows = [r for r in table if r["season_label"] == season]
        statuses = Counter(r["status"] for r in rows)
        if any(not r["match_date_utc"] or not r["home_team_id"] or not r["away_team_id"] for r in rows):
            raise ValueError(f"Missing fixture date or team in {season}")
        seasons[season] = {"fixture_records": len(rows), "finished": statuses["FINISHED"],
                           "abandoned_or_cancelled": statuses["CANCELLED_OR_ABANDONED"],
                           "postponed": statuses["POSTPONED"], "other": statuses["OTHER"],
                           "team_match_associations": len(rows) * 2}
    by_id = {r["match_id"]: r for r in table}
    if by_id["4193691"]["status"] != "CANCELLED_OR_ABANDONED" or by_id["4421797"]["status"] != "FINISHED":
        raise ValueError("Bournemouth-Luton abandoned/replay IDs conflated")
    sample = read_csv(ROOT / "reports/phase_02b0/historical_lineup_comparison.csv")
    appeared = [r for r in sample if r["appearance_status"] == "APPEARED"]
    return {"by_season": seasons, "fixture_records": len(table),
            "finished": sum(r["status"] == "FINISHED" for r in table),
            "abandoned_or_cancelled": sum(r["status"] == "CANCELLED_OR_ABANDONED" for r in table),
            "sampled_verified_participation_entries": len(appeared),
            "sampled_matches": len({r["match_id"] for r in sample}),
            "sampled_player_match_pairs": len({(r["player_id"], r["match_id"]) for r in appeared})}


def write_report() -> dict:
    facts = fixture_facts()
    probes = probe_records()
    lines = ["# Match Index readiness — Phase 2B.0 Step 04B", "",
             "The six cached `leagues` responses provide a season-scoped fixture index. A fixture establishes two team–match associations, not any player appearance. A selected `matchDetails` lineup with starter or `subIn` evidence establishes only the sampled player–match association. Full player–match statistics remain UNKNOWN.", "",
             "| Season | Fixture records | Finished | Abandoned/cancelled | Postponed | Team–match associations |",
             "|---|---:|---:|---:|---:|---:|"]
    for season, r in facts["by_season"].items():
        lines.append(f"| {season} | {r['fixture_records']} | {r['finished']} | {r['abandoned_or_cancelled']} | {r['postponed']} | {r['team_match_associations']} |")
    lines += ["", "The 2023/24 Bournemouth–Luton abandoned fixture `4193691` and finished replay `4421797` are distinct records. The canceled/abandoned record is excluded from the 380 finished games that season. No postponed fixture remains in the saved end-of-season indexes.", "",
              f"Fallback evidence: {facts['sampled_matches']} selected match details yielded {facts['sampled_verified_participation_entries']} confirmed participation entries and {facts['sampled_player_match_pairs']} unique player–match pairs. The Phase 2A `player_match_links` table recorded 47 lineup members, including six unused substitutes; this corrected fallback uses starter/`subIn` evidence only.", "",
              "## playerMatches investigation", "",
              f"The named community wrapper [route implementation]({WRAPPER_SOURCE}) and [route reference]({WRAPPER_REFERENCE}) list `playerId`, Unix `before`, and `parentLeagueId` for `/api/data/playerMatches`. This is a route catalog, not proof that historical requests work. Phase 1 already retained two HTTP 400 responses for one player, including the three-parameter pattern.", "",
              "Two further representative requests used the documented three-parameter pattern, `parentLeagueId=47`, and a `before` cursor after each target season:"]
    for r in probes:
        lines.append(f"- {r['season_label']}, player `{r['params']['playerId']}`, before `{r['params']['before']}`: HTTP {r['http_status']}, `{r['response_error'] or r['outcome']}`; [raw response](../../{r['raw_path']}), [metadata](../../{r['metadata_path']}).")
    if len(probes) < len(PROBES):
        lines.append(f"- Only {len(probes)}/{len(PROBES)} bounded probes are retained; unattempted probes remain UNKNOWN.")
    lines += ["", "The endpoint remains **UNVERIFIED** for historical pagination. A parameter error does not prove historical match data is absent. No additional parameter guessing or full match download was performed. The verified fixture index plus selective matchDetails participation is the current fallback.", ""]
    atomic_write(ROOT / "reports/phase_02b0/match_index_readiness.md", ("\n".join(lines)).encode("utf-8"))
    return {**facts, "player_matches_probes": len(probes),
            "player_matches_statuses": dict(Counter(r["http_status"] for r in probes))}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="allow at most two documented-pattern HTTP probes")
    args = parser.parse_args()
    result = probe_player_matches(args.probe)
    facts = write_report()
    print(json.dumps({"probe": result, "facts": facts}, indent=2))
