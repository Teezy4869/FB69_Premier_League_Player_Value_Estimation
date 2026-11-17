# Phase 2B.0 Step 05 — collection reliability

The configured one-worker plan made **23 actual live HTTP attempts** for 23 logical requests, below the 50-attempt Step 05 cap and 150-attempt absolute ceiling. The plan progressed through six league-index smoke probes, six season leaderboard probes, three live profile/stat pairs, three historical match details, and two known problematic team-roster probes. No request identities were rotated. Source: [per-attempt metrics](request_metrics.csv), [immutable live observations](../../data/phase_02b0/reliability/observations/), [HTTP log](../../logs/phase_02b0_reliability_requests.jsonl), and [runner configuration](../../configs/reliability_config.yaml).

| Live measurement | Observed |
|---|---:|
| HTTP 200 | 23/23 (100.0%) |
| JSON parse success | 23/23 (100.0%) |
| Expected schema shape | 23/23 (100.0%) |
| Endpoint-valid data | 21/23 (91.3%) |
| Direct historical scope accepted | 15/23 (65.2%) |
| Historical scope not directly returned | 8/23 |
| Average / nearest-rank P95 latency | 0.562s / 1.146s |
| Retry attempts | 0 |
| Raw SHA-256 checks | 23/23 |
| Provenance complete | 23/23 |
| Duplicate request keys | 0 |

Outcome categories: {'VALID_DATA': 21, 'HISTORICAL_SCOPE_UNVERIFIED': 2}. HTTP_SUCCESS is 23/23; VALID_DATA is 21/23. EMPTY_DATA, SCHEMA_ERROR, PARAMETER_ERROR, RATE_LIMITED, ACCESS_DENIED, SERVER_ERROR and NETWORK_ERROR were not observed live. Mocked failures are counted separately in the [automated tests](../../tests/collection/test_reliability_step05.py). A 23/23 HTTP result is a small bounded observation, not a prediction of access during full collection.

Six playerData/playerStats responses are linked through season-specific Premier League `statSeasons` entries chosen from live profiles; the responses themselves do not directly return a season identifier. Two `teams` responses have valid JSON shape but no explicit historical squad season; they are `HISTORICAL_SCOPE_UNVERIFIED` and excluded as historical membership evidence. The direct-scope rate deliberately counts neither group as directly verified. See [request rows](request_metrics.csv) and [historical membership rules](historical_membership_rules.md).

## Cache, resume and failure injection

A repeat of the 23-request live plan gave 23/23 checkpoint hits and **0 HTTP attempts**. The cache-hit rate for this repeat is 100.0%, separate from live HTTP reliability. [Recovery results](recovery_test_results.csv) show 6/6 scenario checks passing: an injected interruption after 10 saved responses, resume equivalence with an uninterrupted replay of the same wire bytes, no duplicate request keys, repeated actual normalization into isolated paths, and repair of a deliberately corrupted test output. Raw checksums and metadata were checked before replay. The [failure-injection tests](../../tests/collection/test_reliability_step05.py) cover HTTP 400/403/429/500/503, timeout, connection reset, invalid JSON, empty data, wrong schema, wrong season, and bounded retry behavior. These mocked outcomes are not included in live rates.

Defects fixed before live testing: `AuditClient` now honors a bounded `Retry-After` and retains wire bytes on parse/content failures; `SourceRegistry` preserves but refuses to reuse a wrong-season capture. The remaining conditions are in [the issue tracker](hardening_issue_tracker.csv).
