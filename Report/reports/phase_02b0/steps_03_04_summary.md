# Phase 2B.0 Steps 03–04 — identity, position, metric and Match Index review

**Verdict: CONDITIONAL PASS.** The bounded evidence supports historical club relationships and a status-aware fixture index. Three retrospective second-club relationships, exact position semantics, one minutes conflict and `playerMatches` pagination remain unresolved. No full crawl or modeling was performed.

## Historical identity and team attribution

- 3267 versioned relations: 3264 HISTORICAL_VERIFIED and 3 HISTORICAL_INFERRED. Of the verified rows, 3,262 come from season boards and two additional club relations from historical lineups. There are 5 multi-club player-season pairs: 2 have both relations verified, and three retain an inferred second club (Archer 2023/24, Ramsdale 2024/25, Archer 2024/25). The bounded ID/name collision checks found no review candidates; see the membership rules for the four check types.
- 84/120 pilot current clubs differ from season-board clubs. Current profile fields never generate historical team rows. No duplicate normalized player-season or player-team-season keys; player-season totals are never summed with team relations. See [identity rows](historical_identity_validation.csv) and [membership rules](historical_membership_rules.md).

## Historical position

- The Phase 2A sampling code used numeric code bands. The new [exact-code registry](position_mapping_registry.json) has 88 mappings, retaining raw FotMob codes and historical lineup evidence. Broad role labels inferred from source `usualPlayingPositionId` remain HISTORICAL_INFERRED; uncorroborated or mixed exact codes remain UNKNOWN. There is no arbitrary numeric-range promotion to verified history.
- 44/120 sampled player-season rows have observed starter-lineup position evidence. 3 conflict with the old pilot code-band group: Georginio Wijnaldum 2019/2020: FWD -> MID; Alex Oxlade-Chamberlain 2019/2020: MID -> FWD; Sadio Mané 2019/2020: MID -> FWD. Wijnaldum's 2019/20 leaderboard code `104` was called FWD by the old band, while retained historical lineups show `positionId` 64/77 and source usual-role code 2, supporting an inferred MID group. Multiple match codes are preserved. See [position validation](position_validation_report.csv).

## Statistics reconciliation

- [Metric dictionary v2](metric_dictionary_v2.csv): 24 candidates; {'VERIFIED': 2, 'PARTIAL': 16, 'EXCLUDED_FOR_NOW': 1, 'UNVERIFIED': 1, 'POSITION_SPECIFIC': 4}. Source fields, units, aggregation type, positions, season coverage, missing states and provenance are explicit. Per-90 is retained separately from totals; goalkeeper saves compares the leaderboard's `Total saves` substat.
- [Comparison evidence](metric_reconciliation_report.csv): 183 compatible overlaps, 1 unresolved. In 2024/25, Mac Allister (`831489`) has `2607` minutes in `mins_played` versus `2606` in `playerStats`; both are integer season totals, with no documented rounding explanation or justified source preference. Both raw values remain.

## Match Index and playerMatches

- 2281 fixture records, 2280 finished, one abandoned/cancelled. Bournemouth–Luton `4193691` remains separate from finished replay `4421797`. The 18-match fallback verifies 513 player–match entries; full participation and match-level statistics remain UNKNOWN.
- The named wrapper's documented parameter pattern was tested for two player/seasons within a two-attempt budget. Both returned HTTP 400 `Invalid or missing query parameters`; original response bodies and request metadata are retained. This does not prove historical data is absent. See [Match Index readiness](match_index_readiness.md).

## Reproducibility and limits

```powershell
python -m src.collection.historical_identity
python -m src.collection.position_mapper
python -m src.collection.metric_reconciler
python -m src.collection.match_index_validator
python -m src.collection.phase_02b0_03_04 --tests "48/48 passing (python -m unittest discover -s tests -v)"
python -m unittest discover -s tests -v
```

`match_index_validator --probe` only attempts missing documented-pattern probes and is capped at two HTTP requests. The offline commands above use saved evidence. Validation issues: 0; tests: 48/48 passing (python -m unittest discover -s tests -v). Phase 1, Phase 2A and Steps 01–02 raw evidence were preserved. Steps 05–06 and Phase 2B.1 were not started.
