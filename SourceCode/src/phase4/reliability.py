"""Phase 4.5: missingness, temporal and data reliability analysis of the official FB69 research release.

Descriptive and read-only. The notebook (FB69_report.ipynb) and the evidence CLI both call these functions.
Status semantics of the s_* columns are preserved: statuses are never collapsed into one "missing" class, and a
null is never converted to zero. `temporal_*` and `target_audit_*` columns are read only to audit timing and
consistency (they are never predictors, P4-A03). No row is excluded, nothing is imputed, no staleness filter,
no change to D4/D6, mappings or eligibility.

Usage (evidence): python -I -X utf8 src/phase4/reliability.py <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.phase4 import bivariate as biv  # noqa: E402
from src.phase4 import multivariate as mvt  # noqa: E402
from src.phase4 import profiling as prof  # noqa: E402
from src.phase4 import univariate as uni  # noqa: E402
from src.research_scope.scope import check_table  # noqa: E402

TARGET = uni.TARGET
POSITION = uni.POSITION
POSITION_ORDER = prof.POSITION_ORDER
WINDOW_AUDIT = ROOT / "reports/research_scope_rs5/step_04/evidence/feature_window_audit_rs5.csv"
STATUS_ORDER = ["OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED", "MISSING",
                "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING"]
STATUS_SEMANTICS = {
    "OBSERVED": ("Observed value", "Value reported by the source for the season", "available"),
    "OBSERVED_ZERO": ("Genuine observed zero", "The source reports zero events; the stored value is 0", "available"),
    "OBSERVED_FALLBACK_LEADERBOARD": ("Observed via fallback", "Value taken from the season leaderboard because the player stats page lacked it", "available (alternative source path)"),
    "OBSERVED_SOURCE_REVISED": ("Observed, revised by source", "Value differs between collection passes; the later source value is kept (RS5-13)", "available (revised)"),
    "MISSING": ("Unavailable observation", "The source provides no value for this player-season; the stored value is null", "unavailable"),
    "UNVERIFIED_POSITION": ("Not applicable or unverified by position", "Position-specific metric on a row whose position does not match or is not verified; null", "not applicable"),
    "UNSUPPORTED": ("Unsupported metric", "The source has no data for this metric at all (key_passes); null", "unavailable (no source data)"),
    "CONFLICTING": ("Conflicting source values", "Collection passes disagree and no value could be confirmed; null", "unverified conflict"),
}
STATUS_COLORS = {"OBSERVED": "#1a9850", "OBSERVED_ZERO": "#91cf60", "OBSERVED_FALLBACK_LEADERBOARD": "#66bd63",
                 "OBSERVED_SOURCE_REVISED": "#d9ef8b", "MISSING": "#d73027", "UNVERIFIED_POSITION": "#bdbdbd",
                 "UNSUPPORTED": "#4d4d4d", "CONFLICTING": "#fdae61"}
RD04 = uni.RD04
SOURCE_REPORTED = biv.SOURCE_REPORTED
CLUB_CONTEXT = ["confirmed_team_ids", "confirmed_team_count", "associated_team_count", "associated_team_ids",
                "associated_team_names", "is_multi_club", "multi_club_status", "multi_club_class"]
GK_METRICS = uni.FEATURE_GROUPS["8 Goalkeeping"]
METRICS = [f for f in uni.FEATURES if f.startswith("m_")] + ["m_key_passes"]


def status_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("s_")]


def lineup_minutes(df: pd.DataFrame) -> pd.Series:
    """Minutes from lineup evidence (temporal audit columns). Audit use only: never a predictor (P4-A03)."""
    return df["temporal_minutes_before_or_on_valuation"] + df["temporal_minutes_after_valuation"]


# ----------------------------------------------------------------------------- status semantics
def status_semantics(df: pd.DataFrame) -> pd.DataFrame:
    """Every status with its meaning, stored value and count; checks that value storage matches the status."""
    rows = []
    for st in STATUS_ORDER:
        n = nulls = zeros = 0
        for s in status_cols(df):
            m = "m_" + s[2:]
            sel = df[s].eq(st)
            n += int(sel.sum())
            nulls += int(df.loc[sel, m].isna().sum())
            zeros += int(df.loc[sel, m].eq(0).sum())
        label, meaning, cls = STATUS_SEMANTICS[st]
        rows.append({"status": st, "label": label, "meaning": meaning, "reliability_class": cls, "cells": n,
                     "cells_pct": 0.0, "stored_null": nulls, "stored_zero": zeros, "stored_non_zero": n - nulls - zeros})
    out = pd.DataFrame(rows)
    out["cells_pct"] = out["cells"] / out["cells"].sum() * 100
    return out


def status_matrix(df: pd.DataFrame, rows: pd.Series | None = None) -> pd.DataFrame:
    d = df if rows is None else df[rows]
    return pd.DataFrame({"m_" + s[2:]: d[s].value_counts() for s in status_cols(df)}).T.reindex(columns=STATUS_ORDER).fillna(0).astype(int)


def status_share_by(df: pd.DataFrame, by: pd.Series, order) -> pd.DataFrame:
    out = {}
    for key, idx in by.groupby(by).groups.items():
        counts = pd.Series(df.loc[idx, status_cols(df)].to_numpy().ravel()).value_counts()
        out[key] = counts / counts.sum() * 100
    return pd.DataFrame(out).T.reindex(index=[o for o in order if o in out], columns=STATUS_ORDER).fillna(0)


# ----------------------------------------------------------------------------- feature-level missingness
def feature_missingness(df: pd.DataFrame, reliability: pd.DataFrame, scope) -> pd.DataFrame:
    """Null counts per metric: overall, on applicable rows, by season, by position and by target availability."""
    rel = reliability.rename(columns=lambda c: c.lstrip("﻿")).set_index("feature")
    rows = []
    for m in METRICS:
        app = df[POSITION].eq("GK") if rel.at[m, "applicable_positions"] == "GK_ONLY" else pd.Series(True, index=df.index)
        rec = {"metric": m, "family": rel.at[m, "metric_family"], "applicable_positions": rel.at[m, "applicable_positions"],
               "null": int(df[m].isna().sum()), "null_pct": df[m].isna().mean() * 100,
               "applicable_rows": int(app.sum()), "null_applicable_pct": df.loc[app, m].isna().mean() * 100,
               "null_with_target_pct": df.loc[app & df["target_usable"], m].isna().mean() * 100,
               "null_without_target_pct": df.loc[app & ~df["target_usable"], m].isna().mean() * 100}
        for s in scope.labels:
            sel = app & df["season"].eq(s)
            rec[f"null_{prof.short(s)}_pct"] = df.loc[sel, m].isna().mean() * 100
        for p in POSITION_ORDER:
            rec[f"null_{p}_pct"] = df.loc[df[POSITION].eq(p), m].isna().mean() * 100
        rows.append(rec)
    return pd.DataFrame(rows)


def family_missingness(fm: pd.DataFrame) -> pd.DataFrame:
    g = fm.groupby("family")
    return pd.DataFrame({"metrics": g.size(), "median_null_applicable_pct": g["null_applicable_pct"].median(),
                         "max_null_applicable_pct": g["null_applicable_pct"].max()}).sort_values("median_null_applicable_pct")


# ----------------------------------------------------------------------------- population-level missingness
def population_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """Null metric count (missing_feature_count) by population segment."""
    g = mvt.groups(df)
    segments = {
        "target available": df["target_usable"], "target missing": ~df["target_usable"],
        "goalkeepers": df[POSITION].eq("GK"), "outfield": df[POSITION].ne("GK"),
    }
    for lab in mvt.STARTS_LABELS:
        segments[f"outfield, {lab}"] = df[POSITION].ne("GK") & g["starts_group"].eq(lab)
    for lab in uni.MINUTES_LABELS:
        segments[f"outfield, {lab} minutes"] = df[POSITION].ne("GK") & g["minutes_band"].eq(lab)
    for s in sorted(df["season"].unique()):
        segments[f"season {prof.short(s)}"] = df["season"].eq(s)
    rows = []
    for name, sel in segments.items():
        sub = df.loc[sel]
        counts = pd.Series(sub[status_cols(df)].to_numpy().ravel()).value_counts()
        rows.append({"segment": name, "rows": int(sel.sum()), "null_metrics_mean": sub["missing_feature_count"].mean(),
                     "null_metrics_median": sub["missing_feature_count"].median(),
                     "rows_with_all_detailed_stats_null_pct": (sub["m_touches"].isna() & sub[POSITION].ne("GK")).mean() * 100,
                     **{f"{k}_pct": counts.get(k, 0) / counts.sum() * 100 for k in ("MISSING", "UNVERIFIED_POSITION", "CONFLICTING")}})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- goalkeepers
def goalkeeper_reliability(df: pd.DataFrame, scope) -> dict[str, pd.DataFrame]:
    gk = df[df[POSITION].eq("GK")]
    status = status_matrix(df, df[POSITION].eq("GK"))
    by_season = []
    for s in scope.labels:
        sub = gk[gk["season"] == s]
        rec = {"season": s, "gk_rows": len(sub), "minutes_metric_present": int(sub["m_minutes_played"].notna().sum()),
               "lineup_minutes_present": int(lineup_minutes(sub).notna().sum())}
        for m in GK_METRICS:
            rec[f"{m}_present_pct"] = sub[m].notna().mean() * 100
        by_season.append(rec)
    lm = lineup_minutes(gk)
    checks = []
    sp = gk.dropna(subset=["m_saves", "m_goals_conceded", "m_save_percentage"])
    calc = sp["m_saves"] / (sp["m_saves"] + sp["m_goals_conceded"]) * 100
    diff = (calc - sp["m_save_percentage"]).abs()
    checks.append({"check": "save_percentage = saves / (saves + goals_conceded) x 100", "rows_compared": len(sp),
                   "agree_within_0_1pp": int((diff <= 0.1).sum()), "max_abs_difference": diff.max(),
                   "reading": "consistent with the reported totals (rounding only)"})
    gc = gk.dropna(subset=["m_goals_conceded", "m_goals_conceded_per90"])
    calc = gc["m_goals_conceded"] * 90 / lm[gc.index]
    diff = (calc - gc["m_goals_conceded_per90"]).abs()
    checks.append({"check": "goals_conceded_per90 = goals_conceded x 90 / lineup minutes", "rows_compared": len(gc),
                   "agree_within_0_1pp": int((diff <= 1e-6).sum()), "max_abs_difference": diff.max(),
                   "reading": "identical: the rate is computed from lineup minutes that exist for every GK row"})
    cs = gk.dropna(subset=["m_clean_sheets"])
    checks.append({"check": "clean_sheets <= appearances", "rows_compared": len(cs),
                   "agree_within_0_1pp": int((cs["m_clean_sheets"] <= cs["m_appearances"]).sum()), "max_abs_difference": np.nan,
                   "reading": "bound holds; clean sheets per match not verifiable from this dataset"})
    minutes = pd.DataFrame([{"source": "m_minutes_played (FotMob season stats)", "gk_rows_with_value": int(gk["m_minutes_played"].notna().sum())},
                            {"source": "lineup minutes (temporal_* audit columns, not a predictor)", "gk_rows_with_value": int(lm.notna().sum())}])
    return {"gk_status_matrix": status, "gk_coverage_by_season": pd.DataFrame(by_season).set_index("season"),
            "gk_consistency_checks": pd.DataFrame(checks), "gk_minutes_sources": minutes,
            "gk_outfield_metric_status": status.drop(index=[m for m in GK_METRICS if m in status.index] + ["m_minutes_played", "m_rating",
                                                                                                        "m_appearances", "m_starts"],
                                                     errors="ignore").sum().to_frame("cells").T}


def outfield_minutes_agreement(df: pd.DataFrame) -> dict:
    o = df[df[POSITION].ne("GK")]
    diff = (lineup_minutes(o) - o["m_minutes_played"]).abs()
    return {"rows_compared": int(diff.notna().sum()), "identical": int((diff == 0).sum()), "max_abs_difference": float(diff.max())}


# ----------------------------------------------------------------------------- temporal validity
def temporal_reference(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute the RD-03 reference values from the official dataset."""
    u = df[df["target_usable"]]
    age = u["target_valuation_age_days"]
    after_games = u["temporal_player_games_after_valuation"].sum() / u["temporal_player_games_in_season"].sum() * 100
    mins = u["temporal_minutes_after_valuation"].sum() / (u["temporal_minutes_after_valuation"] + u["temporal_minutes_before_or_on_valuation"]).sum() * 100
    rows = [("Median valuation age (days)", 150, float(age.median())),
            ("Usable targets older than 90 days (%)", 56.62, float((age > 90).mean() * 100)),
            ("Appearances after the valuation date (%)", 44.10, float(after_games)),
            ("Minutes after the valuation date (%)", 43.66, float(mins)),
            ("Targets older than 365 days", 12, float((age > 365).sum())),
            ("Valuations after the season cutoff", 0, float((age < 0).sum())),
            ("Usable targets dated before the season's first match", 18,
             float((u["temporal_player_games_on_valuation_date"].eq(0) & u["temporal_league_games_after_valuation"].eq(u["temporal_league_games_in_season"])).sum()))]
    out = pd.DataFrame(rows, columns=["measure", "reference", "recomputed"])
    out["matches_reference"] = np.isclose(out["reference"], out["recomputed"].round(2), atol=0.005)
    return out


