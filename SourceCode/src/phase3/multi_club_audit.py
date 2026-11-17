"""Step 5: explain the 80 versus 61 multi-club counts, row by row. Read-only; Transfermarkt is audit evidence only.

Usage: python -I src/phase3/multi_club_audit.py <evidence_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
FM = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
CROSSWALK = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
PCS = ROOT / "data/transfermarkt/curated/tm_r2_20260905/tm_player_club_seasons.parquet"


def main() -> None:
    evidence = Path(sys.argv[1])
    evidence.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    for alias, rel in dict(conf="normalized/confirmed_appeared_player_seasons", pts="normalized/player_team_seasons", pm="normalized/player_match_appearances", cur="curated/confirmed_appeared_player_seasons").items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{(FM / (rel + '.parquet')).as_posix()}')")
    con.execute(f"CREATE VIEW cw AS SELECT * FROM read_parquet('{CROSSWALK.as_posix()}')")
    con.execute(f"CREATE VIEW pcs AS SELECT * FROM read_parquet('{PCS.as_posix()}')")
    rows = con.execute("""
        SELECT n.season_label, n.player_id, n.player_name, n.team_names, n.confirmed_team_count, n.associated_team_count, n.is_multi_club, n.confirmed_appearance_count,
               (SELECT count(*) FROM pts t WHERE t.player_id=n.player_id AND t.season_id=n.season_id AND t.validation_status='CONFIRMED') confirmed_relations,
               (SELECT count(*) FROM pts t WHERE t.player_id=n.player_id AND t.season_id=n.season_id AND t.validation_status<>'CONFIRMED') unconfirmed_relations,
               (SELECT count(*) FROM pm p WHERE p.player_id=n.player_id AND p.season_id=n.season_id AND p.participation_status IN ('STARTED','SUBSTITUTED_ON')) appeared_rows,
               (SELECT count(DISTINCT p.team_id) FROM pm p WHERE p.player_id=n.player_id AND p.season_id=n.season_id AND p.participation_status IN ('STARTED','SUBSTITUTED_ON')) clubs_with_appearance,
               (SELECT count(*) FROM pm p WHERE p.player_id=n.player_id AND p.season_id=n.season_id AND p.participation_status='UNKNOWN') unknown_rows,
               (SELECT count(DISTINCT p.team_id) FROM pm p WHERE p.player_id=n.player_id AND p.season_id=n.season_id) clubs_any_squad_row,
               c.m_appearances,
               (SELECT count(DISTINCT x.club_name) FROM cw w JOIN pcs x ON x.tm_player_id=w.transfermarkt_player_id WHERE w.fotmob_player_id=n.player_id AND x.season_label=n.season_label) tm_clubs_with_games,
               (SELECT string_agg(x.club_name, ' | ' ORDER BY x.club_name) FROM cw w JOIN pcs x ON x.tm_player_id=w.transfermarkt_player_id WHERE w.fotmob_player_id=n.player_id AND x.season_label=n.season_label) tm_club_names
        FROM conf n JOIN cur c ON c.player_id=n.player_id AND c.season_id=n.season_id WHERE n.is_multi_club OR n.confirmed_team_count>=2 ORDER BY 1, 3""").fetchall()
    names = ["season", "fotmob_player_id", "player_name", "team_names", "confirmed_team_count", "associated_team_count", "is_multi_club", "confirmed_appearance_count", "confirmed_relations", "unconfirmed_relations", "appeared_rows", "clubs_with_appearance", "unknown_rows", "clubs_any_squad_row", "m_appearances", "tm_clubs_with_games", "tm_club_names"]
    records = [dict(zip(names, r)) for r in rows]
    for record in records:
        record["multi_club_class"] = "MULTI_CLUB_CONFIRMED_APPEARANCES" if record["confirmed_team_count"] >= 2 else "MULTI_CLUB_SQUAD_ONLY"
    with (evidence / "multi_club_investigation.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*names, "multi_club_class"])
        writer.writeheader()
        writer.writerows(records)
    single = con.execute("SELECT count(*), count(*) FILTER (WHERE (SELECT count(DISTINCT p.team_id) FROM pm p WHERE p.player_id=n.player_id AND p.season_id=n.season_id)>1) FROM conf n WHERE NOT n.is_multi_club").fetchone()
    summary = {
        "class_counts": dict(Counter(r["multi_club_class"] for r in records)),
        "by_season": {s: dict(Counter(r["multi_club_class"] for r in records if r["season"] == s)) for s in sorted({r["season"] for r in records})},
        "flag_with_two_clubs_any_squad_row": sum(r["clubs_any_squad_row"] == 2 for r in records), "flagged_total": len(records),
        "clubs_with_appearance_by_class": {c: dict(Counter(r["clubs_with_appearance"] for r in records if r["multi_club_class"] == c)) for c in {r["multi_club_class"] for r in records}},
        "tm_club_count_by_class": {c: dict(Counter(r["tm_clubs_with_games"] for r in records if r["multi_club_class"] == c)) for c in {r["multi_club_class"] for r in records}},
        "appearances_equal_season_metric_confirmed": sum(r["m_appearances"] == r["confirmed_appearance_count"] for r in records if r["multi_club_class"] == "MULTI_CLUB_CONFIRMED_APPEARANCES"),
        "appeared_rows_equal_appearances": sum(r["appeared_rows"] == r["confirmed_appearance_count"] for r in records),
        "single_club_rows": single[0], "single_club_rows_with_second_club_in_any_squad_row": single[1],
    }
    (evidence / "multi_club_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    main()
