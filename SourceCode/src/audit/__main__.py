"""Run with: python -m src.audit"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .discovery import SOURCES, run


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded FotMob availability audit")
    parser.add_argument("--config", default="configs/fotmob_audit.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / args.config).read_text(encoding="utf-8"))
    result = run(config, root)
    rows = result["rows"]
    catalog = result["catalog"]
    lines = [
        "# Phase 1: FotMob API and season availability",
        "",
        f"Collected (UTC): {rows[-1]['collected_at_utc']}",
        f"Competition ID 47 independently verified: **{'yes' if result['league_verified'] else 'no'}**.",
        f"HTTP attempts: {result['attempts']} of {config['request_budget']} allowed.",
        "",
        "## Season evidence",
        "",
        "| Season | Numeric ID | Teams | Matches | Player stat rows | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['season']} | {row['numeric_season_id']} | {row['team_count']} | {row['fixture_count']} | {row['player_stat_count']} | {row['overall_status']} |")
    lines += ["", "The league endpoint uses `YYYY/YYYY` season strings; `leagueseasondeepstats` uses the numeric `TournamentId` from `stats.seasonStatLinks`. A 200 response counts as available only when the requested season is selected and substantive records exist. Match counts are raw fixture entries; the 2023/2024 response contains 381 distinct match IDs, so downstream collection must inspect that extra entry before treating the index as 380 league fixtures.", "", "## Endpoint probes", ""]
    for name, item in catalog.items():
        lines.append(f"- `{name}`: {item['live_status']} (HTTP {item.get('http_status', 'not sent')}); {item.get('last_source_url') or 'no request'}.")
    lines += ["", "`playerMatches` returned HTTP 400 both without `before` and with a historical Unix `before` value. The documented parameter pattern is therefore unconfirmed against the current interface. The six deep-stat probes request only `goals`, so they establish endpoint availability, not coverage of every metric or completeness of all players.", "", "## Limitations and next step", "", "Resolve player match pagination, inspect the extra 2023/2024 fixture entry, and check metric coverage and per-player historical profiles in a separate bounded audit before bulk collection. FotMob's interface is unofficial and may change. No Transfermarkt integration or ML work was done.", "", "## Sources", ""]
    lines += [f"- {url}" for url in SOURCES]
    lines += ["", "Live request URLs, timestamps, statuses, response sizes and errors are in `fotmob_endpoint_catalog.json` and `logs/fotmob_requests.jsonl`. Samples in `data/audit/raw_samples/` are complete when small and marked structural excerpts when large.", ""]
    (result["report_dir"] / "discovery_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote audit reports to {result['report_dir']} ({result['attempts']} HTTP attempts)")


if __name__ == "__main__":
    main()
