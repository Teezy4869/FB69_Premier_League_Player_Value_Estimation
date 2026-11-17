# Historical membership rules — Phase 2B.0 Step 03

An observed player–team–season relation is **HISTORICAL_VERIFIED** only when a season-scoped leaderboard row or a completed season-indexed match lineup supports it. A profile's `primaryTeam`, current position and nationality are CURRENT_ONLY. A retrospective career-history date can create a separately marked **HISTORICAL_INFERRED** candidate but never a verified club spell. Unknown or conflicting IDs must remain UNKNOWN/CONFLICTING until a scoped source resolves them.

Rebuilt 3262 leaderboard team relations, added 2 verified lineup relations and 3 retrospective candidates. 84 of 120 pilot rows have a current club different from the season board. Duplicate normalized player-season and player-team-season keys: 0 and 0.

There are 5 player-season pairs with multiple club relations. Both clubs are season-evidence verified for 2 pairs; the other 3 retain an inferred second club. In the bounded identity index, ID/name review found 0 player IDs with multiple names, 0 season-name keys with multiple player IDs, 0 team IDs with multiple names, and 0 season-team-name keys with multiple team IDs. These checks detect review candidates; a shared name alone would not prove an ID conflict.

`player_seasons` retains one season aggregate per player and season. The playerStats response has no returned team split, and leaderboard values are not proven to be per-club totals. `player_team_seasons` retains relationships but its existing `UNVERIFIED_TEAM_SPLIT` marker forbids summing or allocating the season total across clubs. For transfer cases, keep both verified relations and any inferred candidates; only direct season evidence promotes an inferred relation to HISTORICAL_VERIFIED.

The three previously flagged retrospective cases remain unresolved for the *second* club: Cameron Archer 2023/24 (`10252`), Aaron Ramsdale 2024/25 (`9825`), and Cameron Archer 2024/25 (`10252`). Their season-board club and selected lineup appearances are verified. In addition, selected lineups verify Takumi Minamino–Liverpool 2020/21 and Lucas Digne–Everton 2021/22, both omitted as club relations from the leaderboard union. Neither discovery licenses a statistical team split.

No current roster response is used as a historical team source. Original raw and Phase 2A normalized files are unchanged. Evidence paths and statuses are recorded per row in [historical_identity_validation.csv](historical_identity_validation.csv).
