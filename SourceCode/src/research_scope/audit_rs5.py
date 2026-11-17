"""Prompt 04: data quality, temporal alignment, leakage and feature reliability audit of the rs5 integrated dataset.

Read-only. Nothing is removed, imputed or recoded. Writes evidence files (CSV/JSON) under <out_dir>:
  feature_window_audit_rs5.csv        per metric-season window check (unchanged Phase 3 logic on rs5 FotMob)
  quality_audit.json                  structural, completeness, statistical and reliability results
  temporal_audit.json                 temporal indicators with explicit denominators
  missingness_by_feature_season.csv   null rate per metric and season, with the status breakdown
  metric_distribution_by_season.csv   distribution summary per metric and season
  leakage_audit.csv                   one row per column of the integrated dataset
  feature_reliability.csv             one row per candidate feature

Usage: python -I src/research_scope/audit_rs5.py <out_dir>
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase3 import feature_window_audit  # noqa: E402
from src.phase3.tm_common import file_hash  # noqa: E402
from src.research_scope.build_fotmob_rs5 import RELEASE as FOTMOB_RS5  # noqa: E402
from src.research_scope.build_targets_rs5 import patched  # noqa: E402
from src.research_scope.integrate_rs5 import RELEASE, column_role  # noqa: E402
from src.research_scope.scope import ROOT, load_scope  # noqa: E402

DATASET = RELEASE / "player_season_integrated_rs5_v1.parquet"
HISTORICAL_WINDOWS = ROOT / "reports/phase_03/step_05/evidence/feature_window_audit.csv"
PERCENT = ("aerials_won_percent", "duels_won_percent", "cross_accuracy", "long_ball_accuracy", "passing_accuracy", "save_percentage")
MAY_BE_NEGATIVE = ("goals_prevented",)
STATUS_VOCAB = {"OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED", "MISSING", "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING"}
OBSERVED = {"OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED"}
VERIFIED = {"FULL_EPL_SEASON_VERIFIED", "RARE_EVENT_CONSISTENT"}
EXTREME_IQR = 3.0
HIGH_TARGET_CORRELATION = 0.8


def feature_windows(out: Path) -> tuple[list[dict], dict]:
    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0], str(out / "_fw")]
        with patched(feature_window_audit, FM=FOTMOB_RS5):
            feature_window_audit.main()
    finally:
        sys.argv = old_argv
    (out / "_fw/feature_window_audit.csv").replace(out / "feature_window_audit_rs5.csv")
    (out / "_fw").rmdir()
    with (out / "feature_window_audit_rs5.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    labels = set(load_scope().labels)
    with HISTORICAL_WINDOWS.open(encoding="utf-8-sig", newline="") as handle:
        old = [r for r in csv.DictReader(handle) if r["season"] in labels]
    key = lambda r: (r["metric"], r["season"])  # noqa: E731
    same = {key(r): r for r in old} == {key(r): r for r in rows}
    return rows, {"rows": len(rows), "identical_to_historical_in_scope_rows": same, "seasons": sorted({r["season"] for r in rows})}


def q(con, sql):
    return con.execute(sql).fetchall()


def quality(con, df: pd.DataFrame, metrics: list[str], groups: dict) -> tuple[dict, list[dict], list[dict]]:
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    invalid = {
        "negative_metric_values": {m: int((df[f"m_{m}"] < 0).sum()) for m in metrics if m not in MAY_BE_NEGATIVE and (df[f"m_{m}"] < 0).sum()},
        "percent_outside_0_100": {m: int(((df[f"m_{m}"] < 0) | (df[f"m_{m}"] > 100)).sum()) for m in PERCENT if (((df[f"m_{m}"] < 0) | (df[f"m_{m}"] > 100)).sum())},
        "rating_outside_0_10": int(((df.m_rating < 0) | (df.m_rating > 10)).sum()),
        "starts_greater_than_appearances": int((df.m_starts > df.m_appearances).sum()),
        "appearances_over_38": int((df.m_appearances > 38).sum()),
        "minutes_per_appearance_over_120": int(((df.m_minutes_played / df.m_appearances) > 120).sum()),
        "shots_on_target_greater_than_shots": int((df.m_shots_on_target > df.m_shots).sum()),
        "goals_greater_than_shots": int((df.m_goals > df.m_shots).sum()),
        "age_outside_15_45": int(((df.age_at_season_end_years < 15) | (df.age_at_season_end_years > 45)).sum()),
        "target_not_positive": int((df.target_market_value <= 0).sum()),
        "m_appearances_differs_from_confirmed_appearances": int((df.m_appearances.notna() & (df.m_appearances != df.confirmed_appearance_count)).sum()),
    }
    categories = {"position_group_season": dict(Counter(df.position_group_season)), "target_status": dict(Counter(df.target_status)), "multi_club_class": dict(Counter(df.multi_club_class)),
                  "temporal_alignment_class": dict(Counter(df.temporal_alignment_class)), "crosswalk_status": dict(Counter(df.crosswalk_status)), "target_currency": dict(Counter(df.target_currency.fillna("NULL")))}
    status_values = set()
    for m in metrics:
        status_values |= set(df[f"s_{m}"].dropna())
    inconsistent = {m: {"null_value_with_observed_status": int((df[f"m_{m}"].isna() & df[f"s_{m}"].isin(OBSERVED)).sum()),
                        "value_with_non_observed_status": int((df[f"m_{m}"].notna() & ~df[f"s_{m}"].isin(OBSERVED)).sum())} for m in metrics}
    inconsistent = {m: v for m, v in inconsistent.items() if any(v.values())}
    missing_rows, dist_rows = [], []
    seasons = sorted(df.season.unique())
    for m in metrics:
        for season in ["ALL", *seasons]:
            part = df if season == "ALL" else df[df.season == season]
            values, status = part[f"m_{m}"], part[f"s_{m}"]
            counts = Counter(status)
            missing_rows.append({"metric": m, "metric_group": groups.get(m, ""), "season": season, "rows": len(part), "null": int(values.isna().sum()), "null_pct": round(100 * values.isna().mean(), 2),
                                 **{f"status_{k}": counts.get(k, 0) for k in sorted(STATUS_VOCAB)}})
            v = values.dropna()
            if len(v):
                q1, q3 = v.quantile(0.25), v.quantile(0.75)
                iqr = q3 - q1
                extreme = int(((v > q3 + EXTREME_IQR * iqr) | (v < q1 - EXTREME_IQR * iqr)).sum()) if iqr > 0 else 0
                dist_rows.append({"metric": m, "season": season, "n": len(v), "mean": round(v.mean(), 4), "median": round(v.median(), 4), "p01": round(v.quantile(0.01), 4), "p99": round(v.quantile(0.99), 4),
                                  "min": round(v.min(), 4), "max": round(v.max(), 4), "zero_share_pct": round(100 * (v == 0).mean(), 2), "extreme_beyond_3iqr": extreme})
    per_player = df.groupby("canonical_player_id").missing_feature_count.mean()
    by_group = {}
    for m in metrics:
        g = groups.get(m, "UNKNOWN")
        by_group.setdefault(g, [0, 0])
        by_group[g][0] += int(df[f"m_{m}"].isna().sum())
        by_group[g][1] += len(df)
    season_shift = []
    for m in metrics:
        cov = [100 * df[df.season == s][f"m_{m}"].notna().mean() for s in seasons]
        med = [df[df.season == s][f"m_{m}"].median() for s in seasons]
        med_ok = [x for x in med if x is not None and not math.isnan(x)]
        ratio = (max(med_ok) / min(med_ok)) if med_ok and min(med_ok) > 0 else None
        if max(cov) - min(cov) > 20 or (ratio and ratio > 2):
            season_shift.append({"metric": m, "coverage_pct_by_season": [round(c, 1) for c in cov], "median_by_season": [None if x is None or math.isnan(x) else round(x, 3) for x in med],
                                 "coverage_range_pp": round(max(cov) - min(cov), 1), "median_max_over_min": round(ratio, 2) if ratio else None})
    reliability = {
        "status_cells": {k: int(sum((df[f"s_{m}"] == k).sum() for m in metrics)) for k in sorted(STATUS_VOCAB)},
        "unexpected_status_values": sorted(status_values - STATUS_VOCAB),
        "metric_value_status_inconsistencies": inconsistent,
        "rows_with_unresolved_substitute_matches": int((df.unresolved_substitute_count > 0).sum()), "unresolved_substitute_matches": int(df.unresolved_substitute_count.sum()),
        "fotmob_unknown_player_match_records_in_scope": one(f"SELECT count(*) FROM read_parquet('{(FOTMOB_RS5 / 'normalized/player_match_appearances.parquet').as_posix()}') WHERE participation_status='UNKNOWN'"),
        "unverified_player_seasons_outside_population": one(f"SELECT count(*) FROM read_parquet('{(FOTMOB_RS5 / 'normalized/unverified_player_seasons.parquet').as_posix()}')"),
        "rows_with_any_conflicting_metric": int(sum((df[[f's_{m}' for m in metrics]] == "CONFLICTING").any(axis=1))),
        "profile_status": dict(Counter(df.profile_status)),
        "birth_date_missing": int(df.fotmob_birth_date.isna().sum()),
    }
    out = {
        "structural": {"rows": len(df), "columns": df.shape[1], "duplicate_keys": int(df.duplicated(["canonical_player_id", "season"]).sum()), "duplicate_full_rows": int(df.drop(columns=[]).astype(str).duplicated().sum()),
                       "invalid_values": invalid, "categories": categories, "dtypes": {c: str(t) for c, t in df.dtypes.items() if not c.startswith(("m_", "s_"))}},
        "completeness": {"null_metric_cells": int(df.missing_feature_count.sum()), "metric_cells": len(df) * len(metrics), "null_metric_cell_pct": round(100 * df.missing_feature_count.sum() / (len(df) * len(metrics)), 2),
                         "missing_feature_count_distribution": {k: round(v, 2) for k, v in df.missing_feature_count.describe().items()},
                         "mean_null_metrics_usable_target": round(df[df.target_usable].missing_feature_count.mean(), 2), "mean_null_metrics_missing_target": round(df[~df.target_usable].missing_feature_count.mean(), 2),
                         "mean_null_metrics_by_position": {k: round(v, 2) for k, v in df.groupby("position_group_season").missing_feature_count.mean().items()},
                         "mean_null_metrics_by_season": {k: round(v, 2) for k, v in df.groupby("season").missing_feature_count.mean().items()},
                         "per_player_mean_null_metrics_quantiles": {str(k): round(v, 2) for k, v in per_player.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).items()},
                         "null_pct_by_metric_group": {g: round(100 * a / b, 2) for g, (a, b) in sorted(by_group.items())},
                         "missing_targets": int((~df.target_usable).sum()), "missing_target_reasons": dict(Counter(df[~df.target_usable].target_missing_reason)),
                         "metrics_without_values_in_some_season": sorted({r["metric"] for r in missing_rows if r["season"] != "ALL" and r["null"] == r["rows"]})},
        "statistical": {"season_level_shifts": season_shift, "extreme_values_total": int(sum(r["extreme_beyond_3iqr"] for r in dist_rows if r["season"] == "ALL")),
                        "target_by_season": {s: {k: round(float(v), 1) for k, v in df[(df.season == s) & df.target_usable].target_market_value.describe().items()} for s in seasons},
                        "age_by_season": {s: {k: round(float(v), 2) for k, v in df[df.season == s].age_at_season_end_years.describe().items()} for s in seasons}},
        "reliability": reliability,
    }
    return out, missing_rows, dist_rows


def temporal(con, df: pd.DataFrame, windows: list[dict]) -> dict:
    scope = load_scope()
    usable = df[df.target_usable]
    pm = (FOTMOB_RS5 / "normalized/player_match_appearances.parquet").as_posix()
    # Independent recomputation from FotMob match dates, not from the temporal_* columns.
    con.execute(f"CREATE TEMP TABLE app AS SELECT player_id, season_label, substr(match_date_utc,1,10)::DATE d FROM read_parquet('{pm}') WHERE participation_status IN ('STARTED','SUBSTITUTED_ON')")
    con.register("u", usable[["fotmob_player_id", "season", "target_valuation_date", "target_season_end_date"]])
    after_total = con.execute("SELECT count(*) FILTER (WHERE a.d > u.target_valuation_date), count(*) FROM u JOIN app a ON a.player_id=u.fotmob_player_id AND a.season_label=u.season").fetchone()
    by_season = {}
    for s in scope.labels:
        part = usable[usable.season == s]
        a = con.execute(f"SELECT count(*) FILTER (WHERE a.d > u.target_valuation_date), count(*) FROM u JOIN app a ON a.player_id=u.fotmob_player_id AND a.season_label=u.season WHERE u.season='{s}'").fetchone()
        share = (part.temporal_player_games_after_valuation / part.temporal_player_games_in_season).where(part.temporal_player_games_in_season > 0)
        by_season[s] = {"usable_targets": len(part), "targets_older_than_90_days": int((part.target_valuation_age_days > 90).sum()), "pct_targets_older_than_90_days": round(100 * (part.target_valuation_age_days > 90).mean(), 2),
                        "median_age_days": float(part.target_valuation_age_days.median()), "appearances_after_valuation": a[0], "appearances": a[1], "pct_appearances_after_valuation": round(100 * a[0] / a[1], 2),
                        "mean_share_of_each_players_games_after_valuation_pct": round(100 * share.mean(), 2), "league_games_after_valuation_median": float(part.temporal_league_games_after_valuation.median()),
                        "rows_all_games_after_valuation": int((part.temporal_alignment_class == "ALL_GAMES_AFTER_VALUATION").sum()), "rows_all_games_before": int((part.temporal_alignment_class == "ALL_GAMES_ON_OR_BEFORE_VALUATION").sum())}
    from_columns = (int(usable.temporal_player_games_after_valuation.sum()), int(usable.temporal_player_games_in_season.sum()))
    minutes_after = usable.temporal_minutes_after_valuation.sum() / (usable.temporal_minutes_after_valuation.sum() + usable.temporal_minutes_before_or_on_valuation.sum())
    match_dates = dict(q(con, f"SELECT season_label, max(substr(match_date_utc,1,10)) FROM read_parquet('{(FOTMOB_RS5 / 'normalized/matches.parquet').as_posix()}') WHERE match_status='COMPLETED' GROUP BY 1"))
    first_dates = dict(q(con, f"SELECT season_label, min(substr(match_date_utc,1,10)) FROM read_parquet('{(FOTMOB_RS5 / 'normalized/matches.parquet').as_posix()}') WHERE match_status='COMPLETED' GROUP BY 1"))
    cutoff = {s.season: {"cutoff": s.season_end_date.isoformat(), "last_completed_match": match_dates[s.season], "first_completed_match": first_dates[s.season], "config_first_match": s.first_match_date.isoformat(),
                         "last_match_equals_cutoff": match_dates[s.season] == s.season_end_date.isoformat(), "dataset_cutoff_matches_scope": bool((df[df.season == s.season].target_season_end_date == s.season_end_date).all())} for s in scope.seasons}
    appearances_after_cutoff = con.execute("SELECT count(*) FROM u JOIN app a ON a.player_id=u.fotmob_player_id AND a.season_label=u.season WHERE a.d > u.target_season_end_date").fetchone()[0]
    collected = q(con, f"SELECT min(collected_at_utc), max(collected_at_utc) FROM read_parquet('{(FOTMOB_RS5 / 'normalized/metric_observations.parquet').as_posix()}')")[0]
    window_status = Counter((r["window_status"]) for r in windows)
    ages = usable.target_valuation_age_days
    return {
        "definitions": {
            "pct_targets_older_than_90_days": "numerator: usable targets (target_usable) with target_valuation_age_days > 90; denominator: usable targets",
            "pct_appearances_after_valuation": "numerator: confirmed FotMob appearances (STARTED or SUBSTITUTED_ON) of usable-target player-seasons dated after target_valuation_date; denominator: all confirmed appearances of those player-seasons. Recomputed from FotMob match dates",
            "valuation_age_days": "target_season_end_date - target_valuation_date",
            "pct_minutes_after_valuation": "minutes after valuation / (minutes before or on + after), usable rows with per-match minutes"},
        "overall": {"usable_targets": len(usable), "targets_older_than_90_days": int((ages > 90).sum()), "pct_targets_older_than_90_days": round(100 * (ages > 90).mean(), 2),
                    "appearances_after_valuation": after_total[0], "appearances": after_total[1], "pct_appearances_after_valuation": round(100 * after_total[0] / after_total[1], 2),
                    "temporal_columns_agree_with_recomputation": from_columns == (after_total[0], after_total[1]), "pct_minutes_after_valuation": round(100 * minutes_after, 2),
                    "age_days_quantiles": {str(k): float(v) for k, v in ages.quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]).items()},
                    "staleness_bins": dict(Counter(usable.target_staleness_bucket)), "targets_over_365_days": int((ages > 365).sum()),
                    "valuation_after_cutoff": int((usable.target_valuation_date > usable.target_season_end_date).sum()), "valuations_before_season_start": int(sum(usable.target_valuation_date < pd.Series([load_scope().by_label(s).first_match_date for s in usable.season], index=usable.index))),
                    "alignment_class": dict(Counter(usable.temporal_alignment_class))},
        "by_season": by_season, "season_cutoffs": cutoff, "appearances_after_cutoff": appearances_after_cutoff,
        "valuation_date_by_month": dict(sorted(Counter(pd.to_datetime(usable.target_valuation_date).dt.strftime("%Y-%m")).items())),
        "feature_collection_window_utc": {"first": collected[0], "last": collected[1]}, "feature_window_status_counts": dict(window_status),
        "objective_a_note": "Prediction time under A is the season end. All FotMob features are season totals through the last match, which is on the cutoff date, so they are available at prediction time. The target, however, is the latest published valuation, typically months earlier; features include matches the valuation could not reflect.",
    }


def spearman(df: pd.DataFrame, cols: list[str]) -> dict:
    usable = df[df.target_usable]
    logv = usable.target_market_value.map(math.log)
    out = {}
    for c in cols:
        x = usable[c]
        if x.dtype == object or str(x.dtype).startswith(("string", "str")):
            continue
        mask = x.notna()
        if mask.sum() >= 30 and x[mask].nunique() > 1:
            out[c] = round(float(x[mask].rank().corr(logv[mask].rank())), 4)
    return out


PER90_TOTALS = {"accurate_long_passes_per90": "accurate_long_passes", "accurate_passes_per90": "accurate_passes", "blocks_per90": "blocked_shots", "clearances_per90": "clearances", "goals_conceded_per90": "goals_conceded",
                "interceptions_per90": "interceptions", "recoveries_per90": "recoveries", "shots_on_target_per90": "shots_on_target", "shots_per90": "shots", "tackles_per90": "tackles"}
TM_STAGING = ROOT / "data/transfermarkt/staging/tm_r2_20260905"


def indirect_window_evidence(con, df: pd.DataFrame) -> dict:
    """Checks for metrics without a per-match field: rate = total * 90 / minutes; starts vs confirmed starts; cards vs Transfermarkt."""
    out = {}
    for rate, total in PER90_TOTALS.items():
        m = df[[f"m_{rate}", f"m_{total}", "m_minutes_played"]].dropna()
        m = m[m.m_minutes_played > 0]
        if len(m):
            calc = m[f"m_{total}"] * 90 / m.m_minutes_played
            share = float(((m[f"m_{rate}"] - calc).abs() <= 0.01 + 0.02 * calc.abs()).mean())
            out[rate] = {"check": f"equals {total} * 90 / minutes_played (tolerance 0.01 + 2%)", "compared": len(m), "agree_pct": round(100 * share, 2), "consistent": share >= 0.98}
        else:
            out[rate] = {"check": f"equals {total} * 90 / minutes_played", "compared": 0, "agree_pct": None, "consistent": False, "note": "No row has both the rate and minutes (goalkeepers mostly lack minutes)"}
    s = df[df.m_starts.notna()]
    share = float((s.m_starts == s.started_match_count).mean())
    out["starts"] = {"check": "equals confirmed STARTED lineup count", "compared": len(s), "agree_pct": round(100 * share, 2), "consistent": share >= 0.98}
    years = ", ".join(str(y) for y in load_scope().tm_start_years)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE tm_cards AS SELECT a.player_id tid, g.season||'/'||(g.season+1) season, sum(a.yellow_cards) y, sum(a.red_cards) r
        FROM read_parquet('{(TM_STAGING / 'stg_appearances.parquet').as_posix()}') a JOIN read_parquet('{(TM_STAGING / 'stg_games.parquet').as_posix()}') g USING (game_id)
        WHERE a.competition_id='GB1' AND g.season IN ({years}) GROUP BY 1,2""")
    con.register("cards", df[["transfermarkt_player_id", "season", "m_yellow_cards", "m_red_cards"]])
    for metric, col in (("yellow_cards", "y"), ("red_cards", "r")):
        n, ok = con.execute(f"SELECT count(*), count(*) FILTER (WHERE abs(c.m_{metric} - t.{col}) <= 1) FROM cards c JOIN tm_cards t ON t.tid=c.transfermarkt_player_id AND t.season=c.season WHERE c.m_{metric} IS NOT NULL").fetchone()
        out[metric] = {"check": "within 1 of Transfermarkt EPL total (independent source)", "compared": n, "agree_pct": round(100 * ok / n, 2) if n else None, "consistent": bool(n) and ok / n >= 0.95}
    return out


