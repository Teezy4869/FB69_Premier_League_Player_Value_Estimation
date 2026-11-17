# Phase 2A Steps 01–02 — foundation and historical player reference

Scope: FotMob Premier League (league 47), 2019/20–2024/25. This is a bounded reference collection and sample design. It does not establish a full historical player population or execute later collection steps.

## Phase 1 evidence reviewed

The [Phase 1 audit](../phase_01/fotmob_data_availability_audit.md), [season availability](../phase_01/season_availability.csv), [endpoint catalog](../phase_01/fotmob_endpoint_catalog.json), [feature matrix](../phase_01/feature_availability_matrix.csv), [player coverage](../phase_01/player_coverage_report.csv), [quality ledger](../phase_01/data_quality_audit.csv), saved raw samples, `src/audit/client.py`, `src/audit/normalization.py` and tests were inspected. Phase 1 report and raw samples were not edited.

Phase 1 verified `leagues` with season strings; `leagueseasondeepstats` with numeric season IDs; `teams` for team overview; `playerData`, `playerStats` and `matchDetails` for bounded examples. `playerMatches` returned HTTP 400. Season IDs are 14022, 15382, 16390, 17664, 20720 and 23685 in chronological order. The reliable structures for this step are `leagues.details.selectedSeason`, `table[].data.table.all`, and `leagueseasondeepstats.currentSeasonId`, `currentStatName`, `statsData[]`. The collector validates the season/stat fields before indexing.

The two CRITICAL findings were current profile attributes used as historical values and later match data in old player profiles. Four HIGH findings were saves units, unknown player coverage, the 2023/24 abandoned/replayed fixture and failed player-match pagination. This step addresses historical team assignment by using season-scoped leaderboard team IDs, preserves unit-bearing raw JSON, and retains the coverage warning. The fixture and pagination issues remain for a later step.

## Collection foundation

`src/collection/foundation.py` wraps the existing `AuditClient` rather than duplicating its timeout, 0.7-second interval, one retry with exponential backoff, 3 MB response cap, 40-attempt run budget, JSON validation and structured request log. The pilot configuration is in `configs/pilot_config.yaml`. It allows only five named endpoints and the six fixed seasons. `execute --max-requests N` sets an additional bound of at most 12 HTTP attempts; `--dry-run` makes no requests. A repeated `discover` run made **0 HTTP attempts** and used **24 cache hits**.

Every successful pilot response is stored whole under `data/pilot/raw/` with a companion metadata JSON containing endpoint, parameters, league/competition, season string and ID, UTC collection time, HTTP status, content type, source URL/identifier, wire byte count and SHA-256 of the stored JSON. Cache reads verify this hash and fail visibly on corruption. Writes use temporary files and atomic replacement. Failed requests remain in `logs/phase_02a_requests.jsonl` and appear in the command summary; they are not silently represented as data. No credentials are configured or logged. Completed cache entries support resume and idempotent reruns; an interrupted incomplete entry is detected and requires inspection before continuing.

The bounded run made **26 successful HTTP attempts**: six league responses, 18 season/stat responses (minutes, goals, saves for each season), and two historical-team-roster probes. No player-profile, match-detail or full match-participation crawl was performed. The 26 saved payloads and metadata pairs total approximately 8.26 MB. All six league tables had 20 clubs. The normalized reference copy is in `data/pilot/normalized/player_reference_index.csv`.

## Historical player reference results

| Season | Numeric ID | Unique player IDs | Player–team–season rows | Teams represented | Multi-team IDs in three boards |
|---|---:|---:|---:|---:|---:|
| 2019/20 | 14022 | 515 | 515 | 20 | 0 |
| 2020/21 | 15382 | 524 | 524 | 20 | 0 |
| 2021/22 | 16390 | 537 | 537 | 20 | 0 |
| 2022/23 | 17664 | 554 | 554 | 20 | 0 |
| 2023/24 | 20720 | 570 | 570 | 20 | 0 |
| 2024/25 | 23685 | 562 | 562 | 20 | 0 |

The [reference index](player_reference_index.csv) contains **3,262** season-scoped player/team rows. It keys by player ID, team ID and numeric season ID, so a verified multi-club case can occupy multiple rows; none was observed in these three tables. Names and numeric position codes are retained from the historical leaderboard. Team names are joined only to the corresponding historical league standings. The `position` column is a source code; the broad groups in the sample are conservative inferences, not verified FotMob role labels. **644** reference rows have codes outside the conservative sampling bands; their source codes remain intact.

The [coverage report](reference_coverage_report.csv) separates unique players from player-team-season rows and board counts. Its goals/saves percentages use the **observed three-board union** as denominator only. `population_denominator=UNKNOWN` and `population_coverage_percent` is blank for every season. The `mins_played` board happens to equal that observed union in each season; this does not establish a complete season population, including unused squad members or all transfer stints.

Historical squad investigation found that `teams?id=8650&season=2019/2020` and `teams?id=8650&season=2024/2025` both returned a Liverpool `overview.season` and `details.latestSeason` of **2026/2027** and the same 30 member IDs (including the coach). These complete responses are preserved in `data/pilot/raw/`. The `season` query did not yield a historical roster in these checks, so current squads were excluded from the reference index. Phase 1 `matchDetails` showed selected lineup membership, but the saved excerpts and failed `playerMatches` pagination cannot independently enumerate all historical players. No independent denominator was found.

## Pilot sample and gate

The [sample manifest](pilot_sample_manifest.csv) has **120** player-season observations: 32 each in 2019/20, 2022/23 and 2024/25, and 8 each in the other seasons. It uses seed 6902, standing ranks 1/7/13/20 and bounded position/low-minute rules documented in the [sampling report](pilot_sampling_report.md). Seventeen selected players had fewer than 90 observed minutes. No unsupported transfer case was inserted. The sample is reproducible from the saved raw data and is representative only of the observed reference boards.

**Gate for Prompt 2: historical reference coverage remains unreliable as a complete population.** Before treating the foundation as ready for broader collection, establish a truly season-specific roster or independent match-participation denominator; validate position-code group mapping; and confirm transferred/multi-club player-team relationships. The 2023/24 abandoned match, `playerMatches` HTTP 400 and saves unit distinction also need explicit handling in their later collection steps. No percentage of total player coverage is claimed here.

## Reproduction and checks

Run from the repository root:

```powershell
python -m src.collection.pilot_runner discover --dry-run
python -m src.collection.pilot_runner discover
python -m src.collection.pilot_runner sample
python -m src.collection.pilot_runner execute --max-requests 12 --dry-run
python -m unittest discover -s tests -v
```

The executed test command passed **18/18** tests (14 existing and four new). A second `discover` completed entirely from cache. The `execute` mode was dry-run only; Steps 03–08 were not started.
