# Phase 4.2: Univariate Feature Analysis Report

Date: 2026-11-08. Official dataset (SHA-256 verified), five official seasons. Code: `src/phase4/univariate.py`. Evidence: `evidence/feature_*.csv`, `per90_*.csv`, `zero_recording.csv`, `age_*.csv`, `club_context_counts.csv`, `special_interpretation.csv`. Figures: `figures/fig42_05`–`fig42_08`.

Descriptive only. No feature-target relationship is analysed here (that is Phase 4.3). Nothing is imputed, filtered, capped or transformed. Every null is read with its `s_*` status, and a null is never treated as zero (P4-A07). All metrics are season totals or season rates and include matches after the valuation date (RD-03).

## 1. Feature set and method

- **Analysed:** 53 features from the Phase 4.0 eligibility register: `age_at_season_end_years` and 52 FotMob metrics. 40 are `CANDIDATE_PREDICTOR`. 13 are `CONDITIONAL_PREDICTOR`: the 8 source-reported features (ISS-29) and the 5 RD-04 features. Mapping: `evidence/feature_register_42.csv`.
- **Not analysed as predictors** (`evidence/excluded_from_predictor_analysis.csv`, 122 columns):
  - all `target_*` (16) and `temporal_*` (8) columns;
  - identity, id, population-evidence and provenance columns;
  - `nationality_profile_present_day`;
  - `m_key_passes` and `s_key_passes` (no data);
  - the 53 `s_*` status columns, which are read to interpret availability only (P4-D01);
  - the 8 club-context columns (RS5-12 pending; counts only);
  - `position_group_season`, which is used as a grouping variable (P4-B04).
- **Applicable rows.** The 7 goalkeeper-only metrics are described on the 206 goalkeeper rows. All others are described on all 2,747 rows.
- **Statistics.** n, missing (applicable rows), mean, median, standard deviation, min, p01–p99, max, IQR, adjusted skewness, excess kurtosis, share of zeros, counts beyond the 1.5 and 3 IQR fences (counted, never removed), seasons with values, status counts.

## 2. Group overview (`feature_group_overview.csv`)

| Group | Features | Conditional | Median missing % | Max missing % | Strongly right-skewed | Values beyond 3 IQR |
|---|---:|---:|---:|---:|---:|---:|
| 1 Player context and age | 1 | 0 | 0.0 | 0.0 | 0 | 0 |
| 2 Playing time and participation | 3 | 0 | 0.0 | 7.2 | 0 | 0 |
| 3 Attacking | 9 | 1 | 21.2 | 44.3 | 9 | 329 |
| 4 Expected (model-based) | 4 | 1 | 20.1 | 31.3 | 4 | 234 |
| 5 Passing and possession | 10 | 3 | 15.2 | 41.8 | 6 | 196 |
| 6 Defensive | 14 | 4 | 21.7 | 80.7 | 9 | 104 |
| 7 Discipline and fouls | 4 | 0 | 16.1 | 21.5 | 3 | 229 |
| 8 Goalkeeping (GK rows) | 7 | 4 | 3.9 | 31.6 | 1 | 0 |
| 9 Overall match rating | 1 | 0 | 5.7 | 5.7 | 0 | 0 |

## 3. Findings by group (full table: `feature_summary.csv`)

| Group | Shape | Key numbers |
|---|---|---|
| Context and age | Near-symmetric | Median 26.4 years, range 15.9–40.7, skew 0.19, 0% missing. GK median 30.2; DEF 26.8; MID 26.1; FWD 25.5. Season medians 26.9 → 26.1 |
| Playing time | Flat, slightly left-skewed | Appearances median 21 (1–38); starts median 14, 11.8% zeros; minutes median 1,244 (1–3,420), null on 199 GK rows (ISS-11) |
| Attacking | Strongly right-skewed | Goals median 1, max 36, 45% zeros, **158 beyond 3 IQR** (largest of any feature); shots median 14, max 139; big chances created 44% missing |
| Expected | Strongly right-skewed | xG median 1.2, max 29.3, skew 2.87, 78 beyond 3 IQR; xA almost complete (1.4% missing) vs xG 18%, npxG 22%, xGOT 31% |
| Passing and possession | Totals right-skewed; rates near-symmetric | Accurate passes per 90 skew 0.88; passing accuracy **left**-skewed (−1.18, median 81.1%); cross accuracy 42% missing; long passes skew 2.70 |
| Defensive | Mixed | Tackles skew 1.18; **tackles per 90 skew 25, kurtosis 940** (one value of 60 from 3 minutes, P4-B05); blocked shots 35% missing; clearances 81% missing (RD-04) |
| Discipline and fouls | Zero-heavy, discrete | Red cards: 91% zeros, so IQR = 0 and the fences are meaningless; yellow cards median 2, 19% zeros; fouls near-symmetric |
| Goalkeeping (GK rows) | Mostly flat | Saves median 52 (0–166), skew 0.36; save % median 66.7 (25–100); penalty saves 62% zeros, 31.6% missing; goals prevented median −1.0 (−20.3 to +9.5) |
| Rating | Near-symmetric | Median 6.74, std 0.42, range 4.47–8.12, 5.7% missing |

