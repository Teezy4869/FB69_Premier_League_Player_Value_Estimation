"""Prompt 03 Tasks A/B: revalidate FotMob-to-Transfermarkt identities with in-scope evidence only.

Nothing in the matching or validation rules is re-implemented:
  * `src.phase3.entity_resolution.run` runs unchanged, with its inputs swapped for scoped views:
    FotMob = rs5 release; Transfermarkt games, appearances and club-seasons = official seasons only.
    Player profiles and transfers are player-level career records and stay whole.
  * The independent identity validator (`src.phase3.step3_qa_validate.judge`, rule_v2) re-labels every in-scope
    mapping from scoped evidence (FotMob rs5 season stats vs Transfermarkt in-scope appearances).
  * Historical automated adjudications are filtered to the rs5 universe; `run` itself refuses any adjudication
    whose candidate no longer appears. RULE-based ones are re-judged on scoped evidence.
Then every in-scope identity is compared with the historical `matching_v2_1` decision.

Usage: python -I src/research_scope/entity_resolution_rs5.py
"""
from __future__ import annotations

import contextlib
import copy
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from src.phase3 import entity_resolution, step3_qa_validate  # noqa: E402
from src.phase3.tm_common import file_hash, verify_fotmob_unchanged, write_json  # noqa: E402
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.build_targets_rs5 import patched, verify_rs5_release  # noqa: E402
from src.research_scope.scope import ROOT, ScopeViolation, load_scope  # noqa: E402

MATCHING_VERSION = "matching_v2_1_rs5"
HISTORICAL_RUN = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none"
HISTORICAL_ADJUDICATIONS = ROOT / "data/phase_03/review/automated_adjudications.csv"
HISTORICAL_VALIDATION = ROOT / "reports/phase_03/step_03_qa/evidence/auto_match_validation_all_1299.csv"
OUT = ROOT / "data/research_rs5/entity_resolution"
REVIEW = ROOT / "data/research_rs5/review"
RUN_DIR = OUT / f"{MATCHING_VERSION}__reviews_none"
VALIDATION_OUT = OUT / f"{MATCHING_VERSION}_identity_validation.csv"
TM_CURATED = ROOT / "data/transfermarkt/curated/tm_r2_20260905"
TM_STAGING = ROOT / "data/transfermarkt/staging/tm_r2_20260905"


def scoped_load_inputs(con) -> None:
    """Same view names as entity_resolution.load_inputs; season-bearing inputs restricted to the official seasons."""
    scope = load_scope()
    years = ", ".join(str(y) for y in scope.tm_start_years)
    fm = FOTMOB_RS5 / "normalized"
    for alias, name in {"f_conf": "confirmed_appeared_player_seasons", "f_players": "players", "f_pts": "player_team_seasons", "f_matches": "matches",
                        "f_pm": "player_match_appearances", "f_pos": "historical_position_observations", "f_teams": "teams"}.items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{(fm / name).as_posix()}.parquet')")
    con.execute(f"CREATE VIEW t_players AS SELECT * FROM read_parquet('{(TM_CURATED / 'tm_players').as_posix()}.parquet')")
    con.execute(f"CREATE VIEW t_transfers AS SELECT * FROM read_parquet('{(TM_CURATED / 'tm_transfers').as_posix()}.parquet')")
    con.execute(f"CREATE VIEW t_pcs AS SELECT * FROM read_parquet('{(TM_CURATED / 'tm_player_club_seasons').as_posix()}.parquet') WHERE season_start_year IN ({years})")
    con.execute(f"CREATE VIEW t_games AS SELECT * FROM read_parquet('{(TM_STAGING / 'stg_games').as_posix()}.parquet') WHERE season IN ({years})")
    con.execute(f"CREATE VIEW t_app AS SELECT * FROM read_parquet('{(TM_STAGING / 'stg_appearances').as_posix()}.parquet') SEMI JOIN t_games USING (game_id)")


def universe() -> set[str]:
    return set(pq.read_table(FOTMOB_RS5 / "normalized/confirmed_appeared_player_seasons.parquet", columns=["player_id"])["player_id"].to_pylist())


