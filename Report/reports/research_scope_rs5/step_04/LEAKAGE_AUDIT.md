# rs5 Step 4: Leakage Audit

Objective A (D6), prediction time = official season end. One row per column: `evidence/leakage_audit.csv` (175 rows, each with role, classification, evidence and Spearman correlation with log target). Window evidence: `evidence/feature_window_audit_rs5.csv`. Indirect checks: `evidence/quality_audit.json` → `indirect_window_evidence`.

**Conclusion: no candidate feature contains target information or information from after the season-end cutoff. The dataset is NOT claimed leakage-free in the broader sense.** Two unresolved temporal concerns remain: the features/label construct mismatch (RD-03) and player identity across seasons (must be handled by the Phase 4 split).

## Classification rules

| Class | Used when |
|---|---|
| PASS | Known at prediction time, no target link, no window concern |
| WARNING | Available at prediction time, no target information, but a documented limitation (alignment, unverified source window, no data) |
| FAIL | Would leak the target or post-period facts if used as a predictor. All such columns are excluded by role |
| REQUIRES RESEARCH DECISION | Evidence is incomplete or contradictory, and a human choice is needed before use |

## Checks per focus area

| Question | Finding |
|---|---|
| Available at prediction time? | Yes for every `m_*`, `s_*` and context feature. Last match = cutoff in all seasons; 0 appearances after cutoff |
| Information after the cutoff? | No. 0 valuations after cutoff; no next or future valuation column; current and career-high values never read |
| Aggregates future matches? | Season totals include matches **after the valuation date** (44.10% of appearances), but none after the cutoff |
| Indirectly encodes the target? | No. Largest absolute Spearman between a candidate and log target is **0.671** (`m_clean_sheets`, GK only); next highest are `m_rating` 0.581 and `m_expected_assists` 0.557. The only column at 0.97 is `target_audit_previous_value`, which is excluded by role (FAIL). FotMob's raw `marketValues` isn't carried |
| Invalid observation window? | 5 metrics have incomplete or contradictory window evidence (below) |
| Player identity or season leakage? | **687 players have rows in 2 or more seasons (2,206 of 2,747 rows).** A random row split would put the same player on both sides. Valuation dates are season-wide batches, so season and target timing are linked |

## Full-season features vs a valuation cutoff

The target is the latest valuation on or before season end, a median of 150 days before it. Full-season features therefore include performance the valuation couldn't reflect. Under A, this isn't leakage: no target information flows into the features, and the features are available at prediction time. But it **weakens the label-feature correspondence**, and it would be leakage under a forecasting objective. Every `m_*` metric carries this WARNING. Results must not be read as performance determining value.

## Results

| Class | Candidate predictors (108) | All columns (175) |
|---|---:|---:|
| PASS | 1 (`age_at_season_end_years`) | 16 |
| WARNING | 102 | 118 |
| REQUIRES RESEARCH DECISION | **5** | 13 |
| FAIL | 0 | 28 |

### Candidate metrics requiring a research decision

| Feature | Evidence |
|---|---|
| `m_clearances`, `m_clearances_per90` | No values in 2020/21 or 2022/23; verified in the other three seasons. Season-dependent availability |
| `m_expected_goals_on_target` | Season value agrees with the match sum on 92.06% of 378 rows in 2022/23 (threshold 98%); verified in the other 4 seasons |
| `m_touches_opposition_box` | Disagrees with match sums in 2020/21 to 2023/24 (9-29% agreement); verified only in 2024/25 |
| `m_goals_prevented` (GK) | Per-match field on 1-3% of matches in 2020/21 to 2023/24; verified only in 2024/25 |

### Candidate WARNING groups

| Group | Features | Basis |
|---|---:|---|
| Window verified against match sums in all 5 seasons | 28 metrics | Includes xG, xA, npxG, minutes, goals, assists, passes, shots, tackles, rating, appearances |
| Rate consistent with verified totals (`rate = total × 90 / minutes`, 100% of compared rows) | 8 per90 metrics | Indirect window check |
| `m_starts` | 1 | Equals confirmed starts on 99.53% of 2,746 rows |
| Cards | 2 | Within 1 of Transfermarkt totals: yellow 95.90%, red 99.92% of 2,412 rows |
| Source-reported, not independently verifiable | 8 | 6 accuracy and percentage rates, `m_clean_sheets`, `m_goals_conceded_per90` (GK rows lack minutes) |
| No data | 1 | `m_key_passes` |
| `position_group_season` | 1 | Whole-season modal lineup position, partly after valuation |
| `s_*` statuses | 53 | Same window as their metric; describe the source record, not the target |

### Non-candidate columns

| Columns | Class | Reason |
|---|---|---|
| 16 target columns (TARGET, TARGET_METADATA, TARGET_AUDIT roles) and 8 `temporal_*` columns | FAIL | Target, or derived from its valuation date |
| `canonical_player_id`, `fotmob_player_id`, `transfermarkt_player_id` | FAIL | Identity: use as a group key, never as a predictor |
| `nationality_profile_present_day` | FAIL | Present-day profile value (November 2026), not historical |
| 8 `CLUB_CONTEXT` columns | REQUIRES RESEARCH DECISION | A move can come after the valuation; club can proxy value |
| `season`, `season_id`, identity-quality columns | WARNING | Grouping or sensitivity only |

Features weren't deleted because of audit results; every column stays in the dataset.
