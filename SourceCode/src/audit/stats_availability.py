"""Feature catalog mapping with separate catalog, sample and live-table evidence."""

from __future__ import annotations

from .normalization import leaderboard_rows, player_stat_items


# Candidate-to-source mapping is a hypothesis; every report row is checked against live JSON.
FEATURES = [
    ("General", "Appearances", None, ("matches_uppercase",)),
    ("General", "Minutes played", "mins_played", ("minutes_played",)),
    ("General", "Starts", None, ("player_started_matches",)),
    ("General", "Player ratings", "rating", ("rating",)),
    ("Attacking", "Goals", "goals", ("goals",)),
    ("Attacking", "Assists", "goal_assist", ("assists",)),
    ("Attacking", "Shots", "total_scoring_att", ("shots",)),
    ("Attacking", "Shots on target", "ontarget_scoring_att", ("ShotsOnTarget",)),
    ("Attacking", "Expected goals (xG)", "expected_goals", ("expected_goals", "expected_goals_title")),
    ("Attacking", "Expected assists (xA)", "expected_assists", ("expected_assists", "expected_assists_title")),
    ("Passing & Creation", "Accurate passes", "accurate_pass", ("successful_passes",)),
    ("Passing & Creation", "Passing accuracy", None, ("successful_passes_accuracy",)),
    ("Passing & Creation", "Chances created", "total_att_assist", ("chances_created",)),
    ("Passing & Creation", "Key passes", None, ("key_pass", "key_passes")),
    ("Passing & Creation", "Long passes", "accurate_long_balls", ("long_balls_accurate",)),
    ("Defending", "Tackles", "total_tackle", ("tackles", "total_tackle")),
    ("Defending", "Interceptions", "interception", ("interceptions",)),
    ("Defending", "Clearances", "effective_clearance", ("clearances",)),
    ("Defending", "Blocks", "outfielder_block", ("blocks",)),
    ("Defending", "Duels", None, ("duels_won", "duel_won", "duels")),
    ("Goalkeeping", "Saves", "saves", ("saves",)),
    ("Goalkeeping", "Goals conceded", "goals_conceded", ("goals_conceded",)),
    ("Goalkeeping", "Clean sheets", "clean_sheet", ("clean_sheets",)),
    ("Goalkeeping", "Goals prevented", "_goals_prevented", ("goals_prevented",)),
]


def _kind_and_unit(title: str | None, candidate: str) -> tuple[str, str]:
    text = (title or candidate).lower()
    if "per 90" in text:
        return "per_90", "per 90 minutes"
    if "accuracy" in text or "percentage" in text:
        return "percentage", "percent"
    if "rating" in text:
        return "rating", "FotMob rating points"
    if "minutes" in text:
        return "total", "minutes"
    if "goals prevented" in text:
        return "total", "goals prevented (goal-equivalent; definition unverified)"
    if "expected goal" in text or "expected assist" in text:
        return "total", "expected assists" if "assist" in text else "expected goals"
    return "total", "count"


