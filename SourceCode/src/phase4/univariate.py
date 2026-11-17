"""Phase 4.2: target and univariate analysis of the official FB69 research release.

Descriptive and read-only. The notebook (FB69_report.ipynb) and the evidence CLI both call these functions.
Nothing here imputes, filters, caps, clips, transforms or corrects the dataset. The log scale is computed on the
fly for description only; the stored target is never changed. No feature-target relationship is analysed here
(that is Phase 4.3).

Usage (evidence): python -I -X utf8 src/phase4/univariate.py <out_dir>
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

from src.phase4 import profiling as prof  # noqa: E402
from src.research_scope.scope import check_table  # noqa: E402

TARGET = "target_market_value"
POSITION = "position_group_season"
POSITION_ORDER = prof.POSITION_ORDER
QUANTILES = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]

# Analysis groups (Phase 4.2 taxonomy). The repository's own metric family (docs/feature_reliability.csv) is kept
# next to each feature; it differs only where the 4.2 taxonomy is more specific (discipline, expected, possession).
FEATURE_GROUPS = {
    "1 Player context and age": ["age_at_season_end_years"],
    "2 Playing time and participation": ["m_appearances", "m_starts", "m_minutes_played"],
    "3 Attacking": ["m_goals", "m_assists", "m_shots", "m_shots_on_target", "m_shots_per90",
                    "m_shots_on_target_per90", "m_big_chances_created", "m_dribbles_succeeded",
                    "m_touches_opposition_box"],
    "4 Expected (model-based) metrics": ["m_expected_goals", "m_non_penalty_xg", "m_expected_assists",
                                         "m_expected_goals_on_target"],
    "5 Passing and possession": ["m_accurate_passes", "m_accurate_passes_per90", "m_accurate_long_passes",
                                 "m_accurate_long_passes_per90", "m_chances_created", "m_successful_crosses",
                                 "m_passing_accuracy", "m_long_ball_accuracy", "m_cross_accuracy", "m_touches"],
    "6 Defensive": ["m_tackles", "m_tackles_per90", "m_interceptions", "m_interceptions_per90", "m_recoveries",
                    "m_recoveries_per90", "m_blocked_shots", "m_blocks_per90", "m_clearances",
                    "m_clearances_per90", "m_aerials_won", "m_aerials_won_percent", "m_duels_won",
                    "m_duels_won_percent"],
    "7 Discipline and fouls": ["m_yellow_cards", "m_red_cards", "m_fouls_committed", "m_fouls_won"],
    "8 Goalkeeping": ["m_saves", "m_save_percentage", "m_clean_sheets", "m_goals_conceded",
                      "m_goals_conceded_per90", "m_penalty_saves", "m_goals_prevented"],
    "9 Overall match rating": ["m_rating"],
}
FEATURES = [f for group in FEATURE_GROUPS.values() for f in group]
PREDICTOR_CATEGORIES = {"CANDIDATE_PREDICTOR", "CONDITIONAL_PREDICTOR"}
RD04 = ["m_clearances", "m_clearances_per90", "m_expected_goals_on_target", "m_touches_opposition_box",
        "m_goals_prevented"]
MINUTES_BANDS = [0, 89, 449, 899, 1e9]
MINUTES_LABELS = ["1-89", "90-449", "450-899", "900+"]


def per90_columns() -> list[str]:
    return [f for f in FEATURES if f.endswith("_per90") and f != "m_goals_conceded_per90"]


def group_of(feature: str) -> str:
    return next(g for g, fs in FEATURE_GROUPS.items() if feature in fs)


def kind_of(feature: str) -> str:
    if feature == "age_at_season_end_years":
        return "age (years)"
    if feature in prof.PERCENT_METRICS:
        return "percentage (source-reported)"
    if feature.endswith("_per90"):
        return "per-90 rate"
    if feature == "m_rating":
        return "average rating (0-10)"
    if feature in ("m_expected_goals", "m_non_penalty_xg", "m_expected_assists", "m_expected_goals_on_target",
                   "m_goals_prevented"):
        return "season total (model-based)"
    return "season count/total"


# ----------------------------------------------------------------------------- feature register
def feature_register(eligibility: pd.DataFrame, reliability: pd.DataFrame) -> pd.DataFrame:
    """The 53 analysed features with their Phase 4.0 eligibility, reliability and analysis group."""
    rel = reliability.rename(columns=lambda c: c.lstrip("﻿")).set_index("feature")
    elig = eligibility.set_index("column")
    rows = []
    for f in FEATURES:
        rows.append({
            "feature": f,
            "analysis_group": group_of(f),
            "repository_family": rel.at[f, "metric_family"],
            "kind": kind_of(f),
            "eligibility_category": elig.at[f, "eligibility_category"],
            "reliability_status": elig.at[f, "reliability_status"],
            "condition_ids": elig.at[f, "condition_ids"],
            "applicable_positions": rel.at[f, "applicable_positions"],
            "pending_owner_decision": "RD-04" if f in RD04 else "",
        })
    return pd.DataFrame(rows)


def excluded_from_analysis(df: pd.DataFrame, eligibility: pd.DataFrame) -> pd.DataFrame:
    """Every column that is not analysed as a predictor here, with the reason (from the Phase 4.0 register)."""
    elig = eligibility.set_index("column")
    rows = []
    for col in df.columns:
        if col in FEATURES:
            continue
        cat = elig.at[col, "eligibility_category"]
        if col == POSITION:
            reason = "Categorical context; used as a grouping variable (whole-season modal position, P4-B04)"
        elif col.startswith("s_"):
            reason = "Status column: read to interpret availability, never analysed as a numeric metric (P4-D01)"
        elif cat == "CONDITIONAL_PREDICTOR":
            reason = "Club context: owner decision RS5-12 pending; described as counts only"
        else:
            reason = f"{cat}: {elig.at[col, 'condition_ids']}"
        rows.append({"column": col, "eligibility_category": cat, "reason": reason})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- statistics
def describe(values: pd.Series) -> dict:
    """Summary statistics of the non-null values. Skewness: adjusted Fisher-Pearson; kurtosis: excess (normal = 0)."""
    s = values.dropna().astype(float)
    if s.empty:
        return {"n": 0}
    q = s.quantile(QUANTILES)
    iqr = q[0.75] - q[0.25]
    out = {"n": int(s.size), "mean": s.mean(), "std": s.std(), "min": s.min()}
    out.update({f"p{int(k * 100):02d}": v for k, v in q.items()})
    out.update({"max": s.max(), "iqr": iqr, "skew": s.skew(), "kurtosis": s.kurt(),
                "zero_pct": (s == 0).mean() * 100,
                "upper_1_5iqr": int((s > q[0.75] + 1.5 * iqr).sum()), "upper_3iqr": int((s > q[0.75] + 3 * iqr).sum()),
                "lower_1_5iqr": int((s < q[0.25] - 1.5 * iqr).sum()), "lower_3iqr": int((s < q[0.25] - 3 * iqr).sum())})
    return out


def shape_label(skew: float) -> str:
    if np.isnan(skew):
        return "n/a"
    if skew >= 1:
        return "strongly right-skewed"
    if skew >= 0.5:
        return "moderately right-skewed"
    if skew > -0.5:
        return "approximately symmetric"
    if skew > -1:
        return "moderately left-skewed"
    return "strongly left-skewed"


# ----------------------------------------------------------------------------- target
def usable_target(df: pd.DataFrame) -> pd.Series:
    return df.loc[df["target_usable"], TARGET].astype(float)


def target_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Raw EUR and log10 (descriptive only) statistics of the usable target."""
    t = usable_target(df)
    raw, log = describe(t), describe(np.log10(t))
    out = pd.DataFrame({"raw_eur": raw, "log10_eur": log}).astype(object)
    out.loc["mean_to_median_ratio"] = [raw["mean"] / raw["p50"], np.nan]
    out.loc["shape"] = [shape_label(raw["skew"]), shape_label(log["skew"])]
    out.loc["rows_total"] = [len(df), len(df)]
    out.loc["rows_missing_target"] = [int((~df["target_usable"]).sum())] * 2
    return out


