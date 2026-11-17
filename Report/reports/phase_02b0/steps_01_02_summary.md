# Phase 2B.0 Steps 01–02 — execution summary

**Result: CONDITIONAL PASS**. Step 01 established a bounded appearing-player sample, but the full-season denominator is UNKNOWN. Step 02 has deterministic request identity and immutable new capture storage; original Phase 1/2A raw files remain unchanged.

## Population

- Rebuilt 3262 candidate player-team-season rows from 18 cached leaderboard responses, across six seasons; no claim of full population.
- Validated 18/18 selected match details, of which 12 were newly captured. 513 appeared entries; 456 unique player-season IDs; 0 absent player IDs; 2 missing candidate team relationships. Unused substitutes excluded.
- 5 confirmed entered-substitute appearances have fewer than 90 season leaderboard minutes, so low-minute participation is represented by observed events.
- Re-audit of the preserved Phase 2A `player_match_links`: 41/47 actually appeared; 6 were unused substitutes. That table represented lineup membership, not confirmed participation.
- See [population coverage](population_coverage_report.md) and [row evidence](historical_population_validation.csv).

## Source identity and integrity

- Audited 277 captures: 265 legacy and 12 new. All JSON, SHA-256 and stored paths validated. Computed scope status counts: {'ACCEPTED': 46, 'UNVERIFIED': 231}. The 231 UNVERIFIED responses are 109 playerData, 120 playerStats and two historical `teams` probes whose bodies lack an explicit season scope; a separate verified profile `statSeasons` association does not turn a `playerStats` response into explicit season metadata. 10620 normalized/population/lineup evidence references resolved; 0 structural problems.
- Root cause of Liverpool collision: the two calls supplied the same caller-defined `source_id=team_roster_probe_liverpool`. Their canonical season parameters and legacy filename/cache hashes differ, so request-key/filename generation did not collide. Their content SHA-256 is equal, because both responses contained the same current-oriented roster; `details.latestSeason` is 2026/2027 and the squad has no returned historical season. Both remain **UNVERIFIED** historical roster evidence.
- New `request_key` hashes method, canonical path, sorted normalized parameters and contract; 2019/20 versus 2024/25 team requests have distinct keys. A UUID `capture_id` names an immutable directory; actual bytes have a separate `content_sha256`. The versioned [alias report](source_id_aliases.csv) maps the two legacy records to separate request/capture identities without modifying them.
- New captures are written to a temporary directory and atomically renamed. Cache lookup checks request key **and** expected season, rejects differing payloads under one key/season and verifies checksums. Matching match-detail context is checked against the season fixture index. No HTTP 200 alone is treated as historical proof.
- The source URL for each of the 12 new captures is recoverable from the immutable Phase 2B.0 HTTP log by timestamp, endpoint and canonical parameters; it is included in the source integrity report. Future captures also write it into metadata. Existing raw metadata was not edited.
- See [source integrity rows](source_integrity_report.csv). The 265 legacy captures remain in place; 12 new matchDetails captures are under `data/phase_02b0/raw/`.

## Reproduction and limits

```powershell
python -m src.collection.historical_lineup_validator
python -m src.collection.historical_lineup_validator --collect
python -m src.collection.provenance_validator --tests "40/40 passing (python -m unittest discover -s tests -v)"
python -m unittest discover -s tests -v
```

The non-collect command rebuilds only from cache. Repeating `--collect` uses cache and should issue zero HTTP calls. New collection remains capped at 12 attempts by configuration. Tests: 40/40 passing (python -m unittest discover -s tests -v). Full historical crawl, all-match detail download, Transfermarkt merge and modeling were not performed. Full-season population completeness remains UNKNOWN.
