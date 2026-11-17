# Holdout Step 4: 2025/26 Data Build (D10)

Date: 2026-11-16. **Blind build.** This report contains only counts, coverage, null rates and schema facts. No target value, previous value, prediction or distribution of these was printed or inspected. **Step 5 (scoring) has not been run.** No 2025/26 row has been passed to the final model.

## 1. FotMob collection (owner-authorized 2026-11-16)

- Code: `src/holdout/collect_fotmob.py`. It uses the same endpoints, user agent, 1.2 s spacing and stop rules as Phase 2.
- Raw responses are stored immutably (response plus metadata with SHA-256) in `data/holdout_2025_26/fotmob/raw/`. Request log: `logs/holdout_2025_26_fotmob_requests.jsonl`.

**Requests:** 1,618 including the probe. All returned HTTP 200, with no 403, 429 or retries.

| Request | Count |
|---|---:|
| Probe | 1 |
| Leaderboards | 22 |
| matchDetails | 380 |
| playerData (every lineup player) | 678 |
| playerStats | 537 |

- FotMob season id: **27110**. The API top-level structure is the same as the 2024/25 capture.
- 141 lineup players have no EPL 2025/26 stats entry. None of them appeared in a match, so they fall outside the confirmed population.

## 2. FotMob tables

Code: `src/holdout/fotmob_tables.py`. It reuses the Phase 2 functions unchanged.

**Fidelity check, before use:** run on the saved 2024/25 raw files, the same code reproduces release v3.1 **exactly**:
- 562 of 562 confirmed player-seasons, with 0 set difference
- appearance counts: 0 mismatches
- modal positions: 0 mismatches
- **29,786 metric cells: 0 mismatches**

Test: `tests/holdout/test_fotmob_tables.py`, 2 run, 2 passed.

2025/26 output: `data/holdout_2025_26/fotmob/release_v1/` (separate from v3.1; v3.1 is untouched).

| Item | Count |
|---|---:|
| Matches | 380 |
| Player-match rows | 15,189 |
| Started | 8,360 |
| Substituted on | 3,132 |
| Unknown | 3,697 |
| Confirmed appeared player-seasons | **537** |
| Positions: DEF / MID / FWD / GK | 170 / 166 / 161 / 40 |
| Multi-club players | 14 |
| Missing profiles | 0 |
| Missing stats | 0 |
| New, unmapped position codes | 0 |

## 3. Identity (matching_v2_1, unchanged rules)

- The code `src/phase3/entity_resolution.run` was run on the holdout tables. Its only change is the Transfermarkt season filter, widened from 2019–2024 to 2019–2025 through 6 logged SQL substitutions in `src/holdout/build_holdout.py`.
- No automated adjudication was used.
- Results: **508 AUTO_EXACT**, **29 REVIEW_REQUIRED**.
- **Consistency with development:** 372 returning identities are mapped in both runs, and **372 of 372 map to the same Transfermarkt id**, with 0 disagreements.

## 4. Transfermarkt coverage, so no crawl was needed

The existing snapshot `tm_r2_20260905` covers the season:
- 380 GB1 2025 games
- 11,492 appearances
- valuations up to 2026-06-12

Target status for all 537 rows (statuses only, no values):

| Status | Rows |
|---|---:|
| STALE_TARGET (valuation older than 90 days, still usable) | 279 |
| VALID | 218 |
| TARGET_MISSING | 40 |

The 40 missing targets are mostly the 29 REVIEW_REQUIRED identities, which have no eligible mapping.

## 5. Holdout model input (frozen rules)

- Output: `data/holdout_2025_26/model_input/holdout_model_input_v1.parquet`, SHA-256 `26ecb86b…74fe`. `build_manifest.json` records the freeze-manifest SHA-256 verified at build time.

| Count | Rows |
|---|---:|
| Goalkeepers excluded | 40 |
| Outfield without a usable target | 38 |
| **Model rows (DEF/MID/FWD)** | **459** (459 players) |
| 900 minutes or more | **300** |
| Seen in development | 338 |
| No previous value | 8 |
| Target before season start | 2 |

Null rates follow the development pattern:
- `m_big_chances_created` 32.9%
- `m_successful_crosses_per90` 32.9%
- `m_dribbles_succeeded_per90` 16.3%
- `m_non_penalty_xg` 13.9%
- `log_prev_value` 1.7%

## 6. ISS-01 for the holdout: owner labelling needed

File: `iss01_holdout_labeling.csv` (187 rows, 165 identities). It contains **no value, market or target column**; this is asserted in the code.

| Reason | Rows | What to do |
|---|---:|---|
| NEW_AUTO_EXACT | 136 (all new automatic mappings, a census) | Label `CORRECT`, `WRONG` or `UNSURE` |
| REVIEW_REQUIRED | 51 (29 identities, up to 3 candidates each) | Mark at most one candidate `CORRECT` per identity, the others `WRONG` |

**Rule approved by the owner on 2026-11-16, before labelling and before any scoring.** It decides population only, never values.

- **NEW_AUTO_EXACT:**
  - `WRONG` excludes the row from scoring and counts it, as pre-registered.
  - `UNSURE` stays in the scored population and is reported.
- **REVIEW_REQUIRED:**
  - A candidate labelled `CORRECT` becomes MANUAL_CONFIRMED. Its target and previous value are then built with the frozen rules, and the row joins the holdout.
  - Otherwise the identity stays unmatched and outside the holdout.

The pre-registration did not cover the REVIEW_REQUIRED case explicitly. This rule is recorded here, before any scoring.

## 7. Not done

- Step 5 scoring.
- Rebuilding the model input after the ISS-01 labels.
- `s_*` GK-only status refinements (`UNVERIFIED_POSITION`). These are not used by the model and goalkeepers are excluded.

## 8. ISS-01 labels applied (2026-11-16)

The owner labelled all 187 rows. Labeller and date are filled in on every row. Labels file SHA-256: `daf84a3a…8103`.

| Reason | Result |
|---|---|
| NEW_AUTO_EXACT | **136 of 136 CORRECT**, 0 WRONG, 0 UNSURE |
| REVIEW_REQUIRED | All 29 identities have exactly one CORRECT candidate and are now MANUAL_CONFIRMED. The other 22 candidate rows are WRONG |

The model input was rebuilt with the approved rule. Code: `build_holdout.py --labelled`. Output: `data/holdout_2025_26/model_input/holdout_model_input_v2.parquet`, with `build_manifest_v2.json`. v1 is kept for traceability.

| Count | v1 | **v2** |
|---|---:|---:|
| Outfield without a usable target | 38 | 13 |
| **Model rows / players** | 459 | **484 / 484** |
| 900 minutes or more | 300 | **316** |
| Seen in development | 338 | 356 |
| No previous value | 8 | 8 |
| Target before season start | 2 | 2 |

Still blind: only counts were produced. **Step 5 has not been run.** v2 is the input to score.
