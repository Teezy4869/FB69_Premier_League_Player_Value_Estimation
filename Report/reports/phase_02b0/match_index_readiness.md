# Match Index readiness — Phase 2B.0 Step 04B

The six cached `leagues` responses provide a season-scoped fixture index. A fixture establishes two team–match associations, not any player appearance. A selected `matchDetails` lineup with starter or `subIn` evidence establishes only the sampled player–match association. Full player–match statistics remain UNKNOWN.

| Season | Fixture records | Finished | Abandoned/cancelled | Postponed | Team–match associations |
|---|---:|---:|---:|---:|---:|
| 2019/2020 | 380 | 380 | 0 | 0 | 760 |
| 2020/2021 | 380 | 380 | 0 | 0 | 760 |
| 2021/2022 | 380 | 380 | 0 | 0 | 760 |
| 2022/2023 | 380 | 380 | 0 | 0 | 760 |
| 2023/2024 | 381 | 380 | 1 | 0 | 762 |
| 2024/2025 | 380 | 380 | 0 | 0 | 760 |

The 2023/24 Bournemouth–Luton abandoned fixture `4193691` and finished replay `4421797` are distinct records. The canceled/abandoned record is excluded from the 380 finished games that season. No postponed fixture remains in the saved end-of-season indexes.

Fallback evidence: 18 selected match details yielded 513 confirmed participation entries and 513 unique player–match pairs. The Phase 2A `player_match_links` table recorded 47 lineup members, including six unused substitutes; this corrected fallback uses starter/`subIn` evidence only.

## playerMatches investigation

The named community wrapper [route implementation](https://github.com/ccdejene/fotmob-mcp/blob/main/fotmob_mcp/server.py) and [route reference](https://github.com/ccdejene/fotmob-mcp/blob/main/docs/fotmob-api.md) list `playerId`, Unix `before`, and `parentLeagueId` for `/api/data/playerMatches`. This is a route catalog, not proof that historical requests work. Phase 1 already retained two HTTP 400 responses for one player, including the three-parameter pattern.

Two further representative requests used the documented three-parameter pattern, `parentLeagueId=47`, and a `before` cursor after each target season:
- 2024/2025, player `831489`, before `1748736000`: HTTP 400, `Invalid or missing query parameters`; [raw response](../../data/phase_02b0/player_matches_probes/probe_05278f2cb4c5478ba2c1f16555e008bf/response.json), [metadata](../../data/phase_02b0/player_matches_probes/probe_05278f2cb4c5478ba2c1f16555e008bf/metadata.json).
- 2019/2020, player `108038`, before `1596240000`: HTTP 400, `Invalid or missing query parameters`; [raw response](../../data/phase_02b0/player_matches_probes/probe_3703a21f24dc4ec6ac71cfcda9ede633/response.json), [metadata](../../data/phase_02b0/player_matches_probes/probe_3703a21f24dc4ec6ac71cfcda9ede633/metadata.json).

The endpoint remains **UNVERIFIED** for historical pagination. A parameter error does not prove historical match data is absent. No additional parameter guessing or full match download was performed. The verified fixture index plus selective matchDetails participation is the current fallback.
