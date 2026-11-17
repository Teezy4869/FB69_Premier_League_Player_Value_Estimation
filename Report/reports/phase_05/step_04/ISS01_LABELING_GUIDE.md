# ISS-01 Identity Labelling: Guide for the Owner

File to fill in: `iss01_identity_labeling_sample.csv` (101 rows). It was built by `src/phase5/iss01_sample.py` (seed 0). The manifest records the source SHA-256.

## What the sample contains

- **100 random rows** from stratum `AUTO_EXACT_RANDOM` of the existing unlabelled sample, `data/research_rs5/review/validation_sample_for_labeling.csv`:
  - all 66 pairs that belong to the P4-B01 identity-sensitive subset
  - 34 other pairs, drawn at random
- **1 extra row**: a worst-error, identity-sensitive player from the step 03 error analysis. The other two such players (FotMob 1113790 and 1324871) are not in the source sample. Check them separately if you want.
- The row order is shuffled.

## How to label each row

1. Compare the FotMob columns with the Transfermarkt candidate columns:
   - names
   - date of birth
   - nationality
   - club by season
2. Open `candidate_url` if needed.
3. Fill in:
   - `human_label`: exactly one of `CORRECT`, `WRONG`, `UNSURE`
   - `labeler_name`
   - `label_date` (YYYY-MM-DD)
   - `label_notes`: required for `WRONG` and `UNSURE`
4. Do not edit any other column. Save as CSV in UTF-8.

## Rules

- Label from the evidence. Do not guess to fill the sheet: `UNSURE` is a valid answer.
- A match is `CORRECT` only if it is the same person. A matching name alone is not enough.

## What happens next

Claude estimates the wrong-match rate, with a 95% interval, separately for:
- the identity-sensitive pairs
- the other pairs

Each `WRONG` row is then listed for a decision. No mapping is changed automatically. With 0 errors in 100 rows, the upper bound of the 95% interval is about 3%.

## Round 2 (adjudicated mappings)

File: `iss01_identity_labeling_sample_round2.csv` (38 rows). Built by `src/phase5/iss01_sample_round2.py`.

It contains:
- **every** adjudicated mapping (36 pairs)
- the two worst-error players that were missing from round 1

For 27 rows the evidence is reused from the existing sample. For the other 11 rows (`evidence_source = BUILT_PHASE5`) it was built from the release and the Transfermarkt curated tables. On those rows the FotMob nationality is the present-day profile value. Label exactly as in round 1.
