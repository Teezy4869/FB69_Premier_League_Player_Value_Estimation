# Phase 2B.1 Execution 04: historical identity and match index

Status: CONDITIONAL PASS

Profiles: 1757/1757 unique IDs; missing 0.
Player-seasons: 4052; confirmed memberships: 3323; unresolved: 812; multi-club player-seasons: 61.
Matches: 2280 completed / 2281 fixture records. Bournemouth–Luton abandoned 4193691 is excluded; replay 4421797 retained.
Appearance statuses: {'STARTED': 50160, 'SUBSTITUTED_ON': 15628, 'UNUSED_SUBSTITUTE': 7290, 'UNKNOWN': 16314}. Only STARTED and SUBSTITUTED_ON count as confirmed.
Historical position observations: 151475; labels are Phase 2B.0 inferred exact-code mappings, never current profile positions.
Season-stat appearance reconciliation: {'MATCH': 3260, 'SOURCE_MISSING': 2}; discrepancies are reported, not rewritten.
HTTP attempts this run: 0; errors: {}; profile checkpoint: {'VALIDATED': 414}.
HTTP attempts for Execution 04 profile IDs, all runs: 415; response statuses: {'200': 415}.
Tests: 92 run, exit code 0; see execution04_tests/test_execution.log.

`playerMatches` remains unverified after prior HTTP 400 and was not retried. UNKNOWN substitutes remain unresolved. No season acceptance is asserted.

Raw lineage is retained in profile_raw_path, fixture_raw_path, appearance raw_path, membership evidence_raw_paths, and historical position raw_path.

Resume: `python -m src.collection.execution04_identity --collect --max-requests 50`.

## Season coverage

| Season | Profile IDs | Confirmed membership | Unresolved membership | Completed matches | Started | Substituted on | Unknown |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019/2020 | 614/614 | 522 | 99 | 380 | 8360 | 2254 | 46 |
| 2020/2021 | 641/641 | 532 | 120 | 380 | 8360 | 2033 | 3449 |
| 2021/2022 | 679/679 | 546 | 145 | 380 | 8360 | 2125 | 3401 |
| 2022/2023 | 699/699 | 569 | 154 | 380 | 8360 | 2985 | 2561 |
| 2023/2024 | 734/734 | 580 | 166 | 380 | 8360 | 3024 | 3236 |
| 2024/2025 | 685/685 | 574 | 128 | 380 | 8360 | 3207 | 3621 |

The normalized outputs are versioned under `data/phase_02b1/normalized/execution04_v1/`. The CSV reports in this directory retain profile, membership, position, fixture, appearance, multi-club, exception, and season-stat comparisons.