def leakage(df: pd.DataFrame, windows: list[dict], groups: dict, rho: dict, indirect: dict) -> list[dict]:
    status = {}
    for r in windows:
        status.setdefault(r["metric"], {})[r["season"]] = r["window_status"]
    rows = []
    multi_season_players = int((df.groupby("canonical_player_id").size() > 1).sum())
    for c in df.columns:
        role = column_role(c)
        entry = {"column": c, "role": role, "candidate_predictor": role.startswith("FEATURE") or role == "CONTEXT_FEATURE", "spearman_with_log_target": rho.get(c)}
        if c.startswith("m_"):
            m = c[2:]
            st = status.get(m, {})
            verified = [s for s, v in st.items() if v in VERIFIED]
            common = "Available by season end (prediction time under A); includes matches after the valuation date: temporal alignment limit, not target leakage"
            values = set(st.values())
            if values == {"NO_SEASON_VALUES"}:
                cls, ev = "WARNING", "No values in any season; nothing to leak, nothing to use"
            elif len(verified) == len(st):
                cls, ev = "WARNING", f"Window verified against EPL match sums in all {len(st)} seasons. {common}"
            elif "NO_SEASON_VALUES" in values:
                cls, ev = "REQUIRES RESEARCH DECISION", f"No values in {', '.join(sorted(s for s, v in st.items() if v == 'NO_SEASON_VALUES'))}; verified for {', '.join(sorted(verified)) or 'none'}. Season-dependent availability"
            elif verified:
                cls, ev = "REQUIRES RESEARCH DECISION", f"Window verified only for {', '.join(sorted(verified))}; other seasons: {', '.join(sorted(f'{s}={v}' for s, v in st.items() if v not in VERIFIED))}"
            elif m in indirect and indirect[m]["consistent"]:
                i = indirect[m]
                cls, ev = "WARNING", f"No per-match field; indirect check: {i['check']} on {i['agree_pct']}% of {i['compared']} rows. {common}"
            elif m in indirect:
                i = indirect[m]
                cls, ev = "WARNING", f"Not verifiable: {i.get('note', i['check'])}. Source season value assumed. {common}"
            else:
                cls, ev = "WARNING", f"Not independently verifiable (source-reported rate or GK count; no per-match field). No contradicting evidence. {common}"
            if entry["spearman_with_log_target"] is not None and abs(entry["spearman_with_log_target"]) >= HIGH_TARGET_CORRELATION:
                cls, ev = "REQUIRES RESEARCH DECISION", ev + f"; |Spearman| with log target >= {HIGH_TARGET_CORRELATION}"
            entry.update(family=groups.get(m, ""), classification=cls, evidence=ev)
        elif c.startswith("s_"):
            entry.update(family=groups.get(c[2:], ""), classification="WARNING", evidence="Status describes the source record (observed, missing, unverified position, unsupported, conflicting); same window as its metric. UNVERIFIED_POSITION encodes lineup-position evidence, not the target")
        elif c == "age_at_season_end_years":
            entry.update(classification="PASS", evidence="Birth date (fixed) and the cutoff date; known at prediction time. The 2019/20 age-linked revaluation is out of scope")
        elif c == "position_group_season":
            entry.update(classification="WARNING", evidence="Modal lineup position over the whole season; partly after the valuation date. Historical lineups, not the present-day profile")
        elif role == "CLUB_CONTEXT":
            entry.update(classification="REQUIRES RESEARCH DECISION", evidence="Season club relations; a mid-season move can come after the valuation date, and club can proxy value. Not a candidate predictor by default")
        elif c == "nationality_profile_present_day":
            entry.update(classification="FAIL", evidence="Present-day profile value collected 2026-11; not historical. Excluded by role (IDENTITY_CONTEXT); must not be used as a predictor")
        elif role in ("TARGET", "TARGET_METADATA", "TARGET_AUDIT_NOT_A_PREDICTOR", "TEMPORAL_ALIGNMENT_NOT_A_PREDICTOR"):
            entry.update(classification="FAIL", evidence="Target or derived from the target's valuation date; would leak the target. Excluded by role")
        elif role in ("IDENTITY_QUALITY", "IDENTITY_LINK", "IDENTITY_CONTEXT", "KEY"):
            entry.update(classification="FAIL" if c in ("canonical_player_id", "fotmob_player_id", "transfermarkt_player_id") else "WARNING",
                         evidence=(f"Player identifier: {multi_season_players} players have rows in 2+ seasons, so a random split would put the same player on both sides (identity leakage). Use as a group key, never as a predictor" if c in ("canonical_player_id", "fotmob_player_id", "transfermarkt_player_id")
                                   else "Season key: valuation dates are season-wide batches, so season is linked to target timing; use for temporal splits, not as a free predictor" if c in ("season", "season_id")
                                   else "Identity or data-quality descriptor; not a predictor. Use for sensitivity checks only"))
        else:
            entry.update(classification="PASS", evidence="Population, quality or provenance metadata; not a predictor")
        entry.setdefault("family", "")
        rows.append(entry)
    return rows