def target_by(df: pd.DataFrame, by, order=None) -> pd.DataFrame:
    t = df.loc[df["target_usable"]]
    g = t.groupby(by, observed=True)[TARGET]
    out = pd.DataFrame({
        "rows": df.groupby(by, observed=True).size(),
        "usable_targets": g.size(),
        "median_eur": g.median(),
        "mean_eur": g.mean(),
        "p25_eur": g.quantile(0.25),
        "p75_eur": g.quantile(0.75),
        "p90_eur": g.quantile(0.90),
        "max_eur": g.max(),
        "skew_raw": g.skew(),
        "skew_log10": t.assign(_l=np.log10(t[TARGET].astype(float))).groupby(by, observed=True)["_l"].skew(),
    })
    out["coverage_pct"] = out["usable_targets"] / out["rows"] * 100
    out["mean_to_median"] = out["mean_eur"] / out["median_eur"]
    return out.reindex(order) if order is not None else out


def target_position_season(df: pd.DataFrame, scope, stat: str = "median") -> pd.DataFrame:
    t = df.loc[df["target_usable"]]
    table = t.pivot_table(index=POSITION, columns="season", values=TARGET, aggfunc=stat)
    return table.reindex(index=POSITION_ORDER, columns=list(scope.labels))


def target_tail(df: pd.DataFrame, top: int = 12) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fence counts on raw and log scales, and the largest and smallest targets with audit context.

    target_audit_* columns are read here only to check that tail values are consistent with the player's
    previous valuation (audit use; never a predictor, P4-A03).
    """
    t = usable_target(df)
    rows = []
    for scale, s in (("raw_eur", t), ("log10_eur", np.log10(t))):
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        for k in (1.5, 3.0):
            lo, hi = q1 - k * iqr, q3 + k * iqr
            rows.append({"scale": scale, "fence": f"{k} IQR", "lower_fence": 10 ** lo if scale == "log10_eur" else lo,
                         "upper_fence": 10 ** hi if scale == "log10_eur" else hi,
                         "below": int((s < lo).sum()), "above": int((s > hi).sum())})
    fences = pd.DataFrame(rows)
    cols = ["fotmob_player_name", "season", POSITION, "age_at_season_end_years", TARGET, "target_valuation_date",
            "target_valuation_age_days", "target_status", "target_audit_previous_value",
            "target_audit_ratio_to_previous_value"]
    u = df.loc[df["target_usable"], cols]
    extremes = pd.concat([u.nlargest(top, TARGET).assign(tail="highest"),
                          u.nsmallest(top, TARGET).assign(tail="lowest")])
    return fences, extremes


def tail_consistency(df: pd.DataFrame) -> dict:
    """Evidence that the upper tail is not a data error: tail players' previous valuations are also high."""
    u = df.loc[df["target_usable"]]
    t = u[TARGET]
    q1, q3 = t.quantile([0.25, 0.75])
    tail = u[t > q3 + 3 * (q3 - q1)]
    ratio = tail["target_audit_ratio_to_previous_value"].dropna()
    return {
        "upper_3iqr_rows": len(tail),
        "upper_3iqr_players": int(tail["canonical_player_id"].nunique()),
        "with_previous_valuation": int(ratio.size),
        "ratio_to_previous_median": float(ratio.median()) if ratio.size else None,
        "ratio_to_previous_min": float(ratio.min()) if ratio.size else None,
        "ratio_to_previous_max": float(ratio.max()) if ratio.size else None,
        "previous_value_median_eur": float(tail["target_audit_previous_value"].median()),
        "tail_rows_by_season": tail["season"].value_counts().sort_index().to_dict(),
        "tail_rows_by_position": tail[POSITION].value_counts().reindex(POSITION_ORDER, fill_value=0).to_dict(),
    }


