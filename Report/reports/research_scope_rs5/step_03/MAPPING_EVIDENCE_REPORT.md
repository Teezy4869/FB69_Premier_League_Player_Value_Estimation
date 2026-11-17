# rs5 Step 3: Mapping Evidence and Traceability

Every mapping in `matching_v2_1_rs5` can be traced to these files:

| Evidence | File | Content |
|---|---|---|
| Decision row | `matching_v2_1_rs5__reviews_none/player_crosswalk.parquet` | Status, method, evidence JSON, ranking score, adjudicator, rationale, candidate count, rs5 row count |
| Every candidate considered | `matching_candidates.parquet` | 34 signals per pair: name, birth date, nationality, position, club status, in-scope shared games, Jaccard, transfer-club overlap, blocks |
| Club map | `team_crosswalk.csv` | 27 FotMob teams ↔ TM clubs, derived from fixtures |
| Unresolved identities | `unresolved_identities.csv` | 2 rows with reason and candidate count |
| Human-review inputs | `review_snapshot/matching_review_queue.csv`, `validation_sample_for_labeling.csv` (also in `data/research_rs5/review/`) | 81 queue rows; 514 sample rows across 9 strata, all with blank reviewer fields |
| Automated adjudications used | `review_snapshot/automated_adjudications_in_scope.csv` | 38 historical rows, copied unchanged for in-scope identities |
| Validation labels | `matching_v2_1_rs5_identity_validation.csv` | 1,226 rows: label, three family results, evidence text, scope of evidence, `human_reviewed=False` |
| Run provenance | `run_manifest.json`, `../crosswalk_rs5_manifest.json` | Input, code and output SHA-256; scoped seasons; comparison with `matching_v2_1` |

## Status and confidence labels

| Label | Meaning | Human? |
|---|---|---|
| `AUTO_EXACT` + `EXACT_NAME_DOB_UNIQUE_CLUB_CONFIRMED` | Exact rule, and in-scope games or club-seasons agree | No |
| `AUTO_EXACT` + `EXACT_NAME_DOB_UNIQUE_NO_CLUB_EVIDENCE` | Exact rule; no in-scope club evidence either way | No |
| `AUTO_ADJUDICATED` + `AUTOMATED_ADJUDICATION_RULE` / `_EXTERNAL` / `_RULE_AND_EXTERNAL` | Automated decision on validator or cited sources | No (`adjudicator = automated:...`) |
| `identity_evidence_tier` | `AUTO_EXACT_VALIDATED` (rs5 label confirmed), `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED`, `AUTO_ADJUDICATED_INDEPENDENT_RULE`, `AUTO_ADJUDICATED_EXTERNAL`, `UNRESOLVED` | No |
| `identity_rs5_validation_label` | rule_v2 on in-scope evidence | No |

`identity_human_reviewed` is false on every row.

## Player-season rows by evidence tier (integrated dataset)

| Tier | Rows |
|---|---:|
| AUTO_EXACT_VALIDATED | 2,214 |
| AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED | 449 |
| AUTO_ADJUDICATED_INDEPENDENT_RULE | 76 |
| AUTO_ADJUDICATED_EXTERNAL | 6 |
| UNRESOLVED | 2 |

Rows with `identity_rs5_validation_label` CONFIRMED_MATCH / INCONCLUSIVE / not validated: 2,287 / 458 / 2.
