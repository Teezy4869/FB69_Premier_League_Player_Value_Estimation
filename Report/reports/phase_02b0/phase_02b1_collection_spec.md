# Phase 2B.1 — proposed full historical collection specification

**Execution requires a separate approval and phase gate.** Scope: Premier League (FotMob league 47), seasons 2019/20 through 2024/25. No Transfermarkt merge or modeling. This specification follows the [Phase 2B.0 acceptance](phase_02b0_readiness_report.md) and [issue tracker](hardening_issue_tracker.csv).

## Order and population

Process one season at a time, oldest to newest (2019/20 → 2024/25), with a gate after each season. Start each season from its `leagues` fixture index, preserve every Match ID and status, and include the completed replay while excluding the abandoned Bournemouth–Luton record from completed counts. The expected completed count is 380 per season in the saved indexes; any live deviation requires review. Build a leaderboard candidate union, then derive the appeared-player denominator from all completed `matchDetails` lineups: starters and substitutes with `subIn` only. Reconcile each missing player ID and club relation; do not claim complete coverage while a finished match lacks a validated lineup. [Population method](population_coverage_report.md), [fixture evidence](match_index_readiness.md).

## Endpoint priority and fallback

Use `leagues` for fixtures and `leagueseasondeepstats` for candidate metrics, then `matchDetails` for player appearances. Access `playerData` only to verify player ID and locate the target Premier League `statSeasons` entry; request `playerStats` with that entry ID and retain the indirect-scope caveat. Do not use current `primaryTeam`, position or nationality as historical values. `teams` roster responses lacking an explicit season are excluded. `playerMatches` is not a population source until its parameters and historical scope work in bounded tests; the verified fixture-plus-detail method is the fallback. [Live observations](request_metrics.csv), [Match Index](match_index_readiness.md).

## Identity, metrics and schema

Use FotMob player ID, team ID and season ID; retain every season-evidence verified club relation and mark retrospective candidates inferred. Never allocate a player-season total to multiple clubs. Preserve raw position codes; promote groups only under the exact-code evidence rules, keeping UNKNOWN when ambiguous. Use [metric dictionary v2](metric_dictionary_v2.csv): retain units and total/per-90/percentage distinctions, and preserve both values of unresolved conflicts with no automatic preference. Normalize to the seven existing Parquet tables (`players`, `teams`, `player_seasons`, `player_team_seasons`, `matches`, `player_match_links`, `metric_observations`), extending status and provenance fields by version rather than overwriting previous outputs. Distinct keys are player-season, player-team-season, match ID and appeared player-match. [Schema](../phase_02a/schema_definition.json), [identity rules](historical_membership_rules.md).

## Raw storage, deduplication and resume

Store original wire bytes, immutable per-capture metadata, UTC timestamp, canonical request key, UUID capture ID, source URL, expected season, HTTP status, content type and SHA-256. Write to a temporary directory, fsync files, then atomically commit. Index cache by canonical request key plus season; refuse divergent payloads or wrong-season responses, preserving mismatches separately for audit. Use checkpoints by logical request, verify checksum on every hit, and reconstruct unfinished batches from committed captures after interruption. Never overwrite Phase 1, Phase 2A or Phase 2B.0 raw evidence. [Source rules](source_integrity_report.csv), [recovery evidence](recovery_test_results.csv).

## Rate, budget and progress

Start with **one worker and at least 1.2 seconds between request starts**, as in the 23-attempt Step 05 observation. Use at most one bounded retry with exponential backoff; honor `Retry-After`, and stop rather than wait or retry when it exceeds the configured ceiling. Set an explicit per-batch budget of at most 50 actual HTTP attempts including retries, and a separately approved overall phase budget before any full run. The Step 05 ceiling of 150 is not an authorization or target for Phase 2B.1. Report attempted, cached, valid, empty, rejected, retried, missing and completed counts per endpoint and season after each batch. [Runner configuration](../../configs/reliability_config.yaml), [reliability metrics](collection_reliability_report.md).

## Validation and stop conditions

Per batch: verify status, parse, schema, source scope, raw checksum, unique request key and capture ID, lineage and primary keys. Per season: reconcile 380 completed fixtures and status exceptions, all lineup availability, appeared IDs against candidate union, missing club relations, duplicate keys, nullable metrics, position uncertainty and unresolved metric conflicts. Stop the affected workflow on HTTP 403/429, sustained 5xx, unsafe `Retry-After`, scope mismatch, corrupted cache, duplicate capture identity or missing provenance. Escalate a missing or ambiguous historical player association; do not silently fill with current roster data or zeros. The data-quality gate requires complete fixture/lineup accounting, traceable historical membership, explicit unresolved statuses and zero silent overwrites. [Acceptance checklist](phase_02b0_readiness_report.md), [issues](hardening_issue_tracker.csv).

## Known limits

The 18-match sample cannot prove full population coverage; 3 second-club relations and many position meanings remain inferred/unknown; Mac Allister minutes conflict is unresolved; `playerMatches` historical pagination has not been validated. A 23/23 live HTTP result does not guarantee future access. These conditions remain visible throughout collection. [Prior findings](steps_03_04_summary.md), [live measurements](collection_reliability_report.md).
