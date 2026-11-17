"""Phase 4.4: multivariate and group analysis of the official FB69 research release.

Descriptive and read-only. The notebook (FB69_report.ipynb) and the evidence CLI both call these functions.
Groups are derived on the fly from existing columns for description only; nothing is written back, imputed,
filtered, capped or selected. Rows with a missing grouping value form their own "missing" group (never zero).
No model is fitted and no dimensionality reduction is used.

Every target statement carries RD-03 (mostly mid-season valuation vs whole-season metrics) and, for season
comparisons, ISS-21/ISS-22 (league-wide valuation batches; staleness differs strongly by season).

Usage (evidence): python -I -X utf8 src/phase4/multivariate.py <out_dir>
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
from src.phase4 import profiling as prof  # noqa: E402
from src.phase4 import univariate as uni  # noqa: E402
from src.research_scope.scope import check_table  # noqa: E402

TARGET = uni.TARGET
POSITION = uni.POSITION
POSITION_ORDER = prof.POSITION_ORDER
MIN_N = biv.MIN_N
SEASON_MATCHES = 38   # EPL league matches per club and season (20 clubs, double round robin)

# Playing-time role from league starts: quarter-season boundaries of a 38-match season. Starts are used rather
# than minutes because minutes are null on 199 of 206 goalkeeper rows (ISS-11) while starts are almost complete.
STARTS_BANDS = [-0.5, 0.5, 9.5, 18.5, 28.5, SEASON_MATCHES + 0.5]
STARTS_LABELS = ["0 starts", "1-9 starts", "10-18 starts", "19-28 starts", "29-38 starts"]
STARTS_SHORT = {"0 starts": "none", "1-9 starts": "occasional", "10-18 starts": "rotation",
                "19-28 starts": "regular", "29-38 starts": "core"}
# Usage pattern: share of appearances that were starts. Boundaries at 1/2 (majority of appearances from the bench
# vs from the start) and 0.9 (almost every appearance a start).
SHARE_BANDS = [-0.01, 0.4999, 0.8999, 2.0]
SHARE_LABELS = ["mainly substitute (<50% started)", "mixed (50-89% started)", "starter (>=90% started)"]
AGE_LABELS = biv.AGE_LABELS

OUTFIELD_METRICS = ["m_goals", "m_assists", "m_expected_goals", "m_expected_assists", "m_shots_per90",
                    "m_accurate_passes_per90", "m_passing_accuracy", "m_tackles_per90", "m_interceptions_per90",
                    "m_aerials_won_percent", "m_duels_won_percent", "m_rating"]
GK_METRICS = ["m_saves", "m_save_percentage", "m_clean_sheets", "m_goals_conceded", "m_goals_conceded_per90",
              "m_penalty_saves", "m_goals_prevented", "m_rating"]
PAIR_VARS = ["age_at_season_end_years", "m_starts", "m_rating", "m_expected_goals", "m_expected_assists",
             "m_accurate_passes_per90"]
SEASON_RATE_METRICS = ["m_shots_per90", "m_accurate_passes_per90", "m_passing_accuracy", "m_long_ball_accuracy",
                       "m_tackles_per90", "m_interceptions_per90", "m_recoveries_per90", "m_aerials_won_percent",
                       "m_duels_won_percent", "m_rating"]
RD03 = biv.RD03
ISS21 = ("ISS-21/ISS-22: each season's targets come mainly from one league-wide valuation batch at a different "
         "distance from season end; season level differences mix market movement and batch timing.")


# ----------------------------------------------------------------------------- groups
def groups(df: pd.DataFrame) -> pd.DataFrame:
    """Derived grouping columns (a new frame; the dataset is not changed)."""
    starts = pd.cut(df["m_starts"], STARTS_BANDS, labels=STARTS_LABELS).astype(object)
    share = (df["m_starts"] / df["m_appearances"]).clip(upper=1.0)  # 6 rows with starts > appearances (DQ-RS5-04)
    usage = pd.cut(share, SHARE_BANDS, labels=SHARE_LABELS).astype(object)
    return pd.DataFrame({
        "starts_group": starts.where(df["m_starts"].notna(), "starts missing"),
        "usage_group": usage.where(share.notna(), "appearances missing"),
        "age_band": biv.age_band(df).astype(object),
        "minutes_band": biv.minutes_band(df),
        "p4b01": biv.identity_sensitivity_mask(df),
    }, index=df.index)


def group_boundaries(df: pd.DataFrame) -> pd.DataFrame:
    """Counts behind each grouping, to show that every boundary leaves interpretable groups."""
    g = groups(df)
    rows = []
    for col, order in (("starts_group", STARTS_LABELS + ["starts missing"]), ("usage_group", SHARE_LABELS + ["appearances missing"]),
                       ("age_band", AGE_LABELS), ("minutes_band", [*uni.MINUTES_LABELS, "minutes missing"])):
        counts = pd.crosstab(g[col], df[POSITION]).reindex(index=order, columns=POSITION_ORDER, fill_value=0)
        for label, r in counts.iterrows():
            rows.append({"grouping": col, "group": label, **r.to_dict(), "total": int(r.sum()),
                         "usable_targets": int((df["target_usable"] & g[col].eq(label)).sum())})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- profiles
def profile(df: pd.DataFrame, by: list[str] | str) -> pd.DataFrame:
    """Population, target, age, playing-time and missingness profile per group."""
    by = [by] if isinstance(by, str) else by
    d = df.join(groups(df))
    u = d[d["target_usable"]]
    g, gu = d.groupby(by, observed=True), u.groupby(by, observed=True)
    out = pd.DataFrame({
        "rows": g.size(), "players": g["canonical_player_id"].nunique(),
        "usable_targets": gu.size(),
        "target_p10_eur": gu[TARGET].quantile(0.10), "target_p25_eur": gu[TARGET].quantile(0.25),
        "target_median_eur": gu[TARGET].median(), "target_p75_eur": gu[TARGET].quantile(0.75),
        "target_p90_eur": gu[TARGET].quantile(0.90), "target_max_eur": gu[TARGET].max(),
        "age_median": g["age_at_season_end_years"].median(),
        "starts_median": g["m_starts"].median(), "appearances_median": g["m_appearances"].median(),
        "minutes_median": g["m_minutes_played"].median(),
        "minutes_missing_pct": g["m_minutes_played"].apply(lambda s: s.isna().mean() * 100),
        "null_metrics_median": g["missing_feature_count"].median(),
        "p4b01_share_pct": g["p4b01"].mean() * 100,
        "valuation_age_median_days": gu["target_valuation_age_days"].median(),
    })
    out["interpretable"] = out["usable_targets"] >= MIN_N
    return out


def median_grid(df: pd.DataFrame, rows: str, cols: str, row_order, col_order, sub: pd.Series | None = None):
    """Median target and count for each rows x cols cell; cells below MIN_N are left empty in the median grid."""
    d = df.join(groups(df))
    d = d[d["target_usable"] & (True if sub is None else sub.reindex(d.index, fill_value=False))]
    med = d.pivot_table(index=rows, columns=cols, values=TARGET, aggfunc="median", observed=True)
    n = d.pivot_table(index=rows, columns=cols, values=TARGET, aggfunc="size", observed=True)
    med, n = med.reindex(index=row_order, columns=col_order), n.reindex(index=row_order, columns=col_order).fillna(0).astype(int)
    return med.where(n >= MIN_N), n


def metric_profile(df: pd.DataFrame, by: str, metrics: list[str], rows: pd.Series, order) -> pd.DataFrame:
    """Median, p90 and missing share of metrics per group (pairwise: nulls are counted, never filled)."""
    out = []
    d = df.join(groups(df))[rows]
    for key, sub in d.groupby(by, observed=True):
        for m in metrics:
            s = sub[m]
            out.append({by: key, "metric": m, "rows": len(s), "n": int(s.notna().sum()),
                        "missing_pct": s.isna().mean() * 100, "median": s.median(), "p90": s.quantile(0.9)})
    t = pd.DataFrame(out)
    present = list(dict.fromkeys(t[by]))
    t[by] = pd.Categorical(t[by], [o for o in order if o in present] + [o for o in present if o not in order], ordered=True)
    return t.sort_values([by, "metric"]).reset_index(drop=True)


def status_mix(df: pd.DataFrame, rows: pd.Series, by: str, order) -> pd.DataFrame:
    """Share of metric cells by s_* status per group (all 53 status columns pooled)."""
    s_cols = [c for c in df.columns if c.startswith("s_") and c != "s_key_passes"]
    d = df.join(groups(df))[rows]
    out = {}
    for key, sub in d.groupby(by, observed=True):
        counts = pd.Series(sub[s_cols].to_numpy().ravel()).value_counts()
        out[key] = counts / counts.sum() * 100
    return pd.DataFrame(out).T.reindex([o for o in order if o in out]).fillna(0)


# ----------------------------------------------------------------------------- within-group associations
def within_group_spearman(df: pd.DataFrame, register: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Feature-target Spearman inside each position, for all rows and for rows with at least 19 starts
    (regular or core). Shows whether associations survive once fringe players are set aside."""
    d = df.join(groups(df))
    reg = d["starts_group"].isin(["19-28 starts", "29-38 starts"])
    rho, n = {}, {}
    for f in features:
        sub = biv.pair_frame(df, f, register).join(reg.rename("regular"))
        for pos in POSITION_ORDER:
            for label, mask in (("all", pd.Series(True, index=sub.index)), (">=19 starts", sub["regular"])):
                s = sub[(sub[POSITION] == pos) & mask]
                key = f"{pos} {label}"
                n.setdefault(f, {})[key] = len(s)
                rho.setdefault(f, {})[key] = biv.spearman(s[f].to_numpy(float), s[TARGET].to_numpy(float)) if len(s) >= MIN_N else np.nan
    cols = [f"{p} {l}" for p in POSITION_ORDER for l in ("all", ">=19 starts")]
    return pd.DataFrame(rho).T[cols], pd.DataFrame(n).T[cols]


