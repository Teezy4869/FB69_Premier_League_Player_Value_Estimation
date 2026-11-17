# Target Temporal Validation (Phase 3, Step 4)

Date: 2026-11-04. Tests: `tests/phase3/test_season_targets.py`.

**No selected valuation is after its cutoff.** This holds across all 3,195 selected valuations, and a second implementation reproduces every selection from the original CSV.

## 1. Checks on real output

| Check | Result |
|---|---|
| `selected_valuation_date <= season_end_date` | **0 violations** |
| Independent SQL recomputation from the original source CSV | **All 3,259 eligible player-seasons identical** in date and value |
| A later valid valuation by the cutoff was skipped | **0** |
| Each selected value equals its exact row in the original CSV | All pass |
| One decision per canonical player-season | 3,262 rows, 3,262 keys |
| Population equals the frozen Confirmed population | Exact |
| Cutoffs match config, FotMob fixtures and TM games | All 6 |
| Age equals cutoff minus selected date, with the right bucket | All pass; none negative |
| `market_value` equals 0 anywhere | 0 |
| Missing rows have a reason and a null value | All pass |
| Ineligible identities with a target | 0 |
| Lineage present on all usable targets | All pass |

## 2. Rule tests on synthetic data

| Rule | Tested by |
|---|---|
| Latest on or before the cutoff is selected | `test_selects_latest_on_or_before_cutoff` |
| A valuation on the cutoff is eligible, with age 0 | `test_valuation_on_the_cutoff_is_eligible_with_zero_age` |
| One day after the cutoff is never selected | `test_one_day_after_cutoff_is_never_selected` |
| A closer future value is not a fallback | `test_future_valuation_is_not_a_fallback_even_when_closer` |
| Missing stays null, not zero | `test_no_history_stays_missing_not_zero` |
| Age 90 is `VALID`, age 91 is `STALE_TARGET`, and it's kept | `test_stale_is_labeled_and_kept` |
| Conflicts are flagged without a value | `test_same_date_conflict_is_flagged_without_a_value` |
| Exact duplicates are not conflicts | `test_exact_duplicate_is_not_a_conflict` |
| Invalid values are skipped | `test_invalid_values_are_skipped_for_the_latest_valid_one` |
| Only invalid values gives `INVALID_VALUATION` | `test_only_invalid_values_give_invalid_status` |
| Bucket boundaries are exact | `test_buckets_use_the_exact_reporting_boundaries` |
| Profile market values are never read | `test_module_never_reads_profile_market_values` |

## 3. Leakage versus alignment

| Question | Answer |
|---|---|
| Is a future valuation used? | **No.** Tested |
| Is a current or career-high profile value used? | **No.** The code reads only valuation history |
| Is a value imputed? | **No.** Missing stays null |
| Do features include matches after the valuation date? | **Yes, by design of the approved rule.** 41.09% of appearances. This is a temporal alignment limitation, documented in `TARGET_CONSTRUCTION_REPORT.md`, not future-data leakage |

The full feature leakage audit, including xG/xA windows, belongs to Step 5 and isn't covered here.

## 4. G4 acceptance

| Criterion | Status | Evidence |
|---|---|---|
| All six cutoffs verified and documented | Met | Premier League pages (2 fetched, 4 via search summaries), plus FotMob and TM fixtures |
| Latest-on-or-before-cutoff rule followed | Met | Recomputed independently |
| No future valuation selected | Met | 0 violations |
| Same-date conflicts handled | Met | Tested; none in real data; empty review file produced |
| Staleness calculated and reported | Met | Coverage report |
| Missing targets preserved | Met | 67 rows with reasons |
| No imputation | Met | Tested |
| Provenance complete | Met | Record, row number and file hash |
| One decision per player-season | Met | Tested |
| Temporal tests pass | Met | All pass |

**Decision: `PASS`** on these criteria. Identity reliability is separate and inherited from G3 (`CONDITIONAL_PASS`). Rows carry `identity_evidence_tier` for that reason.