def scoped_adjudications(ids: set[str], path: Path) -> dict:
    """Keep historical adjudication rows for in-scope identities, byte-for-byte."""
    with HISTORICAL_ADJUDICATIONS.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    kept = [r for r in rows if r["fotmob_player_id"] in ids]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(kept)
    return {"historical_rows": len(rows), "in_scope_rows": len(kept), "dropped_out_of_scope": sorted(r["fotmob_player_id"] for r in rows if r["fotmob_player_id"] not in ids),
            "in_scope_by_basis": dict(Counter(r["basis"] for r in kept)), "in_scope_by_outcome": dict(Counter(r["outcome"] for r in kept))}


def run_matching(adjudication_path: Path) -> dict:
    config = yaml.safe_load(entity_resolution.CONFIG_PATH.read_text(encoding="utf-8"))
    if config["auto_high_confidence"]["enabled"]:
        raise RuntimeError("AUTO_HIGH_CONFIDENCE must stay disabled")
    config = copy.deepcopy(config)
    config["matching_version"] = MATCHING_VERSION
    with patched(entity_resolution, load_inputs=scoped_load_inputs, FOTMOB_RELEASE=FOTMOB_RS5):
        return entity_resolution.run(config, OUT, REVIEW, adjudication_path)


def validation_labels(crosswalk: list[dict]) -> list[dict]:
    """Re-label every in-scope AUTO_EXACT and RULE-adjudicated mapping with the unchanged rule_v2 on scoped evidence."""
    with patched(step3_qa_validate, FOTMOB_RELEASE=FOTMOB_RS5, V1=RUN_DIR):
        ev = step3_qa_validate.load_evidence()
    # The validator's Transfermarkt performance query covers 2019-2024; keep only official seasons.
    scope = load_scope()
    ev["tm_perf"] = {tid: {s: v for s, v in seasons.items() if s in scope.labels} for tid, seasons in ev["tm_perf"].items()}
    rows = []
    for r in crosswalk:
        if r["match_status"] not in ("AUTO_EXACT", "AUTO_ADJUDICATED") or not r["transfermarkt_player_id"]:
            continue
        result = step3_qa_validate.judge(r["fotmob_player_id"], r["transfermarkt_player_id"], ev)
        rows.append({"fotmob_player_id": r["fotmob_player_id"], "transfermarkt_player_id": r["transfermarkt_player_id"], "match_status": r["match_status"], "fotmob_names": r["fotmob_names_raw"], "tm_name": r["tm_name_raw"],
                     "label": result["label"], "confidence": result["confidence"], "evidence_families_agree": "|".join(result["agree"]), "evidence_families_disagree": "|".join(result["disagree"]),
                     "career_result": result["families"]["CAREER"], "physical_result": result["families"]["PHYSICAL"], "performance_result": result["families"]["PERFORMANCE"],
                     "performance_seasons_compared": result["performance"].get("seasons_compared", 0), "evidence": step3_qa_validate.describe(result),
                     "evidence_scope": f"FotMob {FOTMOB_RS5.name} season stats and profiles; Transfermarkt appearances in official seasons only; transfers and physical profile player-level",
                     "adjudication_method": step3_qa_validate.METHOD, "validator_rule_version": step3_qa_validate.VALIDATOR_RULE_VERSION, "independent_of_name_dob_rule": True, "human_reviewed": False})
    return rows


