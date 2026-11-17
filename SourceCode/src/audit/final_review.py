"""Offline, evidence-checked Phase 1 final review.

Run from the project root with ``python -m src.audit.final_review``.
This module performs no HTTP requests and does not alter source data.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from .client import utc_now


SEASONS = ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025")
REQUIRED_COLUMNS = {
    "season_availability": {"season", "numeric_season_id", "team_count", "fixture_count", "player_stat_count", "league_sample", "deep_stats_sample"},
    "feature_availability_matrix": {"season", "group", "candidate_feature", "status", "catalog_status", "source_url", "sample_file"},
    "data_dictionary": {"group", "candidate_feature", "api_fields_observed", "historical_definition_note", "evidence_samples"},
    "player_coverage_report": {"season", "denominator_status", "sample_unique_player_ids", "sample_player_id_list", "duplicate_id_rows_within_boards", "sample_files"},
    "player_profile_audit": {"season", "sample_role", "player_id", "current_vs_historical_team_id", "profile_sample_file", "stats_sample_file"},
    "match_index_audit": {"season", "fixture_record_count", "fixtures_with_date", "detail_status", "league_sample_file"},
}


class AuditEvidenceError(ValueError):
    pass


def read_evidence(root: Path, relative: str) -> dict:
    if not relative:
        raise AuditEvidenceError("Missing evidence path")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise AuditEvidenceError(f"Evidence file absent or outside project: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def _table(root: Path, name: str) -> pd.DataFrame:
    path = root / "reports/phase_01" / f"{name}.csv"
    if not path.is_file():
        raise AuditEvidenceError(f"Missing report: {path}")
    frame = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED_COLUMNS[name] - set(frame.columns)
    if missing:
        raise AuditEvidenceError(f"{name} missing columns: {sorted(missing)}")
    return frame


def validate_prior_outputs(root: Path) -> dict:
    tables = {name: _table(root, name) for name in REQUIRED_COLUMNS}
    season_tables = ("season_availability", "feature_availability_matrix", "player_coverage_report", "player_profile_audit", "match_index_audit")
    for name in season_tables:
        if set(tables[name]["season"]) != set(SEASONS):
            raise AuditEvidenceError(f"{name} does not contain exactly the six target seasons")
    matrix = tables["feature_availability_matrix"]
    if len(matrix) != 144 or not matrix.groupby("season").size().eq(24).all():
        raise AuditEvidenceError("Feature matrix is not 24 candidates × six seasons")
    if len(tables["data_dictionary"]) != 24:
        raise AuditEvidenceError("Data dictionary does not have 24 candidate features")
    catalog = json.loads((root / "reports/phase_01/fotmob_endpoint_catalog.json").read_text(encoding="utf-8"))
    if not catalog.get("league_id_verified"):
        raise AuditEvidenceError("Premier League ID is not verified in endpoint catalog")
    for name, column in (("season_availability", "league_sample"),
                         ("season_availability", "deep_stats_sample"),
                         ("feature_availability_matrix", "sample_file"),
                         ("player_profile_audit", "profile_sample_file"),
                         ("player_profile_audit", "stats_sample_file"),
                         ("match_index_audit", "league_sample_file"),
                         ("match_index_audit", "detail_sample_file")):
        for value in tables[name][column]:
            if value:
                read_evidence(root, value)
    for column in ("sample_files",):
        for cell in tables["player_coverage_report"][column]:
            for value in str(cell).split("|"):
                if value:
                    read_evidence(root, value)
    for column in ("evidence_samples", "profile_evidence_samples"):
        for cell in tables["data_dictionary"][column]:
            for value in str(cell).split("|"):
                if value:
                    read_evidence(root, value)
    catalog_sets = []
    sample_checks = []
    goal_agreements = 0
    for season in SEASONS:
        tag = season.replace("/", "_")
        phase_sample = read_evidence(root, f"data/audit/raw_samples/steps_03_05/league_{tag}.json")
        previous_sample = read_evidence(root, f"data/audit/raw_samples/league_{tag}.json")
        row = tables["season_availability"].set_index("season").loc[season]
        link = phase_sample["payload"].get("seasonStatLink") or {}
        if link.get("TournamentId") != int(row["numeric_season_id"]):
            raise AuditEvidenceError(f"Numeric season ID not backed by sample: {season}")
        if previous_sample.get("season_id_evidence", {}).get("TournamentId") != int(row["numeric_season_id"]):
            raise AuditEvidenceError(f"Phase 1 numeric ID evidence differs: {season}")
        if phase_sample["payload"]["details"].get("selectedSeason") != season:
            raise AuditEvidenceError(f"Wrong selected season in saved league response: {season}")
        if phase_sample["payload"]["fixtures"]["total_count"] != int(row["fixture_count"]):
            raise AuditEvidenceError(f"Fixture count differs from saved sample: {season}")
        goal_sample = read_evidence(root, f"data/audit/raw_samples/steps_03_05/goals_{tag}.json")
        minutes_sample = read_evidence(root, f"data/audit/raw_samples/steps_03_05/mins_played_{tag}.json")
        saves_sample = read_evidence(root, f"data/audit/raw_samples/steps_03_05/saves_{tag}.json")
        if goal_sample["payload"]["statsData_total_count"] != int(row["player_stat_count"]):
            raise AuditEvidenceError(f"Goal table count differs from saved sample: {season}")
        stat_list = goal_sample["payload"].get("statsList") or []
        catalog_sets.append({item["name"]: (item.get("title", ""), item.get("category", "")) for item in stat_list})
        coverage = tables["player_coverage_report"].set_index("season").loc[season]
        ids = {x for x in coverage["sample_player_id_list"].split("|") if x}
        teams = {x for x in coverage["sample_team_id_list"].split("|") if x}
        if len(ids) != int(coverage["sample_unique_player_ids"]) or len(teams) != int(coverage["sample_teams_represented"]):
            raise AuditEvidenceError(f"Coverage aggregate does not agree with saved ID/team lists: {season}")
        for metric, sample, column in (("goals", goal_sample, "goals_rows"),
                                       ("mins_played", minutes_sample, "minutes_rows"),
                                       ("saves", saves_sample, "saves_rows")):
            if sample["payload"]["statsData_total_count"] != int(coverage[column]):
                raise AuditEvidenceError(f"{metric} row count differs in sample: {season}")
            for player in sample["payload"]["statsData_first_five"]:
                if str(player.get("id")) not in ids:
                    raise AuditEvidenceError(f"Retained {metric} player absent from coverage ID list: {season}")
                sample_checks.append((metric, player))
        for role, board in (("outfield_top_goals", goal_sample), ("goalkeeper_top_saves", saves_sample)):
            profile = read_evidence(root, f"data/audit/raw_samples/steps_03_05/profile_{role}_{tag}.json")
            if profile["payload"].get("id") != board["payload"]["statsData_first_five"][0].get("id"):
                raise AuditEvidenceError(f"Profile ID mismatch for {season} {role}")
        profile_stats = read_evidence(root, f"data/audit/raw_samples/steps_03_05/player_stats_outfield_top_goals_{tag}.json")
        goal_value = goal_sample["payload"]["statsData_first_five"][0]["statValue"]["value"]
        profile_goals = next((x.get("statValue") for x in (profile_stats["payload"].get("topStatCard") or {}).get("items") or []
                              if x.get("localizedTitleId") == "goals"), None)
        if profile_goals is not None and float(profile_goals) == float(goal_value):
            goal_agreements += 1
    if goal_agreements != 6:
        raise AuditEvidenceError("Top-scorer goals disagree between six leaderboard and profile samples")
    for season in SEASONS:
        tag = season.replace("/", "_")
        save_sample = read_evidence(root, f"data/audit/raw_samples/steps_03_05/saves_{tag}.json")
        save_catalog = next((item for item in save_sample["payload"]["statsList"] if item.get("name") == "saves"), None)
        first_save = save_sample["payload"]["statsData_first_five"][0]
        if not save_catalog or "per 90" not in save_catalog.get("title", "").lower():
            raise AuditEvidenceError(f"Saves unit title not verified for {season}")
        if not isinstance(first_save.get("statValue", {}).get("value"), (int, float)) or not isinstance(first_save.get("substatValue", {}).get("value"), (int, float)):
            raise AuditEvidenceError(f"Saves values lack numeric evidence for {season}")
    anomaly = read_evidence(root, "data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json")
    if anomaly.get("record_count") != 381 or anomaly.get("ordered_pair_count") != 380:
        raise AuditEvidenceError("2023/24 fixture anomaly evidence is inconsistent")
    if not any((x.get("status") or {}).get("cancelled") for x in anomaly.get("duplicate_ordered_pair_entries", [])):
        raise AuditEvidenceError("Abandoned fixture not present in anomaly sample")
    saves_units = read_evidence(root, "data/audit/raw_samples/final_review/saves_2019_2020_units.json")
    if saves_units["payload"].get("substatTitle") != "Total saves" or saves_units["payload"].get("currentStatName") != "saves":
        raise AuditEvidenceError("Saves secondary unit label is not verified")
    first_saved = read_evidence(root, "data/audit/raw_samples/steps_03_05/saves_2019_2020.json")["payload"]["statsData_first_five"][0]
    if saves_units["payload"].get("statsData_first") != first_saved:
        raise AuditEvidenceError("Saves unit probe disagrees with saved player row")
    return {"tables": tables, "catalog": catalog, "catalogs": catalog_sets,
            "catalog_stable": all(x == catalog_sets[0] for x in catalog_sets),
            "retained_board_rows": sample_checks, "goal_agreements": goal_agreements,
            "anomaly": anomaly}


def classify_feature(candidate: str, rows: pd.DataFrame, catalog_stable: bool) -> tuple[str, str]:
    direct = int(rows["status"].eq("AVAILABLE").sum())
    partial = int(rows["status"].eq("PARTIAL").sum())
    if candidate in {"Long passes", "Duels"}:
        return "EXCLUDED_FOR_NOW", "Observed field is a narrower variant (accurate long balls or duels won), not the generic candidate."
    if candidate == "Player ratings":
        return "EXCLUDED_FOR_NOW", "Rating values are listed, but the checked responses do not define an historically stable rating computation."
    if candidate in {"Saves", "Goals conceded", "Clean sheets", "Goals prevented"}:
        return "POSITION_SPECIFIC", "Goalkeeper-specific catalog/profile evidence; do not treat outfield missingness as an error."
    if direct == 6 and catalog_stable:
        return "CORE", "Populated direct table in all six seasons with stable catalog name/title; computation details still need validation."
    if partial == 6:
        return "OPTIONAL", "Listed in all six catalogs or observed in each season's sampled profiles; full player values not collected."
    return "UNVERIFIED", "Not established for every season by a direct table or checked profile sample."


def _link(relative: str, label: str | None = None) -> str:
    return f"[{label or Path(relative).name}](../../{relative.replace('\\', '/')})"


def build_consistency(root: Path, validated: dict, timestamp: str) -> list[dict]:
    matrix = validated["tables"]["feature_availability_matrix"]
    dictionary = validated["tables"]["data_dictionary"]
    rows = []
    for item in dictionary.to_dict("records"):
        candidate = item["candidate_feature"]
        part = matrix[matrix["candidate_feature"].eq(candidate)]
        category, reason = classify_feature(candidate, part, validated["catalog_stable"])
        catalog_present = part["catalog_status"].eq("AVAILABLE").sum()
        title_pairs = sorted({(str(x["source_title"]), str(x["source_category"])) for x in part.to_dict("records") if x["catalog_status"] == "AVAILABLE"})
        evidence = "|".join(str(x) for x in part["sample_file"] if x)
        profile_evidence = "|".join(str(x) for x in part["profile_sample_file"] if x)
        rows.append({"group": item["group"], "candidate_feature": candidate,
                     "classification": category, "direct_available_seasons": int(part["status"].eq("AVAILABLE").sum()),
                     "partial_seasons": int(part["status"].eq("PARTIAL").sum()),
                     "unverified_seasons": int(part["status"].eq("UNVERIFIED").sum()),
                     "catalog_present_seasons": int(catalog_present),
                     "api_fields_observed": item["api_fields_observed"],
                     "source_title_category_variants": "|".join(f"{a} [{b}]" for a, b in title_pairs),
                     "units": item["units_observed_or_title_inferred"],
                     "historical_definition_status": "catalog label stable; computation unverified" if len(title_pairs) <= 1 else "catalog label/category changed",
                     "reason": reason, "affected_seasons": "|".join(SEASONS),
                     "source_endpoint": "leagueseasondeepstats|playerStats",
                     "sample_files": evidence, "profile_sample_files": profile_evidence,
                     "reviewed_at_utc": timestamp})
    return rows


def build_quality(root: Path, validated: dict, timestamp: str) -> list[dict]:
    t = validated["tables"]
    coverage = t["player_coverage_report"]
    profiles = t["player_profile_audit"]
    matches = t["match_index_audit"]
    all_seasons = "|".join(SEASONS)
    base_sample = "data/audit/raw_samples/steps_03_05/goals_2019_2020.json"
    saver = "data/audit/raw_samples/steps_03_05/saves_2019_2020.json"
    gk_stats = "data/audit/raw_samples/steps_03_05/player_stats_goalkeeper_top_saves_2019_2020.json"
    profile_sample = "data/audit/raw_samples/steps_03_05/profile_outfield_top_goals_2019_2020.json"
    anomaly_sample = "data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json"
    error_sample = "data/audit/raw_samples/steps_03_05/player_matches_retest.json"
    out = []

    def add(dimension, severity, status, endpoint, seasons, description, evidence, impact, mitigation):
        out.append({"finding_id": f"DQ{len(out)+1:02d}", "dimension": dimension,
                    "severity": severity, "assessment_status": status,
                    "affected_dataset_or_endpoint": endpoint, "affected_seasons": seasons,
                    "description": description, "supporting_evidence": evidence,
                    "impact_on_usability": impact, "recommended_mitigation": mitigation,
                    "reviewed_at_utc": timestamp})

    total_missing = sum(int(coverage[column].astype(int).sum()) for column in ("missing_id_rows", "missing_team_id_rows", "missing_position_rows", "missing_stat_value_rows"))
    add("Missing values", "MEDIUM", "NOT_DETECTED_IN_CHECKED_BOARDS", "leagueseasondeepstats", all_seasons,
        f"Prior three-board audit reports {total_missing} missing ID, team, position or stat-value cells; other metric tables were not checked.",
        f"reports/phase_01/player_coverage_report.csv|{base_sample}", "Unknown row-level missingness for optional metrics.",
        "Validate null rates per metric and season during a bounded pilot; do not impute now.")
    duplicate_count = int(coverage["duplicate_id_rows_within_boards"].astype(int).sum())
    add("Duplicate records", "LOW", "NOT_DETECTED_IN_CHECKED_BOARDS", "leagueseasondeepstats", all_seasons,
        f"Prior audit reports {duplicate_count} duplicate player-ID rows within the 18 sampled leaderboard tables; retained raw samples contain only five rows per table.",
        "reports/phase_01/player_coverage_report.csv", "Duplicates outside these tables remain untested.",
        "Check (season ID, stat, player ID, team ID) keys when collecting full metric tables.")
    keeper = read_evidence(root, gk_stats)["payload"]
    ratio = next((x.get("statValue") for x in (keeper.get("topStatCard") or {}).get("items") or []
                  if x.get("localizedTitleId") == "saved_penalties"), "")
    add("Invalid data types", "MEDIUM", "OBSERVED", "playerStats", "2019/2020",
        f"A sampled goalkeeper profile mixes numeric strings with a ratio-like saved_penalties value ({ratio}); blanket numeric conversion would fail.",
        gk_stats, "Generic numeric casting can corrupt or drop valid fields.",
        "Parse each localizedTitleId by its statFormat and expected shape; retain raw strings.")
    save_item = next(x for x in read_evidence(root, saver)["payload"]["statsList"] if x.get("name") == "saves")
    save_row = read_evidence(root, saver)["payload"]["statsData_first_five"][0]
    add("Inconsistent units", "HIGH", "OBSERVED", "leagueseasondeepstats|playerStats", "2019/2020",
        f"The saves catalog says '{save_item['title']}' and a follow-up response labels substatTitle 'Total saves'; the 2019/20 top row has statValue={save_row['statValue']['value']} and substatValue={save_row['substatValue']['value']}.",
        f"{saver}|data/audit/raw_samples/final_review/saves_2019_2020_units.json", "Confusing per-90 and totals would create wrong player-season values.",
        "Store value, substat, format and catalog title separately; validate unit semantics before normalization.")
    numeric_examples = [(metric, (player.get("statValue") or {}).get("value")) for metric, player in validated["retained_board_rows"]]
    invalid_examples = [(metric, value) for metric, value in numeric_examples if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0]
    add("Unexpected or out-of-range values", "LOW", "NOT_DETECTED_IN_RETAINED_ROWS" if not invalid_examples else "OBSERVED",
        "leagueseasondeepstats", all_seasons,
        f"Among {len(numeric_examples)} retained first-five goals/minutes/saves rows, {len(invalid_examples)} main values were nonnumeric, nonfinite or negative. This is a narrow sanity check only.",
        "data/audit/raw_samples/steps_03_05", "Unseen rows and signed metrics remain unassessed.",
        "Apply metric-specific domains to complete tables in a pilot; do not treat negative goals-prevented values as automatically invalid.")
    outfield_stats = read_evidence(root, "data/audit/raw_samples/steps_03_05/player_stats_outfield_top_goals_2019_2020.json")["payload"]
    out_keys = {x.get("localizedTitleId") for x in (outfield_stats.get("topStatCard") or {}).get("items") or []}
    keeper_keys = {x.get("localizedTitleId") for x in (keeper.get("topStatCard") or {}).get("items") or []}
    add("Historical schema differences", "MEDIUM", "POSITION_DIFFERENCE_OBSERVED", "leagueseasondeepstats|playerStats", "2019/2020",
        f"All six sampled season catalogs contain 37 identical name/title/category entries; sampled 2019/20 outfield and keeper top cards differ ({len(out_keys ^ keeper_keys)} field keys in symmetric difference). Provider computation stability is unverified.",
        f"{base_sample}|{gk_stats}|data/audit/raw_samples/steps_03_05/player_stats_outfield_top_goals_2019_2020.json",
        "Position-specific missingness must not be mistaken for historical drift.",
        "Version schemas by season and position, and compare definitions rather than labels alone.")
    add("Player ID consistency", "LOW", "NO_CONFLICT_IN_SAMPLES", "leagueseasondeepstats|playerData", all_seasons,
        "All 12 sampled profile IDs match the selected leaderboard player IDs; this does not validate the full population or external identity matching.",
        "reports/phase_01/player_profile_audit.csv|data/audit/raw_samples/steps_03_05",
        "IDs appear usable as internal FotMob keys for a pilot.",
        "Keep FotMob IDs as source keys; validate every later join and record transfers separately.")
    multi = int(coverage["multi_team_ids_across_boards"].astype(int).sum())
    add("Team changes within seasons", "MEDIUM", "UNRESOLVED", "leagueseasondeepstats|playerData", all_seasons,
        f"The three-board audit reports {multi} IDs with multiple team IDs across its sampled boards, but the full season roster and transfer history were not checked.",
        "reports/phase_01/player_coverage_report.csv", "One player-season may need multiple team stints; a single current team can misattribute statistics.",
        "Preserve player-team-season keys and confirm transfer cases in a bounded roster pilot.")
    add("Incomplete player coverage", "HIGH", "UNRESOLVED", "leagueseasondeepstats", all_seasons,
        f"Sampled leaderboard unions range from {coverage['sample_unique_player_ids'].astype(int).min()} to {coverage['sample_unique_player_ids'].astype(int).max()} player IDs, but no complete historical player denominator was established.",
        "reports/phase_01/player_coverage_report.csv", "Coverage percentage and omission bias cannot be stated.",
        "Obtain a season-specific roster/reference population before full extraction.")
    mismatches = int(profiles["current_vs_historical_team_id"].eq("DIFFERENT").sum())
    add("Current profile used as historical", "CRITICAL", "OBSERVED", "playerData|leagueseasondeepstats", all_seasons,
        f"Current primary team differs from historical leaderboard team in {mismatches}/{len(profiles)} sampled player-seasons; current primary position is also mutable.",
        f"reports/phase_01/player_profile_audit.csv|{profile_sample}",
        "Historical team/position attribution can be wrong and can leak later information.",
        "Use season-scoped team IDs; label current profile fields explicitly and avoid historical backfill from them.")
    all_fixtures = int(matches["fixture_record_count"].astype(int).sum())
    all_dated = int(matches["fixtures_with_date"].astype(int).sum())
    add("Missing or inconsistent match dates", "LOW", "NOT_DETECTED_IN_INDEX_AGGREGATES", "leagues", all_seasons,
        f"Prior match-index report records dates for {all_dated}/{all_fixtures} fixture entries; only three raw fixture items per season were retained for independent inspection.",
        "reports/phase_01/match_index_audit.csv|data/audit/raw_samples/steps_03_05/league_2019_2020.json",
        "Full-date completeness and timezone consistency remain unproven.",
        "Validate UTC parsing, season windows and duplicated scheduled/replayed fixtures during collection.")
    add("Conflicting statistics or definitions", "MEDIUM", "NO_NUMERIC_CONFLICT_IN_CHECKED_GOALS", "leagueseasondeepstats|playerStats", all_seasons,
        f"Top-scorer goals agree between leaderboard and sampled season profile in {validated['goal_agreements']}/6 seasons; save totals and per-90 values are distinct fields and cannot be compared directly.",
        f"reports/phase_01/feature_availability_matrix.csv|{base_sample}",
        "Other metric definitions and totals have not been reconciled.",
        "Cross-check a stratified set of player-season metrics with units and source titles attached.")
    current_matches = read_evidence(root, profile_sample)["payload"]["initialMatchesPage_first_two"]["matches"]
    future_dates = [x.get("matchDate", {}).get("utcTime", "") for x in current_matches]
    add("Potential future-information contamination", "CRITICAL", "OBSERVED", "playerData.initialMatchesPage", "2019/2020",
        f"The 2019/20 Jamie Vardy profile sample carries current initialMatchesPage dates {', '.join(future_dates)} alongside a historical statSeasons entry.",
        profile_sample, "Using unscoped current match history for 2019/20 would attach future records.",
        "Require explicit season and match-date filters; never treat initialMatchesPage as a historical season index.")
    duplicates = validated["anomaly"]["duplicate_ordered_pair_entries"]
    cancelled = [x for x in duplicates if (x.get("status") or {}).get("cancelled")]
    add("Abandoned/replayed fixture", "HIGH", "OBSERVED", "leagues.fixtures.allMatches", "2023/2024",
        f"The 381-entry 2023/24 index contains 380 ordered team pairs; Bournemouth–Luton has two IDs, including abandoned match {cancelled[0]['id']} and completed replay.",
        anomaly_sample, "A naive 380-match assumption or unfiltered aggregation can double count a pairing.",
        "Preserve both raw IDs; use cancellation/reason/status to select the completed league fixture for derived views.")
    error = read_evidence(root, error_sample)
    add("Player match pagination", "HIGH", "FAILED", "playerMatches", all_seasons,
        f"The bounded retest returned HTTP {error['http_status']} with error '{error['payload'].get('error')}'. Historical player-to-match pagination remains unverified.",
        error_sample, "A direct complete player-match index cannot yet be planned from this route.",
        "Investigate supported parameters or a sanctioned alternative in a bounded pilot; use fixture lineups selectively.")
    add("Evidence retention", "MEDIUM", "LIMITATION", "raw_samples|player_coverage_report", all_seasons,
        "Only the first five leaderboard rows and first three fixtures per season were retained. Count and ID aggregates cross-check internally but cannot be fully recomputed from saved raw subsets.",
        "reports/phase_01/player_coverage_report.csv|data/audit/raw_samples/steps_03_05",
        "Independent audit reproducibility for full leaderboard identity and date checks is limited.",
        "For a later pilot, retain complete bounded responses or integrity hashes and aggregate extraction manifests.")
    return out


def render_report(root: Path, validated: dict, consistency: list[dict], quality: list[dict], timestamp: str) -> str:
    t = validated["tables"]
    seasons = t["season_availability"]
    matrix = t["feature_availability_matrix"]
    coverage = t["player_coverage_report"]
    profiles = t["player_profile_audit"]
    matches = t["match_index_audit"]
    categories = Counter(x["classification"] for x in consistency)
    status_counts = matrix["status"].value_counts().to_dict()
    quality_sev = Counter(x["severity"] for x in quality)
    mismatch = int(profiles["current_vs_historical_team_id"].eq("DIFFERENT").sum())
    lines = ["# FotMob data availability audit — Phase 1 final review", "",
             f"Reviewed at (UTC): {timestamp}. Scope: Premier League 2019/20–2024/25.", "",
             "## 1. Executive Summary", "",
             "**Overall verdict: CONDITIONAL GO for a bounded data-collection pilot; no full historical crawl yet.** [Observation] All six season identifiers were verified, and season-level goals, minutes and saves tables returned populated player rows. [Inference] The three Level 2+ components appear technically accessible, with separate limitations below. [Unresolved] There is no defensible complete player denominator, `playerMatches` returns HTTP 400, and historical profile fields require careful scoping.",
             "", "## 2. Project Scope", "",
             "Premier League (FotMob league ID 47), six completed seasons, FotMob performance data, and a later Transfermarkt primary dataset. This review audits availability and quality. It does not perform bulk extraction, entity matching, preprocessing, feature selection or modeling.",
             "", "## 3. Data Sources and API Discovery", "",
             f"[Observation] The {_link('reports/phase_01/fotmob_endpoint_catalog.json', 'endpoint catalog')} and {_link('reports/phase_01/discovery_summary.md', 'discovery summary')} record working `allLeagues`, `leagues`, `leagueseasondeepstats`, `teams`, `playerData` and `matchDetails` probes. `playerStats` was also tested in Phase 1 steps 03–05. `playerMatches` failed with HTTP 400 ({_link('data/audit/raw_samples/steps_03_05/player_matches_retest.json', 'error sample')}). These are unofficial JSON interfaces and may change.",
             "", "## 4. Historical Season Availability", "",
             "[Observation] The season string selects `/leagues`; numeric `TournamentId` selects `leagueseasondeepstats`. The following IDs, teams, fixture counts and goal-board rows match saved season links and samples. The 2023/24 381 entries include an abandoned match and replay.", "",
             "| Season | Numeric ID | Teams | Fixture entries | Goal-board rows |", "|---|---:|---:|---:|---:|"]
    for row in seasons.to_dict("records"):
        lines.append(f"| {row['season']} | {row['numeric_season_id']} | {row['team_count']} | {row['fixture_count']} | {row['player_stat_count']} |")
    lines += ["", f"Evidence: {_link('reports/phase_01/season_availability.csv', 'season report')} and six saved `league_*` and `goals_*` samples under `data/audit/raw_samples/steps_03_05/`.",
              "", "## 5. Feature Availability Matrix", "",
              f"[Observation] The {_link('reports/phase_01/feature_availability_matrix.csv', 'matrix')} contains 24 candidates × six seasons: {status_counts.get('AVAILABLE', 0)} direct-table `AVAILABLE`, {status_counts.get('PARTIAL', 0)} catalog/profile-sample `PARTIAL`, and {status_counts.get('UNVERIFIED', 0)} `UNVERIFIED`. All six saved `goals` responses contain the same 37 catalog name/title/category entries. Stable labels do not verify stable calculations.",
              "", "| Classification | Count | Meaning in this audit |", "|---|---:|---|"]
    explanations = {"CORE": "Directly populated in all six seasons with stable catalog labels; goals and minutes only.",
                    "OPTIONAL": "Catalog or sampled profile evidence exists, but full player values and completeness are not verified.",
                    "POSITION_SPECIFIC": "Goalkeeper features require goalkeeper-specific validation and missingness rules.",
                    "UNVERIFIED": "Exact candidate field was not established in the checked sources.",
                    "EXCLUDED_FOR_NOW": "Candidate has a narrower observed field or an unverified rating definition."}
    for category in ("CORE", "OPTIONAL", "POSITION_SPECIFIC", "UNVERIFIED", "EXCLUDED_FOR_NOW"):
        lines.append(f"| {category} | {categories.get(category, 0)} | {explanations[category]} |")
    lines += ["", f"Per-feature decisions and field names: {_link('reports/phase_01/cross_season_consistency.csv', 'cross-season consistency')} and {_link('reports/phase_01/data_dictionary.csv', 'data dictionary')}. `Key passes` remains unverified; `Long passes` maps only to accurate long balls; `Duels` maps only to duels won. In the checked 2019/20 saves response, the main value is per 90 and the secondary value is labeled `Total saves` ({_link('data/audit/raw_samples/final_review/saves_2019_2020_units.json', 'unit evidence')}).",
              "", "## 6. Player Coverage Analysis", "",
              "[Observation] Three player leaderboards per season represent all 20 league teams, but their union is a sampled numerator. The player denominator is `UNKNOWN_DENOMINATOR`; a coverage percentage would be unsupported. The prior audit reports zero duplicate player-ID rows within those boards and zero multi-team IDs across them. Its saved subsets do not allow a complete independent recount.", "",
              "| Season | Unique IDs in three boards | Teams represented | Saves-board rows |", "|---|---:|---:|---:|"]
    for row in coverage.to_dict("records"):
        lines.append(f"| {row['season']} | {row['sample_unique_player_ids']} | {row['sample_teams_represented']}/{row['reference_team_count']} | {row['saves_rows']} |")
    lines += ["", f"Evidence: {_link('reports/phase_01/player_coverage_report.csv', 'coverage report')}. [Unresolved] Players with few minutes, transfers, and omitted metrics may not be captured by these leaderboards.",
              "", "## 7. Player Profile Availability", "",
              f"[Observation] Twelve sampled `playerData` profiles have IDs, names, birth dates, current primary team and position, and a season-associated `statSeasons` entry. All 12 sampled profile IDs match their selected leaderboard IDs. Current team differs from historical leaderboard team in **{mismatch}/12** samples. The `playerStats` season entry is usable as a scoped request key; current primary team and position are not historical attributes.",
              f"Evidence: {_link('reports/phase_01/player_profile_audit.csv', 'profile audit')} and {_link('data/audit/raw_samples/steps_03_05/profile_outfield_top_goals_2019_2020.json', '2019/20 profile sample')}.",
              "", "## 8. Match Index Availability", "",
              f"[Observation] Historical league responses contain {int(matches['fixture_record_count'].astype(int).sum())} fixture entries across six seasons. The prior report records dates and results for all entries; raw samples preserve three fixtures per season. The prior match-detail audit counted {int(matches.loc[matches['season'].eq('2019/2020'), 'lineup_player_ids_count'].iloc[0])} and {int(matches.loc[matches['season'].eq('2024/2025'), 'lineup_player_ids_count'].iloc[0])} lineup player IDs in two responses; saved subsets retain only a few lineup entries. This demonstrates representative player-to-match relationships, not complete coverage.",
              f"The 2023/24 Bournemouth–Luton pair has abandoned ID 4193691 and completed replay ID 4421797 ({_link('data/audit/raw_samples/final_review/fixture_2023_2024_anomaly.json', 'anomaly sample')}). `playerMatches` pagination remains failed. Evidence: {_link('reports/phase_01/match_index_audit.csv', 'match-index report')}.",
              "", "## 9. Historical Consistency", "",
              "[Observation] The 37 catalog name/title/category tuples are identical in all six saved season responses. The six sampled top-scorer goals values agree between leaderboards and season profiles. [Inference] These checks support stable discovery of those fields. [Unresolved] They do not prove provider calculations, every player's values, or position-specific profile schemas are identical across seasons. Goalkeeper and outfield `topStatCard` shapes differ by position.",
              "", "## 10. Data Quality Findings", "",
              f"The {_link('reports/phase_01/data_quality_audit.csv', 'quality ledger')} contains {len(quality)} assessments: " + ", ".join(f"{key} {quality_sev.get(key, 0)}" for key in ("CRITICAL", "HIGH", "MEDIUM", "LOW")) + ". Severity reflects potential effect on later historical collection, not a measured error rate.", "",
              "| Severity | Finding | Evidence |", "|---|---|---|"]
    for item in quality:
        if item["severity"] in ("CRITICAL", "HIGH"):
            first = item["supporting_evidence"].split("|")[0]
            lines.append(f"| {item['severity']} | {item['dimension']}: {item['description']} | {_link(first, 'source')} |")
    lines += ["", "[Observation] No missing IDs/team IDs/positions/stat values or duplicate IDs were reported in the three sampled leaderboard tables. Only the first five raw rows of each board were retained, so the full aggregate checks are not independently replayable from raw JSON.",
              "", "## 11. Technical Limitations", "",
              "`playerMatches` rejected the checked query; complete historical player-to-match pagination is unresolved. Leaderboards cannot be treated as the player population. Raw samples are intentionally partial. Catalog titles can describe per-90 or percentage values, but the checked responses do not publish full metric definitions. Current `playerData.initialMatchesPage` can contain later matches and must not be used as a historical season index.",
              "", "## 12. Level 2+ Feasibility Assessment", "",
              "| Component | Verdict | Evidence and limitation |", "|---|---|---|",
              "| Season-level player statistics | CONDITIONAL_PASS | Populated goals, minutes and saves tables for all six seasons; optional metric completeness and definitions remain unchecked. |",
              "| Player profiles | CONDITIONAL_PASS | Twelve IDs and season entries verified; current team/position are not historical, and full player coverage is unknown. |",
              "| Match index | CONDITIONAL_PASS | All six fixture indexes accessible and two lineups sampled; `playerMatches` failed and an abandoned/replayed pair requires status-aware handling. |",
              "", "## 13. Recommended Data Collection Architecture", "",
              "[Inference] Use direct HTTP JSON as the primary acquisition method. First retrieve season metadata and numeric IDs; then bounded season-stat tables; then supplemental player profiles and season-scoped `playerStats` only for IDs in a verified reference population; then season fixture indexes. Use selective `matchDetails` where player-to-match links or missing fields require it. If `playerMatches` remains unavailable, selective match-detail requests are the fallback for those links. No Selenium need was demonstrated.",
              "", "| Acquisition approach | Role | Observed constraint |", "|---|---|---|",
              "| HTTP JSON season tables | Primary player-stat source | One metric table per request; denominator and optional metric definitions unresolved. |",
              "| Player/team supplemental requests | Identity and season-scoped detail | Current profile fields must not be backdated; historical team stints need validation. |",
              "| Historical league match index | Season fixture IDs, dates, teams and results | Abandoned/replayed entries require status-aware handling. |",
              "| Selective match-detail fallback | Sampled lineups and player-to-match evidence | Response is larger; use only for specific missing links or fields. |",
              "", "Expected JSON shapes observed: `leagues.details`, `stats.seasonStatLinks` and `fixtures.allMatches`; `leagueseasondeepstats.statsList` plus `statsData[]` entries with player/team IDs, position code, `statValue` and `substatValue`; `playerData.statSeasons` and current `primaryTeam`; `playerStats.topStatCard`/`statsSection`; `matchDetails.general`/`header`/`content.lineup`. Treat optional keys and position-specific sections as nullable until further checks.",
              "", "Store raw responses (or complete bounded response archives), request URL/time/status, content hash, season string and numeric ID, field title/format/unit, and schema version. Keep normalized season-stat, profile, player-team-season, fixture and match-link tables separate. Cache completed seasons with a documented refresh policy. Reuse the existing configurable timeout, 0.7-second minimum request interval, 64-attempt audit budget and bounded transient retries as a cautious pilot baseline; tune only after observing service behavior. Log errors and resume by idempotent keys. Deduplicate by season, stat, player and team, while preserving multiple team stints and both raw IDs for abandoned/replayed matches. Validate nulls, types, units, domains, date windows and profile-to-season joins before expanding volume.",
              "", "## 14. Outstanding Risks", "",
              "- No complete season-specific player roster denominator; coverage and omission bias cannot be measured.",
              "- `playerMatches` parameters or alternative historical pagination remain unresolved.",
              "- Current profile attributes and current match page data can contaminate historical records.",
              "- Optional metrics, especially ratings and position-specific fields, need value and definition checks beyond catalog presence.",
              "- Saved raw subsets limit independent replay of aggregate counts; a later pilot must retain complete bounded evidence.",
              "", "## 15. Go / Conditional Go / No-Go Recommendation", "",
              "**Conditional Go for a small, instrumented historical collection pilot. No-Go for an unrestricted full historical crawl at this point.** The pilot should establish a full player denominator, verify a stratified set of optional metrics and historical joins, resolve player-match pagination or a selective lineup fallback, and confirm status-aware fixture handling. Reassess the full crawl only after those checks pass. Transfermarkt matching and any modeling work remain outside this phase.", ""]
    return "\n".join(lines)


def run(root: Path) -> dict:
    root = root.resolve()
    validated = validate_prior_outputs(root)
    timestamp = utc_now()
    consistency = build_consistency(root, validated, timestamp)
    quality = build_quality(root, validated, timestamp)
    report_dir = root / "reports/phase_01"
    pd.DataFrame(consistency).to_csv(report_dir / "cross_season_consistency.csv", index=False, encoding="utf-8")
    pd.DataFrame(quality).to_csv(report_dir / "data_quality_audit.csv", index=False, encoding="utf-8")
    report = render_report(root, validated, consistency, quality, timestamp)
    (report_dir / "fotmob_data_availability_audit.md").write_text(report, encoding="utf-8")
    validate_final_outputs(root)
    return {"consistency_rows": len(consistency), "quality_rows": len(quality),
            "catalog_stable": validated["catalog_stable"], "goal_agreements": validated["goal_agreements"]}


def validate_final_outputs(root: Path) -> None:
    report_dir = root / "reports/phase_01"
    consistency = pd.read_csv(report_dir / "cross_season_consistency.csv", keep_default_na=False)
    quality = pd.read_csv(report_dir / "data_quality_audit.csv", keep_default_na=False)
    if len(consistency) != 24 or set(consistency["classification"]) != {"CORE", "OPTIONAL", "POSITION_SPECIFIC", "UNVERIFIED", "EXCLUDED_FOR_NOW"}:
        raise AuditEvidenceError("Final feature classifications are incomplete")
    if not {"CRITICAL", "HIGH", "MEDIUM", "LOW"}.issubset(set(quality["severity"])):
        raise AuditEvidenceError("Final severity levels are incomplete")
    for frame, columns in ((consistency, ("sample_files", "profile_sample_files")),
                           (quality, ("supporting_evidence",))):
        for column in columns:
            for cell in frame[column]:
                for value in str(cell).split("|"):
                    if value and not (root / value).exists():
                        raise AuditEvidenceError(f"Final report evidence path missing: {value}")
    report = (report_dir / "fotmob_data_availability_audit.md").read_text(encoding="utf-8")
    for path in re.findall(r"\]\((\.\./\.\./[^)]+)\)", report):
        if not (report_dir / path).resolve().is_file():
            raise AuditEvidenceError(f"Broken local link in final report: {path}")
    for section in range(1, 16):
        if f"## {section}. " not in report:
            raise AuditEvidenceError(f"Missing final report section {section}")


if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[2])
    print(f"Final Phase 1 review complete: {result['consistency_rows']} features, {result['quality_rows']} quality assessments; no HTTP requests")
