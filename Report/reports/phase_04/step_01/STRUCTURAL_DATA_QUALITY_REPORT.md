# Phase 4.1: Structural Data Quality Report

Date: 2026-11-08. Official dataset, verified by SHA-256 before it was read. Every finding is reported and kept as published. The dataset was not modified: its hash is unchanged after profiling, which a test checks.

## Results

| Check | Result | Evidence |
|---|---|---|
| Duplicate primary keys (`canonical_player_id`, `season`) | 0 | `profiling_summary.json` |
| Null primary keys | 0 | same |
| Duplicate full rows | 0 | same |
| Arrow types vs data dictionary | 175 of 175 equal | `type_mismatches_vs_dictionary` |
| Column order vs dictionary | equal | `column_patterns` |
| Column patterns | every `m_*` has an `s_*` and vice versa (53/53); all names snake_case | same |
| Categorical domains (65 columns: season, season id, position, target status/reason/bucket/currency, crosswalk status, identity label, population status, multi-club class, scope id, 53 status columns) | 0 unexpected values | `categorical_domains.csv` |
| Domain-invalid numeric values (negative counts, percentages outside 0–100, rating outside 0–10, age outside 15–45, non-positive target, negative valuation age or temporal counts) | 0 | `schema_profile.csv` (`invalid_values`) |
| Metric value vs `s_*` status (a value exactly when the status is an observed one; `OBSERVED_ZERO` equals 0) | 0 disagreements | `metric_status_consistency.csv` |
| Constant columns | 14 (by construction; listed in `DATASET_PROFILING_REPORT.md`) | `schema_profile.csv` |
| Single value plus nulls / near-constant | 3 / 2 | same |

## Cross-column logic (`evidence/logical_checks.csv`)

| Rule | Rows |
|---|---:|
| `m_starts > m_appearances` | **6** (known DQ-RS5-04) |
| `m_shots_on_target > m_shots` | 0 |
| `m_goals > m_shots` | 0 |
| `m_minutes_played > 90 × m_appearances` | 0 |
| `m_appearances > 38` | 0 |
| started + sub-in ≠ confirmed appearances | 0 |
| confirmed appearances < 1 | 0 |
| `target_usable` ≠ target value present | 0 |
| `VALID` target older than 90 days / `STALE_TARGET` not older | 0 / 0 |
| `missing_feature_count` ≠ number of null `m_*` | 0 |
| temporal games after valuation > games in season | 0 |
| per-90 rate reported with minutes < 90 | **40** (new observation, P4-B05) |

## Known anomaly: starts greater than appearances (kept as published)

| Player | Season | `m_appearances` | `m_starts` | Lineup appearances | Lineup starts |
|---|---|---:|---:|---:|---:|
| Liam Cooper | 2020/21 | 25 | 26 | 25 | 25 |
| Harry Maguire | 2020/21 | 34 | 35 | 34 | 34 |
| Lukasz Fabianski | 2020/21 | 35 | 36 | 35 | 35 |
| Alisson Becker | 2020/21 | 33 | 34 | 33 | 33 |
| Jonny Evans | 2020/21 | 28 | 29 | 28 | 28 |
| Ozan Kabak | 2020/21 | 9 | 10 | 9 | 9 |

All 6 rows are in 2020/21, and each reports exactly one extra start. Lineup evidence agrees with `m_appearances`, so the excess sits in the source's start count. The values are **not corrected**. Status `s_starts` is `OBSERVED` on all six rows.

## New observation: per-90 rates on small denominators (P4-B05)

40 rows report per-90 rates while fewer than 90 minutes were played. The rates match the source totals (`rate = total × 90 / minutes`), but small denominators make them extreme. The largest cases (`evidence/extreme_per90_rows.csv`):

| Player | Season | Minutes | Tackles per 90 | Accurate passes per 90 |
|---|---|---:|---:|---:|
| Alexandre Jankewitz | 2020/21 | 3 | 60.0 | 60.0 |
| Kenedy | 2021/22 | 59 | 7.6 | 51.9 |
| Nathaniel Chalobah | 2022/23 | 12 | 7.5 | 30.0 |

These are not errors and nothing was changed. The condition register records P4-B05: Phase 4.2 should read per-90 distributions together with minutes, and any minimum-minutes rule is an owner decision.

## Conclusion

The dataset is structurally sound. No impossible values, type errors, unexpected categories, key violations or value/status contradictions were found. The two structural irregularities are the known 6-row starts anomaly, which is preserved, and unstable per-90 rates on very small minute totals, which are documented. Neither needs a data change.
