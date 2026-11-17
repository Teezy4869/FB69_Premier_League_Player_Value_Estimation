# Phase 2A Step 07 — pilot validation summary

Validated offline against cached evidence; no new HTTP requests. Overall structural checks: **PASS** (0 issues). Readiness: **CONDITIONAL GO**, subject to gates in [Phase 2B plan](phase_02b_readiness_plan.md).

- Scope: 120 selected player-team-season samples, 109 unique players, six seasons. Stats collected: 120/120.
- Saved responses: 265 raw JSON/metadata pairs; 265/265 logged attempts succeeded, 0 retries. SHA-256 and JSON parsed for every pair. 239 wire JSON and 26 earlier canonical JSON pairs; their byte forms are distinguished in metadata.
- Normalized rows: players=109, teams=27, player_seasons=120, player_team_seasons=120, matches=2281, player_match_links=47, metric_observations=2880. Metric cells: 1815 available, 525 missing, 420 N/A, 120 unsupported.
- Cross-source checks: 183 comparable values (minutes=105, goals=63, saves=15); 1 disagreement. 2024/2025 player 831489 team 8650: leaderboard 2607 vs playerStats 2606 minutes (`mins_played_2024_2025`, `stats_2024_2025_831489`).
- Historical identity: 84 current/historical club differences; 9 literal name differences; 3 inferred multi-club candidates, none assigned unverified team stats.
- Match index: 2281 fixture entries, 2280 finished, one abandoned/cancelled; 10 detail responses, 47 verified lineup links across 28 players/32 selected player-season keys.
- Pilot position groups come from an inferred season-board code band. Full historical population denominator: **UNKNOWN**; no population coverage percentage is claimed.
- Local evidence references checked: 931; missing: 0 structural issue(s). Tests: 31/31 passing (python -m unittest discover -s tests -v).

See [data quality rows](pilot_data_quality_report.csv), [feature coverage](pilot_feature_coverage.csv), [cross-season metric table](cross_season_consistency.csv), and [full pilot report](phase_02a_pilot_report.md).
