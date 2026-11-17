# rs5 Step 4: Missingness Report

Per metric and season, with each null's status (MISSING, UNVERIFIED_POSITION, UNSUPPORTED, CONFLICTING): `evidence/missingness_by_feature_season.csv`. Nothing was imputed. Null ≠ zero.

## Overall

| Measure | Value |
|---|---:|
| Null metric cells | 48,043 / 145,591 (33.00%) |
| Null metrics per row: min / median / mean / max (of 53) | 8 / 12 / 17.49 / 52 |
| Every outfield row has at least 8 nulls because | `key_passes` (no data) and the 7 GK-only metrics (not applicable). Goalkeepers lack most outfield metrics |

## By season, position and target

| Group | Mean null metrics per row |
|---|---:|
| 2020/21 / 2021/22 / 2022/23 / 2023/24 / 2024/25 | 17.41 / 17.14 / 17.91 / 18.29 / 16.68 |
| DEF / MID / FWD / GK | 15.01 / 15.69 / 17.92 / **34.49** |
| Usable target / missing target | 17.03 / **42.10** |

**Missingness isn't random.** It concentrates in goalkeepers, whose outfield metrics are null and whose minutes are mostly missing, and in fringe players. The 50 rows without a target average 42.1 null metrics. Complete-case analysis would therefore drop goalkeepers and fringe players selectively.

Per player (mean over their seasons): median 13.0; 90th percentile 46.0.

## By metric family (null share of all cells)

| Family | Null % |
|---|---:|
| GENERAL | 7.96 |
| EXPECTED (xG family) | 18.20 |
| ATTACK | 22.67 |
| PASSING | 28.63 |
| DEFENDING | 29.86 |
| GOALKEEPING | 93.19 (by design: GK-only) |

## Coverage inconsistencies

| Metric | Finding |
|---|---|
| `key_passes` | No value in any season (`UNSUPPORTED`) |
| `clearances`, `clearances_per90` | Values only in 2021/22, 2023/24 and 2024/25; 0% in 2020/21 and 2022/23 |
| GK-only metrics (among GK rows) | clean_sheets, saves, goals_conceded 3.88% null; save_percentage 4.37%; goals_prevented 12.62%; **penalty_saves 31.55%** (null probably means none faced; not converted) |
| `m_minutes_played` | 7.24% null, mostly goalkeepers |

## Targets

50 missing (1.82%): 37 only later valuations, 11 no valuation history, 2 no identity. The share missing per season ranges from 0.53% (2023/24) to 3.02% (2024/25).

**Compared with six seasons:** 33.00% null cells. Phase 3 reported means of about 17 and 40 nulls with and without a target; rs5 has 17.03 and 42.10.
