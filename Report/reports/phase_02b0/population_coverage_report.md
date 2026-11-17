# Phase 2B.0 Step 01 — historical population validation

**Target:** distinct FotMob player ID with evidence of appearing in at least one Premier League match in a given season. Registered players, unused substitutes and leaderboard entries alone are not confirmed appearances. Player-season and player-team-season are separate keys.

The existing minutes/goals/saves leaderboard union is only a candidate set. Rebuilding it found no duplicate player-team-season key and no same-season multi-team player in those boards; lineup comparison still found omitted team relationships. The validation sample is 18 deterministic, season-scoped finished fixtures (early/mid/late in each of six seasons); 12 details were newly requested within the configured budget and six came from Phase 2A cache. A starter counts as appeared; a substitute counts only with a `subIn` event. All match IDs, dates, teams, league and status matched the retained fixture index.

| Season | Candidate players | Candidate team relations | Matches | Unique appeared players | In candidate union | Missing IDs | Other-team relations | SAMPLE COVERAGE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/2020 | 515 | 515 | 3 | 84 | 84 | 0 | 0 | 100.0% |
| 2020/2021 | 524 | 524 | 3 | 68 | 68 | 0 | 1 | 100.0% |
| 2021/2022 | 537 | 537 | 3 | 73 | 73 | 0 | 1 | 100.0% |
| 2022/2023 | 554 | 554 | 3 | 79 | 79 | 0 | 0 | 100.0% |
| 2023/2024 | 570 | 570 | 3 | 70 | 70 | 0 | 0 | 100.0% |
| 2024/2025 | 562 | 562 | 3 | 82 | 82 | 0 | 0 | 100.0% |

Across the sample: 513 appeared lineup entries, 456 unique player-season IDs, 190 unused substitute listings. This includes 5 entered-substitute appearances whose season leaderboard minutes were below 90 (the pilot's low-minute threshold). Missing player-season IDs from leaderboard union: 0. **Full-season appearing-player denominator and full-season completeness are UNKNOWN.** A 100% sample result cannot establish a complete season population.

Two player-team-season relationships are absent from the leaderboard candidate rows despite the player IDs appearing elsewhere in those seasons:
- 2020/2021: Takumi Minamino (player 408943), appeared for team 8650; retain match evidence and verify the club spell before assigning season totals.
- 2021/2022: Lucas Digne (player 210111), appeared for team 8668; retain match evidence and verify the club spell before assigning season totals.

The team requests for Liverpool in 2019/20 and 2024/25 contain the same response bytes and report `latestSeason=2026/2027`, but no explicit historical `squad.season`. They are UNVERIFIED for historical roster completeness and are excluded from the denominator.

Correction to the Phase 2A interpretation: its 47 `player_match_links` rows recorded lineup membership; checking the retained substitution events shows 41 appeared and 6 were unused substitutes. The original Phase 2A evidence remains unchanged. This Phase 2B.0 validation counts only actual appearances.

For Phase 2B.1, discover all season fixtures from the verified `leagues` index, retrieve matchDetails in bounded resumable batches, count only starters and substitutes with `subIn`, union player IDs by season, reconcile against season leaderboard candidates, and inspect every omitted ID/team relation. Set per-season checkpoints for 380 finished fixtures (with replay/status exceptions), lineup availability and unique IDs; report completeness only after validating the entire match population and resolving missing lineup coverage. This is an implementable full-scale method, **not executed here**.

Evidence: [lineup comparisons](historical_lineup_comparison.csv), [sampled matches](historical_match_sample.csv), [population rows](historical_population_validation.csv), and [season leaderboard minutes](../phase_02a/player_reference_index.csv).
