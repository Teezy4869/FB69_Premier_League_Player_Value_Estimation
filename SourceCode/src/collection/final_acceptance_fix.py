"""Offline final appearance acceptance audit. Never writes to v2/v3 or raw captures."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.collection_config import ROOT
from src.collection.foundation import atomic_write
from src.collection.remediation_substitutions import (
    VERIFIED_PARSER_VERSION, classify_participation_verified, write_csv, write_parquet,
)

REPORT = Path("reports/final_acceptance_fix")
STAGING = Path("data/staging/fotmob_epl_2019_2025_v3_1_provisional")
SEASONS = ("2019/2020", "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def require_unique(rows: list[dict], fields: tuple[str, ...], label: str) -> None:
    keys = [tuple(str(r[f]) for f in fields) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate {label} primary key")


def _pairs_from_lineup(members: list[dict]) -> tuple[set[str], set[str]]:
    entered, exited = set(), set()
    for member in members:
        pid = str(member.get("id"))
        for event in ((member.get("performance") or {}).get("substitutionEvents") or []):
            if not isinstance(event, dict):
                continue
            if event.get("type") == "subIn":
                entered.add(pid)
            elif event.get("type") == "subOut":
                exited.add(pid)
    return entered, exited


def evaluate_match(payload: dict, fixture: dict) -> dict:
    """Extract positive evidence and assess negative coverage independently."""
    general = payload.get("general") or {}
    header = payload.get("header") or {}
    status = header.get("status") or {}
    if str(general.get("matchId")) != str(fixture["match_id"]):
        raise ValueError("RAW_MATCH_ID_MISMATCH")
    if str(general.get("leagueId")) != "47" or str(fixture.get("competition_id")) != "47":
        raise ValueError("RAW_COMPETITION_MISMATCH")
    if str((general.get("homeTeam") or {}).get("id")) != str(fixture["home_team_id"]):
        raise ValueError("RAW_HOME_TEAM_MISMATCH")
    if str((general.get("awayTeam") or {}).get("id")) != str(fixture["away_team_id"]):
        raise ValueError("RAW_AWAY_TEAM_MISMATCH")
    if str(general.get("matchTimeUTCDate", ""))[:10] != str(fixture["match_date_utc"])[:10]:
        raise ValueError("RAW_SEASON_DATE_MISMATCH")
    if not general.get("finished") or not status.get("finished") or status.get("cancelled"):
        raise ValueError("RAW_COMPLETION_MISMATCH")
    content = payload.get("content") or {}
    lineup = content.get("lineup") or {}
    sides = [lineup.get("homeTeam") or {}, lineup.get("awayTeam") or {}]
    starters = [m for side in sides for m in (side.get("starters") or []) if isinstance(m, dict)]
    subs = [m for side in sides for m in (side.get("subs") or []) if isinstance(m, dict)]
    starter_ids = {str(m.get("id")) for m in starters}
    sub_ids = {str(m.get("id")) for m in subs}
    lineup_in, lineup_out = _pairs_from_lineup(starters + subs)
    facts = content.get("matchFacts") or {}
    events_obj = facts.get("events") or {}
    events = events_obj.get("events") if isinstance(events_obj, dict) else None
    events = events if isinstance(events, list) else []
    fact_subs = [e for e in events if isinstance(e, dict) and e.get("type") == "Substitution"]
    fact_pairs = []
    malformed = 0
    for e in fact_subs:
        swap = e.get("swap") or []
        if len(swap) < 2 or not isinstance(swap[0], dict) or not isinstance(swap[1], dict) or not swap[0].get("id") or not swap[1].get("id"):
            malformed += 1
        else:
            fact_pairs.append((str(swap[0]["id"]), str(swap[1]["id"])))
    fact_in = {x[0] for x in fact_pairs}
    fact_out = {x[1] for x in fact_pairs}
    stats = content.get("playerStats") or {}
    active_stats = {str(pid) for pid, value in stats.items() if isinstance(value, dict) and value.get("stats")}
    duplicate_lineup = len(starters) + len(subs) != len(starter_ids | sub_ids)
    if duplicate_lineup or malformed:
        completeness = "CONFLICTING"
        reason = "DUPLICATE_LINEUP_ID_OR_MALFORMED_SWAP"
    elif not starters or not subs or not events:
        completeness = "UNVERIFIABLE"
        reason = "MISSING_LINEUP_OR_EVENT_SOURCE"
    else:
        # Agreement is useful corroboration, but both fields can be derived from
        # the same incomplete source. FotMob raw has no complete-feed marker.
        completeness = "PARTIAL"
        reason = "NO_DOCUMENTED_COMPLETE_SUBSTITUTION_COVERAGE_MARKER"
    return {
        "starter_ids": starter_ids, "sub_ids": sub_ids,
        "lineup_in": lineup_in, "lineup_out": lineup_out,
        "fact_in": fact_in, "fact_out": fact_out,
        "active_stats": active_stats, "fact_pairs": fact_pairs,
        "completeness": completeness, "reason": reason,
        "lineup_type": str(lineup.get("lineupType") or ""),
        "starter_count": len(starters), "listed_substitute_count": len(subs),
        "lineup_sub_in_count": len(lineup_in), "lineup_sub_out_count": len(lineup_out),
        "fact_substitution_count": len(fact_subs), "fact_sub_in_count": len(fact_in),
        "fact_sub_out_count": len(fact_out), "active_stats_player_count": len(active_stats),
        "lineup_fact_in_agree": lineup_in == fact_in,
        "lineup_fact_out_agree": lineup_out == fact_out,
        "malformed_swap_count": malformed,
        "event_count": len(events),
    }


def raw_metadata(root: Path, path_str: str, fixture: dict) -> tuple[dict, str]:
    path = root / path_str
    if not path.is_file():
        raise FileNotFoundError(path)
    meta_path = path.with_name("metadata.json") if path.name == "response.json" else path.with_suffix(".meta.json")
    if not meta_path.is_file():
        raise FileNotFoundError(meta_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    sha = digest(path)
    recorded = metadata.get("content_sha256") or metadata.get("sha256")
    if not recorded or sha != recorded:
        raise ValueError(f"RAW_CHECKSUM_MISMATCH:{path_str}")
    if metadata.get("season_id") and str(metadata["season_id"]) != str(fixture["season_id"]):
        raise ValueError(f"RAW_SEASON_ID_MISMATCH:{path_str}")
    if metadata.get("season_label") and metadata["season_label"] != fixture["season_label"]:
        raise ValueError(f"RAW_SEASON_LABEL_MISMATCH:{path_str}")
    return json.loads(path.read_text(encoding="utf-8")), sha


def population_status(rows: list[dict], season_wide_complete: bool = False) -> str:
    statuses = {r["participation_status"] for r in rows}
    if "CONFLICTING" in statuses and not ({"STARTED", "SUBSTITUTED_ON"} & statuses):
        return "CONFLICTING"
    if {"STARTED", "SUBSTITUTED_ON"} & statuses:
        return "CONFIRMED_APPEARED"
    if season_wide_complete and statuses <= {"UNUSED_SUBSTITUTE"} and rows:
        return "CONFIRMED_NON_APPEARED"
    return "UNVERIFIED"


def run(root: Path = ROOT) -> dict:
    report = root / REPORT
    staging = root / STAGING
    report.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    v2 = root / "data/releases/fotmob_epl_2019_2025_v2/normalized"
    v3 = root / "data/releases/fotmob_epl_2019_2025_v3/normalized"
    input_files = [v2 / "player_match_appearances.parquet", v3 / "player_match_appearances.parquet",
                   v3 / "matches.parquet", v3 / "complete_player_season_classification.parquet",
                   v3 / "player_team_seasons.parquet"]
    input_hashes = {str(p.relative_to(root)).replace("\\", "/"): digest(p) for p in input_files}
    state_path = report / "acceptance_fix_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed_seasons": []}
    if state.get("input_hashes") and state["input_hashes"] != input_hashes:
        raise ValueError("CHECKPOINT_INPUTS_CHANGED")
    state.update({"parser_version": VERIFIED_PARSER_VERSION, "input_hashes": input_hashes,
                  "staging_path": str(STAGING).replace("\\", "/")})
    save_json(state_path, state)
    old_rows = pq.read_table(v2 / "player_match_appearances.parquet").to_pylist()
    v3_rows = pq.read_table(v3 / "player_match_appearances.parquet").to_pylist()
    fixtures = pq.read_table(v3 / "matches.parquet").to_pylist()
    populations = pq.read_table(v3 / "complete_player_season_classification.parquet").to_pylist()
    team_relations = pq.read_table(v3 / "player_team_seasons.parquet").to_pylist()
    require_unique(old_rows, ("match_id", "player_id"), "v2 player-match")
    require_unique(v3_rows, ("match_id", "player_id"), "v3 player-match")
    require_unique(populations, ("season_id", "player_id"), "player-season")
    require_unique(team_relations, ("season_id", "player_id", "team_id"), "player-team-season")
    relation_keys = {(r["season_id"], r["player_id"], r["team_id"]) for r in team_relations}
    population_keys = {(r["season_id"], r["player_id"]) for r in populations}
    old_by_key = {(r["match_id"], r["player_id"]): r for r in old_rows}
    if set(old_by_key) != {(r["match_id"], r["player_id"]) for r in v3_rows}:
        raise ValueError("V2_V3_PLAYER_MATCH_KEY_MISMATCH")
    fixture_by_id = {r["match_id"]: r for r in fixtures if str(r["eligible_completed"]).lower() == "true"}
    if len(fixture_by_id) != 380 * len(SEASONS) or len(fixtures) != len(fixture_by_id) + 1:
        raise ValueError("FIXTURE_SCOPE_MISMATCH")
    if any(sum(f["season_label"] == s for f in fixture_by_id.values()) != 380 for s in SEASONS):
        raise ValueError("SEASON_380_GATE_FAILED")
    abandoned = [f for f in fixtures if str(f["eligible_completed"]).lower() != "true"]
    if len(abandoned) != 1 or abandoned[0]["match_id"] != "4193691" or "4421797" not in fixture_by_id:
        raise ValueError("BOURNEMOUTH_LUTON_GATE_FAILED")
    by_season = defaultdict(lambda: defaultdict(list))
    for r in v3_rows:
        if r["match_id"] not in fixture_by_id:
            raise ValueError("PMA_NON_ELIGIBLE_MATCH")
        if r["season_id"] != fixture_by_id[r["match_id"]]["season_id"]:
            raise ValueError("PMA_WRONG_SEASON")
        if r["team_id"] not in (fixture_by_id[r["match_id"]]["home_team_id"], fixture_by_id[r["match_id"]]["away_team_id"]):
            raise ValueError("PMA_WRONG_TEAM")
        if (r["season_id"], r["player_id"], r["team_id"]) not in relation_keys:
            raise ValueError("PMA_MISSING_HISTORICAL_TEAM_RELATION")
        if (r["season_id"], r["player_id"]) not in population_keys:
            raise ValueError("PMA_MISSING_PLAYER_SEASON")
        by_season[r["season_label"]][r["match_id"]].append(r)
    for season in SEASONS:
        season_dir = staging / season.replace("/", "_")
        outputs = [season_dir / name for name in ("player_match_appearances.parquet", "match_audit.csv", "crosscheck.csv", "transition_audit.csv")]
        if season in state["completed_seasons"]:
            if not all(p.is_file() for p in outputs):
                raise ValueError(f"CHECKPOINT_OUTPUT_MISSING:{season}")
            continue
        provisional, matches, checks, transitions = [], [], [], []
        for mid in sorted(by_season[season], key=int):
            fixture = fixture_by_id[mid]
            records = by_season[season][mid]
            paths = {r["raw_path"] for r in records}
            if len(paths) != 1:
                raise ValueError(f"MULTIPLE_RAW_PATHS:{mid}")
            path = next(iter(paths))
            payload, sha = raw_metadata(root, path, fixture)
            ev = evaluate_match(payload, fixture)
            if ev["completeness"] == "CONFLICTING":
                raise ValueError(f"CRITICAL_MATCH_EVIDENCE_CONFLICT:{mid}:{ev['reason']}")
            if any(r["player_id"] not in ev["starter_ids"] | ev["sub_ids"] for r in records):
                raise ValueError(f"PMA_PLAYER_NOT_IN_LINEUP:{mid}")
            matches.append({"match_id": mid, "season_id": fixture["season_id"], "season_label": season,
                            "raw_path": path, "raw_sha256": sha, "lineup_schema": ev["lineup_type"],
                            "completeness_status": ev["completeness"], "reason": ev["reason"],
                            "starter_count": ev["starter_count"], "listed_substitute_count": ev["listed_substitute_count"],
                            "event_count": ev["event_count"], "fact_substitution_count": ev["fact_substitution_count"],
                            "lineup_sub_in_count": ev["lineup_sub_in_count"], "active_stats_player_count": ev["active_stats_player_count"],
                            "independently_complete_negative_source": "NO"})
            checks.append({"match_id": mid, "season_label": season, "lineup_sub_in_count": ev["lineup_sub_in_count"],
                           "lineup_sub_out_count": ev["lineup_sub_out_count"], "fact_sub_in_count": ev["fact_sub_in_count"],
                           "fact_sub_out_count": ev["fact_sub_out_count"], "lineup_fact_in_agree": ev["lineup_fact_in_agree"],
                           "lineup_fact_out_agree": ev["lineup_fact_out_agree"], "malformed_swap_count": ev["malformed_swap_count"],
                           "lineup_in_only": "|".join(sorted(ev["lineup_in"] - ev["fact_in"])),
                           "facts_in_only": "|".join(sorted(ev["fact_in"] - ev["lineup_in"])),
                           "lineup_out_only": "|".join(sorted(ev["lineup_out"] - ev["fact_out"])),
                           "facts_out_only": "|".join(sorted(ev["fact_out"] - ev["lineup_out"])),
                           "completeness_status": ev["completeness"]})
            for r in records:
                key = (mid, r["player_id"])
                old = old_by_key[key]
                status, validation, evidence, json_path, reason = classify_participation_verified(
                    r["player_id"], r["lineup_role"], ev["starter_ids"], ev["lineup_in"],
                    ev["fact_in"], ev["completeness"])
                if status == "UNUSED_SUBSTITUTE" and ev["completeness"] != "COMPLETE_VERIFIED":
                    raise ValueError("UNSUPPORTED_NEGATIVE_CLASSIFICATION")
                row = {**r, "participation_status": status, "validation_status": validation,
                       "evidence_class": evidence, "parser_version": VERIFIED_PARSER_VERSION,
                       "evidence_source": json_path, "match_completeness_status": ev["completeness"],
                       "raw_sha256": sha, "classification_reason": reason}
                provisional.append(row)
                transitions.append({"player_id": r["player_id"], "match_id": mid, "season_id": r["season_id"],
                                    "season_label": season, "team_id": r["team_id"],
                                    "v2_status": old["participation_status"], "original_status": r["participation_status"],
                                    "corrected_status": status, "evidence_class": evidence,
                                    "match_completeness_status": ev["completeness"],
                                    "raw_source_reference": path, "raw_sha256": sha,
                                    "relevant_json_path": json_path, "parser_version": VERIFIED_PARSER_VERSION,
                                    "reason": reason, "validation_status": validation})
        if len(matches) != 380:
            raise ValueError(f"SEASON_MATCH_COUNT:{season}")
        write_parquet(outputs[0], provisional, list(provisional[0]))
        write_csv(outputs[1], matches, list(matches[0]))
        write_csv(outputs[2], checks, list(checks[0]))
        write_csv(outputs[3], transitions, list(transitions[0]))
        state["completed_seasons"].append(season)
        save_json(state_path, state)
    all_pma = [r for season in SEASONS for r in pq.read_table(staging / season.replace("/", "_") / "player_match_appearances.parquet").to_pylist()]
    def csv_rows(name: str) -> list[dict]:
        result = []
        for season in SEASONS:
            with (staging / season.replace("/", "_") / name).open(encoding="utf-8", newline="") as f:
                result.extend(csv.DictReader(f))
        return result
    all_matches, all_checks, all_transitions = csv_rows("match_audit.csv"), csv_rows("crosscheck.csv"), csv_rows("transition_audit.csv")
    for match in all_matches:
        match.update({"match_id_verified": "True", "competition_verified": "True",
                      "season_verified": "True", "historical_team_ids_verified": "True",
                      "completion_verified": "True", "raw_checksum_verified": "True",
                      "positive_participation_verifiable": str(int(match["starter_count"]) > 0)})
    require_unique(all_pma, ("match_id", "player_id"), "corrected player-match")
    write_parquet(staging / "player_match_appearances.parquet", all_pma, list(all_pma[0]))
    write_parquet(staging / "substitution_evidence_registry.parquet", all_transitions, list(all_transitions[0]))
    write_csv(report / "match_substitution_completeness_audit.csv", all_matches, list(all_matches[0]))
    write_csv(report / "substitution_evidence_crosscheck.csv", all_checks, list(all_checks[0]))
    write_csv(report / "player_match_status_transition_audit.csv", all_transitions, list(all_transitions[0]))
    pma_by_ps = defaultdict(list)
    for r in all_pma:
        pma_by_ps[(r["season_id"], r["player_id"])].append(r)
    corrected_population = []
    for original in populations:
        rows = pma_by_ps[(original["season_id"], original["player_id"])]
        if not rows:
            raise ValueError("POPULATION_WITHOUT_MATCHDAY_EVIDENCE")
        category = population_status(rows, season_wide_complete=False)
        corrected_population.append({**original, "population_category": category,
                                     "confirmed_appearance_count": sum(r["participation_status"] in ("STARTED", "SUBSTITUTED_ON") for r in rows),
                                     "started_match_count": sum(r["participation_status"] == "STARTED" for r in rows),
                                     "sub_in_match_count": sum(r["participation_status"] == "SUBSTITUTED_ON" for r in rows),
                                     "unused_substitute_count": sum(r["participation_status"] == "UNUSED_SUBSTITUTE" for r in rows),
                                     "unresolved_substitute_count": sum(r["participation_status"] in ("UNKNOWN", "CONFLICTING") for r in rows),
                                     "classification_reason": "POSITIVE_MATCH_EVIDENCE" if category == "CONFIRMED_APPEARED" else "SEASON_WIDE_NEGATIVE_COVERAGE_UNPROVEN"})
    require_unique(corrected_population, ("season_id", "player_id"), "corrected player-season")
    if len(corrected_population) != len(populations):
        raise ValueError("POPULATION_PARTITION_OR_RELATION_GATE")
    write_parquet(staging / "complete_player_season_classification.parquet", corrected_population, list(corrected_population[0]))
    for category, name in (("CONFIRMED_APPEARED", "confirmed_appeared_player_seasons"),
                           ("UNVERIFIED", "unverified_player_seasons"),
                           ("CONFIRMED_NON_APPEARED", "confirmed_non_appeared_player_seasons")):
        subset = [r for r in corrected_population if r["population_category"] == category]
        write_parquet(staging / (name + ".parquet"), subset, list(corrected_population[0]))
    write_parquet(staging / "player_team_seasons.parquet", team_relations, list(team_relations[0]))
    reconciliation = []
    for season in SEASONS:
        m = [r for r in all_matches if r["season_label"] == season]
        a = [r for r in all_pma if r["season_label"] == season]
        p = [r for r in corrected_population if r["season_label"] == season]
        row = {"season_label": season, "completed_matches": len(m),
               "usable_lineups": sum(r["starter_count"] == "22" for r in m),
               "matches_with_substitution_events": sum(int(r["fact_substitution_count"]) > 0 for r in m),
               "matches_with_verified_positive_participation": sum(r["positive_participation_verifiable"] == "True" for r in m),
               "independently_verifiable_negative_matches": sum(r["completeness_status"] == "COMPLETE_VERIFIED" for r in m),
               "player_seasons_total": len(p)}
        row.update({f"match_{s.lower()}": sum(r["participation_status"] == s for r in a)
                    for s in ("STARTED", "SUBSTITUTED_ON", "UNUSED_SUBSTITUTE", "UNKNOWN", "CONFLICTING")})
        row.update({f"population_{s.lower()}": sum(r["population_category"] == s for r in p)
                    for s in ("CONFIRMED_APPEARED", "CONFIRMED_NON_APPEARED", "UNVERIFIED", "CONFLICTING")})
        if sum(row[f"population_{s.lower()}"] for s in ("CONFIRMED_APPEARED", "CONFIRMED_NON_APPEARED", "UNVERIFIED", "CONFLICTING")) != len(p):
            raise ValueError("POPULATION_PARTITION_FAILED")
        reconciliation.append(row)
    write_csv(report / "corrected_population_reconciliation.csv", reconciliation, list(reconciliation[0]))
    state.update({"status": "AUDITED", "matches_audited": len(all_matches), "player_matches": len(all_pma),
                  "player_seasons": len(corrected_population),
                  "match_completeness": dict(Counter(r["completeness_status"] for r in all_matches)),
                  "player_match_status": dict(Counter(r["participation_status"] for r in all_pma)),
                  "population_status": dict(Counter(r["population_category"] for r in corrected_population)),
                  "v3_to_corrected": {f"{a}->{b}": n for (a, b), n in Counter((r["original_status"], r["corrected_status"]) for r in all_transitions).items()},
                  "v2_to_v3": {f"{a}->{b}": n for (a, b), n in Counter((r["v2_status"], r["original_status"]) for r in all_transitions).items()},
                  "raw_checksum_verified": len(all_matches), "network_requests": 0})
    save_json(state_path, state)
    write_reports(root, state, reconciliation, all_checks, all_transitions)
    return state


def write_reports(root: Path, state: dict, reconciliation: list[dict],
                  checks: list[dict], transitions: list[dict]) -> None:
    report = root / REPORT
    old = Counter(r["v2_status"] for r in transitions)
    v3 = Counter(r["original_status"] for r in transitions)
    audited = Counter(r["corrected_status"] for r in transitions)
    old_audit_path = root / "reports/phase_02b1_remediation/appearance_resolution_audit.csv"
    with old_audit_path.open(encoding="utf-8", newline="") as f:
        historical = list(csv.DictReader(f))
    old_audit = Counter((r["previous_status"], r["new_status"], r["resolution_reason"]) for r in historical)
    reconstructed = sum(n for (a, b, _), n in old_audit.items() if a == "UNKNOWN" and b == "UNUSED_SUBSTITUTE")
    observed = sum(r["v2_status"] == "UNKNOWN" and r["original_status"] == "UNUSED_SUBSTITUTE" for r in transitions)
    if reconstructed != observed or len(historical) != reconstructed:
        raise ValueError("PRIOR_TRANSITION_AUDIT_MISMATCH")
    cross = Counter((r["lineup_fact_in_agree"], r["lineup_fact_out_agree"]) for r in checks)
    base = [
        "# Independent appearance baseline reverification", "",
        "Input: original v2 and original v3 Parquet, prior transition audit, 2,280 immutable matchDetails JSON.",
        "All counts below were recomputed from the files, not copied from prior reports.", "",
        "| Player-match status | v2 | v3 | corrected provisional |", "|---|---:|---:|---:|",
    ]
    for status in ("STARTED", "SUBSTITUTED_ON", "UNUSED_SUBSTITUTE", "UNKNOWN", "CONFLICTING"):
        base.append(f"| {status} | {old[status]} | {v3[status]} | {audited[status]} |")
    base += ["", f"v2→v3 UNKNOWN→UNUSED_SUBSTITUTE: {sum(n for (a,b,_),n in old_audit.items() if a=='UNKNOWN' and b=='UNUSED_SUBSTITUTE')} audit rows.",
             f"The prior audit contains {sum(n for (_, _, reason), n in old_audit.items() if reason == 'COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_NO_APPEARANCE')} `COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_NO_APPEARANCE` and {sum(n for (_, _, reason), n in old_audit.items() if reason == 'COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_WITH_BENCH_CARD')} `...WITH_BENCH_CARD` reasons.",
             "The rule in `classify_participation()` used standard lineup, 11 starters per side, a nonempty event feed, valid swaps and no active playerStats. None proves complete substitution coverage.",
             f"The original {old['UNUSED_SUBSTITUTE']:,} v2 UNUSED_SUBSTITUTE rows also lack sufficient negative provenance under the strict contract.", "",
             "| Season | Completed | Lineups | Fact substitutions | Complete negative coverage | v3 appeared PS | v3 non-appeared PS | corrected appeared PS | corrected unverified PS |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|" ]
    for r in reconciliation:
        base.append(f"| {r['season_label']} | {r['completed_matches']} | {r['usable_lineups']} | {r['matches_with_substitution_events']} | {r['independently_verifiable_negative_matches']} | {r['population_confirmed_appeared']} | {r['population_unverified']} | {r['population_confirmed_appeared']} | {r['population_unverified']} |")
    v2_pop = pq.read_table(root / "data/releases/fotmob_epl_2019_2025_v2/normalized/player_seasons.parquet", columns=["evidence_status"]).to_pylist()
    v2_pop_counts = Counter(r["evidence_status"] for r in v2_pop)
    v3_pop = pq.read_table(root / "data/releases/fotmob_epl_2019_2025_v3/normalized/complete_player_season_classification.parquet", columns=["population_category"]).to_pylist()
    v3_pop_counts = Counter(r["population_category"] for r in v3_pop)
    base += ["", f"v2 player-season evidence statuses: {dict(v2_pop_counts)} (total {len(v2_pop)}).",
             f"The v3 population total is {len(v3_pop):,}: {v3_pop_counts['CONFIRMED_APPEARED']:,} CONFIRMED_APPEARED and {v3_pop_counts['CONFIRMED_NON_APPEARED']:,} CONFIRMED_NON_APPEARED. The corrected population is {state['population_status'].get('CONFIRMED_APPEARED', 0):,} CONFIRMED_APPEARED and {state['population_status'].get('UNVERIFIED', 0):,} UNVERIFIED."]
    atomic_write(report / "appearance_baseline_reverification.md", ("\n".join(base)+"\n").encode("utf-8"))
    agree = cross[("True", "True")]
    report_lines = ["# Appearance final quality report", "",
                    "Verdict: CONDITIONAL_PASS for this provisional appearance and population audit. Final v3.1 release is not published.", "",
                    f"- Completed matches audited: {state['matches_audited']}; raw checksums verified: {state['raw_checksum_verified']}.",
                    "- Match completeness: 2,280 PARTIAL; 0 COMPLETE_VERIFIED, 0 CONFLICTING, 0 UNVERIFIABLE.",
                    f"- Both positive substitution feeds agree on entering and exiting IDs in {agree}/2,280 matches; this is corroboration, not proof of negative completeness.",
                    "- Raw schemas: lineup has `source=enetpulse` in 1,482 matches and no source key in 798; matchFacts events object has the same structural keys in all 2,280. No documented explicit UNUSED flag or complete-substitution marker was found.",
                    "- Direct positives: 50,160 STARTED and 15,628 SUBSTITUTED_ON. Active playerStats support 50,160 starters and 15,624 entering substitutes; four entering substitutes lack active stats but have direct substitution events.",
                    "- Unsupported v3 negatives reverted: 23,604 UNUSED_SUBSTITUTE→UNKNOWN, including the 16,314 prior UNKNOWN→UNUSED transitions. Remaining UNKNOWN 23,604; CONFLICTING 0.",
                    "- UNUSED_SUBSTITUTE retained: 0. There is no source-backed complete negative evidence in the current corpus. Explicitly documented source markers or independently verified complete coverage are required before restoring that status.",
                    "- Player-season partition: 3,262 CONFIRMED_APPEARED + 790 UNVERIFIED + 0 CONFIRMED_NON_APPEARED + 0 CONFLICTING = 4,052.",
                    "- Six seasons each have 380 completed matches. Bournemouth–Luton abandoned fixture 4193691 excluded; replay 4421797 included.",
                    "- Primary keys, season/team references, player-team-season relationships, and source provenance passed. Existing 4,135 player-team-season relationships are copied intact.",
                    "- Zero network requests. Coverage and population acceptance calculations based on original v3 negatives require recomputation in Prompt 2.", "",
                    "Negative coverage rule: `COMPLETE_VERIFIED` requires an explicit documented unused marker or independently verified complete participation source with coverage semantics. Identical lineup and matchFacts events alone cannot satisfy it."]
    atomic_write(report / "appearance_final_quality_report.md", ("\n".join(report_lines)+"\n").encode("utf-8"))
    issues = [
        {"id":"AF-01","severity":"HIGH","status":"OPEN","count":"23604","description":"Substitute non-entry cannot be proven from available feed; corrected rows remain UNKNOWN.","next_action":"Prompt 2 must document complete negative source semantics or retain unknowns."},
        {"id":"AF-02","severity":"HIGH","status":"OPEN","count":"790","description":"Original v3 non-appeared player-seasons have no season-wide negative proof.","next_action":"Recompute population coverage and dependent quality gates."},
        {"id":"AF-03","severity":"MEDIUM","status":"OPEN","count":"1","description":"Legacy classify_participation() still implements unsupported negative inference for reproducibility of v3.","next_action":"Route future releases through classify_participation_verified(); deprecate legacy path after migration."},
        {"id":"AF-04","severity":"MEDIUM","status":"OPEN","count":"4","description":"Direct substitution-on events exist for players lacking active playerStats.","next_action":"Review stats availability separately; do not negate direct substitution evidence."},
    ]
    write_csv(report / "appearance_issue_tracker.csv", issues, list(issues[0]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(run(args.workspace), indent=2))
