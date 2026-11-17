# Original v3 versus corrected v3.1

Original v3: {'CONFIRMED_APPEARED': 3262, 'CONFIRMED_NON_APPEARED': 790}. Corrected v3.1: {'CONFIRMED_APPEARED': 3262, 'CONFIRMED_NON_APPEARED': 0, 'UNVERIFIED': 790}.
Appearance transitions: 23,604 `UNUSED_SUBSTITUTE` → `UNKNOWN`; 50,160 starters and 15,628 entering substitutes retain positive evidence. No unsupported confirmed non-appearance remains.
Metric observation source rows are copied unchanged from v3. Curated numeric metric values are retained; population labels, coverage calculations, metadata and reports are rebuilt.
2019/20 xA coverage remains 96/515 and xG 69/515. The corrected registry independently counts validated fallback and source-revised statuses at distinct player-season grain.
Original v3 manifest: 38 declared files, 13 declared Parquet. v3.1 manifest: 39 physical files, 16 Parquet.
Evidence: Part 1 transition audit, corrected population CSV, corrected coverage CSV, and both release manifests.
