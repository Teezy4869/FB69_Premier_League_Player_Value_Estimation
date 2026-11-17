# Temporal Alignment Audit (Step 4.1)

Date: 2026-11-05. Per-player results: `evidence/temporal_alignment_by_player_season.parquet` (3,262 rows). Built by parsing all 2,280 raw FotMob match files read-only.

**Conclusion:** the current dataset supports **objective A (end-of-season estimation), with limits**. It does **not** support **objective B (prediction from information available at the valuation date)**. They are different research questions, and choosing between them is your decision.

## 1. What the features actually observe

Season metrics carry no dates, so I compared each with the sum of that player's Premier League matches in the raw files.

| Metric | Season value vs match sum | Observation window |
|---|---|---|
| Appearances | Equal on all compared rows (3,260) | Full EPL season |
| Minutes | 3,023 of 3,025 within 0.5; 2 small gaps in 2023/24, cause not determined | Full EPL season; goalkeepers mostly null |
| Goals | All within 0.5 | Full EPL season |
| Assists | All within 0.5 | Full EPL season |
| xG, 2020/21 on | 2,242 of 2,254 within 0.05; all but two within 0.10 | **Full EPL season, now verified** |
| xA, 2020/21 on | 2,387 of 2,400 within 0.05 | **Full EPL season, now verified** |
| **xG and xA, 2019/20** | Recorded in **4 of 380 matches** | **Not a season measure** |

This replaces `UNKNOWN_COVERAGE_WINDOW` for xG and xA in the five later seasons, and turns the suspected 2019/20 problem into a measured one. Other metrics weren't checked this way.

**2019/20 xG detail:** the 4 matches are Liverpool–Leicester (2019-10-05), Man City–Man United (2019-12-07), West Ham–Leicester (2019-12-28) and Newcastle–West Ham (2020-07-05). Only 0.55% of player-games have a value. The 69 players with a season xG have a median of 1 game of xG, against 31 played. **A 2019/20 xG of 0.1 can't be compared with a later season's value.**

**Null doesn't always mean unknown:** from 2020/21 on, xG is recorded in about 47% of player-games and xA in about 69%. So a null season value may mean the player had no shot, not missing data. I did not test this further and nothing was imputed. It matters for Phase 4.

**Other observation points:**
- All metrics were collected on 2026-11-02 and 2026-11-03, years after these seasons. They're retrospective, and 95 cells are marked `OBSERVED_SOURCE_REVISED`. Whether FotMob changed older values before collection can't be determined.
- `m_rating` and other metrics weren't verified against match data.

## 2. Performance before and after the selected valuation

Share of each measure dated **after** the selected valuation, for 3,195 usable targets. A match on the same date counts as before; there are only 14 such player-games.

| Season | Games | Minutes | Goals | Assists | xG | xA | All games before | All games after | Most games after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 25.38% | 24.14% | 24.15% | 23.54% | Unusable | Unusable | 96 | 16 | 47 |
| 2020/21 | 24.91% | 24.75% | 27.34% | 28.18% | 26.63% | 26.24% | 86 | 17 | 40 |
| 2021/22 | 48.58% | 48.72% | 49.37% | 50.00% | 48.34% | 49.17% | 62 | 51 | 261 |
| 2022/23 | 54.72% | 54.35% | 54.19% | 55.02% | 55.68% | 54.50% | 46 | 55 | 319 |
| 2023/24 | 46.84% | 46.22% | 43.94% | 46.87% | 44.43% | 45.48% | 75 | 55 | 284 |
| 2024/25 | 44.16% | 44.27% | 38.08% | 40.30% | 39.38% | 40.81% | 68 | 46 | 249 |
| **Overall** | **41.09%** | **40.42%** | **39.80%** | **41.07%** | 43.14% | 43.54% | **433** | **240** | **1,200** |

*Overall xG and xA include 2019/20's sparse values, which barely move them.*

**Share of each player's games after the valuation:**

| 0% | 1–25% | 26–50% | 51–75% | 76–99% | 100% |
|---:|---:|---:|---:|---:|---:|
| 433 | 632 | 930 | 815 | 145 | 240 |

**240 player-seasons have every game after the valuation,** so the target can't have reflected any of that season's performance. **Only 433 have every game before it.** The remaining 2,522 are mixed.

These timings rely on the selected date. For 2019/20, see the concentration audit: games after the previous valuation are 52.72%, not 25.33%.

## 3. Two research objectives

| | **A. End-of-season estimation** | **B. Prediction at the valuation date** |
|---|---|---|
| **Question** | Given a player's full season, what was the latest published value at season end? | Given only what was known at the valuation date, what value was set? |
| **Features allowed** | Whole season | Only matches on or before each player's valuation date |
| **Current dataset** | Matches this structure | 41.09% of appearances would be future information |
| **Temporal rule** | Met: no valuation after the cutoff | Not met by season-level features |
| **Support** | **Yes, with limits** | **No** |

**Limits on A:**
- The target is the *latest published* value, not a value reassessed at season end. Its median age is 109 days.
- Associations can run the wrong way in time: late-season form can't have caused an earlier value. Results shouldn't be presented as "performance determines value".
- 2019/20 targets follow a birth-year cut, and 2019/20 xG and xA aren't season measures.
- The degree of misalignment varies by season, which complicates comparisons between seasons.

**This isn't future-data leakage under A:** no future valuation is used. It is a temporal alignment limitation. **Under B, using these season totals would be leakage,** which is why the objective must be chosen before modeling.

## 4. Could B be built later?

Possibly, in part, but it would be new work needing your approval:

- **Raw data exists.** Match files hold per-player stats for all 380 matches in all six seasons, and season values reconcile with them.
- **Coverage:** 17 of 53 curated metrics have an identically named per-match field. Others may exist under other names (`total_shots`, `rating_title`), but I didn't map them.
- **Hard limits:** 240 player-seasons would have no current-season data. `datum_mw` semantics are unknown, so "known at that date" would be approximate. 2019/20 xG would still be absent.

I did not build any of this, since it would change features and the research design.

## 5. Handling

No feature was removed, and the target definition is unchanged.
