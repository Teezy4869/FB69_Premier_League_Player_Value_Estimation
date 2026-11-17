"""Hybrid FotMob-to-Transfermarkt entity resolution (Phase 3, Step 3).

Flow: identities -> aligned games -> candidates -> evidence and score -> classification -> crosswalk.
Only a unique exact name + exact birth date can map automatically. Everything else waits for a person.

Human input lives in data/phase_03/review. Decisions are copied into an append-only ledger, so
rerunning never overwrites them. No target, valuation or model is touched here.

Usage: python -I src/phase3/entity_resolution.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402
from rapidfuzz.fuzz import token_sort_ratio  # noqa: E402

from src.phase3.names import is_token_subset, name_keys, normalize_name  # noqa: E402
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, file_hash, load_config, verify_fotmob_unchanged, write_json  # noqa: E402

CONFIG_PATH = ROOT / "configs/phase_03_matching.yaml"
REVIEW_DIR = ROOT / "data/phase_03/review"
# AUTO_ADJUDICATED is a documented adaptation: an automated, evidence-based decision that is not human review.
STATUSES = ("AUTO_EXACT", "AUTO_HIGH_CONFIDENCE", "AUTO_ADJUDICATED", "REVIEW_REQUIRED", "MANUAL_CONFIRMED", "UNMATCHED", "AMBIGUOUS")
MAPPED_STATUSES = ("AUTO_EXACT", "AUTO_HIGH_CONFIDENCE", "AUTO_ADJUDICATED", "MANUAL_CONFIRMED")
ADJUDICATION_PATH = REVIEW_DIR / "automated_adjudications.csv"
REVIEW_DECISIONS = ("CONFIRM_MATCH", "REJECT_CANDIDATE", "MARK_AMBIGUOUS", "MARK_UNMATCHED", "INVESTIGATE")
REVIEW_FIELDS = ("reviewer_decision", "reviewer_name", "review_date", "reviewer_notes")


# ---------- Pure evidence functions ----------

def dob_relation(fotmob: date | None, transfermarkt: date | None) -> str:
    if fotmob is None or transfermarkt is None:
        return "MISSING"
    if fotmob == transfermarkt:
        return "EXACT"
    if abs((fotmob - transfermarkt).days) == 1:
        return "OFF_BY_ONE_DAY"
    if fotmob.year == transfermarkt.year and fotmob.month == transfermarkt.day and fotmob.day == transfermarkt.month:
        return "DAY_MONTH_SWAP"
    return "SAME_YEAR" if fotmob.year == transfermarkt.year else "DIFFERENT"


def nationality_relation(fotmob: str | None, transfermarkt: str | None, aliases: dict) -> str:
    if not fotmob or not transfermarkt:
        return "MISSING"
    left, right = aliases.get(fotmob, fotmob), aliases.get(transfermarkt, transfermarkt)
    return "AGREE" if normalize_name(left) == normalize_name(right) else "DISAGREE"


def position_relation(fotmob_group: str | None, transfermarkt: str | None, position_map: dict) -> str:
    if not fotmob_group or not transfermarkt or transfermarkt == "Missing":
        return "MISSING"
    return "AGREE" if position_map.get(fotmob_group) == transfermarkt else "DISAGREE"


def club_status(fm_club_seasons: set, tm_club_seasons: set, shared_games: int) -> str:
    """CONFIRMED needs shared games. A TM gap is ABSENT, never evidence against a match."""
    if shared_games > 0:
        return "CONFIRMED_GAMES"
    if fm_club_seasons & tm_club_seasons:
        return "CONFIRMED_CLUB_SEASON"
    fm_seasons = {season for season, _ in fm_club_seasons}
    if {season for season, _ in tm_club_seasons} & fm_seasons:
        return "CONTRADICTED"
    return "ABSENT"


def score_candidate(signals: dict, weights: dict) -> tuple[float, float]:
    """Return (score, available points). Missing evidence earns nothing and is not available."""
    relation = signals["dob_relation"]
    score = weights["name_similarity"] * signals["name_similarity"] / 100
    available = float(weights["name_similarity"] + weights["name_subset"])
    if signals["name_subset"]:
        score += weights["name_subset"]
    if relation != "MISSING":
        available += weights["dob_exact"]
        score += {"EXACT": weights["dob_exact"], "OFF_BY_ONE_DAY": weights["dob_near"], "DAY_MONTH_SWAP": weights["dob_near"],
                  "SAME_YEAR": weights["dob_same_year"]}.get(relation, 0)
    if signals["tm_games"] > 0:
        available += weights["game_set_jaccard"]
        score += weights["game_set_jaccard"] * signals["game_jaccard"]
    for field, weight in (("nationality_relation", "nationality"), ("position_relation", "position")):
        if signals[field] != "MISSING":
            available += weights[weight]
            score += weights[weight] if signals[field] == "AGREE" else 0
    return round(score, 3), available


def suggest(signals: dict, config: dict, claimed_by_other: bool) -> str:
    """A description for the reviewer. It never creates a mapping."""
    if claimed_by_other:
        return "ALREADY_MAPPED_TO_ANOTHER_IDENTITY"
    s = config["suggestion"]
    relation, similarity, jaccard = signals["dob_relation"], signals["name_similarity"], signals["game_jaccard"]
    if relation == "EXACT" and (similarity >= s["likely_min_name_similarity"] or signals["name_subset"] or jaccard >= s["likely_min_jaccard"]):
        return "LIKELY_MATCH"
    if relation in ("OFF_BY_ONE_DAY", "DAY_MONTH_SWAP") and similarity >= s["near_dob_likely_min_name_similarity"] and jaccard >= s["near_dob_likely_min_jaccard"]:
        return "LIKELY_MATCH"
    club_confirmed = signals["club_status"].startswith("CONFIRMED")
    if (relation == "EXACT" and club_confirmed) or jaccard >= s["likely_min_jaccard"] or (similarity >= s["possible_min_name_similarity"] and club_confirmed):
        return "POSSIBLE_MATCH"
    return "UNLIKELY"


def classify_identity(candidates: list[dict]) -> dict:
    """Assign one status from an identity's candidates. Fuzzy evidence can never map a player."""
    exact = [c for c in candidates if c["name_exact"] and c["dob_relation"] == "EXACT"]
    if len(exact) > 1:
        return {"status": "AMBIGUOUS", "method": "MULTIPLE_EXACT_NAME_DOB", "tm_id": None}
    if len(exact) == 1:
        if exact[0]["club_status"] == "CONTRADICTED":
            return {"status": "REVIEW_REQUIRED", "method": "EXACT_NAME_DOB_CLUB_CONTRADICTION", "tm_id": None}
        method = "EXACT_NAME_DOB_UNIQUE_CLUB_CONFIRMED" if exact[0]["club_status"].startswith("CONFIRMED") else "EXACT_NAME_DOB_UNIQUE_NO_CLUB_EVIDENCE"
        return {"status": "AUTO_EXACT", "method": method, "tm_id": exact[0]["tm_player_id"]}
    if not candidates:
        return {"status": "UNMATCHED", "method": "NO_CANDIDATE", "tm_id": None}
    likely = [c for c in candidates if c.get("suggestion") == "LIKELY_MATCH"]
    if len(likely) > 1:
        return {"status": "AMBIGUOUS", "method": "MULTIPLE_LIKELY_CANDIDATES", "tm_id": None}
    return {"status": "REVIEW_REQUIRED", "method": "CANDIDATES_NEED_REVIEW", "tm_id": None}


