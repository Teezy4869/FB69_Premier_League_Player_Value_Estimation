# Transfermarkt Source Audit (Phase 3, Step 1)

**Conclusion:** `dcaribou/transfermarkt-datasets` is accessible, documented and usable for local processing. Its upstream rights are the main open question. Updates have stopped, but that does not affect the research window.

## 1. Ownership and location

| Item | Finding | Evidence |
|---|---|---|
| Repository | `dcaribou/transfermarkt-datasets`, public, not archived | GitHub API |
| Latest commit | `e44f186d6f06dd8452aaf54c7921ba66c961f637`, 2026-09-05 | GitHub API |
| Releases and tags | None shown on the repository page | Repository page |
| Kaggle mirror | `davidcariboo/player-scores`, owner David Cariboo, **version 679**, 2026-09-05T09:16:22Z, 914,841,335 bytes | Kaggle API |

## 2. Freshness

The maintainer's announcement ([Discussion #383](https://github.com/dcaribou/transfermarkt-datasets/discussions/383), 2026-09-05) says updates are paused with no resume date, because upstream pages are no longer reliably reachable from GitHub Actions.

| Table | Last data |
|---|---|
| `games`, `game_events` | 2026-07-06 |
| `appearances` | 2026-06-28 |
| `player_valuations` | 2026-06-12 (confirmed from records) |
| `players` | No squads beyond the 2025 season |

**Impact:** none on coverage, because the last cutoff is 2025-05-25. Published files remain available, and a frozen source actually suits an immutable snapshot.

## 3. Distributions

R2 base URL: `https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/`. HEAD checks ran on 2026-11-04; all returned 200.

| File | Bytes | Last-Modified | ETag |
|---|---:|---|---|
| `transfermarkt-datasets.duckdb` | 210,776,064 | 2026-09-05 09:12:34 | `4037c0a1e71ea019e2ce1b05916a38d9-26` |
| `transfermarkt-datasets.zip` | 241,129,627 | 2026-09-05 09:12:29 | `4380527b61993c7f39e9f9cf38e74bc0-29` |
| `player_valuations.csv.gz` | 7,197,935 | 2026-09-05 09:12:22 | `087cb1d21a2469ff4a597b6ca86cced4` |
| `players.csv.gz` | 4,389,958 | 2026-09-05 09:12:22 | `bf46ce79e2aec6db1decce7713bb618c` |
| `transfers.csv.gz` | 5,809,514 | 2026-09-05 09:12:23 | `21cdd99be19205ed521890c45da44235` |
| `appearances.csv.gz` | 45,253,638 | 2026-09-05 09:11:59 | `e0444486c9d78a44a74544d7dfbcc8cc-6` |
| `games.csv.gz` | 4,995,595 | 2026-09-05 09:12:20 | `9d56854283f5d47601688ffbd3baaedd` |
| `clubs.csv.gz` | 51,281 | 2026-09-05 09:12:01 | `f30713f2d0022ca4ecbb382cd695e389` |
| `competitions.csv.gz` | 2,242 | 2026-09-05 09:12:02 | `cc53fe35e2c82d73f57f3f5d3d8cf605` |

**R2 URLs are mutable and unversioned.** They hold "latest", so a snapshot must be pinned by SHA-256 at download time. Kaggle is the only distribution with a version number.

**Cross-distribution check:** the decompressed sizes of all six R2 CSVs I downloaded equal Kaggle v679's listed sizes exactly (`player_valuations.csv` 39,647,280; `players.csv` 19,624,138; `appearances.csv` 198,398,405; `transfers.csv` 18,112,063; `clubs.csv` 208,374; `competitions.csv` 12,247). This is size evidence, not a content hash comparison, because I did not download Kaggle's files.

**Minor inconsistency:** the announcement says Kaggle reflects an August 5 build, while Kaggle v679 and the R2 files are dated September 5. The commit log shows a September 5 change to CSV quoting and name trimming, which may explain it. Not confirmed.

## 4. License

| Item | Finding | Status |
|---|---|---|
| Repository license | CC0 1.0 Universal | Verified (`LICENSE`, GitHub API) |
| Kaggle license | `CC0: Public Domain` | Verified (Kaggle API) |
| Transfermarkt's own terms | **Could not be retrieved.** The fetch of `transfermarkt.co.uk/intern/anb` failed, and a web search returned no primary text | **Unknown** |

**Why CC0 is not the full answer:** the maintainer can only waive rights the maintainer holds. The data originates from Transfermarkt, so CC0 does not establish that Transfermarkt's own rights in its market values, or any database rights, were cleared. I am not giving a legal opinion. The owner should confirm this is acceptable for academic use and how Transfermarkt should be attributed, particularly if the dataset will be redistributed.

## 5. Provenance

- **Collection method:** the data was collected by the maintainer's own pipelines. Kaggle's subtitle reads "scraped from Transfermarkt website", and the repository names `acquire-transfermarkt-scraper` and `acquire-transfermarkt-api` workflows. **FB69 would consume this dataset without scraping anything itself**, which fits the approved rule, but the owner should know the origin when describing the method.
- **Lineage:** published as dbt models. `player_valuations` comes from `base_market_value_development`.
- **Correction history:** [PR #378](https://github.com/dcaribou/transfermarkt-datasets/pull/378), merged 2026-08-03, repaired a 2026-07-11 blocked run that overwrote raw data. It reports `player_valuations` going from 507,815 rows / 31,507 players to 656,301 / 41,528.
- **Independent check:** my download has **exactly 656,301 rows and 41,528 players**, so these files include the correction. The PR notes that restoring does not fully recover players seen only in the overwritten file, so a small gap is possible.

## 6. Known limitations

- Scraped, third-party data with no versioned releases on the primary host.
- `player_valuations` has no source record ID, no currency column, and club columns that can fall back to a present-day value (see `TM_SCHEMA_FEASIBILITY.md`).
- TM's EPL appearances fall short of FotMob in the three earliest seasons (see `TM_IDENTITY_FEASIBILITY.md`).
- Valuations arrive in batches, so selected values can be months old (see `TM_VALUATION_COVERAGE_FEASIBILITY.md`).
- 488 `transfers` rows are dated after the snapshot, up to 2030-06-30.

## 7. Suitability for local processing

Suitable. The six needed tables take about 62 MB compressed and 276 MB decompressed, and DuckDB read them on this machine in-process. There is 81 GB free.

**Not verified:** the DuckDB file's catalog. Remote `ATTACH` failed because the `httpfs` extension would not load on this machine (DLL initialization error), and downloading the 211 MB file counts as acquisition. That is why my recommendation below uses CSV.

## 8. Recommended acquisition for Step 2 (needs approval)

- **Primary:** the R2 CSV set pinned by SHA-256: the six tables measured here plus `games.csv.gz` (about 67 MB). Their structure and counts are already verified.
- **Stop rule:** Step 2 compares each file against the hashes in `source_feasibility_decision.json` and stops on any mismatch.
- **Fallback:** Kaggle v679, which may need a Kaggle account. It should not be used silently.
- **Not needed:** the DuckDB file and ZIP, which carry extra tables FB69 does not use.
