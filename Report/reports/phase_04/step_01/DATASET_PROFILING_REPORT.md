# Phase 4.1: Dataset Profiling Report

Date: 2026-11-08. Dataset: `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet`, SHA-256 `4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd` (verified before every read). Scope `rs5_v1` from `load_scope()`.

The figures come from `src/phase4/profiling.py`. That module writes `evidence/` and also runs inside the Phase 4.1 section of `FB69_report.ipynb`, so the notebook and this report show the same numbers. Nothing was imputed, filtered, corrected or transformed.

## 1. Overview

| Measure | Value |
|---|---:|
| Rows = player-season records | 2,747 |
| Columns | 175 |
| Unique players | 1,228 |
| Seasons (equal to the official scope) | 5 |
| Usable / missing targets | 2,697 / 50 |
| Target coverage | 98.18% |
| Duplicated full rows / duplicated keys / null keys | 0 / 0 / 0 |

Primary key: `canonical_player_id`, `season`. Evidence: `evidence/profiling_summary.json`.

## 2. Schema and column profiling

The full table is `evidence/schema_profile.csv`, with one row per column: Arrow type, dictionary type, role, eligibility category, non-null, null, missing %, unique values, top-value share, constant flags, and domain-invalid count with its rule. Eligibility categories are taken from the Phase 4.0 register. No new classification was introduced.

| Eligibility category | Columns | Mean missing % | Constant |
|---|---:|---:|---:|
| STATUS_MISSINGNESS (`s_*`, `missing_feature_count`) | 53 | 0.00 | 0 |
| CANDIDATE_PREDICTOR | 41 | 23.26 | 0 |
| IDENTITY_METADATA | 33 | 8.82 | 10 |
| CONDITIONAL_PREDICTOR | 21 | 33.11 | 0 |
| TARGET | 16 | 7.88 | 1 |
| TEMPORAL_AUDIT | 8 | 1.14 | 1 |
| EXCLUDED_PREDICTOR | 3 | 33.33 | 2 |

"Constant" means one state on every row, with null counted as a state (14 columns in total).

- **Types:** all 175 Arrow types equal the data dictionary.
- **Domain-invalid values:** none. Every count is non-negative, the 6 percentage metrics lie in [0, 100], rating lies in [0, 10], age in [15, 45], targets are positive, and no valuation age is negative.
- **Strictly constant columns (14):** `population_status`, `population_category`, `classification_reason`, `profile_status`, `target_selection_rule_version`, `identity_human_reviewed` (all False), `matching_version`, `temporal_league_games_in_season` (380), `dataset_version`, `research_scope_id`, `fotmob_source_version`, `transfermarkt_source_version`, `m_key_passes` (all null), `s_key_passes` (all `UNSUPPORTED`). They are constant by construction and carry no analytical information.
- **One value plus nulls (3):** `target_currency`, `target_source_file_sha256` and `identity_adjudicator`. They are filled only where a target or an adjudication exists.
- **Near-constant, top value at 99% or more (2):** `identity_match_status` (2 unresolved rows) and `s_appearances`.
- **Columns with any null:** 75 of 175.

## 3. Season distribution

| Season | Rows | Share | Unique players | Usable | Missing | Coverage | Also in previous season |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020/21 | 524 | 19.08% | 524 | 515 | 9 | 98.28% | n/a |
| 2021/22 | 537 | 19.55% | 537 | 528 | 9 | 98.32% | 349 |
| 2022/23 | 554 | 20.17% | 554 | 542 | 12 | 97.83% | 337 |
| 2023/24 | 570 | 20.75% | 570 | 567 | 3 | 99.47% | 350 |
| 2024/25 | 562 | 20.46% | 562 | 545 | 17 | 96.98% | 352 |

The seasons are balanced. Unique players equal rows in every season, so no player has two rows in one season. About 63–65% of each season's players also appear in the previous season. Seasons per player: 1 season 541, 2 seasons 243, 3 seasons 194, 4 seasons 112, 5 seasons 138 (687 players appear in 2 or more seasons).

## 4. Missingness overview

Measured on the 53 metric columns (`m_*`). For goalkeeper-only metrics it is also measured on goalkeeper rows, the rows where those metrics apply. Each null is paired with its `s_*` status. No cause is inferred.

| Measure | Value |
|---|---:|
| Null metric cells | 48,043 of 145,591 (33.00%) |
| Null cells across all 175 columns | 59,755 of 480,725 (12.43%) |
| Metrics with at least one null | 53 of 53 |

| Group | Null metric cells | Mean null metrics per row |
|---|---:|---:|
| 2020/21 / 2021/22 / 2022/23 / 2023/24 / 2024/25 | 32.84 / 32.34 / 33.79 / 34.50 / 31.47% | 17.41 / 17.14 / 17.91 / 18.29 / 16.68 |
| GK / DEF / MID / FWD | 65.07 / 28.32 / 29.59 / 33.81% | 34.49 / 15.01 / 15.69 / 17.92 |
| Usable target / missing target | n/a | 17.03 / 42.10 |

Null share by metric family: GENERAL 7.96%, EXPECTED 18.20%, ATTACK 22.67%, PASSING 28.63%, DEFENDING 29.86%, GOALKEEPING 93.19% (goalkeeper-only by design).

The most incomplete metrics, measured on the rows where they apply, are `key_passes` (100%), `clearances` and `clearances_per90` (80.67%; values in 3 of 5 seasons), `big_chances_created` (44.27%), `cross_accuracy` and `successful_crosses` (41.75%), `blocked_shots` and `blocks_per90` (34.69%), and `penalty_saves` (31.55% of goalkeeper rows).

**How nulls are coded** (`evidence/status_by_position.csv`):

| Status cells | Outfield rows | Goalkeeper rows |
|---|---:|---:|
| `UNVERIFIED_POSITION` on GK-only metrics | 17,787 | 112 |
| `MISSING` (source gap) | 20,597 | 6,764 |
| `OBSERVED_ZERO` (true zero) | 5,259 | 503 |
| `UNSUPPORTED` (`key_passes`) | 2,541 | 206 |
| `CONFLICTING` | 14 | 22 |

On outfield rows, `UNVERIFIED_POSITION` means a goalkeeper-only metric is not applicable. It does not mean missing performance. Evidence: `missingness_by_*.csv`, `status_by_season.csv`.

## 5. Points for later EDA

1. Rows of the same player are not independent: 687 players have several seasons, and about two thirds of each season's players return the following season.
2. Missingness depends on position, playing time and target availability. Read it through the `s_*` statuses, never as zero.
3. The 14 constant columns and `m_key_passes` carry no information. The RD-04 metrics (`clearances` among them) still await an owner decision.
4. Per-90 rates on small minute totals are unstable (P4-B05; see `STRUCTURAL_DATA_QUALITY_REPORT.md`).
