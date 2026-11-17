"""Pure season-statistic parsing, coverage and scope rules."""
from __future__ import annotations

from collections import defaultdict

from src.collection.normalize_pilot import parse_number


def stat_occurrences(payload: dict) -> list[dict]:
    rows = []
    for component in ("topStatCard", "statsSection"):
        def walk(node):
            if isinstance(node, dict):
                field = node.get("localizedTitleId")
                if isinstance(field, str) and "statValue" in node:
                    rows.append({"original_field": field, "raw_value": node["statValue"],
                                 "title": node.get("title"), "stat_format": node.get("statFormat"),
                                 "source_per90": node.get("per90"), "component": component})
                for child in node.values():
                    if isinstance(child, (dict, list)):
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(payload.get(component))
    return rows


def collapse_stat_occurrences(payload: dict) -> tuple[dict[str, dict], list[dict]]:
    by_field = defaultdict(list)
    for row in stat_occurrences(payload):
        by_field[row["original_field"]].append(row)
    selected, conflicts = {}, []
    for field, rows in by_field.items():
        values = {str(row["raw_value"]) for row in rows}
        if len(values) > 1:
            conflicts.append({"original_field": field, "raw_values": sorted(values),
                              "components": sorted({r["component"] for r in rows})})
        selected[field] = next((r for r in rows if r["component"] == "statsSection"), rows[0])
        selected[field]["duplicate_source_count"] = len(rows)
    return selected, conflicts


def value_status(raw: object) -> tuple[str, float | None]:
    value = parse_number(raw)
    if raw is None or raw == "":
        return "MISSING", None
    if value is None:
        return "UNVERIFIED", None
    return ("OBSERVED_ZERO" if value == 0 else "OBSERVED"), value


def validate_board_filter(payload: dict, params: dict) -> str:
    if str(payload.get("currentSeasonId")) != str(params.get("season")) or payload.get("currentStatName") != params.get("stat"):
        return "HISTORICAL_SCOPE_MISMATCH"
    if "teamId" not in params:
        return "NOT_REQUESTED"
    if payload.get("teamId") is None:
        return "UNVERIFIED_TEAM_FILTER"
    return "VERIFIED_TEAM_FILTER" if str(payload["teamId"]) == str(params["teamId"]) else "TEAM_FILTER_MISMATCH"


def leaderboard_coverage(payload: dict, appeared_ids: set[str]) -> dict:
    rows = payload.get("statsData") or []
    ids = [str(row.get("id")) for row in rows if isinstance(row, dict)]
    unique_ids = set(ids)
    meta = payload.get("pagination") or {}
    total = meta.get("total") if isinstance(meta, dict) else None
    if total is None:
        total = payload.get("totalCount")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None
    if len(ids) != len(unique_ids):
        status = "DUPLICATE_PLAYER_ID"
    elif total is not None and total > len(rows):
        status = "PAGINATED_OR_TRUNCATED"
    elif unique_ids == appeared_ids:
        status = "ALL_APPEARED_IDS"
    else:
        status = "PARTIAL_RANKED_OR_FILTERED"
    return {"status": status, "returned_rows": len(rows), "returned_unique_players": len(unique_ids),
            "appeared_players": len(appeared_ids), "matched_appeared_players": len(unique_ids & appeared_ids),
            "appeared_missing_from_board": len(appeared_ids - unique_ids),
            "outside_appeared_population": len(unique_ids - appeared_ids),
            "reported_total": total, "pagination_metadata_present": total is not None or bool(meta)}


def metric_denominator(appeared_ids: set[str], confirmed_goalkeepers: set[str], goalkeeper_only: bool) -> set[str]:
    return appeared_ids & confirmed_goalkeepers if goalkeeper_only else set(appeared_ids)


def verified_goalkeepers_from_positions(positions: list[dict], season_label_map: dict[str, str] | None = None) -> dict[str, set[str]]:
    """Extract verified goalkeepers by season from historical position observations."""
    gk_by_season = defaultdict(set)
    for r in positions:
        s = (season_label_map.get(str(r.get("season_id", "")), r.get("season_label", str(r.get("season_id", ""))))
             if season_label_map else r.get("season_label", str(r.get("season_id", ""))))
        if r.get("mapped_group") == "GK":
            gk_by_season[s].add(str(r["player_id"]))
    return gk_by_season


