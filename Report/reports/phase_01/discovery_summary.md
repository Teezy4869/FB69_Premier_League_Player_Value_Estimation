# Phase 1: FotMob API and season availability

Collected (UTC): 2026-11-02T06:46:37.196154+00:00
Competition ID 47 independently verified: **yes**.
HTTP attempts: 19 of 25 allowed.

## Season evidence

| Season | Numeric ID | Teams | Matches | Player stat rows | Status |
|---|---:|---:|---:|---:|---|
| 2019/2020 | 14022 | 20 | 380 | 262 | AVAILABLE |
| 2020/2021 | 15382 | 20 | 380 | 270 | AVAILABLE |
| 2021/2022 | 16390 | 20 | 380 | 281 | AVAILABLE |
| 2022/2023 | 17664 | 20 | 380 | 271 | AVAILABLE |
| 2023/2024 | 20720 | 20 | 381 | 298 | AVAILABLE |
| 2024/2025 | 23685 | 20 | 380 | 271 | AVAILABLE |

The league endpoint uses `YYYY/YYYY` season strings; `leagueseasondeepstats` uses the numeric `TournamentId` from `stats.seasonStatLinks`. A 200 response counts as available only when the requested season is selected and substantive records exist. Match counts are raw fixture entries; the 2023/2024 response contains 381 distinct match IDs, so downstream collection must inspect that extra entry before treating the index as 380 league fixtures.

## Endpoint probes

- `allLeagues`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/allLeagues.
- `leagues`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/leagues?id=47&season=2024%2F2025.
- `leagueseasondeepstats`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/leagueseasondeepstats?id=47&season=23685&type=players&stat=goals.
- `teams`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/teams?id=8650.
- `playerData`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/playerData?id=286119.
- `playerMatches`: FAILED (HTTP 400); https://www.fotmob.com/api/data/playerMatches?playerId=286119&before=1596240000&parentLeagueId=47.
- `matchDetails`: AVAILABLE (HTTP 200); https://www.fotmob.com/api/data/matchDetails?matchId=3055738.

`playerMatches` returned HTTP 400 both without `before` and with a historical Unix `before` value. The documented parameter pattern is therefore unconfirmed against the current interface. The six deep-stat probes request only `goals`, so they establish endpoint availability, not coverage of every metric or completeness of all players.

## Limitations and next step

Resolve player match pagination, inspect the extra 2023/2024 fixture entry, and check metric coverage and per-player historical profiles in a separate bounded audit before bulk collection. FotMob's interface is unofficial and may change. No Transfermarkt integration or ML work was done.

## Sources

- https://github.com/pseudo-r/Public-FotMob-API
- https://github.com/ccdejene/fotmob-mcp
- https://github.com/petmorr/FotMobDataAnalysis

Live request URLs, timestamps, statuses, response sizes and errors are in `fotmob_endpoint_catalog.json` and `logs/fotmob_requests.jsonl`. Samples in `data/audit/raw_samples/` are complete when small and marked structural excerpts when large.
