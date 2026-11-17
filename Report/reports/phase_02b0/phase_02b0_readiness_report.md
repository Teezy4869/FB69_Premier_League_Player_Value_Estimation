# Phase 2B.0 Steps 05–06 — final hardening acceptance

## 1. Executive Summary

**Verdict: CONDITIONAL GO.** The bounded live run, cache replay and full regression suite support a carefully monitored Phase 2B.1 collection only under the conditions below. This is not a claim of full historical population completeness or future access reliability. [Reliability evidence](collection_reliability_report.md), [issue tracker](hardening_issue_tracker.csv).

## 2. Original Phase 2A Problems

Phase 2A had a candidate-only population, reused caller-defined source IDs for two team probes, six unused substitutes in a lineup-membership table, numeric-band position guesses, current profiles that did not prove historical clubs, and a one-minute Mac Allister conflict. [Population audit](population_coverage_report.md), [source aliases](source_id_aliases.csv), [Steps 03–04 review](steps_03_04_summary.md).

## 3. Changes Implemented

Steps 01–04 added season-scoped population and source registries, immutable capture IDs, exact-code position evidence and metric conflict records. Step 05 added bounded `Retry-After`, raw-body retention for malformed responses, a cache guard for wrong-season captures, a single-worker reliability runner and replay/normalization recovery checks. [Earlier summary](steps_01_02_summary.md), [Step 05 results](collection_reliability_report.md), [tests](../../tests/collection/test_reliability_step05.py).

## 4. Historical Population Validation

The 18-match historical sample found 0 player IDs absent from the candidate union, but two club relations absent from leaderboard rows. A synthetic missing-ID regression confirms the detector fires. The full six-season appearing-player denominator remains UNKNOWN; Phase 2B.1 must reconcile every finished fixture lineup before claiming completeness. [Coverage report](population_coverage_report.md), [population rows](historical_population_validation.csv), [missing-ID test](../../tests/collection/test_reliability_step05.py).

## 5. Source Identity and Provenance

The independent audit checked 277 pre-Step-05 captures, 10620 normalized/population/lineup references, and 0 unresolved structural problems. Two legacy caller source-ID aliases map to distinct canonical request keys; they are not unresolved request-key collisions. All 23 Step 05 raw paths passed SHA-256 verification and have complete request metadata. [Source integrity](source_integrity_report.csv), [aliases](source_id_aliases.csv), [live metrics](request_metrics.csv).

## 6. Historical Player and Team Integrity

The Step 03 index contains 3264 season-evidence verified and 3 inferred relations. Five player-season pairs have multiple clubs; three second-club claims remain inferred. Current clubs are never promoted automatically, and season totals are not allocated or summed by club. [Identity rows](historical_identity_validation.csv), [rules](historical_membership_rules.md).

## 7. Position Mapping

The exact-code registry has 88 entries: {'HISTORICAL_INFERRED': 32, 'UNKNOWN': 56}. Three old pilot groups conflict with historical lineup evidence; unknown codes stay UNKNOWN. [Registry](position_mapping_registry.json), [validation rows](position_validation_report.csv).

## 8. Metric Reconciliation

The versioned dictionary has 24 candidates with explicit units and aggregation. One of 183 compatible overlaps remains UNRESOLVED: Mac Allister 2024/25 minutes 2607 versus 2606. Both source values are retained; no automatic source preference is applied. [Dictionary](metric_dictionary_v2.csv), [comparison rows](metric_reconciliation_report.csv).

## 9. Match Index Validation

The saved six-season fixture index has 2281 records, 2280 finished, one abandoned/cancelled, and a distinct Bournemouth–Luton replay. The 18-match fallback establishes 513 player-match pairs. `playerMatches` remains unverified after two bounded HTTP 400 responses. [Match Index report](match_index_readiness.md).

## 10. Live HTTP Reliability

23 actual attempts; HTTP 200 100.0%, endpoint-valid data 91.3%, JSON parse 100.0%, direct season scope 65.2%. Average/P95 latency 0.562/1.146 seconds; retries 0. Two historical team probes remain unverified, excluded. [Detailed live report](collection_reliability_report.md), [request metrics](request_metrics.csv).