def compute_metric_eligibility_registry(
    wide: list[dict],
    metrics: list[str],
    rules: list[dict],
    positions: list[dict],
    seasons: list[dict] | None = None
) -> tuple[list[dict], list[dict]]:
    """Compute verified metric eligibility registry and corrected cross-season coverage.

    Guarantees:
    - Numerator and denominator use the same distinct Player-Season grain.
    - Verified position eligibility is derived from match lineup evidence, not top-N leaderboards.
    - Valid observations outside verified eligibility are tracked, never silently discarded.
    - Coverage ratios never exceed 1.0 (100%) when the denominator is valid.
    """
    from collections import Counter
    season_label_map = {str(r["season_id"]): r["season_label"] for r in seasons} if seasons else {}
    gk_by_season = verified_goalkeepers_from_positions(positions, season_label_map)

    pos_by_player_season = defaultdict(set)
    for r in positions:
        s = (season_label_map.get(str(r.get("season_id", "")), r.get("season_label", str(r.get("season_id", ""))))
             if season_label_map else r.get("season_label", str(r.get("season_id", ""))))
        pos_by_player_season[(s, str(r["player_id"]))].add(r.get("mapped_group", "UNKNOWN"))

    by_season_appeared = defaultdict(list)
    for r in wide:
        if r.get("population_status") == "APPEARED":
            by_season_appeared[r["season_label"]].append(r)

    rules_by_name = {r["normalized_field"]: r for r in rules}
    registry_rows = []
    coverage_rows = []

    for season in sorted(by_season_appeared.keys()):
        people = by_season_appeared[season]
        pop_count = len(people)
        appeared_gk = gk_by_season.get(season, set()) & {str(p["player_id"]) for p in people}
        unknown_pos_players = {str(p["player_id"]) for p in people
                               if pos_by_player_season.get((season, str(p["player_id"]))) in (None, set(), {"UNKNOWN"})}

        for metric in metrics:
            rule = rules_by_name[metric]
            is_gk = (rule.get("applicable_positions") == "GK_ONLY")
            eligible_pids = appeared_gk if is_gk else {str(p["player_id"]) for p in people}

            states = Counter(p.get("s_" + metric) for p in people)
            # Reconciled source revisions and validated leaderboard fallbacks are
            # observed values too. Excluding them understated historical xG/xA.
            observed_valid_pids = {str(p["player_id"]) for p in people if p.get("s_" + metric) in (
                "OBSERVED", "OBSERVED_ZERO", "OBSERVED_SOURCE_REVISED", "OBSERVED_FALLBACK_LEADERBOARD")}
            valid_eligible = observed_valid_pids & eligible_pids
            valid_outside = observed_valid_pids - eligible_pids
            missing_eligible = eligible_pids - observed_valid_pids

            if metric == "key_passes":
                status = "UNSUPPORTED"
                cov_ratio = 0.0
            elif len(eligible_pids) == 0:
                status = "UNDEFINED"
                cov_ratio = None
            elif len(valid_outside) > 0:
                status = "ANOMALOUS_OUTSIDE_ELIGIBILITY"
                cov_ratio = round(len(valid_eligible) / len(eligible_pids), 6)
            elif len(valid_eligible) == 0:
                status = "ZERO_OBSERVATIONS"
                cov_ratio = 0.0
            elif season == "2019/2020" and metric in ("expected_goals", "expected_assists"):
                status = "SPARSE_SOURCE_COVERAGE"
                cov_ratio = round(len(valid_eligible) / len(eligible_pids), 6)
            elif len(valid_eligible) == len(eligible_pids):
                status = "FULL_COVERAGE"
                cov_ratio = 1.0
            else:
                status = "VALID_PARTIAL"
                cov_ratio = round(len(valid_eligible) / len(eligible_pids), 6)

            registry_rows.append({
                "season_label": season,
                "metric_name": metric,
                "metric_group": rule.get("metric_group", ""),
                "applicable_positions": rule.get("applicable_positions", ""),
                "population_count": pop_count,
                "eligible_verified_count": len(eligible_pids),
                "eligibility_unknown_count": len(unknown_pos_players) if is_gk else 0,
                "observed_distinct_players": len(observed_valid_pids),
                "valid_eligible_count": len(valid_eligible),
                "valid_outside_verified_eligibility_count": len(valid_outside),
                "missing_eligible_count": len(missing_eligible),
                "coverage_ratio": cov_ratio if cov_ratio is not None else "",
                "coverage_status": status,
                "notes": "Verified match-lineup GK position" if is_gk else "All confirmed appeared players eligible"
            })

            not_applicable_count = (pop_count - len(eligible_pids)) if is_gk else 0
            coverage_rows.append({
                "season_label": season,
                "metric_name": metric,
                "eligible_players": len(eligible_pids),
                "appeared_players": pop_count,
                "valid_values": len(valid_eligible),
                "missing": len(missing_eligible),
                "not_applicable": not_applicable_count,
                "unsupported": states.get("UNSUPPORTED", 0),
                "conflicting": states.get("CONFLICTING", 0),
                "unknown": states.get("COLLECTION_GAP", 0),
                "coverage_fraction": round(cov_ratio, 6) if cov_ratio is not None else 0.0,
                "coverage_status": status,
                "unit": rule.get("unit", ""),
                "data_type": "float64",
                "source_endpoint": "playerStats",
                "aggregation_type": rule.get("aggregation_type", ""),
                "eligibility_basis": "HISTORICAL_GK_LINEUP" if is_gk else "ALL_APPEARED"
            })

    return registry_rows, coverage_rows
