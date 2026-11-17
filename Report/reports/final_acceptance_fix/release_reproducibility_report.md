# Release reproducibility

Content comparison: independent staged build versus promoted release, 38 checksummed files; identical=True.
The comparison covers every non-manifest file. `created_at_utc` in `release_manifest.json` is run-specific; bit-for-bit identity of the manifest is not required. Physical Parquet and report bytes were compared by SHA-256.
Part 1 independently reprocessed 2,280 saved matchDetails captures and reproduced all 31 staging hashes on resume (`preservation_and_resume_verification.json`).
Metric source observations and reconciliation inputs are saved parent artifacts. Independent offline regeneration found 0 value/status differences across 4052 player-seasons, and exactly reproduced 575 conflict entries and 318 coverage rows (`metric_rebuild_verification.json`).
Parent release hash drift: 0 across 74 snapshotted v2/v3 files.
No network collection was performed. Evidence: `release_file_integrity_audit.csv`, `metadata/release_manifest.json`, Part 1 source audit and metric conflict report.