def resolve_tm_conflicts(decisions: dict[str, dict]) -> list[str]:
    """Two identities must not share a TM ID. Conflicting automatic mappings become AMBIGUOUS."""
    owners = defaultdict(list)
    for fm_id, decision in decisions.items():
        if decision["status"] in MAPPED_STATUSES and decision["tm_id"]:
            owners[decision["tm_id"]].append(fm_id)
    conflicted = []
    for tm_id, fm_ids in owners.items():
        if len(fm_ids) > 1:
            for fm_id in fm_ids:
                decisions[fm_id] = {"status": "AMBIGUOUS", "method": "TM_ID_CLAIMED_BY_MULTIPLE_IDENTITIES", "tm_id": None}
            conflicted.append(tm_id)
    return sorted(conflicted)


def apply_review_decisions(decisions: dict[str, dict], ledger: list[dict]) -> None:
    """Human decisions take priority. Contradictory decisions stop the run rather than choose."""
    by_identity = defaultdict(list)
    for row in ledger:
        by_identity[row["fotmob_player_id"]].append(row)
    for fm_id, rows in by_identity.items():
        if fm_id not in decisions:
            raise RuntimeError(f"Review decision refers to unknown FotMob identity {fm_id}")
        confirmed = {r["candidate_tm_player_id"] for r in rows if r["reviewer_decision"] == "CONFIRM_MATCH"}
        rejected_pairs = {r["candidate_tm_player_id"] for r in rows if r["reviewer_decision"] == "REJECT_CANDIDATE"}
        marks = {r["reviewer_decision"] for r in rows if r["reviewer_decision"] in ("MARK_AMBIGUOUS", "MARK_UNMATCHED")}
        if len(confirmed) > 1 or (confirmed and marks) or len(marks) > 1 or (confirmed & rejected_pairs):
            raise RuntimeError(f"Contradictory review decisions for FotMob identity {fm_id}")
        last = rows[-1]
        if confirmed:
            decisions[fm_id] = {"status": "MANUAL_CONFIRMED", "method": "HUMAN_REVIEW", "tm_id": next(iter(confirmed))}
        elif "MARK_AMBIGUOUS" in marks:
            decisions[fm_id] = {"status": "AMBIGUOUS", "method": "HUMAN_REVIEW", "tm_id": None}
        elif "MARK_UNMATCHED" in marks:
            decisions[fm_id] = {"status": "UNMATCHED", "method": "HUMAN_REVIEW", "tm_id": None}
        else:
            if decisions[fm_id].get("tm_id") in rejected_pairs or last["reviewer_decision"] == "INVESTIGATE":
                decisions[fm_id] = {"status": "REVIEW_REQUIRED", "method": "HUMAN_REVIEW_IN_PROGRESS", "tm_id": None}
        decisions[fm_id]["review"] = last


def apply_adjudications(decisions: dict[str, dict], adjudications: list[dict], candidates_by_identity: dict[str, set]) -> int:
    """Map only unresolved identities with a CONFIRMED_MATCH on an existing candidate. Human review runs afterwards."""
    applied = 0
    for row in adjudications:
        fm_id, tm_id = row["fotmob_player_id"], row["tm_player_id"]
        if fm_id not in decisions:
            raise RuntimeError(f"Adjudication refers to unknown FotMob identity {fm_id}")
        if row["outcome"] != "CONFIRMED_MATCH" or decisions[fm_id]["status"] not in ("REVIEW_REQUIRED", "AMBIGUOUS"):
            continue
        if tm_id not in candidates_by_identity.get(fm_id, set()):
            raise RuntimeError(f"Adjudication for {fm_id} is not one of its candidates: {tm_id}")
        decisions[fm_id] = {"status": "AUTO_ADJUDICATED", "method": f"AUTOMATED_ADJUDICATION_{row['basis']}", "tm_id": tm_id, "adjudication": row}
        applied += 1
    return applied


def validate_crosswalk(rows: list[dict]) -> dict:
    """Raise on any broken uniqueness, status or mapping rule. Returns the check results."""
    fm_ids = [r["fotmob_player_id"] for r in rows]
    canonical = [r["canonical_player_id"] for r in rows]
    tm_ids = [r["transfermarkt_player_id"] for r in rows if r["transfermarkt_player_id"]]
    bad_status = [r["fotmob_player_id"] for r in rows if r["match_status"] not in STATUSES]
    unsupported = [r["fotmob_player_id"] for r in rows if r["transfermarkt_player_id"] and r["match_status"] not in MAPPED_STATUSES]
    unmapped = [r["fotmob_player_id"] for r in rows if not r["transfermarkt_player_id"] and r["match_status"] in MAPPED_STATUSES]
    no_evidence = [r["fotmob_player_id"] for r in rows if r["transfermarkt_player_id"] and not r["evidence"]]
    no_adjudicator = [r["fotmob_player_id"] for r in rows if r["match_status"] == "AUTO_ADJUDICATED" and not r.get("adjudicator")]
    passed_as_human = [r["fotmob_player_id"] for r in rows if r.get("adjudicator") and r.get("reviewer")]
    problems = {
        "duplicate_fotmob_ids": len(fm_ids) - len(set(fm_ids)), "duplicate_canonical_ids": len(canonical) - len(set(canonical)),
        "duplicate_transfermarkt_ids": len(tm_ids) - len(set(tm_ids)), "invalid_statuses": len(bad_status),
        "mappings_with_unsupported_status": len(unsupported), "mapped_status_without_id": len(unmapped), "mappings_without_evidence": len(no_evidence),
        "adjudicated_without_adjudicator": len(no_adjudicator), "automated_decision_recorded_as_human": len(passed_as_human),
    }
    if any(problems.values()):
        raise RuntimeError(f"Crosswalk integrity failure: {problems}")
    return problems


