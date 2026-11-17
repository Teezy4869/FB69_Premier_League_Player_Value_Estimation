# Phase 2B.1 Execution 01 — request and raw-storage plan

These are **planning estimates**, not requests executed or guaranteed population counts. The [manifest](collection_manifest.csv) contains 2346 tasks: 2304 fixed HTTP tasks and 42 local gates. 46 fixed HTTP tasks already reuse verified saved raw; up to 2258 fixed HTTP tasks remain uncached in this manifest. Execution 01 sent **zero** collection HTTP requests. [Preflight](preflight_report.md), [prior population audit](../phase_02b0/population_coverage_report.md).

| Endpoint | Fixed tasks | Candidate-based dynamic proxy | Saved raw sample count | Mean sample bytes |
|---|---:|---:|---:|---:|
| `leagues` | 6 | 0 | 12 | 877,687 |
| `leagueseasondeepstats` | 18 | 0 | 24 | 90,099 |
| `matchDetails` | 2280 | 0 | 25 | 236,392 |
| `playerData` | 0 | 1343 | 112 | 109,391 |
| `playerStats` | 0 | 3262 | 123 | 38,624 |

The leaderboard candidate proxy is **1343 distinct player IDs** and **3262 player-season IDs**; appendable tasks use actual appeared-player evidence instead. If every candidate became an appeared player, the simple proxy would be 6,909 logical HTTP tasks, including 2,304 fixed tasks. This is neither a lower nor an upper bound on final requests: the full appeared-player denominator is unknown, profile reuse may reduce calls, and missing leaderboard players may add calls. At the observed endpoint means, fixed raw JSON would be about 545.9 MB and candidate-proxy raw JSON about 818.8 MB, excluding metadata, retries, quarantines and Parquet. Response sizes can change substantially. [Metric dictionary](../phase_02b0/metric_dictionary_v2.csv), [saved response evidence](../phase_02b0/source_integrity_report.csv).

Batch budgeting remains at most 50 actual HTTP attempts including retries per explicitly authorized run, one worker and a configured minimum interval of 1.2 seconds based on the bounded pilot setting. These numbers do not authorize a full crawl. [Configuration](../../configs/full_collection.yaml), [previous live measurements](../phase_02b0/collection_reliability_report.md).
