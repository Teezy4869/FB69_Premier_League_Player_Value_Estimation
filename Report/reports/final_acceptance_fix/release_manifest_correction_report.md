# Release manifest correction

Original v3 declared 38 files; the read-only inventory found 39 physical files. It declared 13 Parquet tables; 16 physical Parquet files exist.
Unlisted Parquet files: normalized/non_appeared_player_seasons.parquet, normalized/substitution_evidence_registry.parquet, normalized/unverified_player_seasons.parquet.
Incorrect row counts: [('normalized/confirmed_appeared_player_seasons.parquet', '3262', '4052')].
Root cause: `remediation_release_v3.py` assembled the manifest from a hand-maintained 13-table list, used `len(pop_v3_rows)` for the physical confirmed-appeared table, and computed total files as a partial scan plus a fixed metadata increment.
Repair: `src/collection/release_manifest.py` inventories all regular release files after creation, reads physical Parquet metadata for rows and schema, computes file sizes and SHA-256, and verifies all entries. It excludes only the manifest's own hash to avoid circularity.
Corrected v3.1: 39 files, 38 checksummed files and 16 physical Parquet tables. All manifest checks and physical row counts pass.
Evidence: `release_v3_baseline_inventory.csv`, `release_file_integrity_audit.csv`, and `data/releases/fotmob_epl_2019_2025_v3_1/metadata/release_manifest.json`.