# ---------- Data loading ----------

def load_inputs(con) -> None:
    fm = FOTMOB_RELEASE / "normalized"
    tm_curated = ROOT / "data/transfermarkt/curated/tm_r2_20260905"
    tm_staging = ROOT / "data/transfermarkt/staging/tm_r2_20260905"
    sources = {"f_conf": fm / "confirmed_appeared_player_seasons", "f_players": fm / "players", "f_pts": fm / "player_team_seasons", "f_matches": fm / "matches",
               "f_pm": fm / "player_match_appearances", "f_pos": fm / "historical_position_observations", "f_teams": fm / "teams",
               "t_players": tm_curated / "tm_players", "t_pcs": tm_curated / "tm_player_club_seasons", "t_transfers": tm_curated / "tm_transfers",
               "t_games": tm_staging / "stg_games", "t_app": tm_staging / "stg_appearances"}
    for alias, path in sources.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path.as_posix()}.parquet')")


def build_game_alignment(con) -> tuple[dict, dict]:
    """Derive the club map from fixtures, not names, then require every match to align exactly once."""
    votes = con.execute("""
        WITH f AS (SELECT home_team_id t, substr(match_date_utc,1,10) d, replace(score,' ','') s FROM f_matches WHERE match_status='COMPLETED'),
             g AS (SELECT home_club_id c, date::VARCHAR d, home_club_goals||'-'||away_club_goals s FROM t_games WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024)
        SELECT f.t, g.c, count(*) n FROM f JOIN g USING (d, s) GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2""").fetchall()
    team_map: dict[str, str] = {}
    for team, club, _ in votes:
        team_map.setdefault(team, club)
    if len(set(team_map.values())) != len(team_map):
        raise RuntimeError("Club map is not one-to-one")
    games = {(d, h, a): g for g, d, h, a in con.execute("SELECT game_id, date::VARCHAR, home_club_id, away_club_id FROM t_games WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024").fetchall()}
    matches = con.execute("SELECT match_id, substr(match_date_utc,1,10), home_team_id, away_team_id FROM f_matches WHERE match_status='COMPLETED'").fetchall()
    match_map = {}
    for match_id, day, home, away in matches:
        game = games.get((day, team_map.get(home), team_map.get(away)))
        if game is None:
            raise RuntimeError(f"Match {match_id} has no aligned Transfermarkt game")
        match_map[match_id] = game
    if len(set(match_map.values())) != len(match_map):
        raise RuntimeError("Match alignment is not one-to-one")
    return team_map, match_map


def load_fotmob_identities(con, team_map: dict, match_map: dict) -> dict:
    identities: dict[str, dict] = {}
    rows = con.execute("""SELECT p.player_id, p.profile_name, p.lineup_name, p.birth_date, p.nationality_name, p.nationality_code, p.current_position, p.profile_raw_path
                          FROM f_players p SEMI JOIN f_conf USING (player_id) ORDER BY p.player_id""").fetchall()
    for fid, profile, lineup, birth, nationality, code, position, raw_path in rows:
        identities[fid] = {"id": fid, "profile_name": profile, "lineup_name": lineup, "dob": date.fromisoformat(birth) if birth else None,
                           "nationality": nationality, "nationality_code": code, "current_position": position, "raw_path": raw_path,
                           "names": {profile, lineup} - {None}, "seasons": [], "club_seasons": set(), "club_labels": set(), "games": set(), "position_group": None}
    for fid, name, season in con.execute("SELECT player_id, player_name, season_label FROM f_conf ORDER BY 1, 3").fetchall():
        identities[fid]["names"].add(name)
        identities[fid]["seasons"].append(season)
    names = dict(con.execute("SELECT DISTINCT team_id, team_name FROM f_teams").fetchall())
    # Only CONFIRMED club relations count; UNVERIFIED associations are not treated as evidence.
    for fid, season, team in con.execute("""SELECT t.player_id, t.season_label, t.team_id FROM f_pts t SEMI JOIN f_conf c ON t.player_id=c.player_id AND t.season_id=c.season_id
                                            WHERE t.validation_status='CONFIRMED' ORDER BY 1, 2, 3""").fetchall():
        identities[fid]["club_seasons"].add((season, team_map[team]))
        identities[fid]["club_labels"].add(f"{season}:{names.get(team, team)}")
    for fid, match_id, team in con.execute("SELECT player_id, match_id, team_id FROM f_pm WHERE participation_status IN ('STARTED','SUBSTITUTED_ON')").fetchall():
        if fid in identities and match_id in match_map:
            identities[fid]["games"].add((match_map[match_id], team_map[team]))
    for fid, group in con.execute("""SELECT player_id, mapped_group FROM f_pos WHERE mapped_group<>'UNKNOWN' GROUP BY 1, 2
                                     QUALIFY row_number() OVER (PARTITION BY player_id ORDER BY count(*) DESC, mapped_group)=1""").fetchall():
        if fid in identities:
            identities[fid]["position_group"] = group
    return identities


def load_tm_players(con) -> dict:
    players: dict[str, dict] = {}
    for tid, raw, first, last, code, norm, dob, nationality, position, url in con.execute(
            "SELECT tm_player_id, player_name_raw, first_name_raw, last_name_raw, player_code, player_name_normalized, date_of_birth, nationality, position_profile, source_profile_url FROM t_players ORDER BY tm_player_id").fetchall():
        full = f"{first} {last}" if first and last else None
        players[tid] = {"id": tid, "raw_name": raw, "normalized": norm, "dob": dob, "nationality": nationality, "position": position, "url": url,
                        "keys": name_keys([raw, full, code.replace("-", " ") if code else None]), "club_seasons": set(), "club_labels": set(), "games": set(), "transfer_clubs": set()}
    for tid, label, club, name in con.execute("SELECT tm_player_id, season_label, tm_club_id, club_name FROM t_pcs WHERE season_start_year BETWEEN 2019 AND 2024 ORDER BY 1, 2, 3").fetchall():
        players[tid]["club_seasons"].add((label, club))
        players[tid]["club_labels"].add(f"{label}:{name}")
    for tid, game, club in con.execute("""SELECT a.player_id, a.game_id, a.player_club_id FROM t_app a JOIN t_games g USING (game_id)
                                          WHERE a.competition_id='GB1' AND g.season BETWEEN 2019 AND 2024""").fetchall():
        if tid in players:
            players[tid]["games"].add((game, club))
    for tid, from_club, to_club in con.execute("SELECT tm_player_id, from_club_id, to_club_id FROM t_transfers WHERE NOT is_after_snapshot").fetchall():
        if tid in players:
            players[tid]["transfer_clubs"].update((from_club, to_club))
    return players


