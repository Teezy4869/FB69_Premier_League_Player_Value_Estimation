# Transfermarkt Normalization Report (Phase 3, Step 2)

Date: 2026-11-04. Rule version: `tm_normalization_v1`. Snapshot: `tm_r2_20260905`.

**G2 assessment: PASS.** Evidence is in section 8. Quality findings are in `TM_DATA_QUALITY_REPORT.md`.

## 1. Pipeline

`Approved R2 files -> data/transfermarkt/source -> staging -> curated`

| Layer | Location | Contents | Size |
|---|---|---|---|
| Source | `data/transfermarkt/source/tm_r2_20260905/` | 7 original `.csv.gz` files, read-only | 65 MB |
| Staging | `data/transfermarkt/staging/tm_r2_20260905/` | 7 typed tables: all rows and columns, with lineage | 41 MB |
| Curated | `data/transfermarkt/curated/tm_r2_20260905/` | 6 tables and an exceptions file | 15 MB |
| Metadata | `data/transfermarkt/metadata/tm_r2_20260905/` | `source_manifest.json`, `schema_snapshot.json`, `normalization_manifest.json`, `quality_results.json` | 92 KB |

## 2. Acquisition

| File | Bytes | SHA-256 | Pin basis |
|---|---:|---|---|
| `player_valuations.csv.gz` | 7,197,935 | `608e32e5ad2231074f3505c469ad727be66d7e6efda6af918afd85379439631d` | Approved SHA-256 |
| `players.csv.gz` | 4,389,958 | `d22e407981d5b51a79bf8ff59835729f3526f7dc3495a6d8ed2f852ed2e86403` | Approved SHA-256 |
| `transfers.csv.gz` | 5,809,514 | `90326983daf7e6ac7aabdfe62b90936d9bf1dd2171e53dec75c3751eb1620a83` | Approved SHA-256 |
| `clubs.csv.gz` | 51,281 | `aa57ab56e87faffaea1e8697439a32caf10116d8f2f2dfb3a57193c0bb1d641b` | Approved SHA-256 |
| `competitions.csv.gz` | 2,242 | `8924ddfbc0e9989f4a42a3c32ebb6faa671614625086d7fa84353f955352ea88` | Approved SHA-256 |
| `appearances.csv.gz` | 45,253,638 | `e096c2b158fc3d52c4550526c4d4850dd62f31007652f4bcae112eadb1646802` | Approved SHA-256 |
| `games.csv.gz` | 4,995,595 | `142561989017d379bcf9e72bad0b87e0996bae0e7b710ebb3def9255f464c741` | **Size and MD5 ETag** |

**`games.csv.gz` pin:** Step 1 only ran a HEAD check on this file, so no SHA-256 existed to approve. It was verified by exact size and by its MD5 equalling the ETag recorded in Step 1. The same MD5-equals-ETag relationship held for the five other single-part files. The SHA-256 above is recorded from this first download, so it fixes the file from now on but was not approved in advance.

No conversion happened on disk. Originals stay gzipped and are read as streams.

## 3. Provenance and rights

