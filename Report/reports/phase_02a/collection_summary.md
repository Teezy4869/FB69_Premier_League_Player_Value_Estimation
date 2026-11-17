# Phase 2A Steps 03–06 — controlled pilot collection

Normalized from 120 selected player–season rows and 109 unique sampled players.
Only the manifest players and selected match details were requested; the league fixture indexes
and three reference boards were reused from Steps 01–02. All successful new responses are cached
whole with request metadata and SHA-256; normalization leaves raw files untouched.

Retained raw response/metadata pairs: 265. New collection responses
are stored as wire JSON; earlier Step 01–02 full payloads remain in their existing canonical JSON form.

## Collection by season

| Season | Selected | Season stats available |
|---|---:|---:|
| 2019/2020 | 32 | 32 |
| 2020/2021 | 8 | 8 |
| 2021/2022 | 8 | 8 |
| 2022/2023 | 32 | 32 |
| 2023/2024 | 8 | 8 |
| 2024/2025 | 32 | 32 |

## Normalized outputs

| Table | Rows |
|---|---:|
| `players.parquet` | 109 |
| `teams.parquet` | 27 |
| `player_seasons.parquet` | 120 |
| `player_team_seasons.parquet` | 120 |
| `matches.parquet` | 2281 |
| `player_match_links.parquet` | 47 |
| `metric_observations.parquet` | 2880 |

## Metrics and identity

Available metric cells: 1815; missing: 525; not applicable: 420; unsupported: 120.
Distinct metrics with a value: 23 of 24 normalized candidates.
The `metric_observations.parquet` table retains each source field, raw value, unit, format,
statistic type, timestamp and missing status. The wide `player_seasons.parquet` keeps nulls.
No missing leaderboard row is interpreted as zero. `key_passes` is unsupported; generic long
passes, duels and blocks are represented only by narrower observed variants when present.
Profile `statValue` totals are separate from its `per90` field. The saves leaderboard's main
value is per 90 while its `Total saves` secondary value is a total; these are never combined.
Passing accuracy retains the provider's percentage and notes that its denominator is not supplied.
Current team differs from the season-scoped historical team in 84 sample rows; current team, position and nationality are classified CURRENT_ONLY.
Profile and season-board names differ literally in 9 sample rows; FotMob IDs remain the join key and both names are retained.
Retrospective career dates flagged 3 possible same-season multi-club cases for review. These did not create unverified team records.
A player with multiple verified team rows retains each player–team–season relationship,
while the player–season aggregate remains one row.

Possible multi-club cases from retrospective career dates (INFERRED only):
- 2023/2024 player `1086647` (Cameron Archer): league team IDs `8657|10252`; season-board team `8657`.
- 2024/2025 player `746395` (Aaron Ramsdale): league team IDs `8466|9825`; season-board team `8466`.
- 2024/2025 player `1086647` (Cameron Archer): league team IDs `8466|10252`; season-board team `8466`.

## Match index

The six cached league responses contain 2281 fixture records; 1 are canceled or abandoned.
Missing match dates: 0; missing results: 0.
Selected match-detail responses: 10; verified selected-player lineup links: 47.
The 2023/24 Bournemouth–Luton raw fixture IDs are preserved separately:
- `4193691`: CANCELLED_OR_ABANDONED; 2023-12-16T15:00:00Z.
- `4421797`: FINISHED; 2024-03-13T19:30:00Z.

`playerMatches` was not retried: Phase 1 recorded HTTP 400 and no verified working
parameter set is available. Fixture membership alone does not establish a player–match link.
Only selected lineups establish the links saved here; match coverage is deliberately partial.

## Data quality and remaining blockers

Missing cells by metric: accurate_long_passes=22, accurate_passes=16, assists=11, blocked_shots=46, chances_created=27, clearances=93, duels_won=31, expected_assists=45, expected_goals=51, goals=15, goals_prevented=4, interceptions=36, passing_accuracy=16, rating=7, shots=31, shots_on_target=42, tackles=32.
Unsupported candidates: key_passes.
Failed HTTP attempts in the pilot log: 0.
The full historical player population remains unknown. Season-stat leaderboards and current
profiles cannot establish it. Retrospective transfer claims and inferred position groups
need independent historical validation. Match links cover only the selected details;
`playerMatches` pagination remains unresolved. Metric definitions and percentage denominators
are not fully documented by the checked source responses.

## Reproduction

```powershell
python -m src.collection.phase_02a_03_06 profiles --max-requests 40
python -m src.collection.phase_02a_03_06 stats --max-requests 40
python -m src.collection.phase_02a_03_06 matches --max-requests 40
python -m src.collection.phase_02a_03_06 normalize
python -m unittest discover -s tests -v
```

Each collection command resumes from cache; repeat it only while `still_missing` is positive.
The normalized Parquet outputs are written atomically and can be regenerated from cached raw JSON.
