# Appearance final quality report

Verdict: CONDITIONAL_PASS for this provisional appearance and population audit. Final v3.1 release is not published.

- Completed matches audited: 2280; raw checksums verified: 2280.
- Match completeness: 2,280 PARTIAL; 0 COMPLETE_VERIFIED, 0 CONFLICTING, 0 UNVERIFIABLE.
- Both positive substitution feeds agree on entering and exiting IDs in 2280/2,280 matches; this is corroboration, not proof of negative completeness.
- Raw schemas: lineup has `source=enetpulse` in 1,482 matches and no source key in 798; matchFacts events object has the same structural keys in all 2,280. No documented explicit UNUSED flag or complete-substitution marker was found.
- Direct positives: 50,160 STARTED and 15,628 SUBSTITUTED_ON. Active playerStats support 50,160 starters and 15,624 entering substitutes; four entering substitutes lack active stats but have direct substitution events.
- Unsupported v3 negatives reverted: 23,604 UNUSED_SUBSTITUTE→UNKNOWN, including the 16,314 prior UNKNOWN→UNUSED transitions. Remaining UNKNOWN 23,604; CONFLICTING 0.
- UNUSED_SUBSTITUTE retained: 0. There is no source-backed complete negative evidence in the current corpus. Explicitly documented source markers or independently verified complete coverage are required before restoring that status.
- Player-season partition: 3,262 CONFIRMED_APPEARED + 790 UNVERIFIED + 0 CONFIRMED_NON_APPEARED + 0 CONFLICTING = 4,052.
- Six seasons each have 380 completed matches. Bournemouth–Luton abandoned fixture 4193691 excluded; replay 4421797 included.
- Primary keys, season/team references, player-team-season relationships, and source provenance passed. Existing 4,135 player-team-season relationships are copied intact.
- Zero network requests. Coverage and population acceptance calculations based on original v3 negatives require recomputation in Prompt 2.

Negative coverage rule: `COMPLETE_VERIFIED` requires an explicit documented unused marker or independently verified complete participation source with coverage semantics. Identical lineup and matchFacts events alone cannot satisfy it.
