# rs5 Step 2 Handoff: G2 Source Dataset Rebuild Gate

Date: 2026-11-07. Prerequisite G1: PASS (verified: report present, protection check clean). **G2: PASS**, with the inherited source limitations listed below.

## Work completed

- FotMob research release `fotmob_epl_2020_2025_rs5_v1`: season filter of v3.1, rows proven unchanged, totals, coverage, conflicts, dictionary season counts and referential integrity recomputed.
- Target `target_rs5_v1__matching_v2_1`: the approved Phase 3 code run unchanged on the rs5 population. 2,747 rows identical to the historical in-scope rows, plus temporal and previous-valuation evidence, also identical.
- 22 new tests; full suite 397 of 397.

## G2 criteria

| Criterion | Evidence | Met |
|---|---|---|
| Both source datasets rebuilt | Two versioned outputs with manifests | Yes |
| Exactly five allowed seasons | `check_parquet` with `require_all` | Yes |
| No 2019/20 records | Tested on every table and CSV; season-data paths checked | Yes |
| Historical datasets unchanged | 38 FotMob hashes; protection check 0 unexpected | Yes |
| Data contracts satisfied | `DATA_CONTRACT_RS5.md` checks | Yes |
| Target methodology preserved | Same function; 0 differing rows | Yes |
| Provenance retained | Raw paths, record references, file hashes | Yes |
| Automated tests passing | 397 of 397 | Yes |
| Rebuild reproducible | Re-runs reported identical content | Yes |

## Statistics

| | Value |
|---|---:|
| Confirmed player-seasons / unique players | 2,747 / 1,228 |
| Unverified (excluded from population) | 691 |
| UNKNOWN player-match participation | 20,184 of 75,358 |
| Open metric conflicts | 36 |
| Usable / missing targets | 2,697 / 50 |
| Targets older than 90 days | 56.62% |
| Appearances after valuation | 44.10% |

## Known limitations (quantified)

1. **Inherited `CONDITIONAL_GO`:** 20,184 UNKNOWN bench participations; 691 Unverified player-seasons.
2. **Identity not yet revalidated in scope:** the target uses the historical mapping (1,190 AUTO_EXACT, 36 AUTO_ADJUDICATED, 2 REVIEW_REQUIRED players). No human labels exist.
3. **RD-01 (research decision requested):** 12 usable targets are over 365 days old, one at 731 days (valuation dated 2019-05-23). The rule has no age cap; nothing was changed.
4. `key_passes` has no values; `clearances` has values in only 3 of 5 seasons.
5. 387 player profiles are stored in 2019_2020-named capture folders; they're player-level, not season data.

## Next actions for Prompt 03

1. Verify G2 evidence and both manifests.
2. Re-run entity resolution with **in-scope evidence only**: FotMob rs5 tables, TM games, appearances and club-seasons for seasons 2020 to 2024. Use the unchanged `entity_resolution.run` with scoped inputs.
3. Compare each in-scope identity's status and TM id with `matching_v2_1`. Re-check the 36 adjudications against the scoped candidate sets. Keep the 2 unresolved players unresolved.
4. If any in-scope mapping changes, rebuild the target under a new matching version. Otherwise reuse `target_rs5_v1__matching_v2_1`, with that equality tested.
5. Integrate with `checked_join`; drop D7 and 2020-04-08 batch columns (all false or redundant in scope).
