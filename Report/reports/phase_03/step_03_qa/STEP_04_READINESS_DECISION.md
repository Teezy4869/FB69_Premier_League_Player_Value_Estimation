# Step 4 Readiness Decision

Date: 2026-11-04. Made autonomously under the authority given for this task.

## Decision: **AUTHORIZED**, on eligible mappings only

Step 4 ran with 3,259 of 3,262 player-season rows eligible for a target. The other 3 stay in the table with a missing target. Results are in `reports/phase_03/step_04/`.

## Conditions

| Condition | Status | Evidence |
|---|---|---|
| 1. Mapped population has a defensible identity basis | Met | 1,299 by unique exact name and birth date, 980 of them independently confirmed; 41 adjudicated with recorded evidence; 0 rejected |
| 2. Unresolved identities excluded or retained as missing | Met | 3 identities get `TARGET_MISSING` with reason `NO_ELIGIBLE_IDENTITY_MATCH` |
| 3. Crosswalk internally consistent | Met | All integrity checks pass; artifacts reconcile |
| 4. Target construction can keep temporal rules | Met | Six cutoffs verified from Premier League pages and two datasets; tests fail on any post-cutoff selection |
| 5. No unresolved defect can silently create wrong labels | Met, with a caveat | No known defect. Identity uncertainty isn't hidden: each row carries `identity_evidence_tier` |

## Caveat carried into Step 4

G3 is still `CONDITIONAL_PASS`. Targets for mappings without independent confirmation (584 rows) are real valuations tied to a less proven identity. They were kept and labeled rather than dropped, because dropping them would silently bias the data against young and fringe players.

**Tiers and row counts:**

| `identity_evidence_tier` | Player-seasons | Usable targets |
|---|---:|---:|
| `AUTO_EXACT_VALIDATED` | 2,577 | 2,549 |
| `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` | 584 | 551 |
| `AUTO_ADJUDICATED_INDEPENDENT_RULE` | 90 | 87 |
| `AUTO_ADJUDICATED_EXTERNAL` | 8 | 8 |
| `UNRESOLVED` | 3 | 0 |

If human review later overturns a mapping, the pipeline produces a new versioned output rather than changing this one.

## Other gates affected

**G0 upgrades to `PASS`.** Its only remaining condition was verified cutoff configuration, which `configs/phase_03_seasons.yaml` now provides, with all six dates sourced from Premier League pages. The FotMob release's own `CONDITIONAL_GO` verdict still stands, and it concerns that data's limits, not this gate.

## Not started

Step 5 hasn't started. The multi-club 80 vs 61 investigation you requested is still open and must happen before Step 5.
