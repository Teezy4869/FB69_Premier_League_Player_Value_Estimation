# Phase 4.5 Temporal Reliability Report

Date: 2026-11-09. Code: `src/phase4/reliability.py`. Notebook: 4.5.E. Evidence: `evidence/temporal_reference_values.csv`, `temporal_by_season.csv`, `temporal_alignment_classes.csv`, `temporal_before_after_association.csv`, `temporal_association_by_after_share.csv`, `old_valuations_over_365_days.csv`. Figures: `fig45_05`, `fig45_06`. `temporal_*` columns were read for audit only (P4-A03). No staleness filter; D4 and D6 unchanged.

## 1. RD-03 reference values (recomputed from the official dataset)

| Measure | Reference | Recomputed |
|---|---:|---:|
| Median valuation age (days) | 150 | 150 |
| Usable targets older than 90 days | 56.62% | 56.62% |
| Appearances after the valuation date | 44.10% | 44.10% |
| Minutes after the valuation date | 43.66% | 43.66% |
| Targets older than 365 days | 12 | 12 |
| Valuations after the season cutoff | 0 | 0 |
| Usable targets dated before the season's first match | 18 | 18 |

All reproduced exactly (test `test_temporal_reference_values_recomputed`).

## 2. By season (league-wide batches, ISS-21/ISS-22)

| Season | Distinct dates | Top date (share) | Top-3 share | Median age | > 90 days | > 365 days | Appearances after valuation | Minutes after |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 2020/21 | 13 | 2021-03-18 (92.6%) | 95.9% | 66 | 2.9% | 1 | 24.9% | 24.8% |
| 2021/22 | 23 | 2021-12-23 (72.7%) | 93.2% | 150 | 78.0% | 4 | 48.6% | 48.7% |
| 2022/23 | 24 | 2022-11-03 (60.5%) | 91.7% | 206 | 67.0% | 0 | 54.7% | 54.4% |
| 2023/24 | 18 | 2023-12-19 (68.8%) | 94.0% | 152 | 72.7% | 0 | 46.8% | 46.2% |
| 2024/25 | 26 | 2024-12-16 (53.4%) | 91.9% | 160 | 59.6% | 7 | 44.2% | 44.3% |

Alignment classes (all seasons): 2,136 mixed, 337 all games on or before the valuation, 224 all games after, 50 without a target. The per-row share of own minutes after valuation spans 0–100% in every season (median about 24% in 2020/21, 46–58% later).

## 3. Does the label follow earlier or later play?

- Spearman of the target with minutes on or before the valuation date: 0.52 (0.51–0.58 per season). With minutes after it: 0.38 (0.36–0.41). Before and after minutes correlate at 0.46. The label tracks earlier playing time more strongly; later play still correlates because playing time persists.
- Feature-target Spearman by the row's share of minutes after valuation (mostly before / mixed / mostly after): rating 0.62 / 0.56 / 0.50; goals 0.54 / 0.44 / 0.40; appearances 0.58 / 0.35 / 0.53; xA 0.59 / 0.45 / 0.56; accurate passes per 90 0.20 / 0.23 / 0.31. Most attacking and playing-time associations are weaker when most minutes follow the valuation. Groups differ in composition (late arrivals, breakthroughs), so this is descriptive.

## 4. Old labels (RD-01)

12 usable targets are older than 365 days (maximum 731 days; listed in `old_valuations_over_365_days.csv`). Kept; flagged as weak labels; owner decision open.

## 5. Conclusions

The temporal mismatch is real, quantified and strongly season-dependent. It weakens label-feature correspondence, more in seasons whose batch is early (2022/23) than in 2020/21. Under objective A it is a documented construct limitation, not leakage, and nothing here implies that later performance caused an earlier valuation. Season-aware evaluation (P4-D02) and season-aware reporting are required later; any staleness rule needs owner approval (ISS-22, RD-01).
