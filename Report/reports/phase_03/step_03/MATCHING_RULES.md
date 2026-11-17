# Matching Rules (`matching_v1`)

Settings: `configs/phase_03_matching.yaml`. Code: `src/phase3/entity_resolution.py`, `src/phase3/names.py`.

## 1. Identity fields actually used

| Evidence | FotMob source | Transfermarkt source | Role |
|---|---|---|---|
| Player ID | `players.player_id` | `tm_players.tm_player_id` | Keys only; **no shared ID exists** |
| Names | `profile_name`, `lineup_name`, season `player_name` | `player_name_raw`, first + last name, `player_code` | Exact key; fuzzy ranking |
| Birth date | `players.birth_date` | `tm_players.date_of_birth` | Primary discriminator |
| Games | `player_match_appearances` with `STARTED`, `SUBSTITUTED_ON` | `stg_appearances`, EPL only | Historical evidence |
| Club-season | `player_team_seasons`, `CONFIRMED` only | `tm_player_club_seasons` | Historical evidence |
| Transfers | Not applicable | `tm_transfers`, excluding after-snapshot rows | Information only |
| Nationality | `nationality_name` | `nationality` | Support only |
| Position | Most common `historical_position_observations.mapped_group` | `position_profile`, present-day | Support only |

**Not used as identity evidence:** FotMob `current_position`, `current_team_id` (null for all), and Transfermarkt current-club fields.

**FotMob identifiers:** `player_id` is the stable person-level key. It repeats across seasons with one profile, and the crosswalk has one row per ID. No two IDs map to one TM player, so there is no sign of split identities.

## 2. Canonical ID

`canonical_player_id = "fb69p_" + fotmob_player_id`. It is stable, contains no name, and covers 1,343 people, not 3,262 player-seasons.

## 3. Name normalization

- Case folding, Unicode decomposition, diacritics removed, special letters mapped (`ø` to `o`), apostrophes joined, hyphens and punctuation split, whitespace collapsed.
- Exact keys are order-free, so "Son Heung-min" equals "Heung-min Son", and include umlaut spellings (Müller, Mueller).
- No token is ever dropped. Raw names stay alongside normalized ones.
- No nickname table is used. "Joe" and "Joseph" stay different, and these pairs go to review rather than being assumed equal.

## 4. Game alignment

Club and game mapping comes from fixtures, not names:

1. Each FotMob club is mapped to the TM club it most often shares a home date and score with.
2. The map must be one-to-one (27 clubs).
3. Every completed match must then find exactly one game by date and both clubs (2,280 of 2,280). Any failure stops the run.

## 5. Evidence hierarchy and status

| Priority | Evidence | Result |
|---|---|---|
| 1 | Verified shared ID | **None exists** |
| 2 | Exact name key + exact birth date, unique, no club contradiction | `AUTO_EXACT` |
| 3 | Exact name + birth date, but club contradicted | `REVIEW_REQUIRED` |
| 4 | More than one exact match, more than one likely candidate, or one TM ID claimed twice | `AMBIGUOUS`, no mapping |
| 5 | Any other candidate | `REVIEW_REQUIRED`, no mapping |
| 6 | No candidate | `UNMATCHED` |
| 7 | Reviewer decision | `MANUAL_CONFIRMED` or as decided; always overrides automation |

`AUTO_EXACT` methods:
- `EXACT_NAME_DOB_UNIQUE_CLUB_CONFIRMED`: also has shared games or a shared club-season.
- `EXACT_NAME_DOB_UNIQUE_NO_CLUB_EVIDENCE`: TM has no EPL rows in those seasons.

**Club evidence rules:**
- `CONTRADICTED` means TM shows the same season at a different club, with no shared game or club-season.
- A TM gap (`ABSENT`) is **never** evidence against a match, because TM rows are known to be missing for some players.

**What can never map a player:** name alone, a high fuzzy score, birth date alone, or game overlap alone. Teammates can have very similar game sets: 79 non-matching pairs reached Jaccard 0.8 or more.

**`AUTO_HIGH_CONFIDENCE` is off.** `CLAUDE.md` requires a labeled sample and owner approval first.

## 6. Candidate generation

Blocks are deterministic and recall-oriented. They select pairs for review and never create a mapping.

| Block | Rule |
|---|---|
| `EXACT_NAME` | Same exact name key |
| `DOB_EXACT` | Same birth date, name similarity at least 40 or token subset |
| `DOB_NEAR` | One day apart or day/month swapped, similarity at least 75 |
| `BIRTH_YEAR_NAME` | Same birth year, similarity at least 88 |
| `ROSTER_NAME` | Same club and season, similarity at least 70 or token subset |
| `GAME_SET` | Jaccard at least 0.8 with at least 3 shared games, any name |

All blocks run for every identity, including automatic matches, so each automatic match is checked against rivals. These rivals never change the automatic decision.

## 7. Scoring

The score only orders candidates. It is a judgment-based heuristic, **not a probability**, and is not yet validated.

| Signal | Points | Why |
|---|---:|---|
| Name similarity (token sort) | 35, scaled | Main identity signal, but unsafe alone |
| Name subset | 5 | Mononyms such as Alisson |
| Birth date | 30 exact; 12 near; 3 same year | Strong, largely independent of names |
| Game-set Jaccard | 20, scaled | Historical and independent of names; shared by teammates |
| Nationality | 5 | Support: single-valued, and dual nationals disagree |
| Position | 5 | Support: TM value is present-day |

Missing evidence earns nothing and reduces `score_available`, so a low score isn't confused with absent evidence. Each signal is stored separately in `matching_candidates.parquet`.

**Suggestions are descriptions only:** `LIKELY_MATCH`, `POSSIBLE_MATCH`, `UNLIKELY`, `ALREADY_MAPPED_TO_ANOTHER_IDENTITY`.

## 8. Human review

1. Fill in `data/phase_03/review/matching_review_queue.csv`:
   - `reviewer_decision`: `CONFIRM_MATCH`, `REJECT_CANDIDATE`, `MARK_AMBIGUOUS`, `MARK_UNMATCHED` or `INVESTIGATE`
   - `reviewer_name` and `review_date`, both required
   - `reviewer_notes`, optional
2. Rerun `entity_resolution.py`. Decisions are copied to the append-only `review_decisions_ledger.csv`, and regenerating the queue keeps them.
3. Contradictory decisions for one identity stop the run. A new output folder is created based on the ledger content, so earlier outputs stay.

## 9. Validation labels

Fill in `data/phase_03/review/validation_sample_for_labeling.csv`: `human_label` as `MATCH`, `NON_MATCH` or `UNSURE`, plus `labeler_name` and `label_date`. Labeled files aren't regenerated. `evaluate_matching.py` reports `NOT_EVALUATED` until labels exist.

## 10. Crosswalk schema

`player_crosswalk.parquet` has one row per FotMob identity:

| Column | Meaning |
|---|---|
| `canonical_player_id`, `fotmob_player_id` | Identity keys; never null |
| `transfermarkt_player_id` | Only for `AUTO_EXACT`, `AUTO_HIGH_CONFIDENCE`, `MANUAL_CONFIRMED` |
| `match_status`, `match_method` | Decision and rule |
| `confidence_score`, `confidence_score_available` | Ranking score of the mapped candidate |
| `evidence` | JSON of signals for the mapped pair |
| `review_status`, `reviewer`, `review_date`, `decision_rationale` | Review trail; blank until a person acts |
| `candidate_count`, `player_season_rows` | Context |
| `fotmob_names_raw`, `tm_name_raw`, `matching_version` | Raw names and version |
