# Phase 2A deterministic pilot sample

Seed: `6902`. Reference: season-scoped goals, minutes and saves boards.
Deep seasons use standings ranks 1, 7, 13 and 20; each club targets eight players.
Light seasons use the same ranks with two players per club: GK/DEF, MID/FWD,
DEF/MID, and FWD/low-minute respectively. This yields a 120-row target.
Within each club, selection prioritizes the lowest observed minutes (<90), then position quotas,
top-minute representatives and seeded draws. Extra slots use seeded draws from supported code bands.
Position groups are code-band inferences for sampling: GK=11, DEF=32–39/51–53,
MID=62–79, FWD=103–115. These are not verified FotMob historical role labels.
No multi-club player was found across these three boards; none was invented for the sample.

| Season | Depth | Rows | GK | DEF | MID | FWD | Low-minute |
|---|---|---:|---:|---:|---:|---:|---:|
| 2019/2020 | DEEP | 32 | 4 | 9 | 11 | 8 | 3 |
| 2020/2021 | LIGHT | 8 | 1 | 3 | 2 | 2 | 1 |
| 2021/2022 | LIGHT | 8 | 1 | 2 | 3 | 2 | 1 |
| 2022/2023 | DEEP | 32 | 4 | 11 | 9 | 8 | 6 |
| 2023/2024 | LIGHT | 8 | 1 | 2 | 2 | 3 | 1 |
| 2024/2025 | DEEP | 32 | 4 | 12 | 8 | 8 | 5 |

## Exceptions and limits

Each `exception_note` in the manifest identifies a role fallback.
Unknown position codes are excluded from the stratified sample.
The source reference is incomplete relative to the unknown full player population,
so this sample is representative only of the observed boards and cannot establish league coverage.
Current team squads were rejected as historical evidence; transferred/multi-club cases remain unresolved.

Exception rows: 0. Details are in `pilot_sample_manifest.csv`.