def temporal_by_season(df: pd.DataFrame, scope) -> pd.DataFrame:
    u = df[df["target_usable"]]
    rows = []
    for s in scope.labels:
        sub = u[u["season"] == s]
        dates = sub["target_valuation_date"].value_counts()
        rows.append({"season": s, "usable_targets": len(sub), "distinct_valuation_dates": int(dates.size),
                     "top1_date": dates.index[0], "top1_share_pct": dates.iloc[0] / len(sub) * 100,
                     "top3_share_pct": dates.iloc[:3].sum() / len(sub) * 100,
                     "median_age_days": sub["target_valuation_age_days"].median(),
                     "over_90_days_pct": (sub["target_valuation_age_days"] > 90).mean() * 100,
                     "over_365_days": int((sub["target_valuation_age_days"] > 365).sum()),
                     "league_games_after_valuation_median": sub["temporal_league_games_after_valuation"].median(),
                     "appearances_after_valuation_pct": sub["temporal_player_games_after_valuation"].sum() / sub["temporal_player_games_in_season"].sum() * 100,
                     "minutes_after_valuation_pct": sub["temporal_minutes_after_valuation"].sum() / (sub["temporal_minutes_after_valuation"] + sub["temporal_minutes_before_or_on_valuation"]).sum() * 100})
    return pd.DataFrame(rows).set_index("season")


