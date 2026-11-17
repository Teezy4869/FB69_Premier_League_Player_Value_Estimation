# Matching Evaluation Report (`matching_v1`)

Date: 2026-11-04. Results: `data/phase_03/entity_resolution/matching_v1__reviews_none/run_manifest.json`.

**Precision and recall are not evaluated.** No person has labeled the validation sample, and I did not create labels. Everything below is automated evidence, not a measured error rate.

## 1. Results

| Measure | Value |
|---|---:|
| FotMob identities | 1,343 |
| Transfermarkt identities | 50,149 |
| Confirmed player-season rows | 3,262 |
| Candidate pairs | 2,807 |
| Human-reviewed matches | 0 |

| Status | Identities | Player-season rows | Share of rows |
|---|---:|---:|---:|
| `AUTO_EXACT` | 1,299 | 3,161 | 96.9% |
| `REVIEW_REQUIRED` | 44 | 101 | 3.1% |
| `AUTO_HIGH_CONFIDENCE` | 0 (disabled) | 0 | 0% |
| `MANUAL_CONFIRMED` | 0 | 0 | 0% |
| `AMBIGUOUS` | 0 | 0 | 0% |
| `UNMATCHED` | 0 | 0 | 0% |

**Reading the zeros:** `AMBIGUOUS` and `UNMATCHED` at 0 mean the rules found none. A reviewer may still assign these statuses to any of the 44 identities.

**By season:**

| Season | `AUTO_EXACT` rows | `REVIEW_REQUIRED` rows |
|---|---:|---:|
| 2019/20 | 498 | 17 |
| 2020/21 | 511 | 13 |
| 2021/22 | 520 | 17 |
| 2022/23 | 539 | 15 |
| 2023/24 | 550 | 20 |
| 2024/25 | 543 | 19 |

**Candidates per identity:** 1: 530; 2: 442; 3: 220; 4: 87; 5: 36; 6: 13; 7: 4; 8: 7; 9: 2; 11: 1; 14: 1.

**Pairs by block** (a pair can be in several): `DOB_EXACT` 2,530; `EXACT_NAME` 1,453; `ROSTER_NAME` 1,354; `BIRTH_YEAR_NAME` 1,329; `GAME_SET` 1,246; `DOB_NEAR` 66.

**Pairs by suggestion:** `LIKELY_MATCH` 1,358 (mostly the automatic matches themselves); `UNLIKELY` 1,306; `ALREADY_MAPPED_TO_ANOTHER_IDENTITY` 137; `POSSIBLE_MATCH` 6.

## 2. Automated corroboration of the 1,299 `AUTO_EXACT` matches

Game history was **not** used to decide these matches, so it gives an independent check. This is not precision, because it can't prove identity on its own.

| Check | Result |
|---|---|
| Game sets identical (Jaccard 1.0) | 1,267 |
| Jaccard 0.90 to under 1.0 | 5 |
| Jaccard 0.50 to under 0.90 | 12 |
| Jaccard above 0 and under 0.50 | 1 |
| No shared games (TM has no rows) | 14 |
| Any rival has a higher Jaccard than the match | **0** |
| Rival ties with the match | 2 (teammates, each already mapped to themselves) |
| Club status | `CONFIRMED_GAMES` 1,285; `ABSENT` 14; contradicted 0 |
| Nationality | Agree 1,284; disagree 9; missing 6 |
| Position | Agree 1,202; disagree 97 |
| Same TM ID claimed twice | 0 |

- **Nationality disagreements** so far look like dual nationals, for example Jamaica and England. That is an impression from the values, not checked.
- **Position disagreements** (7.5%) support treating position as weak evidence, since TM's value is present-day.

**Weakest automatic matches:**
- 14 with `EXACT_NAME_DOB_UNIQUE_NO_CLUB_EVIDENCE` rest on name and birth date only, such as Ezgjan Alioski and Peter Etebo.
- Tyler Onyango has Jaccard 0.25 (1 shared game of 4).

All 15 are in the validation sample.

## 3. Identities in review

| Group | Identities | Examples |
|---|---:|---|
| Exact birth date, nearly always identical games, different name form | 40 | Joseph Gomez / Joe Gomez; Alisson Becker / Alisson; Juan Hernández / Cucho Hernández; Sávio / Savinho |
| **Same name, different birth date** | **4** | Alfie Pond 2004-03-01 / 2004-02-17; Michael Olakigbe 2004-04-06 / 2004-04-25; Omari Kellyman 2005-09-25 / 2005-09-15; Jimi Tauriainen 2004-03-09 / 2004-03-08 |

