# Phase 2B.1 Execution 01 — repository and environment preflight

**PASS.** This preflight built and checked the control plane only. It made **zero Phase 2B.1 collection HTTP attempts**. [Manifest](collection_manifest.csv), [configuration](../../configs/full_collection.yaml), [batch results](batches/), [test log](test_execution.log).

## Actual repository and reusable components

Project root: `D:\PTIT\Hoc_may\FB69`. Existing dependencies are declared in [requirements.txt](../../requirements.txt); installed versions: {'requests': '2.34.2', 'pandas': '3.0.5', 'PyYAML': '6.0.3', 'pyarrow': '24.0.0'}. `pip check` exit code: 0 ([output](dependency_check.log)). No dependency installation was needed. The repository already has `AuditClient` for paced/retried HTTP, `SourceRegistry` for canonical request keys and immutable SHA-256 captures, `historical_lineup_validator` for finished fixtures and appearances, `metric_reconciler`/dictionary v2, `position_mapper`, and seven pilot Parquet schemas. [Prior source audit](../phase_02b0/source_integrity_report.csv), [metric registry](../phase_02b0/metric_dictionary_v2.csv), [pilot schema](../phase_02a/schema_definition.json).

Prior raw checksum scan: 277 Phase 1/2A/2B.0 captures; pilot normalized table row counts: {'matches': 2281, 'metric_observations': 2880, 'player_match_links': 47, 'player_seasons': 120, 'player_team_seasons': 120, 'players': 109, 'teams': 27}. The new source registry writes to a distinct `data/phase_02b1/raw` tree; no previous report or raw capture was rewritten. [Source design](../phase_02b0/steps_01_02_summary.md), [new manifest](collection_manifest.csv).

## Scope and unresolved controls

Season IDs match cached FotMob league evidence and pilot configuration: {'2019/2020': 14022, '2020/2021': 15382, '2021/2022': 16390, '2022/2023': 17664, '2023/2024': 20720, '2024/2025': 23685}. The manifest is acyclic and has 2346 tasks, including 2304 fixed request tasks and 42 local gates. Each season has 380 finished `matchDetails` tasks; the abandoned Bournemouth–Luton ID is excluded and the replay retained. The 6 open Phase 2B.0 conditions remain explicit: unknown full population, three inferred second clubs, unresolved position meanings, the Mac Allister minutes conflict, unverified `playerMatches`, and responses lacking direct season context. [Issue tracker](../phase_02b0/hardening_issue_tracker.csv), [plan](request_storage_plan.md).

Verified endpoint assumptions: `leagues`, `leagueseasondeepstats`, `matchDetails`, `playerData`, `playerStats`. `teams` current squad responses cannot prove historical membership and `playerMatches` is excluded pending a working historical contract. Cache identity uses request key plus season; raw SHA-256 and provenance are checked before validation. `FETCHED` stays separate from `VALIDATED`. The Stage F/G validator checks seven complete-season tables, all 380 fixtures, appeared-player links, metric states and raw lineage. It remains BLOCKED until collection finishes and a full-season normalizer produces those tables; this preflight does not certify an uncollected season. [Quality-gate source](../../src/collection/full_season_gate.py), [batch gate](../../src/collection/batch_quality.py), [runner](../../src/collection/full_orchestrator.py), [prior limitations](../phase_02b0/phase_02b0_readiness_report.md).

## Real automated tests and raw-only batch checks

Command: `python -m unittest discover -s tests -v`. Exit code **0**; tests **61**, failures **0**, errors **0**, skipped **0**. The complete actual output is [test_execution.log](test_execution.log); machine summary and SHA-256 are [test_execution.json](test_execution.json). No manually supplied test-count string is accepted.

Cached validation has accepted 52 task results across six seasons using prior raw evidence; machine-readable batch decisions are [under batches](batches/). It did not fetch any missing match detail. Full-season population tasks remain dependent on all 380 validated match details per season, and dynamic player tasks are appendable only from observed appearances. [Manifest](collection_manifest.csv), [batch gate](../../src/collection/batch_quality.py).

## Execution 02 gate

Infrastructure dry-run, manifest dependencies, cache-only resume and batch quarantine rules are operational. **A full-season normalization producer and complete-season acceptance tests remain required before declaring any season accepted.** Execution 02 also needs a separately authorized bounded run budget. The request/storage numbers are estimates, not completed collection. [Execution guide](execution_guide.md), [planning report](request_storage_plan.md).