Three distribution types recur:
- **Rare-event counts** (goals, assists, cards, penalty saves) are zero-heavy and right-skewed.
- **Volume totals** (minutes, passes, tackles, saves) scale with playing time, so their distributions largely restate it.
- **Rates, percentages and ratings** are close to symmetric, except where small denominators create spikes at 0% and 100% (ISS-29) or very large per-90 values (P4-B05).

## 4. Extreme values

- **Most values beyond 3 IQR:** goals 158, expected goals 78, accurate long passes 65, non-penalty xG 59, assists 53, xGOT 51, crosses 47, xA 46.
- For skewed counts these are the natural upper tail of regular starters and elite attackers. They are kept (P4-A09).
- For zero-inflated counts (red cards, IQR = 0) the fence counts every non-zero value and carries no information.
- **Per-90 rates (P4-B05; `per90_by_minutes_band.csv`, `per90_top1pct_minutes.csv`):**

| Rate | Max, 1–89 min | Max, 90–449 | Max, 450–899 | Max, 900+ | Top-1% rows from < 90 min |
|---|---:|---:|---:|---:|---:|
| tackles per 90 | **60.0** | 7.1 | 4.6 | 5.2 | 6 of 23 |
| shots on target per 90 | **7.5** | 3.1 | 2.2 | 2.1 | 3 of 19 |
| shots per 90 | 7.5 | 6.5 | 5.3 | 4.8 | 1 of 23 |
| recoveries per 90 | 19.1 | 11.8 | 9.5 | 10.2 | 4 of 23 |
| interceptions per 90 | 4.1 | 4.2 | 2.6 | 3.8 | 7 of 22 |

  The extreme per-90 values come from very small denominators. 6–40 rows per rate have under 90 minutes. Per-90 rates must be read with minutes. Whether a minimum-minutes rule applies is an owner decision, and none is applied.

## 5. Missingness and coverage

- **Season coverage** (`feature_coverage_by_season.csv`) is stable within a few points for every feature except:
  - `m_clearances` / `m_clearances_per90`: 0%, 6.1%, 0%, 8.9% and 79.5% by season (RD-04, ISS-28);
  - `m_goals_prevented`: 59.1% in 2024/25 against 90–100% earlier (RD-04).
- **Limited coverage** (`feature_limited_coverage.csv`): 21 features have more than 20% of applicable rows null, or a season below 50% coverage. The worst are clearances (80.7%), big chances created (44.3%), crosses and cross accuracy (41.8%), blocks (34.7%), penalty saves (31.6%), xGOT (31.3%) and shots on target (30.9%).
- **Position relevance** (`feature_present_by_position.csv`):
  - outfield metrics are absent on goalkeeper rows;
  - goalkeeper metrics are absent on outfield rows (`UNVERIFIED_POSITION`, i.e. not applicable; 0 values on non-applicable rows);
  - among outfield players, blocks are present for 85.7% of defenders but 50.8% of forwards.
- **How zeros and nulls are recorded** (`zero_recording.csv`, ISS-25):
  - **18 count metrics never record a zero** (minimum 1), for example tackles, shots on target, big chances created and blocked shots.
  - Their nulls fall on low-minute rows. For most of them the median minutes on null rows is 14–35, against about 1,450–1,800 on observed rows. It is 90–310 for shots on target, blocks, crosses and big chances.
  - **317 outfield rows** have minutes but no detailed statistics: median 14 minutes, maximum 344, 89% under 90 minutes, median 46 of 53 metrics null.
  - This is consistent with "a null may mean no recorded event", but it cannot be verified row by row, so **no null is converted to zero** (P4-A07).
  - Goals, assists, cards and starts do record zeros (`OBSERVED_ZERO`), so the meaning of a null differs by metric.

## 6. Metrics requiring special interpretation (`special_interpretation.csv`)

| Topic | Features | Interpretation |
|---|---|---|
| Source-reported (ISS-29) | aerials won %, cross accuracy, duels won %, long-ball accuracy, passing accuracy, save %, clean sheets, goals conceded per 90 | No independent window check; no denominators; conditional predictors |
| Pending RD-04 | clearances, clearances per 90, xGOT, touches in opposition box, goals prevented | Described; **eligibility not decided** |
| Goalkeeper-only (ISS-11) | 7 goalkeeping metrics | GK rows only; GK minutes null on 199 of 206 rows, so GK per-90 rates cannot be checked |
| Per-90 on small denominators (P4-B05) | 9 per-90 rates | Read with minutes; no minimum-minutes rule applied |
| Bounded scales | 6 percentages, rating | Skewness and IQR fences mean less; small samples give 0%/100% |
| Starts anomaly (DQ-RS5-04) | `m_starts` | 6 rows with starts > appearances kept |
| Whole-season position (P4-B04) | `position_group_season` | Grouping variable; partly post-valuation |
| Zero-heavy counts | red cards, penalty saves | Medians 0; means driven by few players |
| Club context (RS5-12) | 8 club columns | Counts only: 2,674 single-club, 54 multi-club with appearances, 19 squad-only. **Not decided** |

## 7. Conclusion

The 53 candidate features are reliable to describe but need two companions in every later reading:
- **Playing time.** Volumes scale with it, and per-90 rates are unstable below 90 minutes.
- **The paired `s_*` status.** Nulls often sit where zeros would be expected, but they stay nulls.

RD-04, RS5-12 and the source-reported warnings are carried forward unchanged.
