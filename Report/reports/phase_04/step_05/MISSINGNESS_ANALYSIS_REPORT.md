# Phase 4.5 Missingness Analysis Report

Date: 2026-11-09. Official dataset (SHA-256 `4d94ec73…eedd`, verified before and after), scope `rs5_v1`. Code: `src/phase4/reliability.py`. Notebook: 4.5.A–D. Evidence: `evidence/status_semantics.csv`, `status_matrix_all_rows.csv`, `status_share_by_*.csv`, `feature_missingness.csv`, `family_missingness.csv`, `population_missingness.csv`, `gk_*.csv`. Figures: `fig45_01`–`fig45_04`. Nothing was imputed, zero-filled or excluded.

## 1. Status semantics (statuses never collapsed)

| Status | Meaning | Stored value | Cells | % |
|---|---|---|---:|---:|
| `OBSERVED` | value reported | value | 91,289 | 62.70 |
| `OBSERVED_ZERO` | genuine zero | 0 | 5,762 | 3.96 |
| `OBSERVED_FALLBACK_LEADERBOARD` | value via season leaderboard | value (270 zeros) | 402 | 0.28 |
| `OBSERVED_SOURCE_REVISED` | value changed after first collection (RS5-13) | value | 95 | 0.07 |
| `MISSING` | unavailable observation | null | 27,361 | 18.79 |
| `UNVERIFIED_POSITION` | not applicable / unverified for the position | null | 17,899 | 12.29 |
| `UNSUPPORTED` | no source data (`key_passes`) | null | 2,747 | 1.89 |
| `CONFLICTING` | collection passes disagree | null | 36 | 0.02 |

Status and value agree on all 145,591 cells: every unavailable, not-applicable, unsupported or conflicting cell is null; every genuine zero is 0 (test `test_status_semantics_preserved`).

- **Observed zero vs unavailable:** only `OBSERVED_ZERO` (and leaderboard zeros) means "no event". `MISSING` means unknown, even where P4-B07 suggests many would be zeros.
- **Not applicable:** goalkeeper metrics on outfield rows (17,787 cells). On goalkeeper rows, outfield metrics are coded `MISSING` (6,558 cells), not not-applicable (P4-B10).
- **Unverified / conflicting:** 112 unverified-position cells on goalkeeper rows (63 of them `penalty_saves`); 36 conflicting cells (`rating` 17, `goals_prevented` 18, `accurate_passes_per90` 1), mostly in 2024/25.

## 2. Feature level

Median null share on applicable rows by family: goalkeeping 3.9%, general 7.2%, passing 15.2%, expected 20.1%, attack 21.2%, defending 21.6%. Highest: `key_passes` 100%, `clearances`(/90) 80.7%, `big_chances_created` 44.3%, crossing pair 41.8%, blocked shots pair 34.7%, `penalty_saves` 31.6%, `expected_goals_on_target` 31.3%, `shots_on_target`(/90) 30.9%.

- **By season:** stable within a few points, except `clearances` (100% null in 2020/21 and 2022/23) and `goals_prevented` (40.9% null in 2024/25).
- **By position:** forwards have the most nulls on defensive and passing metrics (interceptions 25.8%, long passes 25.8%), defenders on rare attacking counts (big chances 48.1%, shots on target 30.4%); goalkeepers null on almost all outfield metrics.
- **By target availability:** rows without a target are null on 76–96% of most metrics (expected assists 18%, rating 54%).

## 3. Population level

| Segment | Rows | Median null metrics | `MISSING` share of cells | No detailed stats |
|---|---:|---:|---:|---:|
| Target available / missing | 2,697 / 50 | 12 / 47 | 18.0% / 64.3% | 10.2% / 84.0% |
| Goalkeepers / outfield | 206 / 2,541 | 34 / 11 | 62.0% / 15.3% | n/a / 12.5% |
| Outfield 0 / 1–9 / 10–18 / 19–28 / 29–38 starts | 317 / 680 / 563 / 538 / 443 | 46 / 14 / 11 / 10 / 10 | 72.1 / 12.7 / 5.8 / 4.5 / 3.8% | 100% / 0 / 0 / 0 / 0 |
| Outfield under 90 minutes / 900+ | 323 / 1,536 | 46 / 10 | 67.1% / 4.7% | 87.6% / 0% |
| Seasons | 524–570 | 10–12 | 17.2–20.3% | 9.5–14.0% |

Missingness follows playing time and target availability, not season. It is informative, and complete-case analysis would remove fringe players selectively (ISS-27).

## 4. Goalkeepers (separate)

Goalkeeper metrics cover 93–100% of goalkeeper rows per season, except `penalty_saves` (62–77%) and `goals_prevented` (59% in 2024/25). `m_minutes_played` exists on 7 of 206 goalkeeper rows, while lineup minutes (temporal audit columns) exist on all 206 and match `m_minutes_played` on 2,489 of 2,491 outfield rows (max difference 19 minutes). Using them would be a feature derivation from excluded audit columns: owner decision P4-D05. Goalkeeper performance is not inferred from unavailable values.

## 5. Conclusions for later phases

- Read every null with its `s_*` status; the five null-producing statuses carry different meanings.
- Missingness is structural (playing time, position, target availability). Its treatment is a preprocessing decision (ISS-25, P4-D01, P4-B07), not made here.
- Goalkeepers need separate handling of both outfield-metric coding and minutes.