def target_granularity(df: pd.DataFrame) -> dict:
    t = usable_target(df)
    return {
        "distinct_values": int(t.nunique()),
        "multiple_of_100k_pct": float((t % 100_000 == 0).mean() * 100),
        "multiple_of_1m_pct": float((t % 1_000_000 == 0).mean() * 100),
        "multiple_of_5m_pct": float((t % 5_000_000 == 0).mean() * 100),
        "most_common_eur": {str(int(k)): int(v) for k, v in t.value_counts().head(10).items()},
    }


def target_missing(df: pd.DataFrame) -> pd.DataFrame:
    m = df.loc[~df["target_usable"]]
    return pd.crosstab(m["target_missing_reason"], m["season"], margins=True, margins_name="total")


def target_timing(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Valuation age by season (RD-03 / ISS-21 context). Descriptive; no filter is derived from it."""
    u = df.loc[df["target_usable"]]
    g = u.groupby("season")["target_valuation_age_days"]
    out = pd.DataFrame({"usable_targets": g.size(), "median_age_days": g.median(), "p90_age_days": g.quantile(0.9),
                        "max_age_days": g.max(),
                        "share_over_90_days_pct": g.apply(lambda s: (s > 90).mean() * 100),
                        "median_valuation_date": u.groupby("season")["target_valuation_date"].agg(
                            lambda s: pd.Series(pd.to_datetime(s)).median().date()),
                        "modal_valuation_date": u.groupby("season")["target_valuation_date"].agg(lambda s: s.mode().iloc[0]),
                        "modal_date_share_pct": u.groupby("season")["target_valuation_date"].agg(
                            lambda s: (s == s.mode().iloc[0]).mean() * 100)})
    return out.reindex(list(scope.labels))


# ----------------------------------------------------------------------------- features
def applicable_rows(df: pd.DataFrame, feature: str, register: pd.DataFrame) -> pd.Series:
    scope = register.set_index("feature").at[feature, "applicable_positions"]
    return df[POSITION].eq("GK") if scope == "GK_ONLY" else pd.Series(True, index=df.index)


def status_column(feature: str) -> str | None:
    return "s_" + feature[2:] if feature.startswith("m_") else None


def feature_summary(df: pd.DataFrame, register: pd.DataFrame) -> pd.DataFrame:
    """One row per feature, computed on the applicable rows (GK rows for GK-only metrics, all rows otherwise)."""
    reg = register.set_index("feature")
    rows = []
    for f in FEATURES:
        app = applicable_rows(df, f, register)
        s = df.loc[app, f]
        row = {"feature": f, "analysis_group": reg.at[f, "analysis_group"], "kind": reg.at[f, "kind"],
               "eligibility_category": reg.at[f, "eligibility_category"],
               "reliability_status": reg.at[f, "reliability_status"],
               "applicable_positions": reg.at[f, "applicable_positions"],
               "applicable_rows": int(app.sum()), "null_applicable": int(s.isna().sum()),
               "missing_pct_applicable": s.isna().mean() * 100,
               "values_on_non_applicable_rows": int(df.loc[~app, f].notna().sum()),
               "seasons_with_values": int(df.loc[df[f].notna(), "season"].nunique())}
        st = status_column(f)
        if st:
            counts = df.loc[app, st].value_counts()
            for k in ("OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED",
                      "MISSING", "UNVERIFIED_POSITION", "CONFLICTING", "UNSUPPORTED"):
                row[f"status_{k}"] = int(counts.get(k, 0))
        d = describe(s)
        row.update(d)
        row["shape"] = shape_label(d.get("skew", np.nan))
        row["pending_owner_decision"] = reg.at[f, "pending_owner_decision"]
        rows.append(row)
    return pd.DataFrame(rows)


def compact_summary(summary: pd.DataFrame) -> pd.DataFrame:
    cols = ["feature", "kind", "n", "missing_pct_applicable", "mean", "p50", "std", "min", "p05", "p95", "max",
            "skew", "upper_3iqr", "zero_pct", "seasons_with_values"]
    return summary[cols]


def group_overview(summary: pd.DataFrame) -> pd.DataFrame:
    g = summary.groupby("analysis_group")
    return pd.DataFrame({
        "features": g.size(),
        "conditional_or_pending": g.apply(lambda x: int((x["eligibility_category"] != "CANDIDATE_PREDICTOR").sum())),
        "median_missing_pct_applicable": g["missing_pct_applicable"].median(),
        "max_missing_pct_applicable": g["missing_pct_applicable"].max(),
        "strongly_right_skewed": g.apply(lambda x: int((x["skew"] >= 1).sum())),
        "values_beyond_3iqr": g["upper_3iqr"].sum(),
    })


def coverage_by_season(df: pd.DataFrame, register: pd.DataFrame, scope) -> pd.DataFrame:
    """Share of applicable rows with a value, per season."""
    out = {}
    for f in FEATURES:
        app = applicable_rows(df, f, register)
        out[f] = df.loc[app].groupby("season")[f].apply(lambda s: s.notna().mean() * 100)
    return pd.DataFrame(out).T.reindex(columns=list(scope.labels))


def limited_coverage(summary: pd.DataFrame, coverage: pd.DataFrame, threshold: float = 20.0) -> pd.DataFrame:
    """Features with more than `threshold`% of applicable rows null, or a season below 50% coverage."""
    s = summary.set_index("feature")
    worst = coverage.min(axis=1)
    sel = s.index[(s["missing_pct_applicable"] > threshold) | (worst < 50)]
    return pd.DataFrame({"missing_pct_applicable": s.loc[sel, "missing_pct_applicable"],
                         "status_MISSING": s.loc[sel, "status_MISSING"],
                         "lowest_season_coverage_pct": worst[sel],
                         "seasons_with_values": s.loc[sel, "seasons_with_values"],
                         "pending_owner_decision": s.loc[sel, "pending_owner_decision"]}
                        ).sort_values("missing_pct_applicable", ascending=False)


def position_relevance(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Non-null share and median value by position for every feature."""
    present = df.groupby(POSITION)[FEATURES].apply(lambda g: g.notna().mean() * 100).T[POSITION_ORDER]
    median = df.groupby(POSITION)[FEATURES].median().T[POSITION_ORDER]
    return present, median


def per90_by_minutes(df: pd.DataFrame) -> pd.DataFrame:
    """Per-90 rate distribution by minutes band (P4-B05). Descriptive: no minimum-minutes rule is applied."""
    band = pd.cut(df["m_minutes_played"], MINUTES_BANDS, labels=MINUTES_LABELS)
    rows = []
    for f in per90_columns():
        for label in MINUTES_LABELS:
            s = df.loc[band == label, f].dropna()
            rows.append({"feature": f, "minutes_band": label, "n": int(s.size), "median": s.median(),
                         "p95": s.quantile(0.95) if s.size else np.nan, "max": s.max(), "std": s.std()})
    return pd.DataFrame(rows)


def per90_tail_share(df: pd.DataFrame) -> pd.DataFrame:
    """For each per-90 rate: how many of its top-1% values come from rows with under 90 minutes."""
    rows = []
    for f in per90_columns():
        s = df[[f, "m_minutes_played"]].dropna()
        top = s[s[f] >= s[f].quantile(0.99)]
        rows.append({"feature": f, "top1pct_rows": len(top), "of_which_minutes_under_90": int((top["m_minutes_played"] < 90).sum()),
                     "rows_under_90_minutes_with_value": int((s["m_minutes_played"] < 90).sum())})
    return pd.DataFrame(rows)


def zero_recording(df: pd.DataFrame, register: pd.DataFrame) -> pd.DataFrame:
    """How zeros and nulls are recorded per feature (ISS-25). Outfield count metrics without any recorded zero
    have nulls concentrated among low-minute rows: consistent with "null may mean no event", but unverifiable,
    so nulls are NOT converted to zero (P4-A07). Minutes are used only to describe where nulls occur."""
    rows = []
    for f in FEATURES:
        if not f.startswith("m_") or f == "m_minutes_played" or f in FEATURE_GROUPS["8 Goalkeeping"]:
            continue  # goalkeeper metrics: only 7 GK rows have minutes (ISS-11)
        app = applicable_rows(df, f, register) & df["m_minutes_played"].notna()
        sub = df.loc[app, [f, "m_minutes_played"]]
        null = sub[f].isna()
        values = sub.loc[~null, f]
        rows.append({"feature": f, "kind": kind_of(f), "rows_with_minutes": int(app.sum()), "null_rows": int(null.sum()),
                     "recorded_zeros": int((values == 0).sum()), "min_observed": values.min(),
                     "median_minutes_when_null": sub.loc[null, "m_minutes_played"].median(),
                     "median_minutes_when_observed": sub.loc[~null, "m_minutes_played"].median(),
                     "null_rows_under_450_minutes_pct": (sub.loc[null, "m_minutes_played"] < 450).mean() * 100
                     if null.any() else np.nan})
    out = pd.DataFrame(rows)
    counts = out["kind"].isin(["season count/total"])
    out["count_metric_without_recorded_zero"] = counts & out["recorded_zeros"].eq(0) & out["null_rows"].gt(0)
    return out


def detailed_block_missing(df: pd.DataFrame) -> dict:
    """Outfield rows with minutes but no detailed statistics (m_touches null): the 'whole block missing' pattern."""
    o = df[POSITION].ne("GK") & df["m_minutes_played"].notna()
    block = o & df["m_touches"].isna()
    m = df.loc[block]
    return {"outfield_rows_with_minutes": int(o.sum()), "rows_without_detailed_stats": int(block.sum()),
            "median_minutes": float(m["m_minutes_played"].median()),
            "max_minutes": float(m["m_minutes_played"].max()),
            "share_under_90_minutes_pct": float((m["m_minutes_played"] < 90).mean() * 100),
            "median_null_metrics": float(m["missing_feature_count"].median()),
            "target_coverage_pct": float(m["target_usable"].mean() * 100),
            "by_season": m["season"].value_counts().sort_index().to_dict()}


def age_profile(df: pd.DataFrame, scope) -> dict:
    a = df["age_at_season_end_years"]
    return {
        "overall": describe(a),
        "by_season": df.groupby("season")["age_at_season_end_years"].describe().reindex(list(scope.labels)),
        "by_position": df.groupby(POSITION)["age_at_season_end_years"].describe().reindex(POSITION_ORDER),
    }


def club_context_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Counts only (RS5-12 pending): no distribution is read as a candidate predictor."""
    return pd.crosstab(df["multi_club_class"].fillna("<null>"), df["season"], margins=True, margins_name="total")


def special_interpretation(summary: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    s = summary.set_index("feature")
    gk_minutes_null = int(df.loc[df[POSITION] == "GK", "m_minutes_played"].isna().sum())
    rows = [
        ("Source-reported rates and totals (ISS-29)", "m_aerials_won_percent, m_cross_accuracy, m_duels_won_percent, m_long_ball_accuracy, m_passing_accuracy, m_save_percentage, m_clean_sheets, m_goals_conceded_per90",
         "Accepted as the source reports them; no independent window check; denominators not available. Conditional predictors."),
        ("Pending owner decision RD-04", ", ".join(RD04),
         "Described here; eligibility not decided. clearances has values in 3 of 5 seasons."),
        ("Goalkeeper-only metrics (ISS-11)", ", ".join(FEATURE_GROUPS["8 Goalkeeping"]),
         f"Described on GK rows only; outfield rows are UNVERIFIED_POSITION (not applicable, not zero). GK minutes null on {gk_minutes_null} of {int((df[POSITION] == 'GK').sum())} rows."),
        ("Per-90 rates on small denominators (P4-B05)", ", ".join(per90_columns()),
         "Rates from under 90 minutes produce the extreme values; read with minutes; no minimum-minutes rule applied."),
        ("Percentages and ratings", ", ".join(prof.PERCENT_METRICS + ["m_rating"]),
         "Bounded scales; skewness and IQR fences mean less here; small samples produce 0% and 100% values."),
        ("Starts anomaly (DQ-RS5-04)", "m_starts", "6 rows with starts > appearances kept as published."),
        ("Whole-season position (P4-B04, RD-03)", POSITION, "Modal position over the whole season, partly after the valuation date."),
        ("Zero-heavy counts", ", ".join(s.index[s["zero_pct"] >= 50]),
         "Half or more of the observed values are 0 (rare events); medians are 0, means are driven by few players."),
    ]
    return pd.DataFrame(rows, columns=["topic", "features", "interpretation"])


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    dictionary, eligibility, reliability = prof.load_metadata()
    register = feature_register(eligibility, reliability)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tsum = target_summary(df)
    by_season = target_by(df, "season", list(scope.labels))
    import duckdb
    con = duckdb.connect()
    con.register("target_season_table", by_season.rename_axis("season").reset_index())
    scope_check_derived = check_table(con, "target_season_table", scope, "season", None)
    by_position = target_by(df, POSITION, POSITION_ORDER)
    fences, extremes = target_tail(df)
    summary = feature_summary(df, register)
    coverage = coverage_by_season(df, register, scope)
    present, median = position_relevance(df)
    age = age_profile(df, scope)
    tables = {
        "feature_register_42.csv": register,
        "excluded_from_predictor_analysis.csv": excluded_from_analysis(df, eligibility),
        "target_summary.csv": tsum,
        "target_by_season.csv": by_season,
        "target_by_position.csv": by_position,
        "target_median_position_season.csv": target_position_season(df, scope, "median"),
        "target_count_position_season.csv": target_position_season(df, scope, "count"),
        "target_fences.csv": fences,
        "target_extremes.csv": extremes,
        "target_missing_by_reason_season.csv": target_missing(df),
        "target_timing_by_season.csv": target_timing(df, scope),
        "feature_summary.csv": summary,
        "feature_group_overview.csv": group_overview(summary),
        "feature_coverage_by_season.csv": coverage,
        "feature_limited_coverage.csv": limited_coverage(summary, coverage),
        "feature_present_by_position.csv": present,
        "feature_median_by_position.csv": median,
        "per90_by_minutes_band.csv": per90_by_minutes(df),
        "per90_top1pct_minutes.csv": per90_tail_share(df),
        "zero_recording.csv": zero_recording(df, register),
        "age_by_season.csv": age["by_season"],
        "age_by_position.csv": age["by_position"],
        "club_context_counts.csv": club_context_counts(df),
        "special_interpretation.csv": special_interpretation(summary, df),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8",
                     float_format="%.6g")
    summary_json = {
        "dataset": str(prof.DATASET.relative_to(ROOT)).replace("\\", "/"),
        "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_check": verification["scope_check"],
        "scope_id": scope.scope_id,
        "scope_check_derived_target_season_table": scope_check_derived,
        "target": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                   for k, v in tsum["raw_eur"].items()},
        "target_log10": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                         for k, v in tsum["log10_eur"].items()},
        "tail_consistency": tail_consistency(df),
        "granularity": target_granularity(df),
        "detailed_block_missing": detailed_block_missing(df),
        "age_overall": {k: float(v) for k, v in age["overall"].items()},
        "features_analysed": len(FEATURES),
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "univariate_summary.json").write_text(json.dumps(summary_json, indent=1, default=str) + "\n",
                                                     encoding="utf-8")
    return summary_json


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:6000])
