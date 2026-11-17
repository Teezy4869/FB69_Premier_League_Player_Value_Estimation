"""Validate the integrated dataset against frozen sources, and write missingness and leakage evidence.

Read-only on the release. Re-reads source files directly rather than trusting the build's own log.

Usage: python -I src/phase3/validate_integration.py <release_dir> <evidence_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
FM = ROOT / "data/releases/fotmob_epl_2019_2025_v3_1"
TARGET = ROOT / "data/phase_03/targets/target_v1__matching_v2_1/player_season_target.parquet"
CROSSWALK = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet"
DICTIONARY = FM / "manifests/metric_dictionary_v3.csv"
FORBIDDEN_COLUMNS = ("market_value_in_eur", "highest_market_value", "current_position", "current_team_id", "player_current_club", "next_valuation", "next_value", "contract_expiration")
PREDICTOR_ROLES = ("FEATURE_FOTMOB_METRIC", "FEATURE_STATUS_FOTMOB", "CONTEXT_FEATURE")
XG_FAMILY = ("expected_goals", "expected_assists", "non_penalty_xg", "expected_goals_on_target")


def check(results: list, name: str, passed: bool, detail) -> None:
    results.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def validate(con, release: Path) -> list:
    results: list = []
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    n = one("SELECT count(*) FROM d")
    check(results, "row count equals frozen Confirmed population", n == one("SELECT count(*) FROM conf") == 3262, n)
    check(results, "one row per canonical player-season", one("SELECT count(DISTINCT (canonical_player_id, season)) FROM d") == n, one("SELECT count(DISTINCT (canonical_player_id, season)) FROM d"))
    check(results, "one row per FotMob player-season", one("SELECT count(DISTINCT (fotmob_player_id, season_id)) FROM d") == n, n)
    check(results, "distinct players", one("SELECT count(DISTINCT canonical_player_id) FROM d") == 1343, one("SELECT count(DISTINCT canonical_player_id) FROM d"))
    check(results, "no key is null", one("SELECT count(*) FROM d WHERE canonical_player_id IS NULL OR season IS NULL OR fotmob_player_id IS NULL") == 0, 0)
    missing = one("SELECT count(*) FROM (SELECT player_id, season_label FROM conf EXCEPT SELECT fotmob_player_id, season FROM d)")
    extra = one("SELECT count(*) FROM (SELECT fotmob_player_id, season FROM d EXCEPT SELECT player_id, season_label FROM conf)")
    check(results, "no Confirmed row lost and none added", missing == 0 and extra == 0, {"lost": missing, "extra": extra})
    unverified = one("SELECT count(*) FROM d SEMI JOIN unv ON d.fotmob_player_id=unv.player_id AND d.season_id=unv.season_id")
    check(results, "no Unverified row entered", unverified == 0, unverified)
    check(results, "population status is Confirmed appeared only", one("SELECT count(*) FROM d WHERE population_status<>'APPEARED' OR population_category<>'CONFIRMED_APPEARED'") == 0, 0)
    check(results, "crosswalk key unique", one("SELECT count(*)-count(DISTINCT fotmob_player_id) FROM cw") == 0, 0)
    check(results, "crosswalk TM ID unique", one("SELECT count(transfermarkt_player_id)-count(DISTINCT transfermarkt_player_id) FROM cw") == 0, 0)
    check(results, "target key unique", one("SELECT count(*)-count(DISTINCT (canonical_player_id, season)) FROM t") == 0, 0)
    columns = [r[0] for r in con.execute("DESCRIBE d").fetchall()]
    metric_cols = [c for c in columns if c.startswith("m_") or c.startswith("s_")]
    source_cols = [r[0] for r in con.execute("DESCRIBE cur").fetchall()]
    feature_diffs = sum(one(f'SELECT count(*) FROM d JOIN cur c ON d.fotmob_player_id=c.player_id AND d.season_id=c.season_id WHERE d."{c}" IS DISTINCT FROM c."{c}"') for c in metric_cols)
    check(results, "FotMob feature values and nulls identical to source", feature_diffs == 0 and set(metric_cols) == {c for c in source_cols if c.startswith(("m_", "s_"))}, {"cells_different": feature_diffs, "columns": len(metric_cols)})
    new_zeros = sum(one(f'SELECT count(*) FROM d JOIN cur c ON d.fotmob_player_id=c.player_id AND d.season_id=c.season_id WHERE c."{c}" IS NULL AND d."{c}"=0') for c in metric_cols if c.startswith("m_"))
    check(results, "no null feature became zero", new_zeros == 0, new_zeros)
    target_fields = [("target_market_value", "market_value"), ("target_valuation_date", "selected_valuation_date"), ("target_season_end_date", "season_end_date"), ("target_valuation_age_days", "valuation_age_days"), ("target_status", "target_status"), ("target_source_row_number", "source_row_number"), ("transfermarkt_player_id", "transfermarkt_player_id"), ("crosswalk_status", "crosswalk_status"), ("identity_evidence_tier", "identity_evidence_tier")]
    target_diffs = sum(one(f"SELECT count(*) FROM d JOIN t ON d.canonical_player_id=t.canonical_player_id AND d.season=t.season WHERE d.{a} IS DISTINCT FROM t.{b}") for a, b in target_fields)
    check(results, "target fields identical to target dataset", target_diffs == 0, target_diffs)
    check(results, "no selected valuation after cutoff", one("SELECT count(*) FROM d WHERE target_valuation_date>target_season_end_date") == 0, 0)
    check(results, "age equals cutoff minus date", one("SELECT count(*) FROM d WHERE target_valuation_date IS NOT NULL AND target_valuation_age_days<>date_diff('day', target_valuation_date, target_season_end_date)") == 0, 0)
    check(results, "missing target stays null, no zero", one("SELECT count(*) FROM d WHERE target_market_value=0") == 0 and one("SELECT count(*) FROM d WHERE target_status='TARGET_MISSING' AND target_market_value IS NOT NULL") == 0, 0)
    check(results, "missing target count", one("SELECT count(*) FROM d WHERE target_market_value IS NULL") == 67, one("SELECT count(*) FROM d WHERE target_market_value IS NULL"))
    check(results, "no future valuation date exceeds a later valuation substitute", one("SELECT count(*) FROM d JOIN raw_v v ON v.player_id=d.transfermarkt_player_id AND v.d=d.target_valuation_date WHERE v.d>d.target_season_end_date") == 0, 0)
    check(results, "target value equals original CSV row", one("SELECT count(*) FROM d JOIN raw_v v ON v.rn=d.target_source_row_number WHERE v.m<>d.target_market_value OR v.player_id<>d.transfermarkt_player_id") == 0 and one("SELECT count(*) FROM d WHERE target_market_value IS NOT NULL AND target_source_row_number IS NULL") == 0, 0)
    check(results, "unresolved identities retained without target", one("SELECT count(*) FROM d WHERE crosswalk_status='REVIEW_REQUIRED'") == 3 and one("SELECT count(*) FROM d WHERE crosswalk_status='REVIEW_REQUIRED' AND (transfermarkt_player_id IS NOT NULL OR target_market_value IS NOT NULL)") == 0, 3)
    check(results, "no automated match labeled human", one("SELECT count(*) FROM d WHERE identity_human_reviewed OR crosswalk_status='MANUAL_CONFIRMED'") == 0, 0)
    check(results, "adjudicated rows name an automated adjudicator", one("SELECT count(*) FROM d WHERE crosswalk_status='AUTO_ADJUDICATED' AND (identity_review_status<>'AUTOMATED_ADJUDICATION_NOT_HUMAN' OR identity_adjudicator NOT LIKE 'automated:%')") == 0, 0)
    check(results, "2019/20 rows retained and flagged", one("SELECT count(*) FROM d WHERE season='2019/2020'") == 515 and one("SELECT count(*) FROM d WHERE sensitivity_season_2019_20")==515 and one("SELECT count(*) FROM d WHERE xg_xa_unavailable_for_comparison")==515 and one("SELECT count(*) FROM d WHERE xg_xa_unavailable_for_comparison AND season<>'2019/2020'")==0, 515)
    check(results, "April 2020 batch flagged on 491 rows, values unchanged", one("SELECT count(*) FROM d WHERE target_on_2020_04_08_batch")==491 and one("SELECT count(*) FROM d WHERE target_on_2020_04_08_batch AND target_valuation_date<>DATE '2020-04-08'")==0, 491)
    classes = dict(con.execute("SELECT multi_club_class, count(*) FROM d GROUP BY 1").fetchall())
    check(results, "multi-club classes reconcile (61 + 19 = 80)", classes == {"SINGLE_CLUB": 3182, "MULTI_CLUB_CONFIRMED_APPEARANCES": 61, "MULTI_CLUB_SQUAD_ONLY": 19} and one("SELECT count(*) FROM d WHERE is_multi_club")==80, classes)
    check(results, "multi-club players are not duplicated", one("SELECT count(*) FROM (SELECT canonical_player_id, season FROM d WHERE is_multi_club GROUP BY 1,2 HAVING count(*)>1)") == 0, 0)
    clubs = pq.read_table(release / "player_team_season_evidence.parquet", columns=["canonical_player_id"]).num_rows
    check(results, "club evidence retained separately", clubs == 3342, clubs)
    forbidden = [c for c in columns if any(f in c for f in FORBIDDEN_COLUMNS)]
    check(results, "no forbidden present-day or future column", not forbidden, forbidden)
    with (release / "data_dictionary.csv").open(encoding="utf-8-sig", newline="") as handle:
        roles = {r["column"]: r["role"] for r in csv.DictReader(handle)}
    check(results, "every column has a role", set(roles) == set(columns), len(roles))
    predictors = [c for c, r in roles.items() if r in PREDICTOR_ROLES]
    check(results, "target and audit columns are not predictors", not [c for c in predictors if c.startswith(("target_", "temporal_", "identity_"))], len(predictors))
    return results


def missingness(con) -> dict:
    def rows(sql):
        cursor = con.execute(sql)
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, r)) for r in cursor.fetchall()]

    base = "count(*) n, count(target_market_value) with_value, count(*)-count(target_market_value) missing_value, count(*)-count(target_valuation_date) missing_valuation_date, count(*)-count(transfermarkt_player_id) missing_tm_id, round(avg(missing_feature_count),2) mean_missing_features"
    out = {dim: rows(f"SELECT {dim}, {base} FROM d GROUP BY 1 ORDER BY 1") for dim in ("season", "target_status", "target_missing_reason", "crosswalk_status", "identity_evidence_tier", "multi_club_class", "position_group_season", "temporal_alignment_class", "target_staleness_bucket")}
    out["identity_fields_missing"] = {c: con.execute(f"SELECT count(*)-count({c}) FROM d").fetchone()[0] for c in ("canonical_player_id", "fotmob_player_name", "fotmob_birth_date", "nationality_profile_present_day", "transfermarkt_player_id")}
    metrics = [r[0] for r in con.execute("DESCRIBE d").fetchall() if r[0].startswith("m_")]
    per_metric = []
    for metric in metrics:
        record = {"metric": metric, "null_total": con.execute(f'SELECT count(*)-count("{metric}") FROM d').fetchone()[0]}
        for season, nulls in con.execute(f'SELECT season, count(*)-count("{metric}") FROM d GROUP BY 1 ORDER BY 1').fetchall():
            record[season] = nulls
        per_metric.append(record)
    out["per_metric_nulls"] = per_metric
    out["missing_feature_count_distribution"] = rows("SELECT season, min(missing_feature_count) min_missing, median(missing_feature_count) median_missing, max(missing_feature_count) max_missing FROM d GROUP BY 1 ORDER BY 1")
    return out


def leakage_table(con, evidence: Path) -> list:
    with DICTIONARY.open(encoding="utf-8-sig", newline="") as handle:
        dictionary = {r["normalized_field"]: r for r in csv.DictReader(handle)}
    windows = defaultdict(dict)
    with (evidence / "feature_window_audit.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            windows[row["metric"]][row["season"]] = row
    starts = con.execute("SELECT count(m_starts), count(*) FILTER (WHERE m_starts=started_match_count) FROM d").fetchone()
    cards = con.execute("""SELECT metric, compared, agree FROM (SELECT 'yellow_cards' metric, count(*) compared, count(*) FILTER (WHERE abs(d.m_yellow_cards-x.y)<=1) agree FROM d JOIN tm_cards x ON x.player_id=d.transfermarkt_player_id AND x.season=d.season WHERE d.m_yellow_cards IS NOT NULL
        UNION ALL SELECT 'red_cards', count(*), count(*) FILTER (WHERE abs(d.m_red_cards-x.r)<=1) FROM d JOIN tm_cards x ON x.player_id=d.transfermarkt_player_id AND x.season=d.season WHERE d.m_red_cards IS NOT NULL)""").fetchall()
    card_info = {m: (c, a) for m, c, a in cards}
    table = []
    for metric in sorted(windows):
        by_season = windows[metric]
        statuses = {s: r["window_status"] for s, r in by_season.items()}
        entry = dictionary.get(metric, {})
        definition = f"{entry.get('source_titles') or metric}; {entry.get('aggregation_type') or 'unknown'} aggregation; unit {entry.get('unit') or 'unknown'}"
        verified = [s for s, v in statuses.items() if v in ("FULL_EPL_SEASON_VERIFIED", "RARE_EVENT_CONSISTENT")]
        other = {s: v for s, v in statuses.items() if s not in verified}
        rate = metric.endswith(("per90", "percent", "accuracy", "percentage"))
        concern = "Season total includes matches after the selected valuation date: temporal alignment limitation under objective A, not leakage. Collected retrospectively in November 2026."
        if metric == "key_passes":
            observation, conclusion, concern = "No values in any season", "NO_DATA", "None; the column is empty."
        elif metric == "starts":
            observation, conclusion = (f"Full EPL season: equals confirmed starts on {starts[1]} of {starts[0]} rows", "USABLE_WITH_ALIGNMENT_LIMIT")
        elif metric in card_info:
            observation, conclusion = (f"Consistent with EPL season: within 1 of Transfermarkt totals on {card_info[metric][1]} of {card_info[metric][0]} rows; no FotMob per-match field", "USABLE_WITH_ALIGNMENT_LIMIT")
        elif metric in XG_FAMILY:
            bad = sorted(s for s in other if s != "2019/2020")
            observation = "Full EPL season verified for later seasons; **2019/20 from 4 of 380 matches**" + (f"; {', '.join(bad)} below verification threshold" if bad else "")
            conclusion = "USABLE_EXCEPT_2019_20_COMPARISON"
            concern = "2019/20 values are not season measures (D7: unavailable for comparison). " + concern
        elif rate:
            observation, conclusion = "Rate derived from season totals; rate itself not checked against match data", "RATE_WINDOW_NOT_DIRECTLY_VERIFIED"
        elif not other:
            observation, conclusion = "Full EPL season, verified against match sums in all seasons", "USABLE_WITH_ALIGNMENT_LIMIT"
        elif verified:
            observation = f"Verified for {', '.join(sorted(verified))}; not verified for {', '.join(sorted(other))}"
            conclusion = "PARTLY_VERIFIED_USE_WITH_CARE"
        else:
            observation, conclusion = "Observation window could not be verified from match data", "WINDOW_NOT_VERIFIED"
        table.append({"feature": f"m_{metric}", "paired_status_column": f"s_{metric}", "source": "FotMob v3.1 season metrics (" + (entry.get("candidate_source_endpoints") or "see release") + ")", "definition": definition, "observation_period": observation, "available_by_season_end": "Yes" if metric != "key_passes" else "No values", "leakage_concern": concern, "conclusion": conclusion})
    table += [
        {"feature": "age_at_season_end_years", "paired_status_column": "", "source": "FotMob birth date; config cutoff", "definition": "Derived: (season end minus birth date) / 365.25", "observation_period": "As of season end", "available_by_season_end": "Yes", "leakage_concern": "None temporally. 4 birth dates are disputed. In 2019/20 the target cut depends on birth year, so age relates to the target by construction that season.", "conclusion": "USABLE_WITH_CARE_2019_20"},
        {"feature": "position_group_season", "paired_status_column": "", "source": "FotMob historical lineups", "definition": "Most common known lineup position group in that season", "observation_period": "Full EPL season", "available_by_season_end": "Yes", "leakage_concern": "Uses the whole season, so partly after the valuation date. Historical, not the present-day profile.", "conclusion": "USABLE_WITH_ALIGNMENT_LIMIT"},
        {"feature": "confirmed_team_ids, confirmed_team_count, multi_club_class", "paired_status_column": "", "source": "FotMob lineups", "definition": "Clubs with confirmed appearances or squad rows that season", "observation_period": "Full EPL season", "available_by_season_end": "Yes", "leakage_concern": "Club may reflect a transfer that came after the valuation date. Club can proxy for value, which is a modeling issue, not leakage.", "conclusion": "CONTEXT_REVIEW_IN_PHASE_4"},
        {"feature": "nationality_profile_present_day", "paired_status_column": "", "source": "FotMob profile collected November 2026", "definition": "Single current nationality", "observation_period": "Present day, not historical", "available_by_season_end": "**No, not established**", "leakage_concern": "Post-season information. Some players changed national team after the research seasons (for example Andre Brooks, Malang Sarr).", "conclusion": "NOT_A_HISTORICAL_FEATURE"},
    ]
    with (evidence / "feature_leakage_table.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    return table


def main() -> int:
    release, evidence = Path(sys.argv[1]), Path(sys.argv[2])
    evidence.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    for alias, path in dict(d=release / "player_season_integrated_v1.parquet", cur=FM / "curated/confirmed_appeared_player_seasons.parquet", conf=FM / "normalized/confirmed_appeared_player_seasons.parquet", unv=FM / "normalized/unverified_player_seasons.parquet", t=TARGET, cw=CROSSWALK).items():
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    raw = (ROOT / "data/transfermarkt/source/tm_r2_20260905/player_valuations.csv.gz").as_posix()
    con.execute(f"CREATE TABLE raw_v AS SELECT row_number() OVER () rn, player_id, try_cast(date AS DATE) d, try_cast(market_value_in_eur AS BIGINT) m FROM read_csv('{raw}', all_varchar=true, header=true)")
    stg = ROOT / "data/transfermarkt/staging/tm_r2_20260905"
    con.execute(f"""CREATE TABLE tm_cards AS SELECT a.player_id, g.season||'/'||(g.season+1) season, sum(a.yellow_cards) y, sum(a.red_cards) r FROM read_parquet('{(stg / 'stg_appearances.parquet').as_posix()}') a JOIN read_parquet('{(stg / 'stg_games.parquet').as_posix()}') g USING (game_id) WHERE a.competition_id='GB1' GROUP BY 1,2""")
    results = validate(con, release)
    failed = [r for r in results if r["status"] != "PASS"]
    write = lambda name, payload: (evidence / name).write_text(json.dumps(payload, indent=1, default=str, ensure_ascii=False) + "\n", encoding="utf-8")  # noqa: E731
    write("validation_summary.json", {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "checks": len(results), "passed": len(results) - len(failed), "failed": len(failed), "results": results})
    write("missingness.json", missingness(con))
    table = leakage_table(con, evidence)
    print(f"checks {len(results)}, failed {len(failed)}")
    for row in failed:
        print("FAIL", row)
    from collections import Counter
    print(Counter(r["conclusion"] for r in table))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