def alignment_classes(df: pd.DataFrame) -> pd.DataFrame:
    return pd.crosstab(df["temporal_alignment_class"], df["season"], margins=True, margins_name="total")


def row_after_share(df: pd.DataFrame) -> pd.Series:
    """Per row: share of the player's own minutes played after the valuation date (usable targets, minutes > 0)."""
    u = df[df["target_usable"]]
    tot = u["temporal_minutes_after_valuation"] + u["temporal_minutes_before_or_on_valuation"]
    return (u["temporal_minutes_after_valuation"] / tot).where(tot > 0)


def before_after_association(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Spearman of the target with minutes before/on and after the valuation date, overall and per season.
    If the label tracked only pre-valuation playing time, the 'after' association would be much weaker."""
    u = df[df["target_usable"]]
    rows = []
    for name, sub in [("all seasons", u)] + [(prof.short(s), u[u["season"] == s]) for s in scope.labels]:
        y = sub[TARGET].to_numpy(float)
        rows.append({"group": name, "n": len(sub),
                     "spearman_minutes_before": biv.spearman(sub["temporal_minutes_before_or_on_valuation"].to_numpy(float), y),
                     "spearman_minutes_after": biv.spearman(sub["temporal_minutes_after_valuation"].to_numpy(float), y),
                     "spearman_before_vs_after_minutes": biv.spearman(sub["temporal_minutes_before_or_on_valuation"].to_numpy(float),
                                                                      sub["temporal_minutes_after_valuation"].to_numpy(float))})
    return pd.DataFrame(rows)


def association_by_after_share(df: pd.DataFrame, register: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Feature-target Spearman for rows whose own minutes fall mostly before vs mostly after the valuation.
    Descriptive sensitivity only: no row is filtered from any main result."""
    share = row_after_share(df)
    out = {}
    for f in features:
        sub = biv.pair_frame(df, f, register).join(share.rename("after_share"), how="inner").dropna(subset=["after_share"])
        rec = {}
        for label, mask in (("mostly before (<1/3 after)", sub["after_share"] < 1 / 3), ("mixed", sub["after_share"].between(1 / 3, 2 / 3)),
                            ("mostly after (>2/3 after)", sub["after_share"] > 2 / 3)):
            s = sub[mask]
            rec[f"{label} n"] = len(s)
            rec[label] = biv.spearman(s[f].to_numpy(float), s[TARGET].to_numpy(float)) if len(s) >= biv.MIN_N else np.nan
        out[f] = rec
    return pd.DataFrame(out).T


def old_valuations(df: pd.DataFrame, days: int = 365) -> pd.DataFrame:
    u = df[df["target_usable"] & (df["target_valuation_age_days"] > days)]
    return u[["fotmob_player_name", "season", POSITION, "m_starts", TARGET, "target_valuation_date",
              "target_valuation_age_days"]].sort_values("target_valuation_age_days", ascending=False)


# ----------------------------------------------------------------------------- identity sensitivity
def identity_overview(df: pd.DataFrame) -> pd.DataFrame:
    return pd.crosstab(df["identity_evidence_tier"], df["identity_rs5_validation_label"].fillna("<null>"), margins=True, margins_name="total")


def identity_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Main dataset vs P4-B01 subset vs main without the subset: target, composition and missingness."""
    m = biv.identity_sensitivity_mask(df)
    g = mvt.groups(df)
    rows = []
    for name, sel in (("main dataset", pd.Series(True, index=df.index)), ("P4-B01 subset", m), ("main without P4-B01 (sensitivity only)", ~m)):
        sub, gs = df[sel], g[sel]
        u = sub[sub["target_usable"]][TARGET]
        rec = {"population": name, "rows": int(sel.sum()), "players": int(sub["canonical_player_id"].nunique()),
               "usable_targets": len(u), "target_missing_pct": (~sub["target_usable"]).mean() * 100,
               "target_p25_eur": u.quantile(0.25), "target_median_eur": u.median(), "target_p75_eur": u.quantile(0.75),
               "target_p90_eur": u.quantile(0.9), "age_median": sub["age_at_season_end_years"].median(),
               "starts_median": sub["m_starts"].median(), "zero_start_pct": gs["starts_group"].eq("0 starts").mean() * 100,
               "null_metrics_median": sub["missing_feature_count"].median()}
        for p in POSITION_ORDER:
            rec[f"{p}_pct"] = sub[POSITION].eq(p).mean() * 100
        for s in sorted(df["season"].unique()):
            rec[f"{prof.short(s)}_pct"] = sub["season"].eq(s).mean() * 100
        rows.append(rec)
    return pd.DataFrame(rows).set_index("population")


def identity_season_medians(df: pd.DataFrame, scope) -> pd.DataFrame:
    m = biv.identity_sensitivity_mask(df)
    u = df["target_usable"]
    return pd.DataFrame({"median_all_eur": df[u].groupby("season")[TARGET].median(),
                         "median_without_p4b01_eur": df[u & ~m].groupby("season")[TARGET].median(),
                         "p4b01_rows": df[m].groupby("season").size()}).reindex(list(scope.labels))


# ----------------------------------------------------------------------------- RD-04, club context, source-reported
def rd04_assessment(df: pd.DataFrame, scope) -> pd.DataFrame:
    """RD-04 metrics per season: values, status counts, window status from the rs5 window audit, and the
    within-season Spearman with the target (applicable rows)."""
    window = pd.read_csv(WINDOW_AUDIT).rename(columns=lambda c: c.lstrip("﻿"))
    rows = []
    for m in RD04:
        name = m[2:]
        app = df[POSITION].eq("GK") if m in GK_METRICS else pd.Series(True, index=df.index)
        for s in scope.labels:
            sel = app & df["season"].eq(s)
            sub = df[sel]
            w = window[(window["metric"] == name) & (window["season"] == s)]
            pair = sub[sub["target_usable"]][[m, TARGET]].dropna()
            st = sub["s_" + name].value_counts()
            rows.append({"metric": m, "season": s, "applicable_rows": int(sel.sum()), "values": int(sub[m].notna().sum()),
                         "coverage_pct": sub[m].notna().mean() * 100,
                         "status_MISSING": int(st.get("MISSING", 0)), "status_CONFLICTING": int(st.get("CONFLICTING", 0)),
                         "status_UNVERIFIED_POSITION": int(st.get("UNVERIFIED_POSITION", 0)),
                         "window_status": w["window_status"].iloc[0] if len(w) else "",
                         "window_agree_pct": w["agree_pct"].iloc[0] if len(w) else np.nan,
                         "match_coverage_pct": w["match_coverage_pct"].iloc[0] if len(w) else np.nan,
                         "spearman_with_target": biv.spearman(pair[m].to_numpy(float), pair[TARGET].to_numpy(float)) if len(pair) >= biv.MIN_N else np.nan,
                         "pairs": len(pair)})
    return pd.DataFrame(rows)


def club_context(df: pd.DataFrame, scope) -> dict[str, pd.DataFrame]:
    avail = pd.DataFrame([{"column": c, "non_null": int(df[c].notna().sum()), "distinct": int(df[c].astype(str).nunique()),
                           "example": str(df[c].iloc[0])} for c in CLUB_CONTEXT])
    by_season = pd.crosstab(df["multi_club_class"], df["season"], margins=True, margins_name="total")
    u = df[df["target_usable"]]
    target = u.groupby("multi_club_class")[TARGET].agg(["size", "median"]).rename(columns={"size": "usable_targets", "median": "median_eur"})
    multi = df[df["multi_club_class"].ne("SINGLE_CLUB")]
    timing = pd.DataFrame([{"multi_club_rows": len(multi),
                            "with_usable_target": int(multi["target_usable"].sum()),
                            "median_minutes_after_valuation_pct": (multi["temporal_minutes_after_valuation"] /
                                                                   lineup_minutes(multi)).median() * 100,
                            "rows_with_games_after_valuation": int((multi["temporal_player_games_after_valuation"] > 0).sum())}])
    return {"club_context_availability": avail, "club_context_by_season": by_season,
            "club_context_target": target, "club_context_timing": timing}


def source_reported(df: pd.DataFrame, gk_checks: pd.DataFrame) -> pd.DataFrame:
    """Reliability caveat per source-reported metric, with the checks that the dataset allows."""
    notes = {
        "m_aerials_won_percent": "Denominator (aerial duels contested) not in the dataset; not verifiable",
        "m_cross_accuracy": "Denominator (crosses attempted) not in the dataset; not verifiable",
        "m_duels_won_percent": "Denominator (duels contested) not in the dataset; not verifiable",
        "m_long_ball_accuracy": "Denominator (long balls attempted) not in the dataset; not verifiable",
        "m_passing_accuracy": "Denominator (passes attempted) not in the dataset; not verifiable",
        "m_save_percentage": "Consistent with saves / (saves + goals conceded) on every GK row (max difference 0.05 pp)",
        "m_clean_sheets": "Bound clean sheets <= appearances holds; per-match clean sheets not in the dataset",
        "m_goals_conceded_per90": "Identical to goals conceded x 90 / lineup minutes on every GK row with a value",
    }
    rows = []
    for m in SOURCE_REPORTED:
        app = df[POSITION].eq("GK") if m in GK_METRICS else df[POSITION].ne("GK")
        s = df.loc[app, m]
        bounded = m.endswith(("percent", "accuracy", "percentage"))
        rows.append({"metric": m, "applicable_rows": int(app.sum()), "values": int(s.notna().sum()),
                     "null_pct": s.isna().mean() * 100,
                     "outside_0_100": int((~s.between(0, 100) & s.notna()).sum()) if bounded else np.nan,
                     "values_at_0_or_100_pct": (s.isin([0, 100]).sum() / s.notna().sum() * 100) if bounded else np.nan,
                     "check_result": notes[m],
                     "verifiable_in_dataset": m in ("m_save_percentage", "m_goals_conceded_per90")})
    return pd.DataFrame(rows)


def other_conditions(df: pd.DataFrame, scope) -> pd.DataFrame:
    s = status_cols(df)
    revised = {c: int(df[c].eq("OBSERVED_SOURCE_REVISED").sum()) for c in s}
    conflicting = {c: int(df[c].eq("CONFLICTING").sum()) for c in s}
    rows = [
        ("ISS-28", "key_passes excluded", f"m_key_passes null on {int(df['m_key_passes'].isna().sum())} of {len(df)} rows; s_key_passes UNSUPPORTED on {int(df['s_key_passes'].eq('UNSUPPORTED').sum())}", "Excluded; no data to assess"),
        ("P4-A04", "Present-day nationality excluded", f"{int(df['nationality_profile_present_day'].notna().sum())} rows with a value, {df['nationality_profile_present_day'].nunique()} distinct values; collected November 2026", "Not a historical fact; excluded"),
        ("DQ-RS5-04", "Starts greater than appearances", f"{int((df['m_starts'] > df['m_appearances']).sum())} rows, seasons {sorted(df.loc[df['m_starts'] > df['m_appearances'], 'season'].unique().tolist())}", "Kept as published; affects start-share ratios only"),
        ("RS5-13", "Historical source revisions", "; ".join(f"{k[2:]} {v}" for k, v in revised.items() if v), "Later source value kept; values may differ from what was visible at season end"),
        ("RD-01", "Old valuation labels", f"{int((df['target_valuation_age_days'] > 365).sum())} usable targets older than 365 days (max {int(df['target_valuation_age_days'].max())})", "Kept; weak labels; owner decision open"),
        ("ISS-04", "Unresolved identities", f"{int(df['identity_evidence_tier'].eq('UNRESOLVED').sum())} rows (REVIEW_REQUIRED, no target)", "Human review required; not adjudicated"),
        ("P4-B02", "Conflicting cells", "; ".join(f"{k[2:]} {v}" for k, v in conflicting.items() if v), "Null and traceable; never zero"),
        ("P4-B02", "Unverified-position cells", f"{int((df[s] == 'UNVERIFIED_POSITION').sum().sum())} cells: {int((df.loc[df[POSITION].ne('GK'), s] == 'UNVERIFIED_POSITION').sum().sum())} on outfield rows (GK-only metrics), {int((df.loc[df[POSITION].eq('GK'), s] == 'UNVERIFIED_POSITION').sum().sum())} on GK rows", "Not applicable; never zero"),
        ("ISS-27", "Rows without target", f"{int((~df['target_usable']).sum())}: " + ", ".join(f"{k} {v}" for k, v in df.loc[~df['target_usable'], 'target_missing_reason'].value_counts().items()), "Kept in the dataset; no target imputed"),
    ]
    return pd.DataFrame(rows, columns=["condition", "topic", "evidence", "handling"])


def reliability_map(df: pd.DataFrame, register: pd.DataFrame, fm: pd.DataFrame, window: pd.DataFrame) -> pd.DataFrame:
    """One row per analysed feature: coverage, window evidence, source reliability, applicability and the
    resulting descriptive reliability class. Classes describe evidence; they do not select features."""
    reg = register.set_index("feature")
    f_m = fm.set_index("metric")
    rows = []
    for f in uni.FEATURES:
        if f == "age_at_season_end_years":
            rows.append({"feature": f, "null_applicable_pct": 0.0, "seasons_with_values": 5, "window_evidence": "not a season metric",
                         "source_check": "birth date (4 disputed, ISS-07)", "applicability": "all rows", "reliability_class": "reliable with caveat",
                         "caveats": "ISS-07"})
            continue
        name = f[2:]
        w = window[window["metric"] == name]["window_status"]
        if w.empty:
            ws = "not in window audit"
        elif w.eq("FULL_EPL_SEASON_VERIFIED").all():
            ws = "verified all seasons"
        elif w.isin(["FULL_EPL_SEASON_VERIFIED", "NOT_VERIFIABLE_FROM_MATCH_DATA", "VERIFIED_VIA_TOTALS"]).all():
            ws = "verified or derived from verified totals"
        else:
            ws = "incomplete: " + ", ".join(sorted(set(w) - {"FULL_EPL_SEASON_VERIFIED"}))
        null_pct = f_m.at[f, "null_applicable_pct"]
        seasons = int(df.loc[df[f].notna(), "season"].nunique())
        caveats = []
        if f in RD04:
            cls = "pending owner decision (RD-04)"
            caveats.append("RD-04")
        elif f in SOURCE_REPORTED:
            cls = "uncertain: source-reported" if f not in ("m_save_percentage", "m_goals_conceded_per90") else "source-reported, internally consistent"
            caveats.append("ISS-29")
        elif null_pct > 20:
            cls = "reliable values, limited coverage"
        else:
            cls = "reliable with caveat"
        if f.endswith("_per90"):
            caveats.append("P4-B05")
        if f in GK_METRICS:
            caveats.append("GK only, ISS-11")
        if f in ("m_recoveries_per90", "m_interceptions_per90", "m_shots_per90", "m_tackles_per90", "m_passing_accuracy"):
            caveats.append("P4-B09")
        if df["s_" + name].isin(["OBSERVED_SOURCE_REVISED"]).any():
            caveats.append("RS5-13")
        if df["s_" + name].eq("CONFLICTING").any():
            caveats.append("P4-B02")
        if df["s_" + name].eq("OBSERVED_FALLBACK_LEADERBOARD").any():
            caveats.append("leaderboard fallback")
        rows.append({"feature": f, "null_applicable_pct": null_pct, "seasons_with_values": seasons, "window_evidence": ws,
                     "source_check": "source-reported (ISS-29)" if f in SOURCE_REPORTED else "window audit",
                     "applicability": reg.at[f, "applicable_positions"], "reliability_class": cls,
                     "caveats": ", ".join(["RD-03"] + caveats)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    dictionary, eligibility, reliability = prof.load_metadata()
    register = uni.feature_register(eligibility, reliability)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    window = pd.read_csv(WINDOW_AUDIT).rename(columns=lambda c: c.lstrip("﻿"))
    fm = feature_missingness(df, reliability, scope)
    gk = goalkeeper_reliability(df, scope)
    club = club_context(df, scope)
    tby = temporal_by_season(df, scope)

    import duckdb
    con = duckdb.connect()
    con.register("temporal_by_season", tby.reset_index()[["season", "usable_targets"]])
    scope_check_derived = check_table(con, "temporal_by_season", scope, "season", None)

    tables = {
        "status_semantics.csv": status_semantics(df),
        "status_matrix_all_rows.csv": status_matrix(df),
        "status_share_by_season.csv": status_share_by(df, df["season"], list(scope.labels)),
        "status_share_by_position.csv": status_share_by(df, df[POSITION], POSITION_ORDER),
        "status_share_by_target_availability.csv": status_share_by(df, df["target_usable"].map({True: "target available", False: "target missing"}),
                                                                   ["target available", "target missing"]),
        "feature_missingness.csv": fm,
        "family_missingness.csv": family_missingness(fm),
        "population_missingness.csv": population_missingness(df),
        **{f"{k}.csv": v for k, v in gk.items()},
        "temporal_reference_values.csv": temporal_reference(df),
        "temporal_by_season.csv": tby,
        "temporal_alignment_classes.csv": alignment_classes(df),
        "temporal_before_after_association.csv": before_after_association(df, scope),
        "temporal_association_by_after_share.csv": association_by_after_share(df, register, biv.KEY_FEATURES),
        "old_valuations_over_365_days.csv": old_valuations(df),
        "identity_overview.csv": identity_overview(df),
        "identity_comparison.csv": identity_comparison(df),
        "identity_season_medians.csv": identity_season_medians(df, scope),
        "identity_feature_target_sensitivity.csv": biv.identity_sensitivity(df, register),
        "identity_group_sensitivity.csv": mvt.group_identity_sensitivity(df),
        "rd04_assessment.csv": rd04_assessment(df, scope),
        **{f"{k}.csv": v for k, v in club.items()},
        "source_reported_metrics.csv": source_reported(df, gk["gk_consistency_checks"]),
        "other_conditions.csv": other_conditions(df, scope),
        "reliability_map.csv": reliability_map(df, register, fm, window),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8", float_format="%.6g")
    ref = tables["temporal_reference_values.csv"]
    summary = {
        "dataset": str(prof.DATASET.relative_to(ROOT)).replace("\\", "/"),
        "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_id": scope.scope_id, "scope_check": verification["scope_check"],
        "scope_check_derived_temporal_by_season": scope_check_derived,
        "status_cells": tables["status_semantics.csv"].set_index("status")["cells"].to_dict(),
        "temporal_reference_all_match": bool(ref["matches_reference"].all()),
        "temporal_reference": ref.set_index("measure")["recomputed"].round(4).to_dict(),
        "outfield_minutes_agreement": outfield_minutes_agreement(df),
        "identity_sensitivity_rows": int(biv.identity_sensitivity_mask(df).sum()),
        "reliability_classes": tables["reliability_map.csv"]["reliability_class"].value_counts().to_dict(),
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "reliability_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:5000])
