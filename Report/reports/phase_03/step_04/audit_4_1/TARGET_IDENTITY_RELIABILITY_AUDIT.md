# Target Identity Reliability Audit (Step 4.1)

Date: 2026-11-05. Results: `identity` section of `evidence/step_04_1_audit_results.json`.

**Conclusion:** no unresolved identity is treated as confirmed, and no automated decision is presented as human. The crosswalk has no concrete defect, so it was not changed. **G3 remains `CONDITIONAL_PASS`.**

## 1. Coverage by identity status

| Crosswalk status | Evidence tier | Players | Player-seasons | Usable | `VALID` | `STALE_TARGET` | Missing |
|---|---|---:|---:|---:|---:|---:|---:|
| `AUTO_EXACT` | `AUTO_EXACT_VALIDATED` | 980 | 2,577 | 2,549 | 963 | 1,586 | 28 |
| `AUTO_EXACT` | `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 319 | 584 | 551 | 174 | 377 | 33 |
| `AUTO_ADJUDICATED` | `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 34 | 90 | 87 | 32 | 55 | 3 |
| `AUTO_ADJUDICATED` | `AUTO_ADJUDICATED_EXTERNAL` | 7 | 8 | 8 | 2 | 6 | 0 |
| `REVIEW_REQUIRED` | `UNRESOLVED` | 3 | 3 | 0 | 0 | 0 | 3 |
| `MANUAL_CONFIRMED` | Not present | 0 | 0 | 0 | 0 | 0 | 0 |
| `UNMATCHED` | Not present | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | | **1,343** | **3,262** | **3,195** | **1,171** | **2,024** | **67** |

## 2. Checks

| Check | Result |
|---|---|
| Target rows disagreeing with the crosswalk on ID, status or canonical ID | 0 |
| Unresolved rows with a value, TM ID or valuation date | 0 |
| Reviewer or review date filled anywhere | 0 |
| Review ledger | Doesn't exist, because no person has reviewed |
| `AUTO_ADJUDICATED` rows labeled other than automated, or without an adjudicator | 0 |
| Duplicate TM IDs | 0 |
| Crosswalk file versus the target manifest's recorded hash | Matches |

## 3. Unresolved rows

| Player | Season | Status | Target |
|---|---|---|---|
| Jota | 2019/20 | `REVIEW_REQUIRED` | `TARGET_MISSING`, `NO_ELIGIBLE_IDENTITY_MATCH` |
| Daniel Chesters | 2021/22 | `REVIEW_REQUIRED` | `TARGET_MISSING`, `NO_ELIGIBLE_IDENTITY_MATCH` |
| Jimi Tauriainen | 2023/24 | `REVIEW_REQUIRED` | `TARGET_MISSING`, `NO_ELIGIBLE_IDENTITY_MATCH` |

## 4. Risk to the target

| Tier | Median value (EUR) | Median games | Over 90 days |
|---|---:|---:|---:|
| `AUTO_EXACT_VALIDATED` | 14,500,000 | 23 | 62.2% |
| `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 6,500,000 | 13 | 68.4% |
| `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 15,000,000 | 21 | 63.2% |
| `AUTO_ADJUDICATED_EXTERNAL` | 2,850,000 | 8 | 75.0% |

**Unvalidated rows are not a random subset.** They skew toward fringe players with lower values and fewer games, because those players give the validator less evidence to work with. So:

- Dropping them would bias the dataset against fringe players. That's why they were kept and labeled.
- If any identity errors exist, they would most likely sit in lower-value rows.
- Comparing results with and without this tier is a sensible Phase 4 check.

## 5. Unchanged

No crosswalk change was made, and G3 stays as decided. The evidence needed to close it is still human labels for the sampled pairs.
