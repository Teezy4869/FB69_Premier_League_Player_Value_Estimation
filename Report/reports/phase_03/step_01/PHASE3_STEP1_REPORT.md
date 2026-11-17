# Phase 3 Step 1 Report: Repository Inspection and Source Feasibility

Date: 2026-11-04. Status: **complete, awaiting owner decisions. Step 2 has not started.**

## Summary

| Gate | Decision | Why |
|---|---|---|
| **G0** Foundation ready | **CONDITIONAL PASS** | All seven Step 1 criteria are met. `CLAUDE.md` also requires verified cutoff configurations, and those are not finished. |
| **G1** Source feasible | **CONDITIONAL PASS** | Source, schema and coverage hold up. Owner approval and a rights decision are outstanding. |

The FotMob input is sound and reconciles exactly to 3,262 rows. `dcaribou/transfermarkt-datasets` has real historical valuations covering 98.2% of TM's own EPL player-seasons.

The most important finding is about timing rather than availability: **63.3% of latest eligible valuations are over 90 days old at the cutoff**, because valuations arrive in batches.

## Questions answered

| # | Question | Answer | Evidence level |
|---|---|---|---|
| 1 | Is FotMob v3.1 complete and usable? | Yes, with its documented limits | Records and hashes |
| 2 | Does Confirmed reconcile to 3,262? | Yes, exactly | Records |
| 3 | Is the TM dataset accessible and documented? | Yes; the documentation is thin at column level | Records and docs |
| 4 | Does it have historical valuations for targets? | Yes: 656,301 observations, unique per player and date | Records |
| 5 | Does it cover all six seasons? | Yes for TM's EPL population; FotMob's is unknown until Step 4 | Records |
| 6 | Is the schema enough for identity resolution? | Yes, but there is no shared ID, so matching is needed | Records |
| 7 | Any license, provenance, freshness or quality limits? | Yes, listed below | Mixed |
| 8 | Is it suitable for Step 2? | Yes, once the conditions are approved | Judgment |

## What was inspected

- The repository layout, configs, code, tests and environment.
- All 38 checksummed files of the v3.1 release, and all 1,343 Confirmed raw profiles (scanned for a TM ID).
- TM repository documentation, dbt SQL and tests, PR #378, Discussion #383, and Kaggle metadata.
- Six TM tables, downloaded to the session scratchpad as evidence only (about 62 MB). They are **not** project data and not the Step 2 snapshot.

## Actual row counts

**FotMob:** Confirmed 3,262 (515, 524, 537, 554, 570, 562 by season); Unverified 790; total 4,052; 1,343 unique Confirmed players; 80 multi-club rows by flag, 61 by confirmed club count.

**Transfermarkt:** `player_valuations` 656,301; `players` 50,149; `transfers` 175,165; `clubs` 796; `competitions` 65; `appearances` 1,894,350.

## Limitations and risks

| ID | Issue | Severity | Next action |
|---|---|---|---|
| R1 | Under the approved rule, 63.3% of valuations are over 90 days old, and 24-67% of each season's games follow the most common selected date | **High** (research validity) | Owner decision D4 before Step 4 |
| R2 | CC0 comes from the maintainer; Transfermarkt's terms were not retrievable | **Medium**, depends on use | Owner decision D2 |
| R3 | TM appearances fall short of FotMob in 2019/20 to 2021/22 (-3, -2, -29 players), cause unknown | Medium | Investigate in Steps 2 and 3 |
| R4 | 2019/20: 489 of 496 valuations share one April 2020 date; a non-performance effect is possible but unverified | Medium | Report in Step 4 |
| R5 | No shared ID; agreement of DOB between sources is unmeasured | Medium | Labeled sample in Step 3 |
| R6 | R2 URLs are mutable and unversioned | Low, controlled | SHA-256 stop rule |
| R7 | `player_valuations.current_club_id` can fall back to a present-day club | Low, controlled | Use `appearances.player_club_id` |
| R8 | No source record ID or currency column for valuations | Low | Derived lineage key; EUR as documented |
| R9 | FotMob xG/xA windows unverified; 2019/20 xG on only 69 of 515 rows | Medium | Leakage audit in Step 5 |
| R10 | Goalkeepers mostly lack `m_minutes_played` (235 of 237 null rows); `m_key_passes` is empty | Medium for Phase 4 | Report in Step 5 |
| R11 | Multi-club definitions disagree (80 vs 61) | Low | Define in Step 5 |
| R12 | No git repository, so no code version can be recorded; frozen files are not write-protected | Low to medium | Owner decision D5; re-verify the manifest at each step |
| R13 | Environment has no project venv, and `requirements.txt` lacks `duckdb` | Low | Owner decision D3 |