## 11. Cache and Resume Testing

23/23 checkpoint hits with zero live HTTP on repeat; 6/6 isolated recovery scenarios passed, including 10-checkpoint interruption and seven-table normalization replay. [Recovery rows](recovery_test_results.csv), [reliability report](collection_reliability_report.md).

## 12. Failure Injection Results

Mocked 400, 403, 429/Retry-After, 500/503, timeout, reset, invalid/empty/unexpected JSON and wrong-season captures were handled with bounded retries or rejection. Existing valid raw remained intact in the interrupted-write and corrupted-cache tests. These are **mocked**, separate from live rates. [New tests](../../tests/collection/test_reliability_step05.py), [earlier registry tests](../../tests/collection/test_phase_02b0.py).

## 13. Automated Test Results

`python -m unittest discover -s tests -v`: 54/54 passing; failures 0; skipped 0; failures 0, skipped 0. The run includes Phase 1, Phase 2A, Steps 01–04 and Step 05 regressions. [Test modules](../../tests/collection/test_reliability_step05.py), [execution guide](phase_02b0_execution_guide.md).

## 14. Remaining Risks

Full population completeness, three inferred second clubs, position semantics, one minutes conflict, `playerMatches` pagination, and eight responses without direct season fields remain explicitly unresolved. See [issue tracker](hardening_issue_tracker.csv).

## 15. Mandatory Acceptance Checklist

| Mandatory control | Result | Evidence |
|---|---|---|
| No unresolved request identity collisions | PASS | [source_integrity_report.csv](source_integrity_report.csv), [source_id_aliases.csv](source_id_aliases.csv), [request_metrics.csv](request_metrics.csv) |
| No silent raw overwriting or loss | PASS | [source_integrity_report.csv](source_integrity_report.csv), [recovery_test_results.csv](recovery_test_results.csv) |
| Current club never becomes historical club automatically | PASS | [historical_membership_rules.md](historical_membership_rules.md), [historical_identity_validation.csv](historical_identity_validation.csv) |
| No unsupported position-code guessing | PASS | [position_mapping_registry.json](position_mapping_registry.json), [position_validation_report.csv](position_validation_report.csv) |
| Verified missing-player detection strategy | PASS_WITH_PHASE_2B1_COMPLETION | [population_coverage_report.md](population_coverage_report.md), [historical_population_validation.csv](historical_population_validation.csv), [test_reliability_step05.py](../../tests/collection/test_reliability_step05.py) |
| Metric conflict strategy documented | PASS | [metric_dictionary_v2.csv](metric_dictionary_v2.csv), [metric_reconciliation_report.csv](metric_reconciliation_report.csv) |
| Historical fixture index and limitations | PASS | [match_index_readiness.md](match_index_readiness.md) |
| Bounded requests, cache, resume and errors | PASS | [collection_reliability_report.md](collection_reliability_report.md), [recovery_test_results.csv](recovery_test_results.csv) |
| Mandatory automated tests | PASS | [test_reliability_step05.py](../../tests/collection/test_reliability_step05.py) |
| Traceable evidence for major claims | PASS | [request_metrics.csv](request_metrics.csv), [source_integrity_report.csv](source_integrity_report.csv) |

## 16. Final Verdict

**CONDITIONAL GO.** No observed critical defect remains in the bounded tested paths. The small live sample and unknown full population prevent an unconditional GO. A failed per-batch control during Phase 2B.1 must stop collection and reopen this decision. [Live report](collection_reliability_report.md), [issue tracker](hardening_issue_tracker.csv).

## 17. Required Actions Before Phase 2B.1

Review and approve the [collection specification](phase_02b1_collection_spec.md). Keep one worker, bounded per-batch attempts, source checksums and checkpoint resume; exclude unverified team rosters and never promote inferred positions/clubs. Begin Phase 2B.1 with per-season fixture/lineup reconciliation and stop on access restrictions, scope mismatch, raw corruption or unresolved missing players. This report does not start Phase 2B.1. [Specification](phase_02b1_collection_spec.md), [execution guide](phase_02b0_execution_guide.md).
