# Phase 2B.1 Execution 02 — historical appeared-player population

The population counts only starters and substitutes with an explicit `subIn`. An unused substitute does not count. A missing substitution field remains UNKNOWN. The three validated season leaderboards (`mins_played`, `goals`, `saves`) are candidate evidence only; assists, passing, defending and other groups have no validated season-wide contract in the saved evidence. Registration is not inferred from lineup listings, and current roster data is excluded.

| Season | Completed fixtures | Validated details | Usable lineups | Unambiguous matches | Appeared players | Candidate players | Uncertain-only players | Missing candidates | Multi-club players | Unknown records | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2019/2020 | 380 | 380 | 380 | 375 | 515 | 515 | 10 | 0 | 7 | 46 | CONDITIONAL PASS |
| 2020/2021 | 380 | 380 | 380 | 70 | 524 | 524 | 99 | 0 | 8 | 3449 | CONDITIONAL PASS |
| 2021/2022 | 380 | 380 | 380 | 104 | 537 | 537 | 107 | 0 | 9 | 3401 | CONDITIONAL PASS |
| 2022/2023 | 380 | 380 | 380 | 126 | 554 | 554 | 103 | 0 | 15 | 2561 | CONDITIONAL PASS |
| 2023/2024 | 380 | 380 | 380 | 57 | 570 | 570 | 144 | 0 | 10 | 3236 | CONDITIONAL PASS |
| 2024/2025 | 380 | 380 | 380 | 0 | 562 | 562 | 123 | 0 | 12 | 3621 | CONDITIONAL PASS |

Exceptions: 16314. See [exact records](population_exceptions.csv), [reconciliation](population_reconciliation.csv), [coverage](population_coverage_by_season.csv), and [progress](population_collection_progress.json).
Every detail counted as validated was rechecked against its raw SHA-256, request identity, JSON schema and season-scoped fixture context before population extraction.
HTTP attempts logged for this stage: 2258; outcomes: {'OK': 2258}; failure categories: {}.

Parquet outputs: [historical_fixture_index](../../data/phase_02b1/population/historical_fixture_index.parquet), [historical_matches](../../data/phase_02b1/population/historical_matches.parquet), [seasons](../../data/phase_02b1/population/seasons.parquet), [historical_player_population](../../data/phase_02b1/population/historical_player_population.parquet), [historical_appeared_players](../../data/phase_02b1/population/historical_appeared_players.parquet), [player_match_appearances](../../data/phase_02b1/population/player_match_appearances.parquet), [player_team_season_reference](../../data/phase_02b1/population/player_team_season_reference.parquet).

The 2023/24 fixture index retains abandoned Bournemouth–Luton match 4193691 as ineligible and includes replay 4421797 among the 380 eligible completed matches.

A season is INCOMPLETE until all 380 eligible match details are validated. This output does not authorize collection of player season statistics.

Resume from the manifest without repeating validated requests:
```powershell
python -m src.collection.population_execution02 --execute --max-batches 50 --max-requests 50
python -m src.collection.population_execution02 --report-only
```

Independent output/raw audit: **PASS**; 2280 raw checksums reverified; 2258 logged HTTP attempts. [Machine audit](population_final_audit.json).

Automated tests: `python -m unittest discover -s tests -v`; exit code 0; 69 run, 0 failures, 0 errors. [Full actual log](execution02_tests/test_execution.log), [machine result](execution02_tests/test_execution.json).