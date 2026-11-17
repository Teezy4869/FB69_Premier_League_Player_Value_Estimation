# Independent appearance baseline reverification

Input: original v2 and original v3 Parquet, prior transition audit, 2,280 immutable matchDetails JSON.
All counts below were recomputed from the files, not copied from prior reports.

| Player-match status | v2 | v3 | corrected provisional |
|---|---:|---:|---:|
| STARTED | 50160 | 50160 | 50160 |
| SUBSTITUTED_ON | 15628 | 15628 | 15628 |
| UNUSED_SUBSTITUTE | 7290 | 23604 | 0 |
| UNKNOWN | 16314 | 0 | 23604 |
| CONFLICTING | 0 | 0 | 0 |

v2→v3 UNKNOWN→UNUSED_SUBSTITUTE: 16314 audit rows.
The prior audit contains 16305 `COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_NO_APPEARANCE` and 9 `...WITH_BENCH_CARD` reasons.
The rule in `classify_participation()` used standard lineup, 11 starters per side, a nonempty event feed, valid swaps and no active playerStats. None proves complete substitution coverage.
The original 7,290 v2 UNUSED_SUBSTITUTE rows also lack sufficient negative provenance under the strict contract.

| Season | Completed | Lineups | Fact substitutions | Complete negative coverage | v3 appeared PS | v3 non-appeared PS | corrected appeared PS | corrected unverified PS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/2020 | 380 | 380 | 380 | 0 | 515 | 99 | 515 | 99 |
| 2020/2021 | 380 | 380 | 380 | 0 | 524 | 117 | 524 | 117 |
| 2021/2022 | 380 | 380 | 380 | 0 | 537 | 142 | 537 | 142 |
| 2022/2023 | 380 | 380 | 380 | 0 | 554 | 145 | 554 | 145 |
| 2023/2024 | 380 | 380 | 380 | 0 | 570 | 164 | 570 | 164 |
| 2024/2025 | 380 | 380 | 380 | 0 | 562 | 123 | 562 | 123 |

v2 player-season evidence statuses: {'APPEARED': 3262, 'UNKNOWN_PARTICIPATION': 586, 'UNUSED_SUBSTITUTE_ONLY': 204} (total 4052).
The v3 population total is 4,052: 3,262 CONFIRMED_APPEARED and 790 CONFIRMED_NON_APPEARED. The corrected population is 3,262 CONFIRMED_APPEARED and 790 UNVERIFIED.
