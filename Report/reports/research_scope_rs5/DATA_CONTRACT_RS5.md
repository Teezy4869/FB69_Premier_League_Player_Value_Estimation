# Data Contract: FB69 rs5 Research Data

Applies to every artifact under `data/releases/*rs5*` and `data/research_rs5/`. Historical contract: `reports/phase_03/step_05/DATA_CONTRACT.md` (unchanged; it governs v1 only).

## Scope (D9)

- **Allowed seasons:** `2020/2021`, `2021/2022`, `2022/2023`, `2023/2024`, `2024/2025`. Source: `configs/research_scope.yaml`.
- **Excluded:** `2019/2020` (FotMob `season_id` 14022, Transfermarkt season 2019). No row, aggregate, evidence or report value derived from it may appear in an rs5 artifact.
- **Objective:** A, end-of-season estimation (D6). Unchanged.
- **Cutoff:** official season end from `configs/phase_03_seasons.yaml`; rule `latest_valid_on_or_before_season_end_v1` (D4).
- **D7 is superseded.** No 2019/20 flags, sensitivity or comparison columns.

## Enforcement

- Each rs5 builder calls `src/research_scope/scope.py` (`check_table` / `check_parquet`). Any excluded or unknown season, or a label/id mismatch, raises `ScopeViolation` and the build writes nothing.
- `tests/research_scope/` re-checks every rs5 parquet file.
- No rs5 source file may hard-code a season (tested).

## Grain and keys

| Artifact | Grain | Key |
|---|---|---|
| FotMob player-season tables | player × season | `season_id, player_id` |
| Player-team-season | player × team × season | `season_id, player_id, team_id` |
| Player-match | player × match | `match_id, player_id` |
| Target | player × season | `canonical_player_id, season` |
| Crosswalk | FotMob identity | `fotmob_player_id` (also unique `canonical_player_id`; mapped `transfermarkt_player_id` unique) |
| Integrated dataset | player × season | `canonical_player_id, season` |

## Values

- FotMob values, statuses, provenance and timestamps are carried unchanged from v3.1. Nothing is recomputed per row.
- Null means missing. `UNKNOWN`, `UNVERIFIED` and null are never converted to zero, and nothing is imputed.
- Target values are EUR as published by the source. Not converted.
- Column roles follow the historical dictionary. Only `FEATURE_*` and `CONTEXT_FEATURE` may be candidate predictors. `target_*`, `temporal_*` and `identity_*` columns are never predictors.

## Versioning

Every rs5 artifact has a manifest with: version, scope id, source references and their SHA-256, code SHA-256, row counts by season, output SHA-256, and generation time. A changed input or rule means a new version. Builders refuse to overwrite an existing version with different content.

## Integrated dataset `player_season_integrated_rs5_v1` (added in Step 3)

Location: `data/releases/fb69_player_season_integrated_rs5_v1/`. 2,747 rows × 175 columns; full list with role, type and predictor eligibility: `data_dictionary.csv`.

| Role | Columns | Candidate predictor |
|---|---:|---|
| `FEATURE_FOTMOB_METRIC` (`m_*`) / `FEATURE_STATUS_FOTMOB` (`s_*`) | 53 / 53 | Yes |
| `CONTEXT_FEATURE` (`age_at_season_end_years`, `position_group_season`) | 2 | Yes |
| `KEY`, `IDENTITY_LINK`, `IDENTITY_CONTEXT`, `POPULATION_EVIDENCE`, `CLUB_CONTEXT` | 4, 1, 4, 8, 8 | No |
| `TARGET`, `TARGET_METADATA`, `TARGET_AUDIT_NOT_A_PREDICTOR` | 2, 11, 3 | No |
| `IDENTITY_QUALITY` (includes `identity_rs5_validation_label`) | 11 | No |
| `TEMPORAL_ALIGNMENT_NOT_A_PREDICTOR` | 8 | No |
| `QUALITY_FLAG` (`missing_feature_count`), `PROVENANCE` (includes `research_scope_id`) | 1, 6 | No |

**Removed from v1:** `sensitivity_season_2019_20`, `xg_xa_unavailable_for_comparison`, `feature_quality_status` (D7), `target_on_2020_04_08_batch`, `target_audit_last_non_batch_valuation_date`, `target_audit_age_days_from_last_non_batch`, `temporal_player_games_after_last_non_batch` (constant or duplicated in scope).

`CLUB_CONTEXT` columns aren't candidate predictors by default; Phase 4 decides (historical leakage note: club can proxy value and reflect a later transfer).