# ---------- Candidate generation ----------

def similarity(fm_normalized: list[str], tm_normalized: str | None) -> float:
    if not tm_normalized:
        return 0.0
    return max((token_sort_ratio(n, tm_normalized) for n in fm_normalized), default=0.0)


def generate_candidates(identity: dict, players: dict, index: dict, config: dict, include_fuzzy: bool) -> dict[str, set]:
    """Return {tm_id: {block names}} using deterministic blocks. Output order never affects results."""
    b = config["blocking"]
    blocks: dict[str, set] = defaultdict(set)
    fm_keys = name_keys(identity["names"])
    fm_norm = sorted({n for n in (normalize_name(x) for x in identity["names"]) if n})
    for key in fm_keys:
        for tid in index["by_key"].get(key, ()):
            blocks[tid].add("EXACT_NAME")
    dob = identity["dob"]
    subset = lambda tid: any(is_token_subset(n, players[tid]["normalized"]) for n in fm_norm)  # noqa: E731
    if dob:
        for tid in index["by_dob"].get(dob, ()):
            if similarity(fm_norm, players[tid]["normalized"]) >= b["dob_exact_min_name_similarity"] or subset(tid):
                blocks[tid].add("DOB_EXACT")
    if not include_fuzzy:
        return blocks
    if dob:
        nearby = [dob - timedelta(days=1), dob + timedelta(days=1)]
        if dob.day <= 12 and dob.day != dob.month:
            nearby.append(date(dob.year, dob.day, dob.month))
        for other in nearby:
            for tid in index["by_dob"].get(other, ()):
                if similarity(fm_norm, players[tid]["normalized"]) >= b["dob_near_min_name_similarity"]:
                    blocks[tid].add("DOB_NEAR")
        for tid in index["by_year"].get(dob.year, ()):
            if similarity(fm_norm, players[tid]["normalized"]) >= b["birth_year_min_name_similarity"]:
                blocks[tid].add("BIRTH_YEAR_NAME")
    for club_season in identity["club_seasons"]:
        for tid in index["by_club_season"].get(club_season, ()):
            if similarity(fm_norm, players[tid]["normalized"]) >= b["roster_min_name_similarity"] or subset(tid):
                blocks[tid].add("ROSTER_NAME")
    shared = Counter()
    for game in identity["games"]:
        shared.update(index["by_game"].get(game, ()))
    fm_games = identity["games"]
    for tid, count in shared.items():
        if count >= b["game_set_min_shared_games"] and count / len(fm_games | players[tid]["games"]) >= b["game_set_min_jaccard"]:
            blocks[tid].add("GAME_SET")
    return blocks


def evidence_signals(identity: dict, player: dict, blocks: set, config: dict) -> dict:
    fm_norm = sorted({n for n in (normalize_name(x) for x in identity["names"]) if n})
    shared = len(identity["games"] & player["games"])
    union = len(identity["games"] | player["games"])
    fm_clubs = {club for _, club in identity["club_seasons"]}
    signals = {
        "name_exact": bool(name_keys(identity["names"]) & player["keys"]),
        "name_similarity": round(similarity(fm_norm, player["normalized"]), 2),
        "name_subset": any(is_token_subset(n, player["normalized"]) for n in fm_norm),
        "dob_relation": dob_relation(identity["dob"], player["dob"]),
        "nationality_relation": nationality_relation(identity["nationality"], player["nationality"], config["nationality_aliases"]),
        "position_relation": position_relation(identity["position_group"], player["position"], config["position_map"]),
        "club_status": club_status(identity["club_seasons"], player["club_seasons"], shared),
        "club_season_overlap": len(identity["club_seasons"] & player["club_seasons"]),
        "fm_club_seasons": len(identity["club_seasons"]), "tm_club_seasons": len(player["club_seasons"]),
        "shared_games": shared, "fm_games": len(identity["games"]), "tm_games": len(player["games"]),
        "game_jaccard": round(shared / union, 4) if union else 0.0,
        "transfer_club_overlap": len(fm_clubs & player["transfer_clubs"]),
        "blocks": "|".join(sorted(blocks)),
    }
    return signals


def build_index(players: dict) -> dict:
    index = {"by_key": defaultdict(set), "by_dob": defaultdict(set), "by_year": defaultdict(set), "by_club_season": defaultdict(set), "by_game": defaultdict(set)}
    for tid, player in players.items():
        for key in player["keys"]:
            index["by_key"][key].add(tid)
        if player["dob"]:
            index["by_dob"][player["dob"]].add(tid)
            index["by_year"][player["dob"].year].add(tid)
        for club_season in player["club_seasons"]:
            index["by_club_season"][club_season].add(tid)
        for game in player["games"]:
            index["by_game"][game].add(tid)
    return index


def stable_rank(seed: str, *parts: str) -> str:
    return hashlib.sha256("|".join((seed, *parts)).encode("utf-8")).hexdigest()


# ---------- Review ledger ----------

QUEUE_COLUMNS = ["queue_id", "fotmob_player_id", "fotmob_names", "fotmob_dob", "fotmob_nationality", "fotmob_club_seasons", "fotmob_player_season_rows", "identity_status", "identity_method",
                 "candidate_rank", "candidate_tm_player_id", "candidate_name", "candidate_dob", "candidate_nationality", "candidate_position_profile", "candidate_club_seasons", "candidate_url",
                 "score", "score_available", "name_exact", "name_similarity", "name_subset", "dob_relation", "nationality_relation", "position_relation", "club_status", "club_season_overlap",
                 "shared_games", "fm_games", "tm_games", "game_jaccard", "transfer_club_overlap", "blocks", "suggested_decision", *REVIEW_FIELDS]
