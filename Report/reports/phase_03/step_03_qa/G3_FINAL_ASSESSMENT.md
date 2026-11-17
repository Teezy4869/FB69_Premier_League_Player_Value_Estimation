# G3 Final Assessment

Date: 2026-11-04.

## Decision: `CONDITIONAL_PASS`

I did not upgrade G3 to `PASS`. The crosswalk's integrity is fully verified, but the required validation evidence is not all there: direct evidence falls short of 99%, and no person has labeled anything. Calling that a pass would mean lowering the standard.

## Criteria

| Criterion | Status | Evidence |
|---|---|---|
| Crosswalk schema documented | Met | `step_03/MATCHING_RULES.md`, with changes in `MATCHING_ARCHITECTURE_REVIEW.md` |
| Actual identity fields verified | Met | Inspected; birth dates re-derived from raw files with 0 mismatches |
| Rules explicit and reproducible | Met | Config-driven; byte-identical reruns |
| Name-only false matches prevented | Met | Tested; name, fuzzy score and game overlap can't map alone |
| Labeled sample exists or absence documented | **Partly met** | 300 automated labels exist; **human labels: 0** |
| Precision/recall claims supported | Met, narrowly | Only the bounds below are claimed |
| Ambiguous and unmatched retained | Met | 3 retained; all 44 stay reviewable |
| Mappings have traceable evidence | Met | Every mapping has evidence; automated ones name the adjudicator |
| Uniqueness and cardinality | Met | 0 duplicates in FotMob, canonical or TM IDs |
| Review workload reported | Met | Below |
| **Evaluated labeled sample (`CLAUDE.md`)** | **Not met as human labels** | Automated evaluation only |
| **Critical false matches resolved or quarantined (`CLAUDE.md`)** | **Met on current evidence** | 0 found; 72 sampled pairs remain unverified |
| **Precision at least 99% (SOP)** | **Not established directly** | 98.70% lower bound among decided pairs |

## What is verified

- Population, counts, uniqueness and checksums (all reproduced).
- 980 of 1,299 automatic mappings are confirmed by independent evidence; 0 are rejected.
- No rival outperforms any mapped pair, and no club contradiction exists.
- The validator rejects most wrong pairs and rarely confirms them (at most 0.6% in the hardest control).

## What remains uncertain

| Uncertainty | Size | Affects the mapped population? |
|---|---:|---|
| Automatic mappings with no independent confirmation | 319 identities, 584 rows | **Yes.** Not shown wrong, but not shown right beyond name, birth date and game history |
| Adjudicated by external evidence | 7 identities, 8 rows | Yes, lightly; they rest on search summaries |
| Reliability of exact birth dates | At least 4 players disagree | Failure sends cases to review rather than creating wrong mappings |
| Unresolved identities | 3 identities, 3 rows | No; they get no target |

**Model-based estimate:** if wrong mappings behave like the control pairs, precision is at least 99.15%, and likely higher. This supports confidence but doesn't replace a direct estimate.

## What evidence would close G3

1. **A person labels the 300 random pairs**, especially the 72 inconclusive ones. The file is ready, and it would take a few hours.
2. **Review of the 3 unresolved identities**, and ideally spot checks of the 41 automated decisions.

0 errors across all 300 would give a 99.0% lower bound. One error would give about 98.4%, and that decision would need your view. G3 could then become `PASS`.

## Can Step 4 safely run on the verified subset?

**Yes.** See `STEP_04_READINESS_DECISION.md`. Each target row carries its identity evidence tier, so any later analysis can exclude weaker tiers.