def build_feature_reports(seasons: list[str], catalogs: dict, boards: dict,
                          sampled_profiles: dict, evidence: dict) -> tuple[list[dict], list[dict]]:
    matrix = []
    dictionary = []
    for group, candidate, catalog_key, profile_keys in FEATURES:
        titles = set()
        observed_fields = set()
        observed_types = set()
        observed_units = set()
        profile_titles = set()
        season_statuses = []
        for season in seasons:
            catalog = catalogs.get(season) or {}
            item = catalog.get(catalog_key) if catalog_key else None
            catalog_status = "AVAILABLE" if item else ("MISSING" if catalogs.get(season) is not None else "FAILED")
            board = (boards.get(season) or {}).get(catalog_key) if catalog_key else None
            board_rows = leaderboard_rows(board)
            direct_requested = catalog_key in ("goals", "mins_played", "saves")
            profiles = sampled_profiles.get(season) or []
            found = []
            for sample in profiles:
                metrics = player_stat_items(sample.get("stats_payload"))
                for key in profile_keys:
                    if key in metrics:
                        found.append((key, metrics[key]))
            profile_keys_found = sorted({key for key, _ in found})
            profile_titles.update(str(value.get("title")) for _, value in found if value.get("title"))
            title = item.get("title") if item else (found[0][1].get("title") if found else "")
            kind, unit = _kind_and_unit(title, candidate)
            if candidate == "Long passes" and item:
                kind, unit = "per_90", "accurate long passes per 90 minutes"
            if candidate == "Duels" and found:
                unit = "observed duel variant; see profile field"
            field = catalog_key if item else (profile_keys_found[0] if profile_keys_found else "")
            if item:
                titles.add((item.get("title") or "", item.get("category") or ""))
                observed_fields.add(catalog_key)
            observed_fields.update(profile_keys_found)
            sample_value = None
            if board_rows:
                sample_value = (board_rows[0].get("statValue") or {}).get("value")
            if sample_value is not None:
                observed_types.add(type(sample_value).__name__)
            if found:
                observed_types.add("str (playerStats.statValue)")
            if item or found:
                observed_units.add(unit)
            if direct_requested:
                if board is None:
                    status = "FAILED" if evidence.get(season, {}).get(catalog_key, {}).get("outcome") == "FAILED" else "UNVERIFIED"
                elif board_rows:
                    status = "AVAILABLE"
                else:
                    status = "EMPTY"
            elif item or found:
                status = "PARTIAL"
            else:
                status = "UNVERIFIED"
            season_statuses.append(status)
            catalog_ev = evidence.get(season, {}).get(catalog_key) or evidence.get(season, {}).get("goals", {})
            profile_ev = next((sample.get("stats_evidence", {}) for sample in profiles
                               if any(key in player_stat_items(sample.get("stats_payload")) for key in profile_keys)), {})
            supporting_ev = profile_ev if found and not item else catalog_ev
            source_endpoint = ("leagueseasondeepstats|playerStats" if item and found else
                               "leagueseasondeepstats" if item else "playerStats" if found else "leagueseasondeepstats (catalog check)")
            matrix.append({"season": season, "group": group, "candidate_feature": candidate,
                           "status": status, "catalog_status": catalog_status,
                           "api_field": field, "leaderboard_field": catalog_key if item else "",
                           "profile_fields_observed": "|".join(profile_keys_found),
                           "source_title": title, "source_category": item.get("category", "") if item else "",
                           "value_type_observed": type(sample_value).__name__ if sample_value is not None else ("str" if found else "UNKNOWN"),
                           "kind": kind if item or found else "UNKNOWN", "unit": unit if item or found else "UNKNOWN",
                           "unit_basis": "source title or statFormat; check definition" if item or found else "unverified",
                           "direct_table_rows": len(board_rows) if board is not None else "",
                           "sampled_profiles_with_field": len({sample_index for sample_index, sample in enumerate(profiles) if any(k in player_stat_items(sample.get('stats_payload')) for k in profile_keys)}),
                           "coverage_scope": "single leaderboard" if status == "AVAILABLE" else ("catalog and sampled profiles" if status == "PARTIAL" else "none"),
                           "source_endpoint": source_endpoint,
                           "source_url": supporting_ev.get("source_url", ""),
                           "sample_file": supporting_ev.get("sample_file", ""),
                           "profile_source_url": profile_ev.get("source_url", ""),
                           "profile_sample_file": profile_ev.get("sample_file", ""),
                           "collected_at_utc": supporting_ev.get("timestamp_utc", ""),
                           "note": "Accurate long balls only; total long-pass attempts not established" if candidate == "Long passes" else ("Duels won variant only; total duels unverified" if candidate == "Duels" else ("No equivalence assumed between key passes and chances created" if candidate == "Key passes" else ""))})
        dictionary.append({"group": group, "candidate_feature": candidate,
                           "api_fields_observed": "|".join(sorted(observed_fields)),
                           "source_titles_categories": "|".join(sorted(f"{a} [{b}]" for a, b in titles)),
                           "value_types_observed": "|".join(sorted(observed_types)) or "UNKNOWN",
                           "profile_title_variants": "|".join(sorted(profile_titles)),
                           "units_observed_or_title_inferred": "|".join(sorted(observed_units)) or "UNKNOWN",
                           "statistic_kind": _kind_and_unit(next(iter(titles))[0] if titles else None, candidate)[0] if observed_units else "UNKNOWN",
                           "available_seasons": "|".join(s for s, status in zip(seasons, season_statuses) if status == "AVAILABLE"),
                           "partial_seasons": "|".join(s for s, status in zip(seasons, season_statuses) if status == "PARTIAL"),
                           "unverified_or_failed_seasons": "|".join(s for s, status in zip(seasons, season_statuses) if status in ("UNVERIFIED", "FAILED", "EMPTY")),
                           "historical_definition_note": "Catalog/profile labels compared across six seasons; metric computation definition not published in checked responses" if len(titles) <= 1 and len(profile_titles) <= 1 else f"Label/category variants: catalog={sorted(titles)}, profile={sorted(profile_titles)}",
                           "limitation": "Accurate long balls only" if candidate == "Long passes" else ("No exact key-pass field verified" if candidate == "Key passes" else ""),
                           "source_endpoint": "leagueseasondeepstats|playerStats",
                           "evidence_samples": "|".join(evidence.get(s, {}).get("goals", {}).get("sample_file", "") for s in seasons),
                           "profile_evidence_samples": "|".join(sample.get("stats_evidence", {}).get("sample_file", "") for s in seasons for sample in sampled_profiles.get(s, []) if any(key in player_stat_items(sample.get("stats_payload")) for key in profile_keys)),
                           "collected_at_utc": evidence.get(seasons[0], {}).get("goals", {}).get("timestamp_utc", "")})
    return matrix, dictionary
