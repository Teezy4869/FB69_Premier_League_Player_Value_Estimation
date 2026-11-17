"""Step 3 QA: automated, rule-based identity adjudication using evidence independent of the match rule.

This is AUTOMATED ADJUDICATION, not human review. Name and birth date are never read as evidence, and
game overlap is never counted as an evidence family.

Families (each agrees, disagrees, is uninformative or is missing):
  CAREER       FotMob senior career clubs vs Transfermarkt transfer clubs, outside the 27 EPL clubs, dated.
  PHYSICAL     Height and preferred foot.
  PERFORMANCE  Season goals, assists, cards and minutes.

Label rule, fixed before results were seen:
  CONFIRMED_MATCH      at least 2 families agree and none disagrees
  CONFIRMED_NON_MATCH  at least 2 families disagree and none agrees
  INCONCLUSIVE         everything else; never counted as positive

Negative controls apply the same rule to pairs of different mapped players, to measure false confirmation.

Usage: python -I src/phase3/step3_qa_validate.py <evidence_dir>
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
from rapidfuzz.fuzz import ratio, token_set_ratio  # noqa: E402

from src.phase3.evaluate_matching import lower_bound  # noqa: E402
from src.phase3.names import normalize_name  # noqa: E402
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT, write_json  # noqa: E402

V1 = ROOT / "data/phase_03/entity_resolution/matching_v1__reviews_none"
STG = ROOT / "data/transfermarkt/staging/tm_r2_20260905"
METHOD = "AUTOMATED_RULE_BASED_ADJUDICATION_NOT_HUMAN_REVIEW"
CLUB_NOISE = {"fc", "afc", "cf", "sc", "ac", "as", "ss", "sv", "fk", "sk", "cd", "ca", "rc", "ud", "sd", "club", "football", "de", "bk", "if", "ssc", "vfl", "vfb", "tsg", "rcd", "cp", "sl", "the", "1", "1899", "1904", "1910", "1846", "1860", "cfp", "kv", "krc", "k", "stade", "spvgg"}
YOUTH = {"u17", "u18", "u19", "u20", "u21", "u22", "u23", "ii", "b", "youth", "academy", "yth", "reserves"}
NOT_CLUBS = {"unknown", "without club", "retired", "career break", "ban", "without"}
CLUB_SIMILARITY = 92
CLUB_SPELLING_SIMILARITY = 88
VALIDATOR_RULE_VERSION = "rule_v2"
DATE_TOLERANCE_YEARS = 1
HEIGHT_AGREE_CM, HEIGHT_DISAGREE_CM = 1, 5
MIN_PERFORMANCE_EVENTS = 3
METRIC_TOLERANCE = 1
MINUTES_AGREE, MINUTES_DISAGREE = 0.10, 0.30


def club_key(name: str | None) -> str | None:
    norm = normalize_name(name)
    if not norm or norm in NOT_CLUBS:
        return None
    tokens = [t for t in norm.split() if t not in CLUB_NOISE and t not in YOUTH]
    return " ".join(tokens) or norm


@lru_cache(maxsize=None)
def clubs_same(a: str, b: str) -> bool:
    """Rule v2 also handles abbreviations (qpr, sheff wed, west brom) and spelling (olympiakos, olympiacos)."""
    if a == b or token_set_ratio(a, b) >= CLUB_SIMILARITY or ratio(a, b) >= CLUB_SPELLING_SIMILARITY:
        return True
    short, long = sorted((a, b), key=len)
    compact = short.replace(" ", "")
    if 2 <= len(compact) <= 5 and " " not in short and compact == "".join(t[0] for t in long.split()):
        return True
    tokens_short, tokens_long = short.split(), long.split()
    return len(tokens_short) >= 2 and all(l.startswith(t) and len(t) >= 3 for t, l in zip(tokens_short, tokens_long))


def career_family(fm_clubs: list[tuple[str, int | None]], tm_moves: list[tuple[str, int | None]], epl_keys: set[str]) -> dict:
    """fm_clubs: (club key, start year); tm_moves: (club key, move year)."""
    fm_non_epl = sorted({k for k, _ in fm_clubs if not any(clubs_same(k, e) for e in epl_keys)})
    shared, dated = [], []
    for club in fm_non_epl:
        hits = [y for k, y in tm_moves if clubs_same(club, k)]
        if hits:
            shared.append(club)
            starts = [y for k, y in fm_clubs if k == club and y is not None]
            if any(abs(s - h) <= DATE_TOLERANCE_YEARS for s in starts for h in hits if h is not None):
                dated.append(club)
    tm_keys = {k for k, _ in tm_moves}
    tm_non_epl = {k for k in tm_keys if not any(clubs_same(k, e) for e in epl_keys)}
    if dated:
        result = "AGREE"
    elif not tm_moves or not fm_clubs:
        result = "MISSING"
    elif len(fm_non_epl) >= 2 and len(tm_non_epl) >= 2 and not shared:
        result = "DISAGREE"
    else:
        result = "UNINFORMATIVE"
    return {"result": result, "shared_non_epl": shared, "dated_non_epl": dated, "fm_non_epl_clubs": len(fm_non_epl), "tm_non_epl_clubs": len(tm_non_epl)}


def physical_family(fm_height, tm_height, fm_foot, tm_foot) -> dict:
    if fm_height is None or tm_height is None:
        height = "MISSING"
    else:
        gap = abs(fm_height - tm_height)
        height = "AGREE" if gap <= HEIGHT_AGREE_CM else "DISAGREE" if gap >= HEIGHT_DISAGREE_CM else "UNINFORMATIVE"
    foot = "MISSING" if not fm_foot or not tm_foot else "AGREE" if fm_foot == tm_foot else "UNINFORMATIVE" if "both" in (fm_foot, tm_foot) else "DISAGREE"
    if height == "DISAGREE" or foot == "DISAGREE":
        result = "DISAGREE"
    elif height == "AGREE" and foot == "AGREE":
        result = "AGREE"
    elif "MISSING" in (height, foot):
        result = "MISSING" if height == foot else "UNINFORMATIVE"
    else:
        result = "UNINFORMATIVE"
    return {"result": result, "height": height, "foot": foot, "fm_height": fm_height, "tm_height": tm_height, "fm_foot": fm_foot, "tm_foot": tm_foot}


def performance_family(fm_seasons: dict, tm_seasons: dict) -> dict:
    """Both dicts: season -> metrics. Only seasons present in both can be compared."""
    compared = sorted(set(fm_seasons) & set(tm_seasons))
    if not compared:
        return {"result": "MISSING", "seasons_compared": 0, "events": 0}
    events, metric_breaks, big_breaks, minute_ok, minute_bad, minute_seen = 0, 0, 0, 0, 0, 0
    for season in compared:
        fm, tm = fm_seasons[season], tm_seasons[season]
        for metric in ("goals", "assists", "yellow_cards", "red_cards"):
            if fm.get(metric) is None:
                continue
            events += int(fm[metric])
            gap = abs(fm[metric] - tm[metric])
            metric_breaks += gap > METRIC_TOLERANCE
            big_breaks += gap >= 3
        if fm.get("minutes") and tm["minutes"]:
            minute_seen += 1
            gap = abs(fm["minutes"] - tm["minutes"]) / max(fm["minutes"], tm["minutes"])
            minute_ok += gap <= MINUTES_AGREE
            minute_bad += gap > MINUTES_DISAGREE
    if big_breaks or (minute_seen and minute_bad == minute_seen):
        result = "DISAGREE"
    elif events >= MIN_PERFORMANCE_EVENTS and not metric_breaks and minute_ok == minute_seen:
        result = "AGREE"
    else:
        result = "UNINFORMATIVE"
    return {"result": result, "seasons_compared": len(compared), "events": events, "metric_breaks": metric_breaks, "minutes_seen": minute_seen, "minutes_ok": minute_ok}


def adjudicate(career: dict, physical: dict, performance: dict) -> dict:
    results = {"CAREER": career["result"], "PHYSICAL": physical["result"], "PERFORMANCE": performance["result"]}
    agree = [k for k, v in results.items() if v == "AGREE"]
    disagree = [k for k, v in results.items() if v == "DISAGREE"]
    if len(agree) >= 2 and not disagree:
        label = "CONFIRMED_MATCH"
    elif len(disagree) >= 2 and not agree:
        label = "CONFIRMED_NON_MATCH"
    else:
        label = "INCONCLUSIVE"
    confidence = "HIGH" if label != "INCONCLUSIVE" and (len(agree) == 3 or len(disagree) == 3) else "MEDIUM" if label != "INCONCLUSIVE" else "NONE"
    return {"label": label, "confidence": confidence, "families": results, "agree": agree, "disagree": disagree}


def upper_population_errors(sample_size: int, errors_found: int, population: int, confidence: float = 0.95) -> int:
    """Largest number of wrong items in the population still consistent with the sample (exact hypergeometric)."""
    alpha = 1 - confidence
    largest = errors_found
    for wrong in range(errors_found, population + 1):
        total = comb(population, sample_size)
        tail = sum(comb(wrong, k) * comb(population - wrong, sample_size - k) for k in range(0, errors_found + 1)) / total
        if tail >= alpha:
            largest = wrong
        else:
            break
    return largest


def sensitivity_error_bound(observed_non_matches: int, detection_rate: float, confidence: float = 0.95) -> int:
    """Largest number of wrong pairs consistent with the non-matches seen, if a wrong pair is flagged at this rate."""
    largest = observed_non_matches
    wrong = observed_non_matches
    while wrong <= 5000:
        tail = sum(comb(wrong, k) * detection_rate**k * (1 - detection_rate) ** (wrong - k) for k in range(0, observed_non_matches + 1))
        if tail < 1 - confidence:
            break
        largest = wrong
        wrong += 1
    return largest


def load_evidence() -> dict:
    con = duckdb.connect()
    con.execute("SET threads=1")
    fm = FOTMOB_RELEASE / "normalized"
    players = con.execute(f"""SELECT p.player_id, p.profile_raw_path FROM read_parquet('{(fm / 'players.parquet').as_posix()}') p
        SEMI JOIN read_parquet('{(fm / 'confirmed_appeared_player_seasons.parquet').as_posix()}') c USING (player_id) ORDER BY 1""").fetchall()
    fm_info = {}
    for fid, path in players:
        body = json.loads((ROOT / path).read_text(encoding="utf-8"))
        height, foot, country = None, None, None
        for item in body.get("playerInformation") or []:
            value = item.get("value") or {}
            if item.get("title") == "Height":
                height = value.get("numberValue")
            elif item.get("title") == "Preferred foot":
                foot = (value.get("key") or value.get("fallback") or "").lower() or None
            elif item.get("title") == "Country":
                country = value.get("fallback")
        clubs = []
        items = ((body.get("careerHistory") or {}).get("careerItems") or {})
        for entry in (items.get("senior") or {}).get("teamEntries") or []:
            key = club_key(entry.get("team"))
            if key:
                start = entry.get("startDate")
                clubs.append((key, int(start[:4]) if start else None))
        fm_info[fid] = {"height": height, "foot": foot, "country": country, "clubs": clubs}
    tm_info = defaultdict(lambda: {"moves": [], "height": None, "foot": None, "country_of_birth": None, "city_of_birth": None})
    for tid, height, foot, country, city in con.execute(f"SELECT player_id, height_in_cm, foot, country_of_birth, city_of_birth FROM read_parquet('{(STG / 'stg_players.parquet').as_posix()}')").fetchall():
        tm_info[tid].update(height=height, foot=foot, country_of_birth=country, city_of_birth=(city or "").replace("\xa0", " ").strip() or None)
    for tid, day, frm, to in con.execute(f"SELECT player_id, transfer_date, from_club_name, to_club_name FROM read_parquet('{(STG / 'stg_transfers.parquet').as_posix()}') WHERE transfer_date<=DATE '2026-09-05'").fetchall():
        for name in (frm, to):
            key = club_key(name)
            if key:
                tm_info[tid]["moves"].append((key, day.year if day else None))
    fm_perf: dict[str, dict] = defaultdict(dict)
    for fid, season, goals, assists, yellow, red, minutes in con.execute(f"SELECT player_id, season_label, m_goals, m_assists, m_yellow_cards, m_red_cards, m_minutes_played FROM read_parquet('{(FOTMOB_RELEASE / 'curated/confirmed_appeared_player_seasons.parquet').as_posix()}')").fetchall():
        fm_perf[fid][season] = {"goals": goals, "assists": assists, "yellow_cards": yellow, "red_cards": red, "minutes": minutes}
    tm_perf: dict[str, dict] = defaultdict(dict)
    for tid, season, goals, assists, yellow, red, minutes in con.execute(f"""SELECT a.player_id, g.season||'/'||(g.season+1), sum(a.goals), sum(a.assists), sum(a.yellow_cards), sum(a.red_cards), sum(a.minutes_played)
        FROM read_parquet('{(STG / 'stg_appearances.parquet').as_posix()}') a JOIN read_parquet('{(STG / 'stg_games.parquet').as_posix()}') g USING (game_id)
        WHERE a.competition_id='GB1' AND g.season BETWEEN 2019 AND 2024 GROUP BY 1,2""").fetchall():
        tm_perf[tid][season] = {"goals": goals, "assists": assists, "yellow_cards": yellow, "red_cards": red, "minutes": minutes}
    with (V1 / "team_crosswalk.csv").open(encoding="utf-8-sig", newline="") as handle:
        epl = set()
        for row in csv.DictReader(handle):
            epl.update(filter(None, (club_key(row["fotmob_team_name"]), club_key(row["tm_club_name"]))))
    return {"fm": fm_info, "tm": tm_info, "fm_perf": fm_perf, "tm_perf": tm_perf, "epl": epl}


def judge(fid: str, tid: str, ev: dict) -> dict:
    fm, tm = ev["fm"][fid], ev["tm"][tid]
    career = career_family(fm["clubs"], tm["moves"], ev["epl"])
    physical = physical_family(fm["height"], tm["height"], fm["foot"], tm["foot"])
    performance = performance_family(ev["fm_perf"].get(fid, {}), ev["tm_perf"].get(tid, {}))
    return {"career": career, "physical": physical, "performance": performance, **adjudicate(career, physical, performance)}


def describe(result: dict) -> str:
    c, p, f = result["career"], result["physical"], result["performance"]
    return (f"CAREER {c['result']}: dated non-EPL clubs {c['dated_non_epl']}; PHYSICAL {p['result']}: FotMob {p['fm_height']}cm/{p['fm_foot']} vs TM {p['tm_height']}cm/{p['tm_foot']}; "
            f"PERFORMANCE {f['result']}: {f.get('seasons_compared', 0)} seasons, {f.get('events', 0)} events.")


def stable(seed: str, *parts: str) -> str:
    return hashlib.sha256("|".join((seed, *parts)).encode()).hexdigest()


def main() -> None:
    evidence = Path(sys.argv[1])
    ev = load_evidence()
    con = duckdb.connect()
    rows = con.execute(f"SELECT fotmob_player_id, transfermarkt_player_id, match_status, fotmob_names_raw, tm_name_raw FROM read_parquet('{(V1 / 'player_crosswalk.parquet').as_posix()}') ORDER BY 1").fetchall()
    mapped = {r[0]: r[1] for r in rows if r[1]}
    with (V1 / "review_snapshot/validation_sample_for_labeling.csv").open(encoding="utf-8-sig", newline="") as handle:
        sample_pairs = [(r["fotmob_player_id"], r["candidate_tm_player_id"]) for r in csv.DictReader(handle) if r["stratum"] == "AUTO_EXACT_RANDOM"]
    if len(sample_pairs) != 300 or any(mapped.get(f) != t for f, t in sample_pairs):
        raise RuntimeError("Fixed random sample does not match the v1 automatic mappings")

    judged = {fid: judge(fid, tid, ev) for fid, tid in mapped.items()}
    out: dict = {"method": METHOD, "rule": "CONFIRMED_MATCH: >=2 families agree, none disagrees. CONFIRMED_NON_MATCH: >=2 disagree, none agrees. Otherwise INCONCLUSIVE."}

    def tally(pairs):
        return dict(Counter(judged[f]["label"] for f, _ in pairs))

    sample_counts = tally(sample_pairs)
    all_counts = tally(list(mapped.items()))
    out["sample_300"] = {"labels": sample_counts, "family_results": {fam: dict(Counter(judged[f]["families"][fam] for f, _ in sample_pairs)) for fam in ("CAREER", "PHYSICAL", "PERFORMANCE")}}
    out["all_1299"] = {"labels": all_counts, "family_results": {fam: dict(Counter(judged[f]["families"][fam] for f in mapped)) for fam in ("CAREER", "PHYSICAL", "PERFORMANCE")}, "confidence": dict(Counter(judged[f]["confidence"] for f in mapped))}
    decided = sample_counts.get("CONFIRMED_MATCH", 0) + sample_counts.get("CONFIRMED_NON_MATCH", 0)
    ok, wrong = sample_counts.get("CONFIRMED_MATCH", 0), sample_counts.get("CONFIRMED_NON_MATCH", 0)
    out["statistics"] = {
        "sample": 300, "decided": decided, "confirmed": ok, "non_match": wrong, "inconclusive": 300 - decided,
        "precision_among_decided": ok / decided if decided else None, "clopper_pearson_95_lower_among_decided": round(lower_bound(ok, decided), 5),
        "conservative_verified_share_of_sample": ok / 300, "clopper_pearson_95_lower_verified_share": round(lower_bound(ok, 300), 5),
        "assumption_note": "The among-decided bound assumes inconclusive pairs resemble decided ones. The verified-share bound assumes nothing about inconclusive pairs and counts them as unverified, not as errors.",
    }

    # Negative controls: pairs of different mapped players, so a correct validator should not confirm them.
    club_seasons = defaultdict(set)
    for fid, team in con.execute(f"""SELECT player_id, season_id||':'||team_id FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/player_team_seasons.parquet').as_posix()}') WHERE validation_status='CONFIRMED'""").fetchall():
        if fid in mapped:
            club_seasons[team].add(fid)
    teammates = defaultdict(set)
    for members in club_seasons.values():
        for fid in members:
            teammates[fid].update(members - {fid})
    ordered = sorted(mapped)
    controls: dict[str, list] = {"RANDOM_OTHER_PLAYER": [], "RANDOM_TEAMMATE": [], "MOST_SIMILAR_BODY_TEAMMATE": []}
    for fid in ordered:
        random_other = min((o for o in ordered if o != fid), key=lambda o: stable("neg-random", fid, o))
        controls["RANDOM_OTHER_PLAYER"].append((fid, mapped[random_other]))
        if teammates[fid]:
            mates = sorted(teammates[fid])
            controls["RANDOM_TEAMMATE"].append((fid, mapped[min(mates, key=lambda o: stable("neg-mate", fid, o))]))
            height, foot = ev["fm"][fid]["height"], ev["fm"][fid]["foot"]
            def closeness(o):
                tm = ev["tm"][mapped[o]]
                gap = abs((height or 0) - (tm["height"] or 0)) if height and tm["height"] else 99
                return (gap, 0 if foot == tm["foot"] else 1, stable("neg-body", fid, o))
            controls["MOST_SIMILAR_BODY_TEAMMATE"].append((fid, mapped[min(mates, key=closeness)]))
    out["negative_controls"] = {}
    false_confirmed = []
    for name, pairs in controls.items():
        results = [judge(f, t, ev) for f, t in pairs]
        labels = Counter(r["label"] for r in results)
        fc = labels.get("CONFIRMED_MATCH", 0)
        out["negative_controls"][name] = {"pairs": len(pairs), "labels": dict(labels), "false_confirmation_rate": fc / len(pairs), "false_confirmation_95_upper": round(1 - lower_bound(len(pairs) - fc, len(pairs)), 5),
                                          "family_agree_rate": {fam: round(sum(r["families"][fam] == "AGREE" for r in results) / len(results), 4) for fam in ("CAREER", "PHYSICAL", "PERFORMANCE")},
                                          "family_disagree_rate": {fam: round(sum(r["families"][fam] == "DISAGREE" for r in results) / len(results), 4) for fam in ("CAREER", "PHYSICAL", "PERFORMANCE")}}
        false_confirmed += [{"control": name, "fotmob_player_id": f, "tm_player_id": t, "families": r["families"], "evidence": describe(r)} for (f, t), r in zip(pairs, results) if r["label"] == "CONFIRMED_MATCH"]
    out["negative_control_false_confirmations"] = false_confirmed[:50]
    labels = out["all_1299"]["labels"]
    x = labels.get("CONFIRMED_NON_MATCH", 0)
    out["sensitivity_bound_all_1299"] = {
        "observed_non_matches": x, "population": len(mapped),
        "note": "Model-based, not a sample estimate. Assumes a wrong mapping behaves like the named control pair, and that the validator flags it at that rate.",
        **{name: {"non_match_detection_rate": round(v["labels"].get("CONFIRMED_NON_MATCH", 0) / v["pairs"], 4), "max_wrong_pairs_95": sensitivity_error_bound(x, v["labels"].get("CONFIRMED_NON_MATCH", 0) / v["pairs"]),
                   "implied_min_precision": round(1 - sensitivity_error_bound(x, v["labels"].get("CONFIRMED_NON_MATCH", 0) / v["pairs"]) / len(mapped), 5)} for name, v in out["negative_controls"].items()},
    }
    out["statistics"]["finite_population_max_wrong_95_if_decided_is_random"] = upper_population_errors(decided, wrong, len(mapped))
    out["validator_rule_version"] = VALIDATOR_RULE_VERSION
    out["true_vs_control_note"] = {"confirmed_share_true_pairs": labels.get("CONFIRMED_MATCH", 0) / len(mapped)}

    names = {r[0]: (r[3], r[4]) for r in rows}
    columns = ["fotmob_player_id", "transfermarkt_player_id", "fotmob_names", "tm_name", "label", "confidence", "evidence_families_agree", "evidence_families_disagree", "career_result", "physical_result", "performance_result", "evidence", "evidence_source", "reasoning", "adjudication_method", "independent_of_name_dob_rule", "human_reviewed"]

    def record(fid, tid, result):
        return {"fotmob_player_id": fid, "transfermarkt_player_id": tid, "fotmob_names": names[fid][0], "tm_name": names[fid][1], "label": result["label"], "confidence": result["confidence"], "evidence_families_agree": "|".join(result["agree"]), "evidence_families_disagree": "|".join(result["disagree"]),
                "career_result": result["families"]["CAREER"], "physical_result": result["families"]["PHYSICAL"], "performance_result": result["families"]["PERFORMANCE"], "evidence": describe(result),
                "evidence_source": "FotMob raw profile (careerHistory, playerInformation) and curated season metrics; Transfermarkt players, transfers and appearances", "reasoning": f"Rule outcome: {len(result['agree'])} agree, {len(result['disagree'])} disagree.", "adjudication_method": METHOD, "independent_of_name_dob_rule": True, "human_reviewed": False}

    evidence.mkdir(parents=True, exist_ok=True)
    for name, pairs in (("auto_match_validation_sample_300.csv", sample_pairs), ("auto_match_validation_all_1299.csv", sorted(mapped.items()))):
        with (evidence / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(record(f, t, judged[f]) for f, t in pairs)

    # The 44 unresolved identities, each with all candidates.
    candidates = con.execute(f"""SELECT d.fotmob_player_id, d.tm_player_id, d.candidate_rank, d.fotmob_names, d.tm_name, d.fotmob_dob, d.tm_dob, d.dob_relation, d.name_similarity, d.name_subset, d.game_jaccard, d.shared_games, d.fm_games, d.tm_games, d.nationality_relation, d.fotmob_nationality, d.tm_nationality, d.suggestion, d.tm_url
        FROM read_parquet('{(V1 / 'matching_candidates.parquet').as_posix()}') d JOIN read_parquet('{(V1 / 'player_crosswalk.parquet').as_posix()}') w USING (fotmob_player_id) WHERE w.transfermarkt_player_id IS NULL ORDER BY 1, 3""").fetchall()
    keys = ["fotmob_player_id", "tm_player_id", "candidate_rank", "fotmob_names", "tm_name", "fotmob_dob", "tm_dob", "dob_relation", "name_similarity", "name_subset", "game_jaccard", "shared_games", "fm_games", "tm_games", "nationality_relation", "fotmob_nationality", "tm_nationality", "suggestion", "tm_url"]
    unresolved = []
    for row in candidates:
        item = dict(zip(keys, row))
        result = judge(item["fotmob_player_id"], item["tm_player_id"], ev)
        item.update(label=result["label"], confidence=result["confidence"], career_result=result["families"]["CAREER"], physical_result=result["families"]["PHYSICAL"], performance_result=result["families"]["PERFORMANCE"], evidence=describe(result))
        unresolved.append(item)
    write_json(evidence / "unresolved_44_automated_evidence.json", {"method": METHOD, "candidates": unresolved})

    # Nationality disagreements in automatic mappings, with supporting birth country.
    nationality = con.execute(f"""SELECT d.fotmob_player_id, d.tm_player_id, d.fotmob_names, d.tm_name, d.fotmob_nationality, d.tm_nationality, d.fotmob_dob, d.game_jaccard, d.tm_url
        FROM read_parquet('{(V1 / 'matching_candidates.parquet').as_posix()}') d JOIN read_parquet('{(V1 / 'player_crosswalk.parquet').as_posix()}') w ON d.fotmob_player_id=w.fotmob_player_id AND d.tm_player_id=w.transfermarkt_player_id WHERE d.nationality_relation='DISAGREE' ORDER BY 1""").fetchall()
    out["nationality_disagreements"] = [{"fotmob_player_id": n[0], "tm_player_id": n[1], "fotmob_name": n[2], "tm_name": n[3], "fotmob_nationality": n[4], "tm_nationality": n[5], "dob": n[6], "game_jaccard": n[7], "tm_url": n[8], "tm_country_of_birth": ev["tm"][n[1]]["country_of_birth"], "tm_city_of_birth": ev["tm"][n[1]]["city_of_birth"],
                                         "label": judged[n[0]]["label"], "families": judged[n[0]]["families"], "evidence": describe(judged[n[0]])} for n in nationality]
    out["position_disagreements"] = [dict(zip(("fm_position", "tm_position", "n"), r)) for r in con.execute(f"""SELECT w.position_relation, 1, count(*) FROM read_parquet('{(V1 / 'matching_candidates.parquet').as_posix()}') w JOIN read_parquet('{(V1 / 'player_crosswalk.parquet').as_posix()}') x ON w.fotmob_player_id=x.fotmob_player_id AND w.tm_player_id=x.transfermarkt_player_id GROUP BY 1""").fetchall()]
    weak = [record(f, mapped[f], judged[f]) for f in sorted(mapped) if judged[f]["label"] != "CONFIRMED_MATCH" and (judged[f]["disagree"] or judged[f]["label"] == "CONFIRMED_NON_MATCH")]
    out["auto_with_any_disagreeing_family"] = weak
    write_json(evidence / "auto_match_validation_summary.json", out)
    print(json.dumps({k: out[k] for k in ("sample_300", "all_1299", "statistics", "negative_controls", "sensitivity_bound_all_1299")}, default=str))
    print("NON_MATCH or disagree count", len(weak))
    for w in weak[:40]:
        print(w["fotmob_names"], "|", w["tm_name"], "|", w["label"], "|", w["evidence"][:230])
    print("-- nationality")
    for n in out["nationality_disagreements"]:
        print(n["fotmob_name"], n["fotmob_nationality"], n["tm_nationality"], "birth", n["tm_country_of_birth"], n["tm_city_of_birth"], n["label"], n["families"], n["game_jaccard"])
    print("-- unresolved rank1")
    for u in unresolved:
        if u["candidate_rank"] == 1:
            print(u["fotmob_names"], "|", u["tm_name"], "|", u["label"], u["confidence"], u["career_result"], u["physical_result"], u["performance_result"], u["dob_relation"], u["game_jaccard"])


if __name__ == "__main__":
    main()
