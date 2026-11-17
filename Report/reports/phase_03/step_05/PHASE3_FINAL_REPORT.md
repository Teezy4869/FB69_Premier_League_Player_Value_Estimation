# Phase 3 Final Report: Transfermarkt Data Integration

Date: 2026-11-05. Dataset: `data/releases/fb69_player_season_integrated_v1/player_season_integrated_v1.parquet`.

**Recommendation: `CONDITIONAL PASS`.** G5 passes. Phase 3 isn't fully accepted because G3 remains conditional and you haven't yet reviewed this final gate.

## 1. Executive summary

Phase 3 joined frozen FotMob v3.1 performance data with historical Transfermarkt valuations into one row per player-season.

| Result | Value |
|---|---:|
| Rows / unique player-seasons | 3,262 / 3,262 |
| Players / seasons | 1,343 / 6 |
| Identity mapped | 3,259 rows (99.91%) |
| Usable target | 3,195 rows (97.95%) |
| Rows lost or duplicated | 0 |
| Tests / validation checks | 366 of 366 / 31 of 31 |

**What holds firmly:** population, grain, temporal rule, lineage and reproducibility.

**What carries caveats:** automatic identities haven't been checked by a person. Most targets are over 90 days old at season end, so full-season features partly follow the valuation. 2019/20 needs separate treatment.

## 2. Scope and approved decisions

- **Scope:** Premier League, 2019/20 to 2024/25, Confirmed player-seasons only.
- **Target:** latest valid Transfermarkt valuation on or before the official season end.
- **Objective:** A, end-of-season estimation (D6). Results must not be presented as forecasting, or as performance determining value.
- **Non-goals met:** no scraping, Docker, feature selection, model training or Phase 4 work.

The full decision log is in `PHASE3_EXECUTION_TRACKER.md`.

## 3. FotMob source and population

Frozen release `fotmob_epl_2019_2025_v3_1`. All 38 file hashes remain valid. Its own verdict, `CONDITIONAL_GO`, still stands.

| Season | Confirmed | Unverified (excluded) |
|---|---:|---:|
| 2019/20 | 515 | 99 |
| 2020/21 | 524 | 117 |
| 2021/22 | 537 | 142 |
| 2022/23 | 554 | 145 |
| 2023/24 | 570 | 164 |
| 2024/25 | 562 | 123 |
| **Total** | **3,262** | **790** |

## 4. Transfermarkt source and provenance

`dcaribou/transfermarkt-datasets`, commit `e44f186`, seven R2 CSV files pinned by SHA-256 (`tm_r2_20260905`).

- **Rights (D2):** CC0 is the maintainer's declaration. Upstream Transfermarkt rights aren't independently verified, and Transfermarkt hasn't been shown to grant CC0. Internal academic use with attribution; no raw redistribution.
- **Origin:** collected by the maintainer's own pipelines. FB69 scraped nothing.
- **Upstream cleaning:** same-day duplicates and empty values are removed before publication. `datum_mw` semantics are unknown.
- **`games.csv.gz`:** pinned by size and MD5 ETag at download, with its SHA-256 recorded at that point.

## 5. Normalization

Staging keeps all source rows and columns, typed, with lineage. Curated tables exclude current and career-high values. No row was deleted: problems are flagged. 0 cast failures. Valuations: 656,301 rows, 656,300 `VALID`, 1 zero value from 2008 flagged. Details: `step_02/`.

## 6. Entity resolution

Only a unique exact name plus exact birth date can map automatically. Fuzzy evidence can only propose candidates.

| Status | Players | Rows | Basis |
|---|---:|---:|---|
| `AUTO_EXACT` | 1,299 | 3,161 | Exact rule |
| `AUTO_ADJUDICATED` | 41 | 98 | Automated evidence, **not human** |
| `REVIEW_REQUIRED` | 3 | 3 | Too thin for an automated decision |
| `MANUAL_CONFIRMED` | 0 | 0 | No human review exists |

**Validation (automated, with no name, birth date or game overlap as evidence):**

