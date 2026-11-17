# ISS-01 Identity Labelling Result

Date: 2026-11-16. Source: `reports/phase_05/step_04/iss01_identity_labeling_sample.csv`, labelled by the owner on 2026-11-16. Labeller name and date are filled in on every row.

## Labels

| Group | Rows | CORRECT | WRONG | UNSURE | 95% upper bound of wrong-match rate (Clopper-Pearson) |
|---|---:|---:|---:|---:|---:|
| All | 101 | 101 | 0 | 0 | **3.6%** |
| Identity-sensitive (P4-B01) | 67 | 67 | 0 | 0 | 5.4% |
| Other | 34 | 34 | 0 | 0 | 10.3% |

## Reading

- No wrong match was found. With 0 errors, the data are consistent with a wrong-match rate of up to about 3.6% overall, not with a rate of 0.
- The sample was drawn from the automatic-match random stratum (`AUTO_EXACT_RANDOM`), plus one worst-error case. The estimate therefore covers automatic exact matches only. It does not cover the adjudicated mappings (36 players), and it does not cover the two worst-error players outside the source sample (FotMob 1113790 and 1324871).
- The higher error of the identity-sensitive rows in step 03 (MAE 0.343 vs 0.247) is therefore **not explained by wrong identities in this sample**. It more likely reflects what those rows are: fewer minutes and players with less validation evidence. This is an interpretation, not a test.

## Status

- ISS-01: owner labelling done.
- Suggested status: **CONDITIONAL PASS**. Automatic exact matches show no error in 101 labelled rows, with an upper bound of 3.6%.
- Still open: adjudicated mappings are not sampled, and mapping precision is not established for them.
- This suggested status does not close ISS-01. Only the owner can accept it.
- No mapping was changed.

## Round 2 (2026-11-16)

Source: `iss01_identity_labeling_sample_round2.csv`, labelled by the owner. Labeller name and date are filled in on every row.

| Group | Rows | CORRECT | WRONG | UNSURE |
|---|---:|---:|---:|---:|
| Adjudicated mappings (all 36, a census rather than a sample) | 36 | 36 | 0 | 0 |
| Worst-error players missing from round 1 | 2 | 2 | 0 | 0 |

- Every adjudicated mapping in the modeling scope was checked by a human, so for this group no estimate is needed: **0 of 36 are wrong**.
- The Michael Olakigbe pair has different dates of birth in the two sources (2004-04-06 vs 2004-04-25). It was labelled CORRECT, with no note. A note giving the reason would make the record complete.
- All three step 03 worst-error identity-sensitive players are now confirmed CORRECT. Their large errors are not identity errors.

## Combined status

| Mapping group | Checked | Wrong | Basis |
|---|---:|---:|---|
| Automatic exact matches | 101 (random sample) | 0 | 95% upper bound 3.6% |
| Adjudicated matches | 36 (all) | 0 | full census |
| UNRESOLVED | 2 rows | – | No target; not in the modeling population |

Suggested ISS-01 status: **PASS**. The residual risk is limited to unsampled automatic exact matches, bounded at 3.6% (95% upper bound). The owner must accept this status before it applies. No mapping was changed.

## Owner decision

2026-11-16: the owner **accepted ISS-01 as PASS**. This was recorded at the owner's request in the chat session. The Phase 4 issue tracker was not edited. Phase 5 reports refer to this file as the record of the decision.
