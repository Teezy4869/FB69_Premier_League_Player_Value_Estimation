# rs5 Step 4: Audit Test Results

| Run | Result |
|---|---|
| `tests/research_scope/test_audit_rs5.py` | 9 of 9 PASS |
| Full repository (protected runner; `evidence/full_test_run/`) | **431 of 431 passed, 0 failed, 0 skipped** (366 historical + 65 rs5) |
| Historical protection check (`evidence/protection_check_g4.json`) | 0 unexpected changes, 0 removed |

## What the audit tests assert

1. The audit evidence was produced from the current dataset (its SHA-256 is recorded and re-checked).
2. Feature windows were re-checked on exactly the five seasons, and match the historical per-season rows.
3. Temporal indicators were recomputed independently from match dates and agree with the dataset columns: 56.62% and 44.10%. Zero valuations and zero appearances fall after the cutoff, and both definitions state their denominators.
4. Every one of the 175 columns has a leakage classification and evidence. No candidate predictor is FAIL. Every `target_*` and `temporal_*` column is FAIL and has a non-predictor role.
5. No candidate feature has |Spearman| ≥ 0.8 with the log target.
6. The reliability table covers every candidate feature.
7. The evidence files contain only official seasons.
8. Quality invariants hold: 0 duplicate keys, 0 unexpected statuses, 0 value/status inconsistencies, 0 non-positive targets.
