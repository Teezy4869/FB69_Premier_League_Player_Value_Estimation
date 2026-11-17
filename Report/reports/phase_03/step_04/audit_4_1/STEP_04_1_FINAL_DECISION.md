# Step 4.1 Final Decision

Date: 2026-11-05.

## Decisions

| Question | Decision |
|---|---|
| **Does G4 remain `PASS`?** | **Yes**, with limitations that must now travel with the data |
| **Must more limitations be documented?** | **Yes**, section 2 |
| **Is the dataset suitable for Step 5?** | **Yes.** Integration preserves all rows and doesn't depend on the open questions |
| **Is a methodological decision needed before Phase 4?** | **Yes:** the research objective |
| **G3** | Unchanged: `CONDITIONAL_PASS` |

**Why G4 stays `PASS`:** its criteria concern the approved rule, and all are met and independently reproduced. These findings concern what the targets mean. Downgrading G4 for them would confuse "built correctly" with "fit for every purpose".

## 1. Evidence

- Target reproduced with 0 differences across 3,262 rows; 0 selections after a cutoff.
- 337 of 337 tests pass with no protected or watched file changed.
- No unresolved identity carries a target.

## 2. Limitations to carry into Step 5 and Phase 4

| ID | Severity | Limitation | Handling |
|---|---|---|---|
| ISS-19 | HIGH | **491 of 498 usable 2019/20 targets follow a birth-year 0.8/0.9 cut on 2020-04-08.** Median age from the last earlier valuation is 229 days, and 52.72% of those players' games follow it | Join `target_quality_flags.parquet`; values unchanged |
| ISS-20 | HIGH | **2019/20 xG and xA come from 4 of 380 matches.** They aren't season measures | Flag in Step 5; values unchanged |
| ISS-02 (updated) | HIGH | 41.09% of appearances follow the selected valuation. 240 player-seasons have all games after it, 433 have all before | Documented; decides the objective |
| ISS-21 | MEDIUM | Selected dates are mostly league-wide batches, so age mostly reflects season, not player | Season-aware analysis |
| ISS-22 | MEDIUM | Strict staleness filters change the season mix and favor younger, higher-value players | No filter applied; Phase 4 topic |
| ISS-23 | MEDIUM | The source removes same-day duplicates and rows with no value before publishing, so conflicts and gaps can't be seen | Documented; `AMBIGUOUS_VALUATION` can't occur with this source |
| ISS-24 | MEDIUM | `datum_mw` semantics (effective vs publication date) are unknown | Documented as unknown |
| ISS-25 | MEDIUM | From 2020/21 on, xG appears in about 47% of player-games and xA in about 69%, so a null season value may mean no shot, not missing | Phase 4 must decide; not imputed here |
| ISS-26 | LOW | 2 minutes gaps in 2023/24 (9 and 19 minutes), cause not determined | Documented |

These are additions to `step_03_qa/ISSUE_TRACKER.md`, which was left unchanged. Step 5 should merge them into the final tracker.

**Resolved:** ISS-03's unverified xG/xA windows are now verified for 2020/21 on, and measured for 2019/20. ISS-06's April 2020 question is answered as far as the evidence allows.

## 3. Documentation versus owner decision

**Documentation is enough for:** ISS-21 to ISS-26, and the target's definition and lineage.

**Requires your decision:**

### D6: Research objective (before Phase 4)

| Option | Meaning | Effect |
|---|---|---|
| **A. End-of-season estimation** (recommended) | Use the full season to estimate the latest published value at season end | Fits the current data and approved rule. Results must not be described as performance determining value, or as forecasting |
| **B. Prediction at the valuation date** | Use only information available at each valuation date | Needs new feature engineering from raw match files, and approval of that scope. 240 player-seasons would have no current-season data |

I recommend A, because it matches what's been built and approved. B may suit a forecasting claim, but it's a different study. I haven't changed anything for either.

### D7: 2019/20 treatment in analysis (before Phase 4)

Recommended: keep all rows in the canonical dataset, flag them, and require Phase 4 results with and without 2019/20. Treat 2019/20 xG and xA as unavailable in analysis, without altering stored values.

### D8: Step 5 authorization

Recommended: authorize it. It should first run the multi-club 80 vs 61 investigation you asked for, and join the quality flags.

### Still open from earlier

Human labels for the 300 sampled pairs, and review of 3 identities. Neither blocks Step 5, but G3 can't reach `PASS` without the labels.

## 4. Not done

No cutoff, selection rule or staleness threshold changed. No record was removed, no review case was resolved, Step 5 hasn't started, and no model was trained.
