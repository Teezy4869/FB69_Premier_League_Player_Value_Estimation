# Phase 2B.1 Execution 03: Season Statistics

Generated: 2026-11-03T01:57:35.286736+00:00

Appeared player-seasons: 3262; dictionary metrics: 53; leaderboard captures: 132.

| Season | State | Appeared | Represented by valid statistic | playerStats validated | Boards | Metrics observed | Confirmed GK |
|---|---|---:|---:|---:|---:|---:|---:|
| 2019/2020 | COMPLETE | 515 | 515 | 515 | 22 | 52 | 20 |
| 2020/2021 | COMPLETE | 524 | 524 | 524 | 22 | 51 | 20 |
| 2021/2022 | COMPLETE | 537 | 537 | 537 | 22 | 52 | 20 |
| 2022/2023 | COMPLETE | 554 | 554 | 554 | 22 | 51 | 19 |
| 2023/2024 | COMPLETE | 570 | 570 | 570 | 22 | 52 | 19 |
| 2024/2025 | COMPLETE | 562 | 562 | 562 | 22 | 52 | 19 |

## Core metric coverage

| Season | Minutes | Goals | xG | xA | Saves | Key passes |
|---|---:|---:|---:|---:|---:|---:|
| 2019/2020 | 515/515 | 477/515 | 69/515 | 96/515 | 20/20 | 0/515 |
| 2020/2021 | 524/524 | 486/524 | 433/524 | 516/524 | 20/20 | 0/524 |
| 2021/2022 | 537/537 | 496/537 | 446/537 | 532/537 | 20/20 | 0/537 |
| 2022/2023 | 554/554 | 515/554 | 458/554 | 549/554 | 19/19 | 0/554 |
| 2023/2024 | 570/570 | 532/570 | 460/570 | 559/570 | 19/19 | 0/570 |
| 2024/2025 | 562/562 | 520/562 | 457/562 | 553/562 | 19/19 | 0/562 |

Ranked boards with fewer rows than appeared players have PARTIAL_RANKED_OR_FILTERED status unless explicit pagination metadata exists.
COMPLETE means all planned collection tasks passed their season gates; it does not mean every metric is available for every appeared player.
Board team tags are retained. A playerStats season total is compared with a leaderboard value only for a one-club appeared player and the same metric, unit, and aggregation.
Missing values are never imputed as zero. Goalkeeper denominators use only IDs confirmed by the saves leaderboard and are a lower-bound position cohort.
The API payload does not provide a stable explicit unit for every source item; source_reported_unit remains blank in those observations. Normalized unit and source format are separate columns.
Current playerData profile fields are excluded; only the checked EPL statSeasons entry supports playerStats scope.

Requests: {'attempts': 4504, 'unique_request_identities': 4490, 'repeated_request_identities': 14, 'task_level_recollection_attempts': 14, 'by_endpoint': {'leagueseasondeepstats': 114, 'playerData': 1234, 'playerStats': 3156}, 'transport_retry_attempts': 0, 'http_non_200': 0, 'outcomes': {'OK': 4490, 'FAILED': 14}}
Exceptions: {'SOURCE_VALUE_CONFLICT': 575}
Quality gates (historical batches): {'PASS': 142, 'STOP': 2, 'REVIEW': 4}; errors seen: {'RAW_CAPTURE_ERROR': 1, 'NO_STATS_PAYLOAD': 13, 'SCHEMA_ERROR': 4}
Current unresolved task errors: {}
Reconciliation: {'MATCH_ROUNDED': 17578, 'INCOMPARABLE_MULTICLUB': 707, 'MATCH': 12727, 'CONFLICTING': 575}
Metrics with no observed values at this checkpoint: ['key_passes']

Detailed per-season, per-metric denominators and missingness are in metric_collection_coverage.csv.
The source API has no verified pagination or team-filter contract in these captures; no unverified page or team probes were made.

## Checkpoint

No player task is pending or retryable. No collection resume is required.
Regenerate reports without HTTP: `python -m src.collection.statistics_report` and `python -m src.collection.statistics_audit`.
