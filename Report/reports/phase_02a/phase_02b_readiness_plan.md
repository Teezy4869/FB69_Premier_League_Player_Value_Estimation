# Phase 2B readiness plan (planning only)

Verdict: **CONDITIONAL GO**. This document authorizes no Phase 2B requests. The following are gates before a full historical crawl.

## Hard gates

1. Build a season-scoped, independent historical player denominator. Validate team and player coverage separately for each of the six seasons; report UNKNOWN until complete.
2. Change raw `source_id` generation to include season and endpoint/parameters, migrate or alias the two existing Liverpool team probes, and reject collisions in validation.
3. Define source precedence for team/player-season totals. Keep the 2024/25 Mac Allister minutes conflict (2607 leaderboard, 2606 playerStats) visible and add an exception register.
4. Validate historical position and multi-club spells with season-scoped evidence. Preserve one aggregate player-season row and separate verified player-team-season rows; never divide an aggregate without evidence.
5. Prove one supported, bounded player-match participation route with pagination and status behavior. If no route passes, scope Phase 2B to fixture index and selected details explicitly.

## Proposed collection order and endpoint priority

1. Cache six `leagues` responses and season/team fixture inventories; validate season IDs, 20 teams, fixture status and replay handling.
2. Establish complete historical player references by a verified season-scoped roster endpoint or independently reconciled player index; do not infer completeness from leaderboards.
3. Collect `playerData` once per unique ID, then request `playerStats` only for verified `statSeasons` entries and season IDs.
4. Collect `leagueseasondeepstats` only for explicitly needed cross-checks and documented metric definitions. Defer `matchDetails` to a bounded participation plan; do not brute-force `playerMatches` parameters.

## Request budget, storage and recovery

Estimate requests from the verified denominator and endpoint plan before execution. Set a per-run cap, bounded retries with backoff, concurrency ceiling and stop condition for 429/5xx; preserve response status and timestamps. The pilot's 265/265 success rate is not a forecast. Store immutable raw JSON and metadata under `data/phase_02b/raw/<season>/<endpoint>/` with SHA-256, exact parameters, UTC timestamp, HTTP status, content type, response-byte kind and unique source ID. Write atomically. Cache key includes endpoint, parameters and season; verify checksum before reuse. Maintain a durable request ledger with PENDING/OK/FAILED and resumable cursor. Never overwrite verified raw bytes; quarantine corrupt or incomplete pairs and retry deliberately.

## Normalized schema and duplicate policy

Use the pilot's seven tables: players, teams, player_seasons, player_team_seasons, matches, player_match_links, metric_observations. Keep explicit primary keys and source IDs. Preserve original FotMob fields, raw values, units, statistic type, source title, status and timestamps. Use player ID plus season ID for aggregates, player/team/season for verified club relationships, match ID for fixtures, player/match for lineup links, and player/season/metric for observations. Reject duplicate keys and inconsistent repeated payloads; maintain both raw versions and a reconciliation record rather than silently replacing data. Keep current profile fields separate from historical facts.

## Validation checkpoints

- Before requests: verify season IDs, endpoint contracts, budget and denominator evidence.
- After each batch: check logged attempts vs raw pairs, checksums, JSON parse, unique source IDs, season/team scope and cache restore.
- After each season: check reference coverage against independent denominator, profile season association, playerStats completion, nulls by metric/position, field/unit versioning and cross-source conflicts.
- After match ingestion: require 380 finished league fixtures per season or document status/replay exceptions; validate match dates, teams and selected player lineup evidence.
- Before sign-off: enforce Parquet schemas, unique keys, foreign keys, source lineage, idempotent rebuild hashes, and thresholds set using the pilot report; document unresolved UNKNOWN values.

## Pilot-driven adjustments

Use position-aware missingness. Keep `key_passes` UNVERIFIED, `minutes_played` OPTIONAL until the one-minute conflict has a source-precedence rule, and rating EXCLUDED_FOR_NOW until its definition is established. Retain goalkeeper N/A distinctly from missing. Do not treat `initialMatchesPage` as historical. Do not infer a zero from absent stats. Include the source-ID collision and Mac Allister minute conflict as regression fixtures.
