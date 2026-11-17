# rs5 Recalculation Matrix

Every item named in Task B, with its action and the step that does it. Historical values in the right column are **not** rs5 values; they're listed only so each can be visibly replaced.

| Item | Season dependency | Affected | Action | Step | Historical value (do not reuse) |
|---|---|---|---|---|---|
| Player-Season records | Season-local | Yes | FILTER v3.1; recount Confirmed/Unverified per season | 2A | 3,262 Confirmed, 790 Unverified |
| Player-Team-Season | Season-local | Yes | FILTER; recount multi-club | 2A, 3C | 80 / 61 multi-club |
| Player-Match | Season-local | Yes | FILTER; recount STARTED / SUBSTITUTED_ON / UNKNOWN | 2A | 23,604 UNKNOWN |
| Metric observations | Season-local | Yes | FILTER; values, provenance, timestamps and status unchanged | 2A | 207,043 |
| Metric-Season coverage | Season-local rows + totals | Yes | FILTER rows; REBUILD cross-season summary and dictionary season counts | 2A | 318 rows, six seasons |
| Match audit | Season-local | Yes | FILTER; recount completed matches | 2A | 2,281 rows |
| Metric conflict records | Season-local | Yes | FILTER `metric_reconciliation_report.csv`; recount open conflicts | 2A | 36 open |
| Transfermarkt valuation records | Player-level | No for values | REUSE; re-measure rs5 window coverage | 2B | 656,301 rows |
| Player crosswalk | Player-level; evidence season-bearing | Universe and evidence | REVALIDATE with in-scope evidence | 3A/B | 1,343 identities |
| Entity resolution evidence | Season-bearing | Yes | REBUILD candidates from in-scope seasons | 3A | 2,807 candidate rows |
| Automated adjudications | Player-level | 36 of 41 in scope | REVALIDATE against rs5 candidate sets | 3A | 41 |
| Identity validation labels | Used 2019/20 stats as evidence | Partly | REVALIDATE: report which labels rest on in-scope evidence | 3A | 980 confirmed of 1,299 |
| Target construction | Season-local by rule | Rows no; totals yes | REBUILD with the same rule; prove row equality | 2B | 3,195 usable, 67 missing |
| Target coverage, distribution, staleness | Totals | Yes | REBUILD per season, per position, overall | 2B | 63.35% over 90 days |
| Integrated dataset | Season grain | Yes | REBUILD as rs5 v1; drop D7 and batch columns | 3C | 3,262 rows, 180 columns |
| Missingness reports | Totals | Yes | REBUILD | 4 | about 17 / 40 null metrics |
| Temporal alignment | Per row + totals | Yes | REBUILD | 2B, 4 | 41.09% appearances after valuation |
| Leakage audit | Per feature, per season | Yes (xG family conclusion changes) | REBUILD | 4 | 4 features `USABLE_EXCEPT_2019_20_COMPARISON` |
| Data quality reports | Totals | Yes | REBUILD | 4 | |
| Feature window verification | Per metric-season | Rows no; conclusions yes | Re-run on rs5 seasons | 4 | |

## Percentage definitions to fix before Step 4

Both historical headline percentages must be recomputed with a stated denominator:

- **Targets older than 90 days**: usable targets with `valuation_age_days > 90` / all usable targets (`VALID` + `STALE_TARGET`).
- **Appearances after valuation**: sum of a player's confirmed appearances (STARTED or SUBSTITUTED_ON) dated after the selected valuation date / sum of confirmed appearances, over usable-target rows. This is the definition `season_targets.summarize` used (`pct_player_games_after_valuation`).
