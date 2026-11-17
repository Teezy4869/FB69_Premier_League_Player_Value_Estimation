# rs5 Step 3: Unmatched and Unresolved Players

Two in-scope identities have no mapping. Both stay `REVIEW_REQUIRED`; neither was forced into a match. Each costs one player-season row its target (`NO_ELIGIBLE_IDENTITY_MATCH`). The rows stay in the dataset.

| FotMob id | Name | Season, club | Candidates | Why it isn't automatic |
|---|---|---|---|---|
| 1188035 | Jimi Tauriainen (born 2004-03-09) | 2023/24, Chelsea | TM 681615 "Jimi Tauriainen", born **2004-03-08**, Chelsea 2023/24; 1 of 1 game shared | Birth date one day apart, so the exact rule can't apply; evidence too thin for an automated adjudication |
| 982620 | Daniel Chesters (born 2002-04-04) | 2021/22, West Ham | TM 561452 "Dan Chesters", same birth date, no TM EPL game; TM 692807 "Ivan Gutesa", same birth date, unlikely | Name form differs; no in-scope game or club evidence on the TM side; two same-date candidates |

Historical adjudication for both: `REVIEW_REQUIRED` (basis `EXTERNAL_TOO_THIN`).

## Out of scope, not carried

The six-season crosswalk had a third unresolved identity, Jota (244563), who appears only in 2019/20. He isn't in the rs5 universe and isn't listed in any rs5 output.

## Impact

- 2 of 2,747 rows (0.07%) have no identity, and so no target.
- In total, 50 rows have no target: 37 have only later valuations, 11 have no valuation history and 2 have no identity. Each is listed with its reason in the integrated dataset (`target_missing_reason`).

## To resolve

A person reviews the 3 queue rows in `data/research_rs5/review/matching_review_queue.csv`. The reviewer fields are `reviewer_decision`, `reviewer_name`, `review_date` and `reviewer_notes`. Any confirmed mapping creates a new crosswalk version, then a new target and dataset version.
