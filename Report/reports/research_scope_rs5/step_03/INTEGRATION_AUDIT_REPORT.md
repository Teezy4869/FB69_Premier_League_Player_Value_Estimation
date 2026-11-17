# rs5 Step 3: Integration Audit

Release: **`data/releases/fb69_player_season_integrated_rs5_v1/`**: `player_season_integrated_rs5_v1.parquet` (2,747 × 175), `player_team_season_evidence.parquet` (2,820), `data_dictionary.csv`, `integration_manifest.json`. Builder: `src/research_scope/integrate_rs5.py`. Validator: `src/research_scope/validate_rs5.py` (evidence: `evidence/integration_validation.json`).

## Inputs

FotMob `fotmob_epl_2020_2025_rs5_v1` (curated and normalized), crosswalk `matching_v2_1_rs5`, rs5 validation labels, and target `target_rs5_v1__matching_v2_1_rs5` with its temporal and previous-valuation evidence. Every input's SHA-256 is in the manifest.

## Business rules kept from Phase 3 (`src/phase3/integrate.py`)

- Start from the Confirmed population: an ordered LEFT JOIN chain, with no row dropped.
- Every join uses the approved `checked_join`: right keys unique and non-null, row count unchanged, or the build stops.
- FotMob `m_*` and `s_*` values copied unchanged. Multi-club players stay one row; club detail goes in the separate evidence table.
- Crosswalk and target must agree on canonical id, TM id and matching version on every row.
- Expected rows and players are read from the rs5 FotMob release, not hard-coded.

## Joins (all at most one right row per left row)

| Join | Right rows = unique keys | Rows before → after | Left rows without match |
|---|---:|---:|---:|
| Population attributes | 2,747 | 2,747 → 2,747 | 0 |
| FotMob players | 1,611 | 2,747 → 2,747 | 0 |
| Season position (modal lineup; covers Unverified rows too) | 3,437 | 2,747 → 2,747 | 0 |
| Crosswalk rs5 | 1,228 | 2,747 → 2,747 | 0 |
| Validation label (optional) | 1,226 | 2,747 → 2,747 | 2 (unresolved) |
| Target rs5 | 2,747 | 2,747 → 2,747 | 0 |
| Previous-valuation audit | 2,747 | 2,747 → 2,747 | 0 |
| Temporal alignment | 2,747 | 2,747 → 2,747 | 0 |

No many-to-many join; no row added or lost.

## Results

| Measure | Value |
|---|---:|
| Player-season rows / unique keys | 2,747 / 2,747 |
| Unique players | 1,228 |
| Rows per season | 524 / 537 / 554 / 570 / 562 |
| Matched (mapped) rows / unmatched | 2,745 / 2 |
| Usable / missing targets | **2,697 / 50** |
| Integration coverage (usable targets / rows) | **98.18%** |
| Duplicate player-season rows | 0 |
| Null metric cells | 48,043 of 145,591 (33.00%) |
| Mean null metrics per row, with target / without | 17.03 / 42.10 of 53 |
| Multi-club rows: confirmed appearances / squad only | 54 / 19 |

**Every non-usable row has a documented reason:** 37 `ONLY_VALUATIONS_AFTER_CUTOFF`, 11 `NO_VALUATION_HISTORY`, 2 `NO_ELIGIBLE_IDENTITY_MATCH`. No row was excluded.

## Reconciliation with the historical six-season release

On the 168 shared columns, leaving out identity labels and version strings, the rs5 dataset **equals the v1 rows for the five seasons exactly** (0 rows differ in either direction). The differences are all intentional:

| Difference | Rows | Why |
|---|---:|---|
| `identity_evidence_tier` | 32 | Validation re-derived on in-scope evidence |
| `crosswalk_method` | 1 | Deeney: no in-scope club evidence |
| `matching_version`, `dataset_version`, `fotmob_source_version` | all | New versions |
| 7 dropped columns | | D7 flags and the 2020-04-08 batch columns; constant or duplicated in scope |
| 2 added columns | | `identity_rs5_validation_label`, `research_scope_id` |

## Column roles

Of 175 columns, the candidate predictors are the 106 `FEATURE_*` (53 `m_*` metrics, 53 `s_*` statuses) and the 2 `CONTEXT_FEATURE` columns. Every `target_*`, `temporal_*` and `identity_*` column has a non-predictor role (tested). `nationality_profile_present_day` stays `IDENTITY_CONTEXT`.
