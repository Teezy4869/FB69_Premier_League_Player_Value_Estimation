# rs5 Dependency Inventory

Read from code, not file names. Arrows mean "is read by". `[S]` means the artifact carries a season key. IDs refer to `ARTIFACT_INVENTORY.csv`.

## Historical chain (kept frozen)

| Consumer (script) | Reads | Writes |
|---|---|---|
| `src/phase3/normalize_tm.py` | TM raw A20 | TM staging/curated A21, metadata A22 |
| `src/phase3/step3_qa_validate.py` | FotMob v3.1 `players`, `confirmed_appeared_player_seasons`, `player_team_seasons`, curated wide [S]; TM `stg_players`, `stg_transfers`, `stg_appearances`+`stg_games` (2019-2024) [S]; crosswalk v1 | `auto_match_validation_all_1299.csv` A25 |
| `src/phase3/step3_qa_adjudicate.py` | QA evidence | `automated_adjudications.csv` A25 |
| `src/phase3/entity_resolution.py` | FotMob `confirmed_appeared_player_seasons`, `players`, `player_team_seasons`, `matches`, `player_match_appearances`, `historical_position_observations`, `teams` [S]; TM `tm_players`, `tm_player_club_seasons` (2019-2024) [S], `tm_transfers`, `stg_games` and `stg_appearances` (2019-2024) [S]; adjudications | crosswalk A23, candidates/team map/unresolved A24, review files A26 |
| `src/phase3/season_targets.py` | `configs/phase_03_seasons.yaml`; crosswalk A23; `tm_valuation_history` A21; validation labels A25; FotMob `confirmed_appeared_player_seasons`, `matches`, `player_match_appearances` [S] | target A30, A31 |
| `src/phase3/step4_1_audit.py`, `step4_1_followups.py` | target A30; crosswalk; FotMob tables; raw matchDetails; raw TM valuations | flags and temporal parquet A32 |
| `src/phase3/integrate.py` | FotMob curated and normalized [S]; crosswalk; target; A32 | integrated v1 A40 |
| `src/phase3/validate_integration.py`, `feature_window_audit.py`, `multi_club_audit.py` | A40; FotMob raw | step_05 reports A41 |

## rs5 chain (new; every step reads `configs/research_scope.yaml`)

| Step | rs5 consumer | Reads | Writes |
|---|---|---|---|
| 2A | `src/research_scope/build_fotmob_rs5.py` | FotMob v3.1 (hash-verified) | `data/releases/fotmob_epl_2020_2025_rs5_v1` |
| 2B | `src/research_scope/build_targets_rs5.py` | rs5 FotMob; TM `tm_valuation_history`; cutoff config via scope; crosswalk `matching_v2_1` (player-level, reused until Step 3 revalidates it); validation labels | `data/research_rs5/targets/target_rs5_v1__matching_v2_1` |
| 3A/B | `src/research_scope/entity_resolution_rs5.py` | rs5 FotMob; TM tables **filtered to scope seasons**; historical adjudications; historical crosswalk for comparison | `data/research_rs5/entity_resolution/matching_v2_1_rs5__reviews_none` |
| 3B' | rebuild of 2B if any in-scope mapping changed | 3A output | new target version |
| 3C | `src/research_scope/integrate_rs5.py` | rs5 FotMob; rs5 crosswalk; rs5 target; rs5 temporal evidence | `data/releases/fb69_player_season_integrated_rs5_v1` |
| 4 | `src/research_scope/audit_rs5.py` | rs5 release; FotMob raw matchDetails (in-scope seasons only) | `reports/research_scope_rs5/step_04` |
| 5 | `src/research_scope/reproduce_rs5.py` | all of the above | reproduction evidence |

## Ordering constraint

The prompts put target rebuild (Step 2) before identity revalidation (Step 3), but a target needs an identity. Step 2 therefore uses the **historical player-level mapping** for in-scope players. Step 3 revalidates it with in-scope evidence. **If any in-scope mapping changes, the target is rebuilt under a new version before integration**; if none changes, the Step 2 target is used as is, and that equality is a tested invariant.

## Downstream of each statistic

| Statistic | Produced by | Used by |
|---|---|---|
| Confirmed population (2,747) | FotMob rs5 | target, crosswalk universe, integration |
| Identity mapping | crosswalk rs5 | target, integration, identity sensitivity in Phase 4 |
| Target value/date/age | target rs5 | integration, temporal audit |
| Games and minutes after valuation | rs5 temporal evidence | temporal audit (not predictors) |
| Metric coverage per season | FotMob rs5 quality reports | feature reliability assessment |
