# Data Contract: `player_season_integrated_v1`

Location: `data/releases/fb69_player_season_integrated_v1/`. Full column list with roles and types: `data_dictionary.csv`.

## Grain and keys

- **One row per canonical player-season.** Business key: `canonical_player_id + season`.
- Population: the frozen FotMob v3.1 Confirmed set: 3,262 rows and 1,343 players, across 6 seasons.
- `season` uses the source's labels (`2019/2020`).
- Identifiers are text. `canonical_player_id` is `fb69p_<fotmob_player_id>`.

## Columns by role

| Role | Columns | Use |
|---|---:|---|
| `KEY` | 4 | Keys |
| `IDENTITY_LINK` | 1 | `transfermarkt_player_id`; null if unresolved |
| `IDENTITY_CONTEXT` | 4 | Names and birth date; **`nationality_profile_present_day` isn't historical** |
| `POPULATION_EVIDENCE` | 8 | Why the row is Confirmed |
| `CLUB_CONTEXT` | 8 | Club relations and `multi_club_class` |
| `CONTEXT_FEATURE` | 2 | `age_at_season_end_years`, `position_group_season` |
| `FEATURE_FOTMOB_METRIC` | 53 | `m_*`: unchanged FotMob values |
| `FEATURE_STATUS_FOTMOB` | 53 | `s_*`: unchanged status per metric |
| `TARGET` | 2 | `target_market_value`, `target_currency` |
| `TARGET_METADATA` | 11 | Status, dates, age, lineage |
| `TARGET_AUDIT_NOT_A_PREDICTOR` | 6 | April 2020 batch flag and previous valuation |
| `IDENTITY_QUALITY` | 10 | Crosswalk status and evidence tier |
| `TEMPORAL_ALIGNMENT_NOT_A_PREDICTOR` | 9 | Games and minutes relative to the valuation |
| `QUALITY_FLAG` | 4 | 2019/20 and missingness flags |
| `PROVENANCE` | 5 | Versions and raw paths |

**Only the `FEATURE_*` and `CONTEXT_FEATURE` roles may be candidate predictors.** Anything `target_`, `temporal_` or `identity_` isn't one: these are derived from the target's date, or describe it. Which candidates to use is a Phase 4 decision.

## Missing values

- Null means missing. No null is converted to zero, and nothing is imputed.
- `target_market_value` is null if `target_usable` is false, and `target_missing_reason` explains why.
- `s_*` columns say why a metric is null: for example `MISSING`, `UNSUPPORTED` or `UNVERIFIED_POSITION`.

## Target

- Latest valid Transfermarkt valuation with date on or before the official season end. Rule version `latest_valid_on_or_before_season_end_v1`.
- EUR as recorded by the source; not converted.
- `target_status`: `VALID` (up to 90 days), `STALE_TARGET` (over 90 days; usable, labeled only), `TARGET_MISSING`. `INVALID_VALUATION` and `AMBIGUOUS_VALUATION` are allowed values with no rows in this version.

## Owner decisions in force

| Decision | Rule |
|---|---|
| **D6** | Research objective is **A: end-of-season estimation**. Results must not be presented as forecasting, or as performance determining value |
| **D7** | Keep all 2019/20 rows and original values. Treat 2019/20 xG and xA as unavailable for comparison (`xg_xa_unavailable_for_comparison`). Require results with and without 2019/20 (`sensitivity_season_2019_20`) |
| **D2** | Internal academic research with attribution. Upstream Transfermarkt rights aren't independently verified. Don't redistribute raw data or imply Transfermarkt licensed it |

**Family extension:** the D7 flag is row-level, and applies to `m_expected_goals`, `m_expected_assists`, `m_non_penalty_xg` and `m_expected_goals_on_target`. All four have the same 4-of-380 coverage in 2019/20.

## Change rules

Any change means a new version. Human review of an identity changes the crosswalk version, then the target, then this dataset. Never edit a generated file by hand.
