# Historical xG/xA coverage review

The stored season endpoints provide player-season values but do not independently date-bound their observation windows. No value was changed or imputed.
2019/20 partial-season reporting was asserted by the previous remediation report, but its precise start/end dates are not proven in the saved source metadata. The machine-readable quality indicator is therefore `UNKNOWN_COVERAGE_WINDOW`, with `partial_season_suspected=true` for 2019/20.
The same missing explicit window marker affects the other five seasons; this review does not present any xG/xA value as independently verified full-season coverage.

| Season | Metric | Observed / eligible | Window | Partial suspected |
|---|---|---:|---|---|
| 2019/2020 | expected_goals | 69/515 | UNKNOWN_COVERAGE_WINDOW | true |
| 2019/2020 | expected_assists | 96/515 | UNKNOWN_COVERAGE_WINDOW | true |
| 2020/2021 | expected_goals | 433/524 | UNKNOWN_COVERAGE_WINDOW | false |
| 2020/2021 | expected_assists | 516/524 | UNKNOWN_COVERAGE_WINDOW | false |
| 2021/2022 | expected_goals | 446/537 | UNKNOWN_COVERAGE_WINDOW | false |
| 2021/2022 | expected_assists | 532/537 | UNKNOWN_COVERAGE_WINDOW | false |
| 2022/2023 | expected_goals | 458/554 | UNKNOWN_COVERAGE_WINDOW | false |
| 2022/2023 | expected_assists | 549/554 | UNKNOWN_COVERAGE_WINDOW | false |
| 2023/2024 | expected_goals | 460/570 | UNKNOWN_COVERAGE_WINDOW | false |
| 2023/2024 | expected_assists | 559/570 | UNKNOWN_COVERAGE_WINDOW | false |
| 2024/2025 | expected_goals | 457/562 | UNKNOWN_COVERAGE_WINDOW | false |
| 2024/2025 | expected_assists | 553/562 | UNKNOWN_COVERAGE_WINDOW | false |

Evidence: `quality_reports/historical_xg_xa_coverage_quality.csv`, corrected coverage matrix, and original raw paths in `normalized/metric_observations.parquet`. Do not infer a coverage start date or zero-fill missing players.
