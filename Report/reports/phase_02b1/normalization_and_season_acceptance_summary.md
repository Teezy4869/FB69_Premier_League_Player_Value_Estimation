# Phase 2B.1 Execution 05: normalization and season acceptance

Raw references audited: 9373; checksum verified: 9373; accepted tasks without valid evidence: 0.
Normalized table counts: {'players': 1757, 'teams': 120, 'seasons': 6, 'matches': 2281, 'player_seasons': 4052, 'player_team_seasons': 4135, 'player_match_appearances': 89392, 'historical_position_observations': 151475, 'metric_observations': 207043, 'player_season_metrics_wide': 4052}.
Unresolved comparable metric conflicts: 575; curated values are null for these keys.
Prior semantically rejected raw attempts: 14; all are retained but excluded from accepted normalized lineage.
Historical batch decisions: {'PASS': 240, 'STOP': 2, 'REVIEW': 4}; current manifest gaps: 12 local gates.
Season statuses: {'2019/2020': 'CONDITIONAL_PASS', '2020/2021': 'CONDITIONAL_PASS', '2021/2022': 'CONDITIONAL_PASS', '2022/2023': 'CONDITIONAL_PASS', '2023/2024': 'CONDITIONAL_PASS', '2024/2025': 'CONDITIONAL_PASS'}. Full test suite: 97 tests, exit 0.

The older local normalization/acceptance gates remain PLANNED because their original schema and absolute participation gate do not represent the documented UNKNOWN substitute state in the versioned Execution 04/05 contract. The independent season reports assign CONDITIONAL_PASS only to the confirmed appeared-player scope. They do not certify the unresolved substitute population.

Consolidation may proceed with conditional release metadata if the independent referential and reproduction audit passes.