- **Source:** `dcaribou/transfermarkt-datasets` (David Cariboo), commit `e44f186d6f06dd8452aaf54c7921ba66c961f637`. The commit and license were re-checked immediately before download and were unchanged from Step 1.
- **Declared license:** CC0-1.0, declared by the dataset maintainer.
- **Upstream rights:** **not independently verified.** Transfermarkt has not been shown to grant CC0, and this project does not claim it has.
- **Permitted use (owner decision D2):** internal academic research, with attribution. The raw dataset must not be redistributed or represented as officially licensed by Transfermarkt.
- **Attribution:** data derived from dcaribou/transfermarkt-datasets (David Cariboo), built from Transfermarkt data (https://www.transfermarkt.co.uk/).
- **Origin:** collected by the maintainer's own pipelines. FB69 ran no scraper or crawler.

## 4. Actual schema

All files are UTF-8 with no BOM, LF line endings, comma-delimited and double-quote-escaped. No row has the wrong width. Missing values are empty unquoted fields, and no empty quoted strings exist. The CSVs declare no types, so types below were chosen after inspection.

| Source table | Rows | Columns | Key checked | Used for |
|---|---:|---:|---|---|
| `player_valuations` | 656,301 | 6 | `(player_id, date)` unique | Valuation history |
| `players` | 50,149 | 26 | `player_id` unique | Player identity |
| `transfers` | 175,165 | 10 | None in source | Club-move evidence |
| `clubs` | 796 | 17 | `club_id` unique | Club reference |
| `competitions` | 65 | 11 | `competition_id` unique | Competition reference |
| `appearances` | 1,894,350 | 13 | `appearance_id` unique | Historical club evidence |
| `games` | 88,958 | 23 | `game_id` unique | Season label for appearances |

Text values that look like null tokens are kept as text: for example `Unknown` club names (3,199 valuation rows) and one player's surname, `Na`. `city_of_birth` is padded with non-breaking spaces on 44,493 rows and is left as-is in staging; it is not used in curated tables.

## 5. Logical to physical mapping

The full column-by-column map, including derived fields and conversions, is `column_map` in `normalization_manifest.json`.

| FB69 entity | Source | Curated table | Grain |
|---|---|---|---|
| Player records | `players` | `tm_players.parquet` | 1 row per source row; ID is unique |
| Valuation observations | `player_valuations` | `tm_valuation_history.parquet` | 1 row per observation |
| Club records | `clubs` | `tm_clubs.parquet` | 1 row per club |
| Competition records | `competitions` | `tm_competitions.parquet` | 1 row per competition |
| Historical player-club relation | `appearances`, `games`, `clubs` | `tm_player_club_seasons.parquet` | Player x club x season, EPL only |
| Club moves | `transfers` | `tm_transfers.parquet` | 1 row per source row |

**Not available in the source, and not invented:** a valuation record ID, a currency column, and a historical club on the valuation row.

## 6. Normalization rules

**Types**
- Identifiers stay text, matching the FotMob release.
- Casts are strict: a value that fails its format check becomes null and is counted, with the original kept in `<column>__raw`. `12.5` is not rounded to an integer, and `2021-02-30` does not become a date.
- `date_of_birth` converts from timestamp text to `DATE`, and `market_value` to `BIGINT`.

**Lineage**
- Every staging row and every row-level curated table has `_source_file`, `_source_sha256` and `_source_row_number`. Aggregated `tm_player_club_seasons` has the file and hash only.
- `source_record_id` for valuations is `player_valuations:<player_id>:<date>`. This is **derived**, because the source has no record ID. Its uniqueness is verified.

**Duplicates and invalid records**
- Nothing is removed; rows are flagged in `quality_status`.
- Status priority: `INVALID_PLAYER_ID`, `INVALID_DATE`, `INVALID_DATE_AFTER_SNAPSHOT`, `INVALID_VALUE_MISSING_OR_UNPARSEABLE`, `INVALID_VALUE_NONPOSITIVE`, `CONFLICT_SAME_DATE`, `DUPLICATE_EXACT`, `ORPHAN_PLAYER`, `VALID`.
- Every non-`VALID` row is also written to `tm_valuation_exceptions.csv`. Step 4 decides how each status is used.

**Currency**
- Values are not converted. `currency` is the literal `EUR`, and `currency_basis` records that this rests on the source's column name and documentation.

**Names**
- `player_name_normalized` lowercases, removes diacritics and punctuation, joins apostrophes, splits hyphens and collapses whitespace. It keeps all tokens and their order, and raw names sit alongside it.
- This rule differs slightly from the Step 1 audit's helper, so the count of name groups shared by several IDs is 988 here against 982 in Step 1.

**Filtering**
- Only `tm_player_club_seasons` filters: `competition_id = 'GB1'`, all available seasons, grouped.
- Valuations outside the research period are kept, because the latest valuation before a cutoff can predate the period.

**Deliberately excluded from curated tables**

These remain in staging for audit only.

| Column | Reason |
|---|---|
| `players.market_value_in_eur`, `highest_market_value_in_eur` | Current or career values, forbidden as targets |
| `players.current_club_*`, `last_season`, `contract_expiration_date` | Present-day profile |
| `appearances.player_current_club_id` | Present-day club |
| `transfers.market_value_in_eur`, `transfer_fee` | Not valuation observations |

`position_profile` and `sub_position_profile` are kept for identity support and named to show they are present-day values. `source_current_club_*` on valuations is kept for audit and documented as not historical.

## 7. Row counts

| Table | Source | Staging | Curated | Removed |
|---|---:|---:|---:|---:|
| Players | 50,149 | 50,149 | 50,149 | 0 |
| Valuations | 656,301 | 656,301 | 656,301 | 0 |
| Clubs | 796 | 796 | 796 | 0 |
| Competitions | 65 | 65 | 65 | 0 |
| Transfers | 175,165 | 175,165 | 175,165 | 0 |
| Games | 88,958 | 88,958 | Staging only | 0 |
| Appearances | 1,894,350 | 1,894,350 | See below | 0 from staging |

`tm_player_club_seasons`: 1,894,350 appearances, then 149,751 with `GB1` (0 without a game), then **7,599** grouped rows.

Source counts were taken two independent ways, by Python's `csv` module and by DuckDB, and agree for all tables.

## 8. G2 acceptance

| Criterion | Status | Evidence |
|---|---|---|
| Source matches approved decision | Met | 6 of 6 approved SHA-256 pins match; `games` matches size and MD5 ETag (see section 2) |
| Provenance, license, version, checksum recorded | Met | `source_manifest.json` |
| Raw source preserved unchanged | Met | Hashes re-verified after the build; all 7 files read-only; no extra files |
| Schema inspected and documented | Met | `schema_snapshot.json`, from actual files |
| Explicit, valid types | Met | 0 cast failures; type tests pass |
| Valuations traceable | Met | Record ID, row number and file hash; a test compares 500 rows back to the source |
| Duplicate and invalid handling documented | Met | Section 6; fixture tests cover each status |
| Row counts reconciled | Met | Section 7 |
| Tests executed successfully | Met | 42 of 42 new tests, 28 of 28 existing release tests, in `.venv` |
| Limitations reported | Met | `TM_DATA_QUALITY_REPORT.md` |

## 9. How to reproduce

See `ENVIRONMENT_SETUP.md`. A full rebuild from the snapshot is byte-identical for all 13 Parquet files, verified by automated test. `acquire_tm.py` refuses to run if the snapshot exists, and `normalize_tm.py` refuses to replace different output. The project is not a git repository (owner decision D5), so manifests record a null code version.