def position_correlation(df: pd.DataFrame, position: str, variables: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Spearman matrix among selected variables and the log10 target, within one position (usable targets)."""
    rows = df[POSITION].eq(position) & df["target_usable"]
    d = df.loc[rows, variables].astype(float).assign(log10_target=np.log10(df.loc[rows, TARGET].astype(float)))
    corr = d.corr(method="spearman", min_periods=MIN_N)
    present = d.notna().astype(int)
    return corr, present.T @ present


# ----------------------------------------------------------------------------- seasons
def season_population(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Rows, players, returning players (also present in the previous official season) and composition."""
    seasons = list(scope.labels)
    players = {s: set(df.loc[df["season"] == s, "canonical_player_id"]) for s in seasons}
    d = df.join(groups(df))
    out = []
    for i, s in enumerate(seasons):  # noqa: B007
        sub = d[d["season"] == s]
        ret = len(players[s] & players[seasons[i - 1]]) if i else np.nan
        row = {"season": s, "rows": len(sub), "players": len(players[s]),
               "returning_from_previous_season": ret,
               "returning_pct": ret / len(players[s]) * 100 if i else np.nan,
               "usable_targets": int(sub["target_usable"].sum()),
               "missing_targets": int((~sub["target_usable"]).sum()),
               "starts_median": sub["m_starts"].median(), "minutes_median": sub["m_minutes_played"].median(),
               "minutes_missing": int(sub["m_minutes_played"].isna().sum()),
               "null_metrics_median": sub["missing_feature_count"].median(),
               "multi_club_rows": int(sub["multi_club_class"].ne("SINGLE_CLUB").sum()),
               "p4b01_rows": int(sub["p4b01"].sum())}
        for pos in POSITION_ORDER:
            row[f"share_{pos}_pct"] = sub[POSITION].eq(pos).mean() * 100
        for lab in STARTS_LABELS:
            row[f"share_{STARTS_SHORT[lab]}_pct"] = sub["starts_group"].eq(lab).mean() * 100
        out.append(row)
    return pd.DataFrame(out).set_index("season")


def season_timing(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Target timing per season (ISS-21/ISS-22): reuse of the Phase 4.2 implementation plus staleness buckets."""
    t = uni.target_timing(df, scope)
    u = df[df["target_usable"]]
    buckets = pd.crosstab(u["season"], u["target_staleness_bucket"], normalize="index") * 100
    return t.join(buckets.add_prefix("bucket_").add_suffix("_pct")).reindex(list(scope.labels))


def season_stratified_medians(df: pd.DataFrame, scope, coarse: bool = False) -> pd.DataFrame:
    """Median target per season within position x starts group, and its ratio to the first season. If the season
    level shift were only a change in composition, stratified ratios would stay near 1. `coarse` uses two roles
    (fewer than 19 starts / at least 19) so that more cells reach MIN_N."""
    rows = []
    d = df.join(groups(df))
    d = d[d["target_usable"]]
    if coarse:
        d["starts_group"] = np.where(d["m_starts"] >= 19, ">=19 starts", "<19 starts")
    labels = ["<19 starts", ">=19 starts"] if coarse else STARTS_LABELS
    seasons = list(scope.labels)
    for pos in POSITION_ORDER:
        for grp in labels:
            sub = d[(d[POSITION] == pos) & (d["starts_group"] == grp)]
            n = sub.groupby("season").size().reindex(seasons, fill_value=0)
            med = sub.groupby("season")[TARGET].median().reindex(seasons)
            ok = n >= MIN_N
            rec = {"position": pos, "starts_group": grp, "min_n": int(n.min())}
            for s in seasons:
                rec[f"median_{prof.short(s)}"] = med[s] if ok[s] else np.nan
                rec[f"n_{prof.short(s)}"] = int(n[s])
            base = med[seasons[0]] if ok[seasons[0]] else np.nan
            rec["last_to_first_ratio"] = med[seasons[-1]] / base if ok[seasons[-1]] and pd.notna(base) else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def returning_player_change(df: pd.DataFrame, scope) -> pd.DataFrame:
    """For players present in consecutive seasons with usable targets: median log10 ratio of their own target.
    Removes population composition, but still mixes ageing, performance, market movement and batch timing."""
    seasons = list(scope.labels)
    u = df[df["target_usable"]].set_index(["canonical_player_id", "season"])[TARGET]
    rows = []
    for a, b in zip(seasons, seasons[1:]):
        pa, pb = u.xs(a, level="season"), u.xs(b, level="season")
        both = pa.index.intersection(pb.index)
        ratio = np.log10(pb[both] / pa[both])
        rows.append({"from": a, "to": b, "players": len(both), "median_ratio": 10 ** ratio.median(),
                     "share_increase_pct": (ratio > 0).mean() * 100, "share_unchanged_pct": (ratio == 0).mean() * 100,
                     "share_decrease_pct": (ratio < 0).mean() * 100})
    return pd.DataFrame(rows)


def season_metric_medians(df: pd.DataFrame, scope) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Median of rate metrics per season for outfield players with at least 19 starts (stable denominators),
    and the share of those rows with a value. Detects definition or coverage changes across seasons."""
    d = df.join(groups(df))
    rows = d[POSITION].isin(biv.OUTFIELD) & d["starts_group"].isin(["19-28 starts", "29-38 starts"])
    sub = d[rows]
    med = sub.groupby("season")[SEASON_RATE_METRICS].median().T.reindex(columns=list(scope.labels))
    cov = sub.groupby("season")[SEASON_RATE_METRICS].apply(lambda g: g.notna().mean() * 100).T.reindex(columns=list(scope.labels))
    return med, cov


# ----------------------------------------------------------------------------- identity sensitivity of groups
def group_identity_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    """Median target per position x starts group, with and without the P4-B01 rows (comparison only)."""
    d = df.join(groups(df))
    d = d[d["target_usable"]]
    rows = []
    for (pos, grp), sub in d.groupby([POSITION, "starts_group"], observed=True):
        strict = sub[~sub["p4b01"]]
        rows.append({"position": pos, "starts_group": grp, "n_all": len(sub), "n_without_p4b01": len(strict),
                     "p4b01_share_pct": sub["p4b01"].mean() * 100, "median_all_eur": sub[TARGET].median(),
                     "median_without_p4b01_eur": strict[TARGET].median() if len(strict) >= MIN_N else np.nan})
    out = pd.DataFrame(rows)
    out["ratio"] = out["median_without_p4b01_eur"] / out["median_all_eur"]
    return out


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    dictionary, eligibility, reliability = prof.load_metadata()
    register = uni.feature_register(eligibility, reliability)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seasons = list(scope.labels)
    g = groups(df)
    outfield = df[POSITION].isin(biv.OUTFIELD)

    pos_profile = profile(df, POSITION).reindex(POSITION_ORDER)
    season_prof = profile(df, "season").reindex(seasons)
    within_rho, within_n = within_group_spearman(df, register, uni.FEATURES)
    grid_med, grid_n = median_grid(df, POSITION, "starts_group", POSITION_ORDER, STARTS_LABELS)
    med_rates, cov_rates = season_metric_medians(df, scope)
    pop = season_population(df, scope)

    import duckdb
    con = duckdb.connect()
    con.register("season_population", pop.reset_index()[["season", "rows"]])
    scope_check_derived = check_table(con, "season_population", scope, "season", None)

    tables = {
        "group_boundaries.csv": group_boundaries(df),
        "position_profile.csv": pos_profile,
        "position_outfield_metrics.csv": metric_profile(df, POSITION, OUTFIELD_METRICS, outfield, biv.OUTFIELD),
        "position_goalkeeper_metrics.csv": metric_profile(df, "starts_group", GK_METRICS, df[POSITION].eq("GK"),
                                                          STARTS_LABELS),
        "position_status_mix.csv": status_mix(df, pd.Series(True, index=df.index), POSITION, POSITION_ORDER),
        "position_starts_group_profile.csv": profile(df, [POSITION, "starts_group"]),
        "position_age_band_profile.csv": profile(df, [POSITION, "age_band"]),
        "usage_group_profile.csv": profile(df, [POSITION, "usage_group"]),
        "starts_group_profile.csv": profile(df, "starts_group").reindex(STARTS_LABELS + ["starts missing"]).dropna(how="all"),
        "starts_group_status_mix.csv": status_mix(df, outfield, "starts_group", STARTS_LABELS),
        "median_target_position_x_starts.csv": grid_med,
        "count_position_x_starts.csv": grid_n,
        "within_group_spearman.csv": within_rho,
        "within_group_n.csv": within_n,
        "season_population.csv": pop,
        "season_profile.csv": season_prof,
        "season_timing.csv": season_timing(df, scope),
        "season_stratified_medians.csv": season_stratified_medians(df, scope),
        "season_stratified_medians_two_roles.csv": season_stratified_medians(df, scope, coarse=True),
        "returning_player_change.csv": returning_player_change(df, scope),
        "season_rate_metric_medians_regular_outfield.csv": med_rates,
        "season_rate_metric_coverage_regular_outfield.csv": cov_rates,
        "group_identity_sensitivity.csv": group_identity_sensitivity(df),
    }
    for pos in POSITION_ORDER:
        variables = PAIR_VARS if pos != "GK" else ["age_at_season_end_years", "m_starts", "m_rating", "m_clean_sheets",
                                                   "m_save_percentage", "m_goals_conceded_per90"]
        corr, _ = position_correlation(df, pos, variables)
        tables[f"position_correlation_{pos}.csv"] = corr
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8", float_format="%.6g")
    strat = tables["season_stratified_medians_two_roles.csv"]
    summary = {
        "dataset": str(prof.DATASET.relative_to(ROOT)).replace("\\", "/"),
        "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_id": scope.scope_id, "scope_check": verification["scope_check"],
        "scope_check_derived_season_population": scope_check_derived,
        "rows": len(df), "usable_targets": int(df["target_usable"].sum()),
        "groupings": {"starts_group": STARTS_LABELS, "usage_group": SHARE_LABELS, "age_band": AGE_LABELS,
                      "minutes_band": uni.MINUTES_LABELS},
        "min_n": MIN_N,
        "position_median_target_eur": pos_profile["target_median_eur"].to_dict(),
        "stratified_last_to_first_ratio_median": float(strat["last_to_first_ratio"].median()),
        "stratified_cells_with_ratio": int(strat["last_to_first_ratio"].notna().sum()),
        "temporal_caveats": [RD03, ISS21],
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "multivariate_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:4000])