| Measure | Result |
|---|---|
| Random 300: confirmed / rejected / inconclusive | 228 / 0 / 72 |
| 95% lower bound among decided pairs | **98.70%**, below the SOP's 99% |
| All 1,299: confirmed / rejected / inconclusive | 980 / 0 / 319 |
| False confirmation, hardest control | 3 of 1,299 |

Details: `step_03/`, `step_03_qa/`.

## 7. Target construction

For each eligible player-season, the latest valid valuation with `date <= season end`. Cutoffs were verified against Premier League pages and two independent fixture datasets: 2020-07-26, 2021-05-23, 2022-05-22, 2023-05-28, 2024-05-19, 2025-05-25.

No value was imputed or converted. Current and career-high values aren't read. Independent SQL from the original CSV reproduced every selection. Details: `step_04/`, `step_04/audit_4_1/`.

## 8. Staleness and coverage

| Season | Rows | `VALID` | `STALE_TARGET` | Missing | Usable | Median age | Over 90 days | Appearances after valuation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019/20 | 515 | 1 | 497 | 17 | 96.70% | 109 | 99.80% | 25.38% |
| 2020/21 | 524 | 500 | 15 | 9 | 98.28% | 66 | 2.91% | 24.91% |
| 2021/22 | 537 | 116 | 412 | 9 | 98.32% | 150 | 78.03% | 48.58% |
| 2022/23 | 554 | 179 | 363 | 12 | 97.83% | 206 | 66.97% | 54.72% |
| 2023/24 | 570 | 155 | 412 | 3 | 99.47% | 152 | 72.66% | 46.84% |
| 2024/25 | 562 | 220 | 325 | 17 | 96.98% | 160 | 59.63% | 44.16% |
| **Total** | **3,262** | **1,171** | **2,024** | **67** | **97.95%** | 109 | 63.35% | 41.09% |

**2019/20:** 491 of 498 usable targets are dated 2020-04-08 and follow a 0.8/0.9 birth-year cut. External reports describe a pandemic adjustment. Original dates and values are kept. From the last earlier valuation, median age is 229 days.

**Staleness filters** change season mix and favor younger, higher-value players, so none was applied.

## 9. Integration

A LEFT JOIN from the frozen population through 7 checked joins. Each join requires unique right keys and an unchanged row count, or the build stops. FotMob features stay unchanged. Multi-club players stay one row, with club detail in a separate table.

**Multi-club 80 vs 61:** both are valid. 61 played for two clubs; 80 were listed with two, including 19 with bench rows only at a second club. `multi_club_class` makes this explicit. Transfermarkt independently agrees with all 80.

## 10. Population and cardinality validation

| Check | Result |
|---|---|
| Rows at every join | 3,262 |
| Unique canonical player-season keys | 3,262 |
| Lost / added / Unverified entered | 0 / 0 / 0 |
| Duplicate crosswalk or target keys | 0 |
| Many-to-many joins | 0 |
| Multi-club duplicates | 0 |

Details: `INTEGRATION_AUDIT.md`.

## 11. Missingness

| Item | Result |
|---|---|
| Missing target | 67: 51 only later valuations, 13 no history, 3 no identity |
| Missing Transfermarkt ID | 3 |
| Mean null metrics, with / without a target | About 17 / about 40, of 53 |
| Null features converted to zero, or imputed | 0 |

Missingness isn't random: it concentrates in fringe players and goalkeepers, and some metrics cover only some seasons. Details: `MISSINGNESS_REPORT.md`.

## 12. Leakage

**No critical leakage under objective A.** No future valuation or current profile value is used, the target is separated by column role, and nationality is labeled as present-day.

| Feature conclusion | Count |
|---|---:|
| Usable, alignment limit applies | 27 |
| Usable, except 2019/20 comparison (xG family) | 4 |
| Partly verified | 5 |
| Rate not directly verified | 16 |
| Window not verified / no data | 1 / 1 |
| Other context, reviewed individually | 3 |

**Features follow the valuation in 41.09% of appearances.** This is a temporal alignment limitation under A, not leakage. The same features would be leakage under a prediction objective. Details: `LEAKAGE_AUDIT.md`.

## 13. Reproducibility and tests

