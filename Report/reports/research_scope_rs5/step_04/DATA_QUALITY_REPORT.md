# rs5 Step 4: Data Quality Report

Dataset audited: `data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet` (SHA-256 `4d94ec73…eedd`, recorded in `evidence/audit_summary.json`). Auditor: `src/research_scope/audit_rs5.py`. Nothing was removed, imputed or recoded.

## Structural quality

| Check | Result |
|---|---|
| Schema and types | 175 columns; every column has a role and a dictionary type (27 integration checks pass) |
| Primary key `canonical_player_id + season` | 2,747 unique of 2,747 rows; 0 duplicate keys; 0 duplicate full rows |
| Referential integrity | Every row in the FotMob rs5 Confirmed set; every TM id in `tm_players`; crosswalk and target agree |
| Categories | position GK 206 / DEF 935 / MID 839 / FWD 767 (no UNKNOWN); target status VALID 1,170 / STALE_TARGET 1,527 / TARGET_MISSING 50; currency EUR or null |
| Status vocabulary | Only the 8 documented `s_*` values; 0 unexpected |
| Value/status consistency | 0 null values with an observed status; 0 values with a non-observed status |

### Invalid or implausible values

| Rule | Rows |
|---|---:|
| Negative metric (except `goals_prevented`) | 0 |
| Percentage outside 0-100 | 0 |
| Rating outside 0-10 | 0 |
| Appearances over 38 | 0 |
| Minutes per appearance over 120 | 0 |
| Shots on target > shots; goals > shots | 0; 0 |
| Age outside 15-45 | 0 |
| Target not positive | 0 |
| `m_appearances` ≠ confirmed appearances | 0 |
| **`m_starts` > `m_appearances`** | **6**, all 2020/21 (Cooper, Maguire, Fabiański, Alisson, Evans, Kabak): FotMob reports one more start than confirmed lineups. Kept as published (DQ-RS5-04) |

## Statistical validity

- **Target:** heavily right-skewed (skewness 2.31; log scale -0.84). Median €13.0m, maximum €200m. Medians rise over the seasons: €10m in 2020/21 and 2021/22, €17m in 2024/25. That's consistent with market inflation, not a data error.
- **Extreme values:** 885 metric values lie more than 3 IQR beyond the quartiles, mostly in count metrics: goals 158, xG 78, accurate long passes 65, npxG 59, assists 53. These are heavy tails, as expected for elite players, not errors. **None was removed.** Per metric and season: `evidence/metric_distribution_by_season.csv`.
- **Season-level differences:** only `clearances` and `clearances_per90` shift abnormally: coverage 0%, 6.1%, 0%, 8.9% and 79.5% by season. Every other metric's coverage stays within 20 points across seasons, and its median within a factor of 2.

## Data reliability

| Item | Count | Meaning, preserved as is |
|---|---:|---|
| UNKNOWN player-match participation (FotMob rs5) | 20,184 | Bench status unknown; never treated as "did not play" |
| Unverified player-seasons (outside the population) | 691 | Excluded from the population with reasons, as approved |
| Rows with unresolved substitute matches | 2,120 (16,814 matches) | Population evidence; appearance counts use confirmed events only |
| Null metric cells | 48,043 of 145,591 (33.00%) | See the missingness report |
| `UNVERIFIED_POSITION` cells | 17,899 | Metric eligibility depends on an unverified lineup position |
| `CONFLICTING` cells (null value) | 36 in 34 rows | Source disagreement; null and traceable |
| `OBSERVED_SOURCE_REVISED` | 95 | FotMob changed the value between collections |
| `OBSERVED_FALLBACK_LEADERBOARD` | 402 | Value from the leaderboard source |
| Feature collection window | 2026-11-02 to 2026-11-03 | All metrics collected retrospectively |
| Identity not human-reviewed | 2,747 rows | All identity decisions are automated |

## Verdict

No structural defect. Six rows have an internal FotMob inconsistency (starts). The remaining issues are source-data limitations, quantified in this report and in `ISSUE_TRACKER.md`.
