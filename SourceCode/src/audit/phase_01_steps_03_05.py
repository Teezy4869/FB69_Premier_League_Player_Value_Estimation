"""Run Phase 1 steps 03–05: python -m src.audit.phase_01_steps_03_05."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .client import AuditClient, BudgetExceeded, utc_now
from .normalization import fixture_facts, leaderboard_rows, season_profile_entry, stat_catalog
from .player_coverage import coverage_row
from .profile_match_audit import match_row, profile_row
from .stats_availability import build_feature_reports


def _sample_payload(endpoint: str, payload: dict, season: str) -> dict:
    """Retain exact source objects, with lists sliced to a few representative items."""
    if endpoint == "leagues":
        stats = payload.get("stats") or {}
        return {"details": payload.get("details"),
                "seasonStatLink": next((x for x in stats.get("seasonStatLinks") or [] if x.get("Name") == season), None),
                "table": [{"data": {"table": {"all": ((section.get("data") or {}).get("table") or {}).get("all", [])[:3]}}}
                          for section in (payload.get("table") or [])[:1]],
                "fixtures": {"total_count": len((payload.get("fixtures") or {}).get("allMatches") or []),
                             "allMatches_first_three": ((payload.get("fixtures") or {}).get("allMatches") or [])[:3]}}
    if endpoint == "leagueseasondeepstats":
        return {"statsList": payload.get("statsList"), "currentSeasonId": payload.get("currentSeasonId"),
                "currentStatName": payload.get("currentStatName"),
                "statsData_total_count": len(leaderboard_rows(payload)), "statsData_first_five": leaderboard_rows(payload)[:5]}
    if endpoint == "playerData":
        selected = {key: payload.get(key) for key in ("id", "name", "birthDate", "primaryTeam", "positionDescription", "matchesUrl", "matchFilters")}
        selected["statSeasons_selected"] = [x for x in payload.get("statSeasons") or [] if x.get("seasonName") == season]
        selected["initialMatchesPage_first_two"] = {"matches": ((payload.get("initialMatchesPage") or {}).get("matches") or [])[:2],
                                                      "previous": (payload.get("initialMatchesPage") or {}).get("previous")}
        return selected
    if endpoint == "playerStats":
        return {"topStatCard": payload.get("topStatCard"), "statsSection": payload.get("statsSection"),
                "sectionOrder": payload.get("sectionOrder"),
                "shotmap_record_count": len(payload.get("shotmap") or [])}
    if endpoint == "matchDetails":
        lineup = ((payload.get("content") or {}).get("lineup") or {})
        return {"general": payload.get("general"), "header": payload.get("header"),
                "lineup": {side: {"id": (lineup.get(side) or {}).get("id"),
                                  "starters_first_five": ((lineup.get(side) or {}).get("starters") or [])[:5],
                                  "subs_first_two": ((lineup.get(side) or {}).get("subs") or [])[:2]}
                           for side in ("homeTeam", "awayTeam")}}
    return payload


def _write_sample(root: Path, name: str, endpoint: str, season: str, result: dict) -> str:
    directory = root / "data/audit/raw_samples/steps_03_05"
    directory.mkdir(parents=True, exist_ok=True)
    payload = result.get("payload")
    record = result["record"]
    sample = {"sample_kind": "source_subset" if payload is not None else "error_response",
              "endpoint": endpoint, "season": season,
              "source_url": record.get("source_url"), "collected_at_utc": record.get("timestamp_utc"),
              "http_status": record.get("http_status"), "response_bytes": record.get("response_bytes"),
              "payload": _sample_payload(endpoint, payload, season) if isinstance(payload, dict) else {"error": record.get("response_error") or record.get("error")}}
    path = directory / f"{name}.json"
    path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.relative_to(root).as_posix()


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")


def run(root: Path) -> dict:
    base = json.loads((root / "configs/fotmob_audit.json").read_text(encoding="utf-8"))
    phase = json.loads((root / "configs/phase_01_steps_03_05.json").read_text(encoding="utf-8"))
    config = {**base, **phase}
    previous = pd.read_csv(root / "reports/phase_01/season_availability.csv")
    previous_ids = {row.season: int(row.numeric_season_id) for row in previous.itertuples(index=False)
                    if row.overall_status == "AVAILABLE" and pd.notna(row.numeric_season_id)}
    report_dir = root / "reports/phase_01"
    client = AuditClient(config, root / "logs/fotmob_steps_03_05_requests.jsonl")
    cache = {}

    def probe(endpoint: str, params: dict, season: str, name: str) -> dict:
        key = (endpoint, tuple(sorted(params.items())))
        if key in cache:
            result = cache[key]
        else:
            try:
                result = client.get(endpoint, params)
            except BudgetExceeded as exc:
                result = {"record": {"timestamp_utc": utc_now(), "source_url": "",
                                     "outcome": "UNVERIFIED", "error": str(exc)}, "payload": None}
            cache[key] = result
        sample_file = _write_sample(root, name, endpoint, season, result)
        return {"payload": result["payload"], "evidence": {"source_url": result["record"].get("source_url", ""),
                "timestamp_utc": result["record"].get("timestamp_utc", ""),
                "http_status": result["record"].get("http_status", ""),
                "outcome": result["record"].get("outcome", "UNVERIFIED"),
                "error": result["record"].get("response_error") or result["record"].get("error", ""),
                "sample_file": sample_file}}

    catalogs = {}
    boards = {}
    league_payloads = {}
    evidence = {}
    profile_samples = {}
    profile_rows = []
    coverage_rows = []
    match_rows = []
    selected_matches = {}
    seasons = base["seasons"]

    for season in seasons:
        tag = season.replace("/", "_")
        sid = previous_ids.get(season)
        evidence[season] = {}
        boards[season] = {}
        profile_samples[season] = []
        league = probe("leagues", {"id": 47, "season": season}, season, f"league_{tag}")
        league_payloads[season] = league["payload"]
        evidence[season]["leagues"] = league["evidence"]
        if isinstance(league["payload"], dict):
            link = next((x for x in ((league["payload"].get("stats") or {}).get("seasonStatLinks") or [])
                         if x.get("Name") == season), None)
            if not link or link.get("TournamentId") != sid or (league["payload"].get("details") or {}).get("selectedSeason") != season:
                sid = None
        else:
            sid = None
        for stat in phase["deep_stats_probes"]:
            if sid is None:
                evidence[season][stat] = {"outcome": "UNVERIFIED", "error": "numeric season ID not reconfirmed"}
                continue
            result = probe("leagueseasondeepstats", {"id": 47, "season": sid, "type": "players", "stat": stat},
                           season, f"{stat}_{tag}")
            boards[season][stat] = result["payload"]
            evidence[season][stat] = result["evidence"]
        catalogs[season] = stat_catalog(boards[season].get("goals")) if boards[season].get("goals") is not None else None

        for role, stat in (("outfield_top_goals", "goals"), ("goalkeeper_top_saves", "saves")):
            rows = leaderboard_rows(boards[season].get(stat))
            if not rows or rows[0].get("id") is None:
                continue
            historical = rows[0]
            pid = historical["id"]
            profile = probe("playerData", {"id": pid}, season, f"profile_{role}_{tag}")
            entry = season_profile_entry(profile["payload"], season, 47)
            stats = {"payload": None, "evidence": {"outcome": "UNVERIFIED"}}
            if entry and entry.get("entryId"):
                stats = probe("playerStats", {"playerId": pid, "seasonId": entry["entryId"]},
                              season, f"player_stats_{role}_{tag}")
            profile_samples[season].append({"role": role, "historical": historical,
                                            "profile": profile["payload"], "stats_payload": stats["payload"],
                                            "profile_evidence": profile["evidence"], "stats_evidence": stats["evidence"]})
            profile_rows.append(profile_row(season, role, historical, profile["payload"], stats["payload"],
                                            profile["evidence"], stats["evidence"]))
        goalkeeper_confirmed = any(x["role"] == "goalkeeper_top_saves" and
                                   (((x.get("profile") or {}).get("positionDescription") or {}).get("primaryPosition") or {}).get("label", "").lower() in ("keeper", "goalkeeper")
                                   for x in profile_samples[season])
        team_count = int(previous.loc[previous["season"] == season, "team_count"].iloc[0])
        coverage_rows.append(coverage_row(season, team_count, boards[season], evidence[season], goalkeeper_confirmed))

    # Only two full match details, to confirm historical lineup IDs without crawling matches.
    for season in phase["match_detail_seasons"]:
        first_id = fixture_facts(league_payloads.get(season))["first_match_id"]
        if first_id:
            tag = season.replace("/", "_")
            selected_matches[season] = probe("matchDetails", {"matchId": first_id}, season, f"match_{tag}")

    player_matches = None
    first_profile = next((x for x in profile_samples.get("2019/2020", []) if x["role"] == "outfield_top_goals"), None)
    if first_profile:
        player_matches = probe("playerMatches", {"playerId": first_profile["historical"]["id"],
                                                 "before": 1596240000, "parentLeagueId": 47},
                               "2019/2020", "player_matches_retest")

    for season in seasons:
        detail = selected_matches.get(season) or {}
        match_rows.append(match_row(season, league_payloads.get(season), detail.get("payload"),
                                    evidence[season].get("leagues", {}), detail.get("evidence", {}),
                                    player_matches.get("evidence") if season == "2019/2020" and player_matches else None))
    matrix, dictionary = build_feature_reports(seasons, catalogs, boards, profile_samples, evidence)
    _write_csv(report_dir / "feature_availability_matrix.csv", matrix)
    _write_csv(report_dir / "data_dictionary.csv", dictionary)
    _write_csv(report_dir / "player_coverage_report.csv", coverage_rows)
    _write_csv(report_dir / "player_profile_audit.csv", profile_rows)
    _write_csv(report_dir / "match_index_audit.csv", match_rows)
    counts = pd.DataFrame(matrix).groupby(["group", "status"]).size().to_dict()
    lines = ["# Phase 1 steps 03–05: availability findings", "",
             f"Collected at (UTC): {utc_now()}",
             f"Seasons: {len(seasons)}; HTTP attempts in this run: {client.attempts}/{config['request_budget']}.",
             "", "## Statistics", "",
             "The matrix checks 24 candidate features in each of six seasons. `AVAILABLE` means a nonempty direct leaderboard probe; `PARTIAL` means the season catalog lists the field or a sampled player profile returns it; `UNVERIFIED` means the checked sources did not establish the field. `MISSING` in `catalog_status` means missing from that season's `statsList` only.", ""]
    for group in ("General", "Attacking", "Passing & Creation", "Defending", "Goalkeeping"):
        detail = ", ".join(f"{status} {counts.get((group, status), 0)}" for status in ("AVAILABLE", "PARTIAL", "EMPTY", "FAILED", "UNVERIFIED"))
        lines.append(f"- {group}: {detail} season-feature checks.")
    lines += ["", "The three directly fetched tables are `goals`, `mins_played`, and `saves`. Other listed fields have not had all their values downloaded. Per-player `playerStats` samples supply additional fields such as appearances, starts, shots and pass accuracy, but do not establish league-wide completeness. Catalog title stability does not prove unchanged provider definitions.",
              "", "## Player coverage", "",
              "The union of three leaderboards is only a sampled player numerator. The league team index does not supply a complete player roster, so the player denominator and coverage percentage remain `UNKNOWN_DENOMINATOR`. Duplicate and multi-team counts refer only to the sampled boards. Numeric position codes are reported as observed; goalkeeper identity is checked against sampled profile positions.", ""]
    for row in coverage_rows:
        lines.append(f"- {row['season']}: {row['sample_unique_player_ids']} unique sampled IDs across three boards; {row['sample_teams_represented']}/{row['reference_team_count']} league teams represented; {row['duplicate_id_rows_within_boards']} duplicate rows within boards; {row['multi_team_ids_across_boards']} IDs with multiple team IDs across boards; goalkeeper profile confirmed: {row['goalkeeper_profile_confirmed']}.")
    lines += ["", "## Profiles and match indexes", "",
              "`playerData` includes player ID, name, birth date, primary position, current primary team and a season-specific `statSeasons` entry. The current team and primary position are mutable and must not be assigned to a past season. Historical team IDs in these reports come from that season's leaderboard.",
              "Historical `leagues?season=` responses supply match IDs, dates, team IDs and results. Two `matchDetails` samples check league identity and lineup player IDs; this supports representative player-to-match links, not a complete relationship table. The `playerMatches` retest status is recorded separately and remains a pagination blocker if it fails.",
              "", "## Remaining checks before a final audit report", "",
              "- Establish a defensible full player roster denominator, including transfers and short appearances.",
              "- Check all metric definitions, row missingness, and goalkeeper feature coverage beyond the sampled boards.",
              "- Resolve `playerMatches` historical pagination or document an alternative; inspect the 381-entry 2023/2024 fixture index.",
              "- Verify historical team and position joins without using mutable current profile fields.",
              "", "## Evidence", "",
              "Season-level CSV rows link to request URLs, timestamps and representative JSON samples where data was returned. The data dictionary links to sample files across seasons. Request attempts are in `logs/fotmob_steps_03_05_requests.jsonl`. The samples are source subsets and include only a few leaderboard players or fixtures, so they are not a training dataset.", ""]
    (report_dir / "availability_findings.md").write_text("\n".join(lines), encoding="utf-8")
    return {"attempts": client.attempts, "matrix_rows": len(matrix), "coverage_rows": coverage_rows,
            "profile_rows": profile_rows, "match_rows": match_rows, "matrix": matrix}


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    result = run(project_root)
    print(f"Phase 1 steps 03–05 complete: {result['matrix_rows']} feature checks, {result['attempts']} HTTP attempts")