LEDGER_COLUMNS = ["fotmob_player_id", "candidate_tm_player_id", *REVIEW_FIELDS, "imported_at_utc"]


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def import_reviews(queue_path: Path, ledger_path: Path, imported_at: str) -> list[dict]:
    """Copy new human decisions from the queue into the append-only ledger, validating each one."""
    ledger = read_csv_rows(ledger_path)
    seen = {tuple(row[c] for c in LEDGER_COLUMNS[:-1]) for row in ledger}
    new = []
    for row in read_csv_rows(queue_path):
        decision = (row.get("reviewer_decision") or "").strip()
        if not decision:
            continue
        if decision not in REVIEW_DECISIONS:
            raise RuntimeError(f"Invalid decision '{decision}' in queue row {row.get('queue_id')}")
        if not (row.get("reviewer_name") or "").strip() or not (row.get("review_date") or "").strip():
            raise RuntimeError(f"Queue row {row.get('queue_id')} needs reviewer_name and review_date")
        record = {c: (row.get(c) or "") for c in LEDGER_COLUMNS[:-1]}
        record["reviewer_decision"] = decision
        if tuple(record[c] for c in LEDGER_COLUMNS[:-1]) not in seen:
            new.append({**record, "imported_at_utc": imported_at})
    if new:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        exists = ledger_path.exists()
        with ledger_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
            if not exists:
                writer.writeheader()
            writer.writerows(new)
    return ledger + new


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------- Validation sample ----------

def build_validation_sample(candidates: list[dict], decisions: dict, identities: dict, config: dict) -> tuple[list[dict], dict]:
    """Choose pairs for a human to label, with fixed seeded ordering. Labels stay blank."""
    settings = config["validation_sample"]
    seed, per_stratum = settings["seed"], settings["per_stratum"]
    by_id = defaultdict(list)
    for c in candidates:
        by_id[c["fotmob_player_id"]].append(c)
    mapped = lambda c: decisions[c["fotmob_player_id"]].get("tm_id") == c["tm_player_id"]  # noqa: E731
    multi_club = {fid for fid, i in identities.items() if len({s for s, _ in i["club_seasons"]}) < len(i["club_seasons"])}
    strata = {
        "AUTO_EXACT_RANDOM": ([c for c in candidates if mapped(c)], settings["auto_exact_random"]),
        "AUTO_EXACT_NO_CLUB_EVIDENCE": ([c for c in candidates if mapped(c) and not c["club_status"].startswith("CONFIRMED")], per_stratum),
        "AUTO_EXACT_LOW_GAME_OVERLAP": ([c for c in candidates if mapped(c) and c["club_status"].startswith("CONFIRMED") and c["game_jaccard"] < 0.5], per_stratum),
        "MULTI_CLUB_SEASON": ([c for c in candidates if mapped(c) and c["fotmob_player_id"] in multi_club], per_stratum),
        "DIFFICULT_POSITIVE_CANDIDATE": ([c for c in candidates if not c["name_exact"] and c["suggestion"] == "LIKELY_MATCH"], per_stratum),
        "COMMON_NAME_COLLISION": ([c for c in candidates if c["name_exact"] and c["dob_relation"] != "EXACT"], per_stratum),
        "SIMILAR_NAME_NEGATIVE_CANDIDATE": ([c for c in candidates if not c["name_exact"] and c["name_similarity"] >= 80 and c["dob_relation"] in ("DIFFERENT", "SAME_YEAR") and c["suggestion"] != "LIKELY_MATCH"], per_stratum),
        "INCOMPLETE_EVIDENCE": ([c for c in candidates if c["nationality_relation"] == "MISSING" or c["dob_relation"] == "MISSING" or c["position_relation"] == "MISSING"], per_stratum),
        "MULTIPLE_PLAUSIBLE_CANDIDATES": ([c for fid, group in by_id.items() if sum(x["suggestion"] in ("LIKELY_MATCH", "POSSIBLE_MATCH") for x in group) > 1 for c in group], per_stratum),
    }
    sample, used, counts = [], set(), {}
    for stratum, (pool, size) in strata.items():
        ordered = sorted(pool, key=lambda c: stable_rank(seed, stratum, c["fotmob_player_id"], c["tm_player_id"]))
        chosen = ordered[:size]
        counts[stratum] = {"pool": len(pool), "selected": len(chosen)}
        for c in chosen:
            key = (c["fotmob_player_id"], c["tm_player_id"])
            sample.append({"sample_id": f"{stratum}:{c['fotmob_player_id']}:{c['tm_player_id']}", "stratum": stratum, "already_in_another_stratum": key in used, "fotmob_player_id": key[0], "candidate_tm_player_id": key[1],
                           "fotmob_names": c["fotmob_names"], "fotmob_dob": c["fotmob_dob"], "fotmob_nationality": c["fotmob_nationality"], "fotmob_club_seasons": c["fotmob_club_seasons"],
                           "candidate_name": c["tm_name"], "candidate_dob": c["tm_dob"], "candidate_nationality": c["tm_nationality"], "candidate_club_seasons": c["tm_club_season_labels"], "candidate_url": c["tm_url"],
                           "human_label": "", "labeler_name": "", "label_date": "", "label_notes": ""})
            used.add(key)
    return sample, counts


# ---------- Main ----------

