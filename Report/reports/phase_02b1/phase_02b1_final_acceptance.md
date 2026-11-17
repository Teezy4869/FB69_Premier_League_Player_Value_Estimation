# Phase 2B.1 final acceptance

## 1. Executive Summary

CONDITIONAL_GO for the confirmed historical EPL appeared-player scope; all six seasons are CONDITIONAL_PASS.

## 2. Collection Scope

FotMob, EPL competition 47, seasons 2019/20–2024/25, Level 2+.

## 3. Data Collection Architecture

Immutable raw captures, SQLite manifest, versioned normalized tables, curated wide player-season table.

## 4. Actual Data Collected

{'players': 1757, 'teams': 120, 'seasons': 6, 'matches': 2281, 'player_seasons': 4052, 'player_team_seasons': 4135, 'player_match_appearances': 89392, 'historical_position_observations': 151475, 'metric_observations': 207043, 'player_season_metrics_wide': 4052}

## 5. Coverage by Season

{'2019/2020': 'CONDITIONAL_PASS', '2020/2021': 'CONDITIONAL_PASS', '2021/2022': 'CONDITIONAL_PASS', '2022/2023': 'CONDITIONAL_PASS', '2023/2024': 'CONDITIONAL_PASS', '2024/2025': 'CONDITIONAL_PASS'}

## 6. Historical Player Population

3,262 confirmed appeared player-seasons; 586 uncertain-only and 204 unused-only season listings. 1,757 unique profile IDs.

## 7. Statistics Availability

53 canonical metrics, 207,043 long observations; key_passes unsupported. See cross_season_feature_coverage.csv.

## 8. Player Profiles

1,757/1,757 unique discovered IDs have ID-verified profile captures; current club/position remain current-only.

## 9. Historical Team Membership

3,323 confirmed relations, 812 unresolved, 61 multi-club player-seasons.

## 10. Match Index

2,280 completed league matches; abandoned Bournemouth–Luton 4193691 excluded, replay 4421797 included.

## 11. Data Quality and Missingness

16,314 UNKNOWN substitute listings, 7,290 UNUSED_SUBSTITUTE listings. Null metric cells retain explicit status.

## 12. Historical Consistency

Historical club and position evidence are match-scoped; inferred exact-code positions remain marked as such.

## 13. Source Provenance

9373 raw references checksum verified; lineage paths preserved.

14 prior null playerStats attempts remain in raw storage but are excluded from accepted normalized lineage.

## 14. Data Integrity

23 referential/identity checks passed; 6 match and 6 metric raw rebuild samples passed.

## 15. Testing and Reproducibility

97 automated tests passed; exit code 0. See execution06_tests/test_execution.log.

## 16. Remaining Issues

- 16,314 substitute lineup entries have UNKNOWN participation; they are excluded from confirmed appearances.
- 575 comparable source metric conflicts are preserved in long observations; curated cells are null.
- key_passes has no supported source values; missing values are never zero-filled.
- Historical broad position groups are inferred exact-code mappings; current profile position is CURRENT_ONLY.
- playerMatches historical paging remains unverified after prior HTTP 400; matchDetails is the verified fallback.
- 12 legacy normalization/season acceptance gates remain PLANNED under the older absolute-participation contract.

## 17. Dataset Release Contents

`data/releases/fotmob_epl_2019_2025_v2/` with normalized, curated, metadata, quality_reports and manifests.

## 18. Final Acceptance Verdict

CONDITIONAL_GO: confirmed core records and reproducibility checks passed; unresolved participation and source conflicts prevent unconditional GO.

## 19. Handover Instructions

Use the release manifest and data dictionary; filter APPEARED and confirmed links for participation analysis; inspect s_ metric statuses before numeric use. Run the three reproduction commands in README.md. Do not interpret current profile club/position as historical.
