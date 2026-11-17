# Phase 3 Issue Tracker (Final)

Updated 2026-11-05. This consolidates `step_03_qa/ISSUE_TRACKER.md` and the Step 4.1 additions, both of which are kept unchanged.

**No open issue is CRITICAL.** No issue blocks Phase 4 from starting, subject to the conditions in `PHASE3_FINAL_REPORT.md`.

## Open

| ID | Severity | Issue | Impact | Owner | Next action |
|---|---|---|---|---|---|
| ISS-01 | HIGH | No human identity labels. Direct precision bound is 98.70%, below the SOP's 99% | Keeps G3 `CONDITIONAL_PASS`. 584 rows lack independent confirmation | Project owner | Label 300 sampled pairs |
| ISS-02 | HIGH | 63.35% of targets over 90 days old; 41.09% of appearances after the valuation | Temporal alignment limitation under D6 | Phase 4 | Report; don't claim performance determines value |
| ISS-19 | HIGH | 491 of 498 usable 2019/20 targets follow a 0.8/0.9 birth-year cut | Level shift in that season | Phase 4 | With and without 2019/20 (D7) |
| ISS-20 | HIGH | 2019/20 xG, xA, npxG and xGOT come from 4 of 380 matches | Not season measures | Phase 4 | Treat as unavailable for comparison (D7) |
| ISS-04 | MEDIUM | 3 identities unresolved | 3 rows without a target | Project owner | Review the queue |
| ISS-07 | MEDIUM | Birth dates disagree for 4 players; external sources are split | Source quality | Owner, optional | Official records if ever needed |
| ISS-09 | MEDIUM | Height differs by 5 cm or more on 5.6% of mapped pairs | Weak evidence and feature | Phase 4 | Use with care |
| ISS-10 | MEDIUM | Assists differ between FotMob and TM in some seasons | Don't mix sources | Phase 4 | FotMob stays the feature source |
| ISS-21 | MEDIUM | Valuation age mostly reflects league-wide batches | Age tracks season | Phase 4 | Season-aware analysis |
| ISS-22 | MEDIUM | Strict staleness filters change season mix and favor younger, higher-value players | Selection bias if filtered | Phase 4 | No filter applied |
| ISS-23 | MEDIUM | Source removes same-day duplicates and empty values before publishing | Conflicts and gaps can't be seen | Documented | None |
| ISS-24 | MEDIUM | `datum_mw` semantics unknown | Effective vs publication date unknown | Documented | None |
| ISS-25 | MEDIUM | A null xG may mean no shot | Null meaning | Phase 4 | Decide before using |
| ISS-27 | MEDIUM | Missingness isn't random: no-target rows have about 40 of 53 metrics null | Complete-case bias | Phase 4 | Plan for missingness |
| ISS-28 | MEDIUM | `m_clearances` is mostly only in 2024/25; `m_goals_prevented` absent in 2019/20; `m_touches_opposition_box` and `m_goals_prevented` unverified in most seasons | Uneven feature availability | Phase 4 | Check per-season coverage |
| ISS-29 | MEDIUM | 16 rates and `m_clean_sheets` weren't directly verified | Window assumed from totals | Phase 4 | Recompute rates if used |
| ISS-11 | LOW | `m_key_passes` is empty; goalkeepers mostly lack minutes and goals | Feature availability | Phase 4 | Noted |
| ISS-12 | LOW | 51 rows only have later valuations; 13 have no history | Stay missing by rule | None | Reported |
| ISS-13 | LOW | No git (D5); frozen files aren't write-protected | Script hashes stand in | Owner | Decided |
| ISS-14 | LOW | Raw FotMob has `marketValues` | Not in the dataset | Future work | Don't use it |
| ISS-15 | LOW | External evidence came from search summaries | 9 identities; 4 cutoff dates | Documented | Dates also agree with two datasets |
| ISS-16 | LOW | Upstream Transfermarkt rights unverified (D2) | Internal academic use only | Owner | Decided |
| ISS-18 | LOW | Plain `unittest discover` rewrites 10 Phase 2 files; the repo's own runner protects only 9 | Safe runner exists | Agent | Use `step3_qa_run_full_tests.py` |
| ISS-26 | LOW | 2 minutes gaps in 2023/24; cause not determined | Negligible | Documented | None |
| ISS-30 | LOW | `m_starts` differs from confirmed starts on 19 rows | Small | Documented | None |
| ISS-31 | LOW | SOP's separate `fotmob_confirmed_population.parquet` not produced | Population is in the integrated dataset | Documented | None |

## Resolved

| ID | Issue | Resolution |
|---|---|---|
| ISS-05 | Multi-club 80 vs 61 | Different definitions; both kept, with `multi_club_class` |
| ISS-03 | xG/xA windows unverified | Verified for 2020/21 on; 2019/20 measured; D7 applies |
| ISS-06 | April 2020 cluster unexplained | Birth-year pattern measured; external reports fit; date semantics unknown |
| ISS-08 | TM appearance shortfall | Located in 32 player-seasons; cause unknown; no effect on targets |
| ISS-17 | SOP documents missing | `DATA_CONTRACT.md` and execution tracker delivered |
| ISS-R3, ISS-G0, FIX-01 to FIX-09 | See `step_03_qa/ISSUE_TRACKER.md` | Closed with tests |