## Gate evidence

### G0: Conditional pass

| Criterion | Status | Evidence |
|---|---|---|
| Input location identified | Met | `data/releases/fotmob_epl_2019_2025_v3_1` |
| Schema documented | Met | `FOTMOB_INPUT_AUDIT.md` sections 2 and 5-7 |
| Confirmed population reconciled | Met | 3,262 of 3,262, all set checks 0 |
| Six seasons accounted for | Met | Each season has rows and 380 completed matches |
| Uniqueness assessed | Met | 3,262 unique keys |
| Provenance and checksums recorded | Met | 38 of 38 files verified |
| Initial data contract | Met | `FOTMOB_INPUT_AUDIT.md` section 7 |
| Six cutoff configurations verified (`CLAUDE.md` section 12) | **Not complete** | Dates match fixtures; 2 of 6 have a direct official league source; `seasons.yaml` belongs to Step 4 |

This condition blocks Step 4 only. Separately, the release itself carries a `CONDITIONAL_GO` verdict, and that stays in force.

### G1: Conditional pass

| Criterion | Status | Evidence |
|---|---|---|
| Specific snapshot identified | Met | Hashes in `source_feasibility_decision.json` |
| Provenance and license understood | **Partly** | CC0 and collection method verified; upstream rights unverified |
| Required schema verified | Met | `TM_SCHEMA_FEASIBILITY.md`, from records |
| Valuation capability demonstrated | Met | 656,301 rows, 0 duplicate keys |
| Six-season coverage assessed | Met | 96.9-99.6% by season, TM's EPL population |
| Identity feasibility evaluated | Met | `TM_IDENTITY_FEASIBILITY.md` |
| Acquisition limits documented | Met | `TM_SOURCE_AUDIT.md` |
| Owner approval | **Outstanding** | |

## Proposed structure for Steps 2-5

Follows the existing `configs/`, `src/`, `tests/`, `reports/phase_XX/` and versioned release conventions. Nothing beyond the Step 1 files has been created.

```text
configs/phase_03_seasons.yaml, phase_03_matching.yaml
src/phase3/    acquire_tm.py, normalize_tm.py, names.py, entity_resolution.py,
               season_targets.py, integrate.py, validate.py
tests/phase3/  unit and acceptance tests, synthetic fixtures kept separate
data/transfermarkt/
  source/tm_20260905/   immutable snapshot    (Raw)
  metadata/             manifest, schema
  staging/              typed, normalized     (Staging)
  curated/              validated tables      (Curated)
data/phase_03/          crosswalk, targets, review queues
data/releases/fb69_player_season_integrated_v1/   final release with manifest
reports/phase_03/step_0N/
```

**Dependencies:** add only `duckdb` to the existing list; `rapidfuzz` is decided in Step 3 if fuzzy comparison is needed. No Docker, no orchestration.

## Files created

All new; no existing project file was modified.

- `reports/phase_03/step_01/`: this report, `REPOSITORY_INVENTORY.md`, `FOTMOB_INPUT_AUDIT.md`, `TM_SOURCE_AUDIT.md`, `TM_SCHEMA_FEASIBILITY.md`, `TM_VALUATION_COVERAGE_FEASIBILITY.md`, `TM_IDENTITY_FEASIBILITY.md`, `source_feasibility_decision.json`
- `reports/phase_03/step_01/evidence/`: `step1_audit_results.json`, `step1_followups.json`, `post_audit_integrity.json`
- `src/phase3/`: `step1_audit.py`, `step1_followups.py`

## Owner decisions

### Required before Step 2

- **D1: Approve the source.** The R2 CSV set of seven files, pinned by SHA-256, with a stop on mismatch.
- **D2: Rights position.** Accept CC0 as declared and use the data for academic research with attribution, or first check Transfermarkt's terms yourself.
- **D3: Environment.** Allow a project-local `.venv` and adding `duckdb` to `requirements.txt`.

### Required before Step 4

- **D4: Target timing.** The locked rule stays in force unless you change it.
  - **Option A, recommended:** keep the rule, and have Steps 4 and 5 report valuation age and the share of each player's games after the valuation date. This keeps your approved decision and makes the weakness measurable.
  - **Option B:** keep the rule and also restrict features to matches on or before the valuation date. FotMob's season-level metrics may not support this directly, so it needs a feasibility check first.
  - **Option C:** change the target rule, which would reverse a locked decision and would need your explicit instruction.

### Optional

- **D5: Git.** Initialize a repository so outputs can record a commit. I would not do this without your say-so.