| Check | Result |
|---|---|
| Full repository tests, protected runner | 366 of 366 |
| Dataset validator | 31 of 31 |
| Rebuild of all stages, byte comparison | 12 of 12 identical |
| Protected Phase 2 files against backup | 10 of 10 identical |
| Frozen FotMob hashes | 38 of 38 |

The manifest records inputs, outputs, script hashes and row counts. There is no git commit (D5). Rebuild steps: `step_02/ENVIRONMENT_SETUP.md`, `src/phase3/reproduce_phase3.py`. Details: `VALIDATION_SUMMARY.md`.

**Disclosed incident:** on 2026-11-04, my unprotected test runs rewrote 10 historical Phase 2 files. All remain byte-identical to the backup; only modification times changed. See `step_03_qa/STEP_03_INDEPENDENT_AUDIT.md`.

## 14. Known limitations

1. Identity is automatically validated, not human-reviewed.
2. The target is the latest published value, typically months old, not a season-end reassessment.
3. Results can't be read as performance causing value.
4. 2019/20 targets include a rule-based cut, and its xG family covers 4 of 380 matches.
5. Valuation dates are mostly league-wide batches, so age tracks season.
6. Metrics were collected retrospectively, in November 2026.
7. Source cleaning hides any same-day conflicts and empty values.
8. Upstream rights are unverified.
9. Some metrics have uneven coverage, or unverified windows.
10. External evidence came from search summaries.

## 15. Unresolved issues

All are in `ISSUE_TRACKER.md`. **No CRITICAL issue is open.** The main ones:

| ID | Severity | Issue | Owner |
|---|---|---|---|
| ISS-01 | HIGH | No human identity labels | Project owner |
| ISS-02 | HIGH | Temporal alignment | Phase 4 |
| ISS-19 | HIGH | 2019/20 birth-year cut | Phase 4 (D7) |
| ISS-20 | HIGH | 2019/20 xG family | Phase 4 (D7) |
| ISS-04 | MEDIUM | 3 unresolved identities | Project owner |

## 16. G0–G5 gates

| Gate | Decision | Evidence | Remaining |
|---|---|---|---|
| **G0** Foundation | `PASS` | Input verified, 3,262 reconciled, six cutoffs verified, contract documented | None |
| **G1** Source | `CONDITIONAL_PASS`, approved | Source, schema and coverage verified; D1 and D2 approved | Upstream rights unverified, accepted under D2 |
| **G2** Normalization | `PASS` | Immutable snapshot, valid types, reconciled rows, tests | `games.csv.gz` pin not separately acknowledged |
| **G3** Crosswalk | **`CONDITIONAL_PASS`** | Integrity verified; automated validation; 0 rejections | **Human labels; 3 identities** |
| **G4** Targets | `PASS` | Rule followed; reproduced independently; 0 after cutoff | Limitations documented |
| **G5** Integration | `PASS` | All 11 criteria below | None |

**G5 criteria:**

| Criterion | Status |
|---|---|
| Intended player-season grain | Met |
| Population reconciled | Met |
| No unintended many-to-many | Met |
| Missing values explicit | Met |
| Target temporally valid | Met |
| Multi-club not duplicated | Met |
| Leakage risks documented | Met |
| Provenance complete | Met |
| Reproducibility successful | Met |
| Reports and tests present | Met |
| Blocking issues resolved or escalated | Met: none blocking; G3 escalated here |

## 17. Recommendation and Phase 4 prerequisites

**`CONDITIONAL PASS`.** The dataset is suitable for Phase 4 exploratory analysis and feasibility work, under these conditions:

1. **Objective A only.** Don't present results as forecasting or causal.
2. **D7 applies:** results with and without 2019/20, and no comparison using its xG family.
3. **Use the column roles:** `target_*`, `temporal_*` and `identity_*` aren't predictors.
4. **Identity sensitivity:** compare results with and without `AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED` and `AUTO_ADJUDICATED`.
5. **Plan for missingness** by reading `s_*` status columns; don't drop or impute silently.
6. **Check metric coverage per season** before using a metric.
7. **Keep G3 visible** until it closes.

**To reach full acceptance:** a person labels the 300 sampled pairs and reviews the 3 identities, then you review this gate. Any changed mapping means a new versioned dataset.

Phase 4 hasn't started, and needs your explicit instruction.