def compare(crosswalk: list[dict], labels: list[dict], ids: set[str]) -> dict:
    historical = {r["fotmob_player_id"]: r for r in pq.read_table(HISTORICAL_RUN / "player_crosswalk.parquet").to_pylist()}
    with HISTORICAL_VALIDATION.open(encoding="utf-8-sig", newline="") as handle:
        old_labels = {r["fotmob_player_id"]: r["label"] for r in csv.DictReader(handle)}
    new = {r["fotmob_player_id"]: r for r in crosswalk}
    if set(new) != ids:
        raise ScopeViolation("rs5 crosswalk identities differ from the rs5 Confirmed universe")
    changed = []
    for fid in sorted(ids):
        a, b = historical[fid], new[fid]
        if (a["match_status"], a["transfermarkt_player_id"]) != (b["match_status"], b["transfermarkt_player_id"]):
            changed.append({"fotmob_player_id": fid, "names": b["fotmob_names_raw"], "historical_status": a["match_status"], "historical_tm_id": a["transfermarkt_player_id"],
                            "rs5_status": b["match_status"], "rs5_tm_id": b["transfermarkt_player_id"], "rs5_method": b["match_method"]})
    method_changed = sum(historical[f]["match_method"] != new[f]["match_method"] for f in ids)
    label_rows = []
    for r in labels:
        old = old_labels.get(r["fotmob_player_id"])
        label_rows.append((r["match_status"], old, r["label"]))
    transitions = Counter((s, o or "NOT_LABELED_HISTORICALLY", n) for s, o, n in label_rows)
    return {"identities_compared": len(ids), "mapping_changes": changed, "mapping_unchanged": len(ids) - len(changed), "method_label_changes": method_changed,
            "label_transitions": [{"match_status": s, "historical_label": o, "rs5_label": n, "identities": c} for (s, o, n), c in sorted(transitions.items())],
            "auto_exact_labels_changed": sum(c for (s, o, n), c in transitions.items() if s == "AUTO_EXACT" and o != n)}


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    fotmob = verify_fotmob_unchanged()
    rs5 = verify_rs5_release()
    scope = load_scope()
    ids = universe()
    adjudication_path = REVIEW / "automated_adjudications_in_scope.csv"
    adjudications = scoped_adjudications(ids, adjudication_path)
    result = run_matching(adjudication_path)
    crosswalk = result["crosswalk"]
    integrity = entity_resolution.validate_crosswalk(crosswalk)
    labels = validation_labels(crosswalk)
    write_rows(VALIDATION_OUT, labels)
    comparison = compare(crosswalk, labels, ids)
    # The scoped adjudication file and the review inputs this run wrote are part of its evidence.
    shutil.copy2(adjudication_path, RUN_DIR / "review_snapshot" / adjudication_path.name)
    summary = result["summary"]
    status_players = Counter(r["match_status"] for r in crosswalk)
    status_rows = Counter()
    for r in crosswalk:
        status_rows[r["match_status"]] += r["player_season_rows"]
    total_rows = sum(status_rows.values())
    mapped_rows = sum(n for s, n in status_rows.items() if s in entity_resolution.MAPPED_STATUSES)
    report = {
        "matching_version": MATCHING_VERSION, "scope_id": scope.scope_id, "seasons": list(scope.labels), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "entity_resolution.run unchanged with scoped inputs; rule_v2 validator unchanged on scoped evidence", "tm_seasons_used": list(scope.tm_start_years),
        "evidence_not_season_scoped": ["tm_players (profile)", "tm_transfers (career moves)", "FotMob profile careerHistory and physical attributes"],
        "fotmob_v3_1_preflight": fotmob, "fotmob_rs5_preflight": rs5, "adjudications": adjudications, "crosswalk_integrity": integrity,
        "identities": len(crosswalk), "status_identities": dict(status_players), "status_player_season_rows": dict(status_rows), "player_season_rows": total_rows,
        "mapping_coverage_identities_pct": round(100 * sum(status_players[s] for s in entity_resolution.MAPPED_STATUSES) / len(crosswalk), 2),
        "mapping_coverage_player_seasons_pct": round(100 * mapped_rows / total_rows, 2), "comparison_with_matching_v2_1": comparison,
        "validation_labels": {"rows": len(labels), "by_status_label": {f"{s}:{l}": c for (s, l), c in sorted(Counter((r["match_status"], r["label"]) for r in labels).items())}},
        "run_summary": {k: summary[k] for k in ("fotmob_identities", "tm_identities", "fotmob_teams_mapped", "fotmob_matches_aligned", "method_identities", "status_by_season", "automated_adjudications_applied",
                                                  "validation_sample_rows", "fotmob_identity_stability", "tm_appearance_gap") if k in summary},
        "code_sha256": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in (ROOT / "src/research_scope/entity_resolution_rs5.py", ROOT / "src/phase3/entity_resolution.py", ROOT / "src/phase3/step3_qa_validate.py", ROOT / "src/phase3/names.py")},
        "output_sha256": {p.relative_to(OUT).as_posix(): file_hash(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "crosswalk_rs5_manifest.json"},
    }
    write_json(OUT / "crosswalk_rs5_manifest.json", report)
    print(json.dumps({k: report[k] for k in ("identities", "status_identities", "status_player_season_rows", "mapping_coverage_identities_pct", "mapping_coverage_player_seasons_pct", "adjudications")}, indent=1))
    print(json.dumps(comparison, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
