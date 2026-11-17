# Entity Resolution Report (Phase 3, Step 3)

Date: 2026-11-04. Version: `matching_v1`. Status: **stopped for owner review. Step 4 has not started.**

**G3 assessment: `CONDITIONAL_PASS`.** The crosswalk is built and its rules hold, but no person has reviewed or labeled anything yet.

## 1. Result

- 1,299 of 1,343 identities are mapped as `AUTO_EXACT`, covering 3,161 of 3,262 player-season rows (96.9%).
- 44 identities (101 rows) wait for human review, with no mapping and no eligibility for automatic targets.
- 1,267 of the automatic matches have game histories identical across the two sources, and no rival beats any match's overlap.
- Precision and recall are **not** evaluated.

Details: `MATCHING_EVALUATION_REPORT.md`. Rules: `MATCHING_RULES.md`.

## 2. Architecture

```text
FotMob v3.1 Confirmed + TM normalized tables
  -> Game alignment (27 clubs, 2,280 matches, from fixtures)
  -> Identities (FotMob 1,343; TM 50,149)
  -> Exact name + DOB pass
  -> Candidates from 6 blocks, for every identity
  -> Separate evidence signals and ranking score
  -> Classification, then TM ID conflict check
  -> Human decisions from an append-only ledger
  -> Integrity checks; the run stops on any failure
  -> Crosswalk, candidates, review queue, unresolved list, manifest
```

## 3. Outputs

| Output | Location |
|---|---|
| `player_crosswalk.parquet` | `data/phase_03/entity_resolution/matching_v1__reviews_none/` |
| `matching_candidates.parquet` (2,807 pairs) | Same folder |
| `unresolved_identities.csv` (44, with reasons) | Same folder |
| `team_crosswalk.csv`, `run_manifest.json`, `matching_evaluation.json` | Same folder |
| `matching_review_queue.csv` (93 rows, reviewer fields blank) | `data/phase_03/review/` |
| `validation_sample_for_labeling.csv` (labels blank) | `data/phase_03/review/` |

## 4. Provenance

Each mapping stores its method and signals. The manifest records hashes of all inputs, the config and the scripts. There is no git (owner decision D5), so script hashes stand in for a commit. Nothing in FotMob or Transfermarkt source data changed, and the FotMob manifest check passes at each run.

## 5. G3 acceptance

| Criterion | Status | Evidence |
|---|---|---|
| Crosswalk schema documented | Met | `MATCHING_RULES.md` section 10 |
| Actual identity fields verified | Met | Inspected before writing rules; section 1 of the rules |
| Rules explicit and reproducible | Met | Config-driven; rerun gives identical crosswalk, candidates and queue |
| Name-only false matches prevented | Met | Tested: name alone, high fuzzy score and game overlap can't map |
| Labeled sample exists or absence documented | **Absence documented** | Sample is built, labels are blank |
| Precision/recall claims supported | Met, by claiming none | Evaluator reports `NOT_EVALUATED` |
| Ambiguous and unmatched retained | Met | 44 retained; the review workflow supports both statuses |
| Confirmed mappings have traceable evidence | Met | Every mapping has evidence, checked by test |
| Uniqueness and cardinality | Met | 0 duplicates in FotMob, canonical or TM IDs |
| Review workload reported | Met | Evaluation report section 7 |

**Why not `PASS`:** `CLAUDE.md` G3 requires an evaluated labeled sample and resolved or quarantined critical false matches. Without labels, the false-match rate of the 1,299 is unknown. The `AUTO_EXACT` rule also rests on exact DOB, which disagrees between the sources for at least 4 players.

**What is blocked:**
- `MANUAL_CONFIRMED` targets for the 44, until they are reviewed.
- Any precision claim, and the SOP's 99% target, until labels exist.

## 6. Limitations

- **Unlabeled.** Game-history agreement is strong corroboration, not proof of identity.
- **Weakest matches.** 14 automatic matches rest on name and DOB alone, because TM has no EPL rows for them.
- **Fixed weights.** Scoring and blocking settings come from judgment and are not calibrated. They affect only which pairs a reviewer sees and in what order. Candidates outside these blocks can't be seen; no `UNMATCHED` occurred, but a correct TM ID could still sit outside a queue's candidates.
- **Name variants.** There is no nickname table, which adds review work but avoids false matches.
- **Population.** Only the 3,262 Confirmed rows are matched. The 790 Unverified rows are out of scope.
- **Present-day fields.** TM position and nationality are present-day; they only inform ranking.

## 7. Items carried forward

| Item | Due |
|---|---|
| Review 44 identities | Before their targets can exist |
| Label the validation sample | Before G3 can become `PASS` |
| Birth date disagreements: decide whether either source is wrong | During review |
| Official evidence for season cutoffs (G0 condition) | Step 4 |
| Multi-club 80 vs 61 investigation (owner request) | Before Step 5 |
| Open SOP decisions and G2 acceptance | Owner |
