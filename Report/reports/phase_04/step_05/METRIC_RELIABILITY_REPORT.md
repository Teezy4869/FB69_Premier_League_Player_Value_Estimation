# Phase 4.5 Metric Reliability Report

Date: 2026-11-09. Code: `src/phase4/reliability.py`. Notebook: 4.5.G–J. Evidence: `evidence/rd04_assessment.csv`, `club_context_*.csv`, `source_reported_metrics.csv`, `gk_consistency_checks.csv`, `other_conditions.csv`, `reliability_map.csv`. Window evidence: `reports/research_scope_rs5/step_04/evidence/feature_window_audit_rs5.csv`. Figures: `fig45_08`, `fig45_09`. Nothing is approved or excluded here.

## 1. RD-04 metrics (pending owner decision)

| Metric | Coverage of applicable rows by season (20/21 → 24/25) | Window evidence | Position | Within-season Spearman with target |
|---|---|---|---|---|
| `clearances` | 0 / 6 / 0 / 9 / 80% | verified where values exist | outfield | – / 0.15 / – / 0.07 / 0.14 |
| `clearances_per90` | as above | not verifiable (derived) | outfield | – / -0.05 / – / -0.12 / -0.24 |
| `expected_goals_on_target` | 70 / 70 / 68 / 68 / 67% | verified except 2022/23 (92.06% agreement) | attacking | 0.38–0.43 |
| `touches_opposition_box` | 80 / 79 / 79 / 78 / 78% | disagrees with match sums 2020/21–2023/24 (9–29% agreement; ratio 1.10–1.33); verified 2024/25 | attacking | 0.46–0.55 |
| `goals_prevented` (GK) | 93 / 98 / 100 / 90 / 59% | per-match field on 1–3% of matches before 2024/25; verified 2024/25 (15 conflicting cells) | GK | 0.03–0.31 (n 36–41) |

Readings: `clearances` is effectively a one-season feature; `touches_opposition_box` probably measures a different quantity before 2024/25; `goals_prevented` has weak evidence in four seasons and lowest completeness in the verified season; `expected_goals_on_target` has the strongest evidence of the five. Options remain exclude, or use with season-aware handling (owner).

## 2. Club context (RS5-12)

All eight columns are complete. 73 multi-club rows (54 with confirmed appearances for two clubs, 19 squad-only); 66 have games after the valuation and a median 44% of their minutes after it. The release has no transfer dates, so whether a move preceded the valuation cannot be determined; club identity may also proxy team strength. Conditional; any use needs an owner decision on temporal interpretation.

## 3. Source-reported metrics (ISS-29)

| Metric | Check possible in the dataset | Result |
|---|---|---|
| `save_percentage` | saves / (saves + goals conceded) | consistent on 197/197 rows (max 0.05 pp) |
| `goals_conceded_per90` | goals conceded x 90 / lineup minutes | identical on 198/198 rows |
| `clean_sheets` | bound <= appearances | holds; per match not verifiable |
| `aerials_won_percent`, `cross_accuracy`, `duels_won_percent`, `long_ball_accuracy`, `passing_accuracy` | denominators absent | not verifiable; values within [0, 100]; 0/100% values from small denominators (cross accuracy 2.2%) |

The ISS-29 caveat stays for six metrics and is weakened for the two consistent goalkeeper rates. `passing_accuracy` also drifts across seasons (P4-B09).

## 4. Other known conditions

| Condition | Evidence | Handling |
|---|---|---|
| ISS-28 `key_passes` | null and `UNSUPPORTED` on all 2,747 rows | excluded |
| P4-A04 present-day nationality | 88 values collected Nov 2026 | excluded |
| DQ-RS5-04 starts > appearances | 6 rows, 2020/21 | kept as published |
| RS5-13 source revisions | `rating` 58, `expected_goals` 34, `minutes_played` 3 | later value kept |
| RD-01 old labels | 12 targets > 365 days (max 731) | kept, weak labels |
| ISS-04 unresolved identities | 2 rows, no target | human review |
| P4-B02 conflicting / unverified-position | 36 / 17,899 cells (112 on GK rows) | null, never zero |
| ISS-27 rows without target | 50 (37 only post-cutoff valuations, 11 no history, 2 unresolved) | kept, no target imputed |

## 5. Reliability classes (descriptive, not selection)

25 reliable with caveat; 15 reliable values with limited coverage; 2 source-reported but internally consistent; 6 uncertain source-reported; 5 pending (RD-04). Full map: `reliability_map.csv`.
