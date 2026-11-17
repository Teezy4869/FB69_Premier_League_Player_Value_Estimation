# Missingness Report (Phase 3, Step 5)

Date: 2026-11-05. Full results, including nulls per metric and season: `evidence/missingness.json`.

**Conclusion:** missing values are preserved everywhere, with reasons. Nothing was imputed or converted to zero. **Missingness is not random**, which Phase 4 must account for.

## 1. By season

| Season | Rows | Missing value | Missing valuation date | Missing TM ID | Mean missing features (of 53) |
|---|---:|---:|---:|---:|---:|
| 2019/20 | 515 | 17 | 17 | 1 | 19.70 |
| 2020/21 | 524 | 9 | 9 | 0 | 17.41 |
| 2021/22 | 537 | 9 | 9 | 1 | 17.14 |
| 2022/23 | 554 | 12 | 12 | 0 | 17.91 |
| 2023/24 | 570 | 3 | 3 | 1 | 18.29 |
| 2024/25 | 562 | 17 | 17 | 0 | 16.68 |
| **Total** | **3,262** | **67** | **67** | **3** | |

## 2. By target status

| Status | Rows | Has value | Mean missing features |
|---|---:|---:|---:|
| `VALID` | 1,171 | 1,171 | 16.36 |
| `STALE_TARGET` | 2,024 | 2,024 | 17.96 |
| `TARGET_MISSING` | 67 | 0 | **40.13** |
| `INVALID_VALUATION`, `AMBIGUOUS_VALUATION` | 0 | 0 | |

| Reason for `TARGET_MISSING` | Rows | Mean missing features |
|---|---:|---:|
| `ONLY_VALUATIONS_AFTER_CUTOFF` | 51 | 38.51 |
| `NO_VALUATION_HISTORY` | 13 | 47.00 |
| `NO_ELIGIBLE_IDENTITY_MATCH` | 3 | 38.00 |

**Stale targets stay usable.** Their age is explicit in every row.

## 3. By crosswalk status and evidence tier

| Crosswalk status | Evidence tier | Rows | Has value | Missing value | Mean missing features |
|---|---|---:|---:|---:|---:|
| `AUTO_EXACT` | `AUTO_EXACT_VALIDATED` | 2,577 | 2,549 | 28 | 16.66 |
| `AUTO_EXACT` | `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 584 | 551 | 33 | 22.40 |
| `AUTO_ADJUDICATED` | `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 90 | 87 | 3 | 20.38 |
| `AUTO_ADJUDICATED` | `AUTO_ADJUDICATED_EXTERNAL` | 8 | 8 | 0 | 28.38 |
| `REVIEW_REQUIRED` | `UNRESOLVED` | 3 | 0 | 3 | 38.00 |

## 4. Identity fields

Canonical ID, FotMob name, birth date and nationality: 0 missing. `transfermarkt_player_id`: 3 missing, all `REVIEW_REQUIRED`.

## 5. By multi-club class

| Class | Rows | Missing value | Mean missing features |
|---|---:|---:|---:|
| `SINGLE_CLUB` | 3,182 | 67 | 17.94 |
| `MULTI_CLUB_CONFIRMED_APPEARANCES` | 61 | 0 | 12.03 |
| `MULTI_CLUB_SQUAD_ONLY` | 19 | 0 | 20.00 |

## 6. By position and temporal alignment

| Position | Rows | Missing value | Mean missing features |
|---|---:|---:|---:|
| Goalkeeper | 243 | 0 | 34.71 |
| Defender | 1,117 | 18 | 15.24 |
| Midfielder | 996 | 27 | 16.23 |
| Forward | 906 | 22 | 18.28 |

| Alignment class | Rows | Mean missing features |
|---|---:|---:|
| `MIXED` | 2,522 | 14.19 |
| `ALL_GAMES_ON_OR_BEFORE_VALUATION` | 433 | 28.70 |
| `ALL_GAMES_AFTER_VALUATION` | 240 | 30.34 |
| `NO_VALUATION_SELECTED` | 67 | 40.13 |

## 7. FotMob features

**Metrics with the most nulls (of 3,262):**

| Metric | Nulls | Why |
|---|---:|---|
| `m_key_passes` | 3,262 | `UNSUPPORTED`: empty in every season |
| `m_penalty_saves` | 3,093 | Goalkeepers, and rare events |
| `m_goals_prevented` | 3,082 | Goalkeepers; **no values in 2019/20** |
| `m_save_percentage` | 3,029 | Goalkeepers only |
| `m_saves`, `m_goals_conceded`, `m_goals_conceded_per90`, `m_clean_sheets` | 3,027 each | Goalkeepers only |
| `m_clearances`, `m_clearances_per90` | 2,700 each | **Mostly present only in 2024/25** |
| `m_big_chances_created` | 1,435 | |
| `m_successful_crosses`, `m_cross_accuracy` | 1,346 each | |
| `m_expected_goals_on_target` | 1,339 | |

**Metrics with the fewest nulls:** `m_appearances` and `m_starts` (2), `m_rating` (176), `m_assists` (219), `m_goals` and `m_minutes_played` (237).

**Goalkeepers mostly lack `m_minutes_played` and `m_goals`,** so a filter requiring minutes would remove nearly all of them.

**Missing features per row:** median 10–16, by season. Maximums reach 53, which means every metric is null for that row.

## 8. What this means for Phase 4

- **Missingness depends on who the player is.** Rows with no target have about 40 of 53 metrics null, against about 17 for rows with one. They're fringe players, so a complete-case analysis would drop them.
- **Null doesn't always mean unknown.** For xG, it may mean no shots recorded. The `s_*` status columns should be read first.
- **Uneven coverage across seasons** makes some metrics unsuitable for comparison between seasons.
- **Imputation and filtering are Phase 4 decisions.** Phase 3 made neither.
