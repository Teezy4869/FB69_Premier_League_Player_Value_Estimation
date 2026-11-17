# Integration Audit (Phase 3, Step 5)

Date: 2026-11-05. Build log: `data/releases/fb69_player_season_integrated_v1/integration_manifest.json`. Validation: `evidence/validation_summary.json` (31 checks, 0 failed).

**Result:** 3,262 rows and 3,262 unique canonical player-seasons, the exact frozen Confirmed population. No row was lost, added or duplicated at any stage.

## 1. Integration contract

| Item | Contract |
|---|---|
| Source grain | One row per FotMob `(season_id, player_id)` |
| Output grain | One row per `canonical_player_id + season` |
| Identity | `canonical_player_id = fb69p_<fotmob_player_id>`: one per person, so grain carries over directly |
| Join type | LEFT JOIN from the population. Right key must be unique, and row count must not change, or the build stops |
| Multi-club | One row per player-season; club rows kept separately |
| Exclusions | **None.** Unmatched, stale and missing rows stay, with status fields |
| Features | FotMob only, unchanged. No Transfermarkt statistic replaces a FotMob one |

## 2. Join audit

| # | Join | Rows before | Right rows | Right unique keys | Rows after | Left without match |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Population attributes (FotMob) | 3,262 | 3,262 | 3,262 | 3,262 | 0 |
| 2 | Player identity (FotMob) | 3,262 | 1,757 | 1,757 | 3,262 | 0 |
| 3 | Season position (FotMob lineups) | 3,262 | 4,051 | 4,051 | 3,262 | 0 |
| 4 | Identity crosswalk | 3,262 | 1,343 | 1,343 | 3,262 | 0 |
| 5 | Season-end target | 3,262 | 3,262 | 3,262 | 3,262 | 0 |
| 6 | Target quality flags (Step 4.1) | 3,262 | 3,262 | 3,262 | 3,262 | 0 |
| 7 | Temporal alignment (Step 4.1) | 3,262 | 3,262 | 3,262 | 3,262 | 0 |

Right tables with more rows than the population (2, 3) include people or seasons outside the Confirmed set, which a LEFT JOIN leaves out.

There is **no many-to-many join**. Tests confirm that a duplicate right key, a null key, or an unmatched required row stops the build.

## 3. Population reconciliation

| Stage | Rows |
|---|---:|
| FotMob v3.1 Confirmed source | 3,262 |
| Unique source keys | 3,262 |
| Final integrated rows | 3,262 |
| Final unique keys | 3,262 |
| Lost / added / Unverified rows entered | 0 / 0 / 0 |
| Distinct players | 1,343 |

| Season | Rows | Identity mapped | Usable target | Missing target |
|---|---:|---:|---:|---:|
| 2019/20 | 515 | 514 | 498 | 17 |
| 2020/21 | 524 | 524 | 515 | 9 |
| 2021/22 | 537 | 536 | 528 | 9 |
| 2022/23 | 554 | 554 | 542 | 12 |
| 2023/24 | 570 | 569 | 567 | 3 |
| 2024/25 | 562 | 562 | 545 | 17 |
| **Total** | **3,262** | **3,259** | **3,195** | **67** |

**Why the numbers differ:**

| From | To | Rows lost | Reason |
|---|---|---:|---|
| 3,262 population | 3,259 identity mapped | 3 | `REVIEW_REQUIRED`: Tauriainen, Jota, Chesters |
| 3,259 mapped | 3,195 usable | 64 | 51 only have valuations after the cutoff; 13 have no valuation history |

None of these rows leaves the dataset.

## 4. Multi-club handling

| Class | Rows | Row duplicated? | Target decisions |
|---|---:|---|---:|
| `SINGLE_CLUB` | 3,182 | No | 1 each |
| `MULTI_CLUB_CONFIRMED_APPEARANCES` | 61 | No | 1 each |
| `MULTI_CLUB_SQUAD_ONLY` | 19 | No | 1 each |

Club-level evidence: `player_team_season_evidence.parquet` (3,342 rows). Full explanation: `MULTI_CLUB_INVESTIGATION.md`.

## 5. Flags joined

| Requested | Columns |
|---|---|
| Target quality | `target_status`, `target_usable`, `target_missing_reason` |
| Staleness | `target_valuation_age_days`, `target_staleness_bucket` |
| Temporal alignment | `temporal_alignment_class`, and games, minutes and league counts before and after the valuation |
| 2019/20 batch | `target_on_2020_04_08_batch`, `target_audit_*` |
| 2019/20 sensitivity (D7) | `sensitivity_season_2019_20`, `xg_xa_unavailable_for_comparison`, `feature_quality_status` |
| Identity reliability | `crosswalk_status`, `identity_evidence_tier`, `identity_review_status`, `identity_human_reviewed`, adjudication fields |

**Original values:** 491 April 2020 rows keep their original date and value. No automated match is labeled human: `identity_human_reviewed` is false on all 3,262 rows.

## 6. Column integrity

| Check | Result |
|---|---|
| 106 FotMob `m_*` and `s_*` columns, compared cell by cell with source, including nulls | 0 differences |
| Null features that became 0 | 0 |
| Target fields vs target dataset | 0 differences |
| Target value vs its exact row in the original CSV | 0 differences |
| Selected valuation after cutoff | 0 |
| Forbidden present-day or future columns | None |
| Columns with no role | 0 of 180 |

## 7. New columns are limited to

Status, audit and context fields. Two derived context fields are new features: `age_at_season_end_years` and `position_group_season`, both from FotMob. `multi_club_class` is a label. No new performance feature was created.

## 8. Other outputs

The SOP asks for `fotmob_confirmed_population.parquet`. I didn't produce a separate copy: the integrated dataset's key columns give the same population, and it's reconciled here. The SOP's `canonical_player_id` definition, `DATA_CONTRACT.md` and execution tracker are delivered in this folder.