Each of these 4 has an identical game set with its TM candidate, although three of those sets are only 1 or 2 games (Olakigbe has 8). So exact-DOB agreement is not universal, and these may reflect a source disagreement, but that's for a reviewer to judge. **The sources' birth dates are not fully interchangeable.**

**34 of the 44** meet the proposed high-confidence criteria (exact DOB, Jaccard ≥ 0.9, at least 5 FotMob games, only one likely candidate). They are only counted; none was mapped.

## 4. Common patterns

These are observations about why identities went to review. They are not measured errors.

| Pattern | Examples |
|---|---|
| Formal name vs short name | Joseph / Joe; Daniel / Dan; Robert / Robbie; Edward / Eddie |
| Mononym vs full name | Alisson Becker / Alisson; Jota / Jota Peleteiro; Kiko / Kiko Femenía |
| Extra or missing name part | Pape Sarr / Pape Matar Sarr; Victor Nilsson Lindelöf / Victor Lindelöf |
| Different spelling or transliteration | Yehor Yarmoliuk / Yegor Yarmolyuk; Jose Holebas / Jose Cholevas |
| Different name in common use | Mbwana Samatta / Ally Samatta; Sávio / Savinho |
| Birth date differs | The 4 identities above |

**The rules appear to err on the side of caution.** Most of the 44 look like true matches that didn't meet the exact rule. That is the intended direction, but recall can't be stated without labels.

## 5. TM appearance shortfall (Step 1 risk R3)

| Season | Rows only in FotMob, mapped players | Player-seasons with no TM rows | Partly short | Rows only in TM |
|---|---:|---:|---:|---:|
| 2019/20 | 36 | 3 | 0 | 0 |
| 2020/21 | 37 | 2 | 0 | 0 |
| 2021/22 | 114 | 27 | 0 | 0 |
| 2022/23 to 2024/25 | 0 | 0 | 0 | 0 |

**Finding:** among mapped players, all 187 missing rows come from 32 player-seasons where TM has no EPL rows for that player. The other 2 of the 189 total fall under identities not yet mapped. There are no partial gaps, and TM never has an extra row.

**Cause:** still unknown. It is specific player-seasons, and earlier reports' guess that it might be substitutes is not supported. Alioski's 36 games in 2020/21 are a clear counterexample.

**Effect:** none on the crosswalk rules, since a gap is never held against a match. These players' valuation history is a separate table, so Step 4 will measure any effect there.

## 6. Validation sample

File: `data/phase_03/review/validation_sample_for_labeling.csv`. 518 rows, 488 unique pairs, labels blank. Selection is fixed by a seed.

| Stratum | Pool | Selected |
|---|---:|---:|
| `AUTO_EXACT_RANDOM` (the unbiased precision estimate) | 1,299 | 300 |
| `AUTO_EXACT_NO_CLUB_EVIDENCE` | 14 | 14 |
| `AUTO_EXACT_LOW_GAME_OVERLAP` | 1 | 1 |
| `MULTI_CLUB_SEASON` | 55 | 40 |
| `DIFFICULT_POSITIVE_CANDIDATE` | 58 | 40 |
| `COMMON_NAME_COLLISION` | 154 | 40 |
| `SIMILAR_NAME_NEGATIVE_CANDIDATE` | 14 | 14 |
| `INCOMPLETE_EVIDENCE` | 29 | 29 |
| `MULTIPLE_PLAUSIBLE_CANDIDATES` | 66 | 40 |

**What it can support:**
- With 300 random labels and 0 errors, the 95% lower bound on `AUTO_EXACT` precision is about 99%. With 1 error, it falls to about 98.4%. So the SOP's 99% target leaves no room for errors at this size.
- Metrics over all strata are deliberately biased toward hard cases, and don't describe the population.
- **FotMob has no missing DOB or nationality** in this population, so `INCOMPLETE_EVIDENCE` only covers cases missing on the TM side, or missing a position.

## 7. Remaining review workload

| Task | Volume | Effect |
|---|---:|---|
| Review queue | 44 identities, 93 rows, 101 player-seasons | Resolves all unmapped rows |
| Validation labels | 488 unique pairs | Enables precision and recall |
| Minimum for the precision estimate | 300 pairs | `AUTO_EXACT_RANDOM` only |