def rows_to_parquet(rows: list[dict], schema: pa.Schema, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({f.name: pa.array([r.get(f.name) for r in rows], f.type) for f in schema})
    pq.write_table(table, path, compression="zstd")
    return file_hash(path)


CANDIDATE_SCHEMA = pa.schema([("fotmob_player_id", pa.string()), ("tm_player_id", pa.string()), ("candidate_rank", pa.int32()), ("score", pa.float64()), ("score_available", pa.float64()),
                              ("name_exact", pa.bool_()), ("name_similarity", pa.float64()), ("name_subset", pa.bool_()), ("dob_relation", pa.string()), ("nationality_relation", pa.string()), ("position_relation", pa.string()),
                              ("club_status", pa.string()), ("club_season_overlap", pa.int32()), ("fm_club_seasons", pa.int32()), ("tm_club_seasons", pa.int32()), ("shared_games", pa.int32()), ("fm_games", pa.int32()), ("tm_games", pa.int32()),
                              ("game_jaccard", pa.float64()), ("transfer_club_overlap", pa.int32()), ("blocks", pa.string()), ("claimed_by_other", pa.bool_()), ("suggestion", pa.string()), ("meets_proposed_high_confidence", pa.bool_()),
                              ("fotmob_names", pa.string()), ("fotmob_dob", pa.string()), ("fotmob_nationality", pa.string()), ("fotmob_club_seasons", pa.string()), ("tm_name", pa.string()), ("tm_dob", pa.string()), ("tm_nationality", pa.string()), ("tm_position_profile", pa.string()), ("tm_club_season_labels", pa.string()), ("tm_url", pa.string())])
CROSSWALK_SCHEMA = pa.schema([("canonical_player_id", pa.string()), ("fotmob_player_id", pa.string()), ("transfermarkt_player_id", pa.string()), ("match_status", pa.string()), ("match_method", pa.string()), ("ranking_score", pa.float64()), ("ranking_score_available", pa.float64()), ("evidence", pa.string()),
                              ("review_status", pa.string()), ("reviewer", pa.string()), ("review_date", pa.string()), ("adjudicator", pa.string()), ("adjudication_date", pa.string()), ("adjudication_confidence", pa.string()), ("adjudication_basis", pa.string()), ("decision_rationale", pa.string()), ("candidate_count", pa.int32()), ("player_season_rows", pa.int32()), ("fotmob_names_raw", pa.string()), ("tm_name_raw", pa.string()), ("matching_version", pa.string())])


def run(config: dict, output_root: Path, review_dir: Path, adjudication_path: Path | None = ADJUDICATION_PATH) -> dict:
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    load_inputs(con)
    team_map, match_map = build_game_alignment(con)
    identities = load_fotmob_identities(con, team_map, match_map)
    players = load_tm_players(con)
    index = build_index(players)
    season_rows = dict(con.execute("SELECT player_id, count(*) FROM f_conf GROUP BY 1").fetchall())

    # First pass: exact name and DOB only, so we know which TM IDs are already claimed.
    first_pass: dict[str, dict] = {}
    for fid, identity in identities.items():
        found = []
        for tid in generate_candidates(identity, players, index, config, include_fuzzy=False):
            signals = evidence_signals(identity, players[tid], {"-"}, config)
            found.append({"tm_player_id": tid, **signals})
        first_pass[fid] = classify_identity([c for c in found if c["name_exact"] and c["dob_relation"] == "EXACT"])
    claimed = Counter(d["tm_id"] for d in first_pass.values() if d["status"] == "AUTO_EXACT")

    # Second pass: all blocks for every identity, so automatic matches also face their rivals.
    # Fuzzy candidates never change an automatic decision; they support auditing and negative examples.
    candidates: list[dict] = []
    decisions: dict[str, dict] = {}
    weights = config["scoring"]
    hc = config["auto_high_confidence"]["proposed_criteria"]
    for fid in sorted(identities):
        identity = identities[fid]
        blocks = generate_candidates(identity, players, index, config, include_fuzzy=True)
        found = []
        for tid in sorted(blocks):
            player = players[tid]
            signals = evidence_signals(identity, player, blocks[tid], config)
            score, available = score_candidate(signals, weights)
            own = first_pass[fid].get("tm_id") == tid
            is_claimed = claimed.get(tid, 0) > (1 if own else 0)
            found.append({"fotmob_player_id": fid, "tm_player_id": tid, "score": score, "score_available": available, **signals, "claimed_by_other": is_claimed,
                          "suggestion": suggest(signals, config, is_claimed),
                          "fotmob_names": " | ".join(sorted(identity["names"])), "fotmob_dob": identity["dob"].isoformat() if identity["dob"] else None, "fotmob_nationality": identity["nationality"],
                          "fotmob_club_seasons": " | ".join(sorted(identity["club_labels"])), "tm_name": player["raw_name"], "tm_dob": player["dob"].isoformat() if player["dob"] else None,
                          "tm_nationality": player["nationality"], "tm_position_profile": player["position"], "tm_club_season_labels": " | ".join(sorted(player["club_labels"])), "tm_url": player["url"]})
        found.sort(key=lambda c: (-c["score"], c["tm_player_id"]))
        likely = [c for c in found if c["suggestion"] == "LIKELY_MATCH"]
        for rank, c in enumerate(found, 1):
            c["candidate_rank"] = rank
            c["meets_proposed_high_confidence"] = (c["dob_relation"] == "EXACT" and c["game_jaccard"] >= hc["min_game_set_jaccard"] and c["fm_games"] >= hc["min_fotmob_games"] and len(likely) == 1 and not c["name_exact"])
        decisions[fid] = classify_identity(found)
        identity["candidates"] = found
        candidates.extend(found)

    conflicts = resolve_tm_conflicts(decisions)
    # The validation sample is drawn from rule-only decisions, so later decisions can't change it.
    rule_decisions = {fid: dict(d) for fid, d in decisions.items()}
    adjudications = read_csv_rows(adjudication_path) if adjudication_path else []
    adjudicated = apply_adjudications(decisions, adjudications, {fid: {c["tm_player_id"] for c in i["candidates"]} for fid, i in identities.items()})

    review_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    queue_path, ledger_path = review_dir / "matching_review_queue.csv", review_dir / "review_decisions_ledger.csv"
    ledger = import_reviews(queue_path, ledger_path, now)
    apply_review_decisions(decisions, ledger)
    conflicts += resolve_tm_conflicts(decisions)

    crosswalk = []
    for fid in sorted(identities):
        identity, decision = identities[fid], decisions[fid]
        tid = decision["tm_id"]
        chosen = next((c for c in identity["candidates"] if c["tm_player_id"] == tid), None)
        evidence = None
        if chosen:
            keep = ("name_exact", "name_similarity", "dob_relation", "nationality_relation", "position_relation", "club_status", "club_season_overlap", "shared_games", "fm_games", "tm_games", "game_jaccard", "transfer_club_overlap", "blocks")
            payload = {k: chosen[k] for k in keep}
            if decision.get("adjudication"):
                payload["automated_adjudication"] = decision["adjudication"]["evidence"]
                payload["external_sources"] = decision["adjudication"]["external_sources"]
            evidence = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        elif tid:
            evidence = json.dumps({"source": "human_review"}, sort_keys=True)
        review = decision.get("review")
        needs_review = decision["status"] in ("REVIEW_REQUIRED", "AMBIGUOUS")
        adjudication = decision.get("adjudication") if not review else None
        crosswalk.append({
            "canonical_player_id": f"fb69p_{fid}", "fotmob_player_id": fid, "transfermarkt_player_id": tid, "match_status": decision["status"], "match_method": decision["method"],
            "ranking_score": chosen["score"] if chosen else None, "ranking_score_available": chosen["score_available"] if chosen else None, "evidence": evidence,
            "review_status": "REVIEWED" if review else ("AUTOMATED_ADJUDICATION_NOT_HUMAN" if adjudication else "PENDING" if needs_review else "NOT_REQUIRED"), "reviewer": review["reviewer_name"] if review else None, "review_date": review["review_date"] if review else None,
            "adjudicator": adjudication["adjudicator"] if adjudication else None, "adjudication_date": adjudication["adjudication_date"] if adjudication else None, "adjudication_confidence": adjudication["confidence"] if adjudication else None, "adjudication_basis": adjudication["basis"] if adjudication else None,
            "decision_rationale": (review["reviewer_notes"] or review["reviewer_decision"]) if review else adjudication["rationale"] if adjudication else decision["method"], "candidate_count": len(identity["candidates"]), "player_season_rows": season_rows[fid],
            "fotmob_names_raw": " | ".join(sorted(identity["names"])), "tm_name_raw": players[tid]["raw_name"] if tid and tid in players else None, "matching_version": config["matching_version"],
        })
    integrity = validate_crosswalk(crosswalk)

    # Review queue: keeps any decisions already made, so regenerating it cannot lose them.
    ledger_lookup = {(r["fotmob_player_id"], r["candidate_tm_player_id"]): r for r in ledger}
    queue = []
    for fid in sorted(identities):
        # Automated decisions stay in the queue so a person can still confirm or overturn them.
        if decisions[fid]["status"] not in ("REVIEW_REQUIRED", "AMBIGUOUS", "AUTO_ADJUDICATED"):
            continue
        identity = identities[fid]
        for c in identity["candidates"][:config["review"]["queue_candidates_per_identity"]]:
            prior = ledger_lookup.get((fid, c["tm_player_id"]), {})
            queue.append({"queue_id": f"{fid}:{c['tm_player_id']}", "fotmob_player_id": fid, "fotmob_names": c["fotmob_names"], "fotmob_dob": c["fotmob_dob"], "fotmob_nationality": c["fotmob_nationality"], "fotmob_club_seasons": c["fotmob_club_seasons"],
                          "fotmob_player_season_rows": season_rows[fid], "identity_status": decisions[fid]["status"], "identity_method": decisions[fid]["method"], "candidate_rank": c["candidate_rank"], "candidate_tm_player_id": c["tm_player_id"],
                          "candidate_name": c["tm_name"], "candidate_dob": c["tm_dob"], "candidate_nationality": c["tm_nationality"], "candidate_position_profile": c["tm_position_profile"], "candidate_club_seasons": c["tm_club_season_labels"], "candidate_url": c["tm_url"],
                          **{k: c[k] for k in ("score", "score_available", "name_exact", "name_similarity", "name_subset", "dob_relation", "nationality_relation", "position_relation", "club_status", "club_season_overlap", "shared_games", "fm_games", "tm_games", "game_jaccard", "transfer_club_overlap", "blocks")},
                          "suggested_decision": c["suggestion"], **{f: prior.get(f, "") for f in REVIEW_FIELDS}})
    write_csv(queue_path, QUEUE_COLUMNS, queue)

    sample, strata = build_validation_sample(candidates, rule_decisions, identities, config)
    sample_path = review_dir / "validation_sample_for_labeling.csv"
    existing = read_csv_rows(sample_path)
    if not any((r.get("human_label") or "").strip() for r in existing):
        write_csv(sample_path, list(sample[0].keys()), sample)

    # Output folder is keyed by version and review content, so runs never overwrite each other.
    ledger_tag = hashlib.sha256(json.dumps(ledger_lookup, sort_keys=True).encode()).hexdigest()[:10] if ledger else "none"
    run_dir = output_root / f"{config['matching_version']}__reviews_{ledger_tag}"
    temp_cw, temp_cd = output_root / "_tmp_cw.parquet", output_root / "_tmp_cd.parquet"
    cw_hash, cd_hash = rows_to_parquet(crosswalk, CROSSWALK_SCHEMA, temp_cw), rows_to_parquet(candidates, CANDIDATE_SCHEMA, temp_cd)
    final_cw, final_cd = run_dir / "player_crosswalk.parquet", run_dir / "matching_candidates.parquet"
    if final_cw.exists() and (file_hash(final_cw) != cw_hash or file_hash(final_cd) != cd_hash):
        temp_cw.unlink(); temp_cd.unlink()
        raise RuntimeError(f"{run_dir} exists with different content. Bump matching_version; it was not overwritten.")
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_cw.replace(final_cw)
    temp_cd.replace(final_cd)

    names = dict(con.execute("SELECT DISTINCT team_id, team_name FROM f_teams").fetchall())
    club_names = dict(con.execute("SELECT home_club_id, any_value(home_club_name) FROM t_games WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024 GROUP BY 1").fetchall())
    team_rows = [{"fotmob_team_id": t, "fotmob_team_name": names.get(t), "tm_club_id": c, "tm_club_name": club_names.get(c)} for t, c in sorted(team_map.items())]
    write_csv(run_dir / "team_crosswalk.csv", ["fotmob_team_id", "fotmob_team_name", "tm_club_id", "tm_club_name"], team_rows)

    unresolved = [{"canonical_player_id": r["canonical_player_id"], "fotmob_player_id": r["fotmob_player_id"], "fotmob_names": r["fotmob_names_raw"], "match_status": r["match_status"], "reason": r["match_method"], "candidate_count": r["candidate_count"],
                   "player_season_rows": r["player_season_rows"], "fotmob_seasons": " | ".join(identities[r["fotmob_player_id"]]["seasons"])} for r in crosswalk if r["match_status"] in ("REVIEW_REQUIRED", "AMBIGUOUS", "UNMATCHED")]
    write_csv(run_dir / "unresolved_identities.csv", ["canonical_player_id", "fotmob_player_id", "fotmob_names", "match_status", "reason", "candidate_count", "player_season_rows", "fotmob_seasons"], unresolved)
    # Each run keeps its own copy of the review files, so later runs can't erase its evidence.
    snapshot = run_dir / "review_snapshot"
    snapshot.mkdir(exist_ok=True)
    for path in (queue_path, sample_path, ledger_path, *([adjudication_path] if adjudication_path else [])):
        if path.exists():
            shutil.copy2(path, snapshot / path.name)

    summary = summarize(crosswalk, candidates, identities, players, team_map, match_map, conflicts, integrity, strata, queue, config)
    summary["tm_appearance_gap"] = appearance_gap(con, crosswalk, identities, players)
    summary["fotmob_identity_stability"] = {
        "ids_with_more_than_one_name_form": sum(1 for i in identities.values() if len(i["names"]) > 1),
        "same_tm_id_mapped_from_multiple_fotmob_ids": len(conflicts),
    }
    summary["automated_adjudications_applied"] = adjudicated
    summary["validation_sample_rows"] = len(sample)
    summary["validation_sample_unique_pairs"] = len({(s["fotmob_player_id"], s["candidate_tm_player_id"]) for s in sample})
    inputs = {str(p.relative_to(ROOT).as_posix()): file_hash(p) for p in sorted(list((FOTMOB_RELEASE / "normalized").glob("*.parquet")) + list((ROOT / "data/transfermarkt/curated/tm_r2_20260905").glob("*.parquet")) + [ROOT / "data/transfermarkt/staging/tm_r2_20260905/stg_games.parquet", ROOT / "data/transfermarkt/staging/tm_r2_20260905/stg_appearances.parquet", CONFIG_PATH])}
    code = {str(p.relative_to(ROOT).as_posix()): file_hash(p) for p in (ROOT / "src/phase3/entity_resolution.py", ROOT / "src/phase3/names.py")}
    write_json(run_dir / "run_manifest.json", {"matching_version": config["matching_version"], "generated_at_utc": now, "code_version": None, "code_version_note": "No git (D5); script hashes recorded instead.", "code_sha256": code, "input_sha256": inputs,
                                               "output_sha256": {str(p.relative_to(run_dir).as_posix()): file_hash(p) for p in sorted(run_dir.rglob("*")) if p.is_file() and p.name not in ("run_manifest.json", "matching_evaluation.json")}, "duckdb_version": duckdb.__version__, "summary": summary})
    return {"run_dir": str(run_dir), "summary": summary, "crosswalk": crosswalk, "candidates": candidates}


def appearance_gap(con, crosswalk: list[dict], identities: dict, players: dict) -> dict:
    """For mapped identities, find where TM's game rows fall short of FotMob's, by season."""
    season_of = {g: label for g, label in con.execute("SELECT game_id, season||'/'||(season+1) FROM t_games WHERE competition_id='GB1' AND season BETWEEN 2019 AND 2024").fetchall()}
    seasons: dict[str, Counter] = defaultdict(Counter)
    for row in crosswalk:
        tid = row["transfermarkt_player_id"]
        if not tid or tid not in players:
            continue
        fm_games, tm_games = identities[row["fotmob_player_id"]]["games"], players[tid]["games"]
        by_season_fm, by_season_tm = defaultdict(set), defaultdict(set)
        for game in fm_games:
            by_season_fm[season_of[game[0]]].add(game)
        for game in tm_games:
            if game[0] in season_of:
                by_season_tm[season_of[game[0]]].add(game)
        for season in set(by_season_fm) | set(by_season_tm):
            missing, extra = by_season_fm[season] - by_season_tm[season], by_season_tm[season] - by_season_fm[season]
            seasons[season]["fotmob_only_game_rows"] += len(missing)
            seasons[season]["tm_only_game_rows"] += len(extra)
            if by_season_fm[season] and not by_season_tm[season]:
                seasons[season]["player_seasons_with_no_tm_rows"] += 1
                seasons[season]["game_rows_in_player_seasons_with_no_tm_rows"] += len(missing)
            elif missing:
                seasons[season]["player_seasons_partially_short"] += 1
    return {season: dict(values) for season, values in sorted(seasons.items())}


def summarize(crosswalk, candidates, identities, players, team_map, match_map, conflicts, integrity, strata, queue, config) -> dict:
    status = Counter(r["match_status"] for r in crosswalk)
    rows_by_status = Counter()
    for r in crosswalk:
        rows_by_status[r["match_status"]] += r["player_season_rows"]
    per_identity = Counter(r["candidate_count"] for r in crosswalk)
    mapped = {r["fotmob_player_id"]: r["transfermarkt_player_id"] for r in crosswalk if r["transfermarkt_player_id"]}
    auto = [c for c in candidates if mapped.get(c["fotmob_player_id"]) == c["tm_player_id"]]
    bins = Counter()
    for c in auto:
        j = c["game_jaccard"]
        bins["1.00" if j == 1 else ">=0.90" if j >= 0.9 else ">=0.50" if j >= 0.5 else ">0" if j > 0 else "0"] += 1
    best_rival = 0
    for c in candidates:
        own = mapped.get(c["fotmob_player_id"])
        if own and c["tm_player_id"] != own and c["game_jaccard"] >= 0.8:
            best_rival += 1
    fm_seasons = defaultdict(Counter)
    for r in crosswalk:
        for season in identities[r["fotmob_player_id"]]["seasons"]:
            fm_seasons[season][r["match_status"]] += 1
    return {
        "fotmob_identities": len(crosswalk), "tm_identities": len(players), "player_season_rows": sum(r["player_season_rows"] for r in crosswalk),
        "fotmob_teams_mapped": len(team_map), "fotmob_matches_aligned": len(match_map), "status_identities": dict(status), "status_player_season_rows": dict(rows_by_status),
        "method_identities": dict(Counter(r["match_method"] for r in crosswalk)), "status_by_season": {s: dict(c) for s, c in sorted(fm_seasons.items())},
        "candidate_pairs": len(candidates), "candidate_count_distribution": {str(k): v for k, v in sorted(per_identity.items())},
        "blocks_pair_counts": dict(Counter(b for c in candidates for b in c["blocks"].split("|"))),
        "suggestion_pair_counts": dict(Counter(c["suggestion"] for c in candidates)),
        "auto_club_status": dict(Counter(c["club_status"] for c in auto)), "auto_game_jaccard_bins": dict(bins),
        "auto_dob_relation": dict(Counter(c["dob_relation"] for c in auto)), "auto_nationality_relation": dict(Counter(c["nationality_relation"] for c in auto)), "auto_position_relation": dict(Counter(c["position_relation"] for c in auto)),
        "auto_matches_with_rival_jaccard_ge_0_8": best_rival,
        "identities_meeting_proposed_high_confidence": len({c["fotmob_player_id"] for c in candidates if c["meets_proposed_high_confidence"] and c["fotmob_player_id"] not in mapped}),
        "tm_id_conflicts": conflicts, "integrity_problems": integrity, "validation_strata": strata,
        "review_queue_rows": len(queue), "review_queue_identities": len({q["fotmob_player_id"] for q in queue}),
        "review_queue_player_season_rows": sum(r["player_season_rows"] for r in crosswalk if r["match_status"] in ("REVIEW_REQUIRED", "AMBIGUOUS")),
    }


def main() -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["auto_high_confidence"]["enabled"]:
        raise RuntimeError("AUTO_HIGH_CONFIDENCE needs a labeled sample and approval, and is not implemented as a mapping path.")
    print(verify_fotmob_unchanged())
    result = run(config, ROOT / "data/phase_03/entity_resolution", REVIEW_DIR)
    print(result["run_dir"])
    print(json.dumps(result["summary"], indent=0, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
