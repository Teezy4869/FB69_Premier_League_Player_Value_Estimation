# rs5 Step 2: Target Construction

Output: `data/research_rs5/targets/target_rs5_v1__matching_v2_1/`. Builder: `src/research_scope/build_targets_rs5.py`.

## Methodology (preserved, not re-implemented)

- **Rule:** `latest_valid_on_or_before_season_end_v1` (D4). For each player-season, take the latest valid Transfermarkt valuation with `valuation_date <= season_end_date`. A later valuation is never used. Nothing is imputed.
- **Code path:** `src.phase3.season_targets.build` runs unchanged. Only its FotMob input points at the rs5 release. Cutoffs come from `configs/phase_03_seasons.yaml`, read through the scope.
- **Cutoffs:** 2021-05-23, 2022-05-22, 2023-05-28, 2024-05-19, 2025-05-25.
- **Values:** EUR as published, from `tm_valuation_history` only. Current and career-high profile values aren't read.
- **Identity:** historical `matching_v2_1` mapping, restricted to the 1,228 rs5 players. Step 3 revalidates it.

## Equivalence with the approved historical construction

| Output | rs5 rows | Historical in-scope rows | Rows differing |
|---|---:|---:|---:|
| Target | 2,747 | 2,747 | **0** |
| Temporal alignment (per-match before/after) | 2,747 | 2,747 | **0** |
| Previous-valuation audit | 2,747 | 2,747 | **0** |

The rule is row-local, so this equality is expected. It confirms that removing 2019/20 changed no in-scope target. One rounding difference appeared in the first audit build: DuckDB and Python round 0.78125 differently. It was fixed by using Python `round()`, as Step 4.1 did.

## Results

| Measure | Value |
|---|---:|
| Player-season rows | 2,747 |
| Usable targets (`VALID` + `STALE_TARGET`) | **2,697 (98.18%)** |
| `VALID` (age 90 days or less) | 1,170 |
| `STALE_TARGET` (over 90 days; usable, label only) | 1,527 |
| Missing (`TARGET_MISSING`) | **50** |
| `INVALID_VALUATION` / `AMBIGUOUS_VALUATION` | 0 / 0 |
| Same-date conflicts | 0 |
| Valid valuation records available for mapped in-scope players, up to 2025-05-25 | 25,659 |

**Missing reasons:** 37 only later valuations, 11 no valuation history, 2 no eligible identity (`REVIEW_REQUIRED`).

## Distribution of usable targets (EUR)

| Season | n | Median | Mean | Max |
|---|---:|---:|---:|---:|
| 2020/21 | 515 | 10,000,000 | 16,877,961 | 120,000,000 |
| 2021/22 | 528 | 10,000,000 | 17,205,492 | 100,000,000 |
| 2022/23 | 542 | 15,000,000 | 19,610,655 | 170,000,000 |
| 2023/24 | 567 | 13,000,000 | 20,129,277 | 180,000,000 |
| 2024/25 | 545 | 17,000,000 | 22,244,817 | 200,000,000 |
| **All** | **2,697** | **13,000,000** | **19,259,307** | **200,000,000** |

Overall: min 100,000; p25 5,000,000; p75 25,000,000; p90 45,000,000. Heavily right-skewed: the mean is 1.48 times the median.

## Validation (14 checks, all PASS)

One row per population player-season; no duplicate keys; population equals the rs5 Confirmed set; EUR whenever a value exists; no value with a missing status; every valuation on or before cutoff; age equals cutoff minus date; every Transfermarkt id exists in `tm_players`; selected record found in valuation history with the same value, date, player, row number and file hash; provenance on every usable target; no later eligible valuation skipped; one rule version; approved statuses only; every missing target has a reason. Details: `target_manifest.json` → `validation`.

## Methodology issue for a research decision

**One target is dated before the 2019/20 season ended.** For player 877402 in 2020/21, the latest valuation before the cutoff is 2019-05-23 (€100,000, age 731 days; 1 appearance). The approved rule has no age limit, so it's kept. This is a Transfermarkt record dated in 2018/19, not 2019/20 season data. But a 731-day-old value is a weak season-end estimate. 12 usable targets are over 365 days old (2020/21: 1, 2021/22: 4, 2024/25: 7). **Requested decision (RD-01):** keep the rule unchanged (current default), or approve a maximum age. No rule was changed.