def reliability_table(df: pd.DataFrame, missing_rows: list[dict], dist_rows: list[dict], leak: list[dict], windows: list[dict], groups: dict, applicable: dict) -> list[dict]:
    leak_by = {r["column"]: r for r in leak}
    dist = {(r["metric"], r["season"]): r for r in dist_rows}
    miss = {(r["metric"], r["season"]): r for r in missing_rows}
    seasons = sorted(df.season.unique())
    out = []
    for c in [c for c in df.columns if c.startswith("m_")] + ["age_at_season_end_years", "position_group_season"]:
        if c.startswith("m_"):
            m = c[2:]
            all_row = miss[(m, "ALL")]
            observed = sum(all_row[f"status_{k}"] for k in OBSERVED)
            seasons_with = sum(miss[(m, s)]["null"] < miss[(m, s)]["rows"] for s in seasons)
            # GK_ONLY metrics: missingness among goalkeeper player-seasons (modal lineup position GK).
            eligible = df[df.position_group_season == "GK"] if applicable.get(m) == "GK_ONLY" else df
            eligible_null_pct = round(100 * eligible[c].isna().mean(), 2)
            conflicts = all_row["status_CONFLICTING"]
            unverified = all_row["status_UNVERIFIED_POSITION"]
            if seasons_with == 0:
                rel, treat = "NO_DATA", "Exclude: no values"
            elif seasons_with < len(seasons):
                rel, treat = "PARTIAL_SEASON_COVERAGE", "Use only with season-aware handling, or exclude; never impute absent seasons"
            elif eligible_null_pct > 50:
                rel, treat = "LOW_COVERAGE", "Candidate only with explicit missingness handling; check by position"
            elif leak_by[c]["classification"] == "REQUIRES RESEARCH DECISION":
                rel, treat = "WINDOW_NOT_FULLY_VERIFIED", "Usable with care; confirm window decision first"
            elif "Not independently verifiable" in leak_by[c]["evidence"] or "Not verifiable" in leak_by[c]["evidence"]:
                rel, treat = "SOURCE_REPORTED_NOT_VERIFIED", "Candidate; source value accepted without independent window check"
            else:
                rel, treat = "RELIABLE_WITH_ALIGNMENT_LIMIT", "Candidate; read with its s_ status; null is not zero"
            d = dist.get((m, "ALL"))
            out.append({"feature": c, "data_type": str(df[c].dtype), "metric_family": groups.get(m, ""), "missingness_pct": all_row["null_pct"], "applicable_positions": applicable.get(m, ""), "missingness_pct_among_applicable": eligible_null_pct, "seasons_with_values": f"{seasons_with}/{len(seasons)}",
                        "observed_status_share_pct": round(100 * observed / len(df), 2), "unverified_position_cells": unverified, "conflicting_cells": conflicts, "reliability_status": rel,
                        "temporal_availability": "Season total through the cutoff; includes post-valuation matches", "leakage_classification": leak_by[c]["classification"],
                        "spearman_with_log_target": leak_by[c]["spearman_with_log_target"], "extreme_values_beyond_3iqr": d["extreme_beyond_3iqr"] if d else None, "recommended_treatment": treat})
        else:
            out.append({"feature": c, "data_type": str(df[c].dtype), "metric_family": "CONTEXT", "missingness_pct": round(100 * df[c].isna().mean(), 2), "applicable_positions": "ALL", "missingness_pct_among_applicable": round(100 * df[c].isna().mean(), 2), "seasons_with_values": f"{len(seasons)}/{len(seasons)}",
                        "observed_status_share_pct": None, "unverified_position_cells": int((df[c] == "UNKNOWN").sum()) if c == "position_group_season" else None, "conflicting_cells": None,
                        "reliability_status": "RELIABLE" if c == "age_at_season_end_years" else "RELIABLE_WITH_ALIGNMENT_LIMIT", "temporal_availability": "Known at season end",
                        "leakage_classification": leak_by[c]["classification"], "spearman_with_log_target": leak_by[c]["spearman_with_log_target"], "extreme_values_beyond_3iqr": None,
                        "recommended_treatment": "Candidate; 4 historically disputed birth dates" if c == "age_at_season_end_years" else "Candidate; categorical"})
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    df = pd.read_parquet(DATASET)
    with (FOTMOB_RS5 / "manifests/metric_dictionary_rs5.csv").open(encoding="utf-8") as handle:
        dictionary = list(csv.DictReader(handle))
    groups = {r["normalized_field"]: r["metric_group"] for r in dictionary}
    applicable = {r["normalized_field"]: r["applicable_positions"] for r in dictionary}
    metrics = sorted(c[2:] for c in df.columns if c.startswith("m_"))
    windows, window_check = feature_windows(out)
    qual, missing_rows, dist_rows = quality(con, df, metrics, groups)
    write_csv(out / "missingness_by_feature_season.csv", missing_rows)
    write_csv(out / "metric_distribution_by_season.csv", dist_rows)
    temp = temporal(con, df, windows)
    candidates = [c for c in df.columns if column_role(c).startswith("FEATURE_FOTMOB_METRIC") or c == "age_at_season_end_years"] + [c for c in df.columns if c.startswith("temporal_") or c.startswith("target_audit_")]
    rho = spearman(df, candidates)
    indirect = indirect_window_evidence(con, df)
    leak = leakage(df, windows, groups, rho, indirect)
    write_csv(out / "leakage_audit.csv", leak)
    rel = reliability_table(df, missing_rows, dist_rows, leak, windows, groups, applicable)
    write_csv(out / "feature_reliability.csv", rel)
    qual["feature_window_recheck"] = window_check
    qual["indirect_window_evidence"] = indirect
    (out / "quality_audit.json").write_text(json.dumps(qual, indent=1, default=str) + "\n", encoding="utf-8")
    (out / "temporal_audit.json").write_text(json.dumps(temp, indent=1, default=str) + "\n", encoding="utf-8")
    summary = {"dataset": DATASET.relative_to(ROOT).as_posix(), "dataset_sha256": file_hash(DATASET), "leakage_classification": dict(Counter(r["classification"] for r in leak)), "candidate_leakage_classification": dict(Counter(r["classification"] for r in leak if r["candidate_predictor"])),
               "reliability_status": dict(Counter(r["reliability_status"] for r in rel)), "max_abs_spearman_candidate": max(((abs(v), k) for k, v in rho.items() if not k.startswith(("temporal_", "target_"))), default=None),
               "window_check": window_check, "temporal_overall": temp["overall"]}
    (out / "audit_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
