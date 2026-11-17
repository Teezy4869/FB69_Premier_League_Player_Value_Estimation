# Staleness Sensitivity Report (Step 4.1)

Date: 2026-11-05. Full results: `evidence/staleness_sensitivity_long.csv`, `evidence/step_04_1_audit_results.json`.

**These are sensitivity analyses only. No threshold was selected or enforced, and no record was removed.**

**Conclusion:** every strict threshold changes which *seasons* remain rather than which players are stale, because age is set mainly by league-wide batch dates. No threshold gives a balanced dataset.

## 1. Coverage

Population: 3,262 player-seasons, of which 3,195 have a usable target.

| Threshold | Eligible | % of population | Distinct players | Median value (EUR) | Median age (years) | Median games |
|---|---:|---:|---:|---:|---:|---:|
| ≤ 30 days | 28 | 0.86% | 28 | 5,000,000 | 23.2 | 3 |
| ≤ 60 days | 141 | 4.32% | 139 | 12,000,000 | 24.9 | 17 |
| ≤ 90 days | 1,171 | 35.90% | 810 | 16,000,000 | 26.1 | 22 |
| ≤ 180 days | 2,805 | 85.99% | 1,247 | 13,000,000 | 26.6 | 22 |
| All available | 3,195 | 97.95% | 1,304 | 12,000,000 | 26.6 | 22 |

## 2. By season (eligible and coverage)

| Season | ≤ 30 | ≤ 60 | ≤ 90 | ≤ 180 | All |
|---|---:|---:|---:|---:|---:|
| 2019/20 | 1 (0.2%) | 1 (0.2%) | **1 (0.2%)** | 495 (96.1%) | 498 (96.7%) |
| 2020/21 | 5 (1.0%) | 9 (1.7%) | **500 (95.4%)** | 508 (97.0%) | 515 (98.3%) |
| 2021/22 | 17 (3.2%) | 112 (20.9%) | 116 (21.6%) | 514 (95.7%) | 528 (98.3%) |
| 2022/23 | 2 (0.4%) | 6 (1.1%) | 179 (32.3%) | **187 (33.8%)** | 542 (97.8%) |
| 2023/24 | 1 (0.2%) | 6 (1.1%) | 155 (27.2%) | 567 (99.5%) | 567 (99.5%) |
| 2024/25 | 2 (0.4%) | 7 (1.2%) | 220 (39.2%) | 534 (95.0%) | 545 (97.0%) |

- **≤ 90 days** nearly removes 2019/20, while 2020/21 becomes 42.7% of the rows.
- **≤ 180 days** looks mild overall, but drops two-thirds of 2022/23, because its main batch was 3 November 2022.

## 3. By position (coverage)

Position is the player's most common historical lineup position that season.

| Position | ≤ 30 | ≤ 60 | ≤ 90 | ≤ 180 | All |
|---|---:|---:|---:|---:|---:|
| Goalkeeper | 0.8% | 3.3% | 30.9% | 86.4% | 100.0% |
| Defender | 0.6% | 3.4% | 34.2% | 86.2% | 98.4% |
| Midfielder | 0.4% | 3.9% | 35.0% | 85.2% | 97.3% |
| Forward | 1.7% | 6.2% | 40.3% | 86.4% | 97.6% |

## 4. By age at cutoff (coverage)

Age uses FotMob's birth date. Those with disputed dates could shift a group, which is negligible here.

| Age | ≤ 30 | ≤ 60 | ≤ 90 | ≤ 180 | All |
|---|---:|---:|---:|---:|---:|
| Under 22 | 1.8% | 6.0% | 38.8% | 77.9% | **88.3%** |
| 22–25 | 0.9% | 5.8% | 38.0% | 87.6% | 99.8% |
| 26–29 | 0.7% | 4.2% | 38.6% | 89.3% | 99.9% |
| 30+ | 0.4% | 1.4% | **27.7%** | 85.6% | 100.0% |

Under-22s have the lowest coverage even with no threshold, because some have no valuation before the cutoff. Any strict threshold also reduces players aged 30 and over.

## 5. Selection bias

Standardized mean difference (SMD), kept versus excluded usable rows. Above about 0.2 is usually considered noticeable, though that's a rule of thumb.

| Threshold | Log value | Player age | Games |
|---|---:|---:|---:|
| ≤ 30 | -0.80 | -0.60 | **-2.00** |
| ≤ 60 | 0.08 | -0.47 | -0.34 |
| ≤ 90 | **0.30** | **-0.23** | 0.05 |
| ≤ 180 | 0.27 | -0.06 | 0.10 |

**Within seasons at ≤ 90 days** (isolating player selection from season mix):

| Season | Kept / excluded | Log value | Player age | Games |
|---|---|---:|---:|---:|
| 2021/22 | 116 / 412 | 0.39 | -0.67 | -0.10 |
| 2022/23 | 179 / 363 | 0.53 | -0.35 | 0.00 |
| 2023/24 | 155 / 412 | 0.48 | -0.48 | 0.17 |
| 2024/25 | 220 / 325 | 0.51 | -0.22 | 0.11 |

*2019/20 has too few kept rows, and 2020/21 too few excluded (15), for a meaningful comparison.*

**Findings:**
- **Fresher valuations favor younger, more valuable players, even within a season.** A 90-day filter would raise the median value from 12.0m to 16.0m. It's plausible that March batches target notable players, but I did not test why.
- **≤ 30 days is unusable.** Its 28 rows have a median of 3 games, and look like unusual cases rather than a fresher sample of the same players.
- **Stale isn't the same as unchanged or wrong.** Age measures time since the last change or review, and many batches leave values unchanged. A stale value may still be current in Transfermarkt's view.
- **Results are descriptive.** They don't show how any threshold would affect a model.

## 6. Identity tier

| Tier | ≤ 90 | ≤ 180 | All |
|---|---:|---:|---:|
| `AUTO_EXACT_VALIDATED` | 37.4% | 87.1% | 98.9% |
| `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 29.8% | 81.9% | 94.3% |
| `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 35.6% | 85.6% | 96.7% |
| `AUTO_ADJUDICATED_EXTERNAL` (8 rows) | 25.0% | 75.0% | 100.0% |
| `UNRESOLVED` (3 rows) | 0% | 0% | 0% |

## 7. Recommendation

Keep all targets with exact ages, as now. Any filter is a Phase 4 decision, and should be tested with season mix in mind. A season-aware analysis would answer more than one global cutoff.
