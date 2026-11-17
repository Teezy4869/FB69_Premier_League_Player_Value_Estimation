"""Phase 4.3: bivariate analysis of the official FB69 research release.

Descriptive association analysis, read-only. The notebook (FB69_report.ipynb) and the evidence CLI both call
these functions. Nothing here imputes, filters, caps, transforms or selects features: correlations are
computed on pairwise-complete rows (a null stays a null and is never read as zero), the log10 target is
computed on the fly for description only, and no feature is removed because it is correlated with another.

Association is not causation. Every target-feature result carries the RD-03 caveat: the target is the latest
valuation on or before season end (in practice mostly a mid-season valuation), while the metrics cover the
whole season. Later performance cannot have caused an earlier valuation.

Usage (evidence): python -I -X utf8 src/phase4/bivariate.py <out_dir>
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
from src.phase4 import univariate as uni  # noqa: E402
from src.research_scope.scope import check_table  # noqa: E402

TARGET = uni.TARGET
POSITION = uni.POSITION
POSITION_ORDER = prof.POSITION_ORDER
OUTFIELD = ["DEF", "MID", "FWD"]
FEATURES = uni.FEATURES
GK_FEATURES = uni.FEATURE_GROUPS["8 Goalkeeping"]
OUTFIELD_FEATURES = [f for f in FEATURES if f not in GK_FEATURES]
SOURCE_REPORTED = ["m_aerials_won_percent", "m_cross_accuracy", "m_duels_won_percent", "m_long_ball_accuracy",
                   "m_passing_accuracy", "m_save_percentage", "m_clean_sheets", "m_goals_conceded_per90"]  # ISS-29
MIN_N = 30            # smallest group size for which a correlation or group statistic is interpreted
BOOT_REPS = 500       # player-cluster bootstrap replicates (RS5-11: rows of the same player are not independent)
BOOT_SEED = 43
STRONG = 0.8          # |Spearman| at or above which a feature pair is listed as strongly associated
REDUNDANT = 0.9       # |Spearman| at or above which features are grouped into a redundancy cluster
# Features shown in the scatter panel: the examples named in the Phase 4.3 instruction.
KEY_FEATURES = ["age_at_season_end_years", "m_minutes_played", "m_appearances", "m_goals", "m_assists",
                "m_expected_goals", "m_expected_assists", "m_rating", "m_accurate_passes_per90",
                "m_tackles_per90"]
AGE_BANDS = [0, 21, 24, 27, 30, 100]
AGE_LABELS = ["<=21", "22-24", "25-27", "28-30", "31+"]
RD03 = ("RD-03: the target is the latest valuation on or before season end (mostly mid-season); the metrics "
        "cover the whole season. Descriptive association only, not causation.")


# ----------------------------------------------------------------------------- identity sensitivity subset
def identity_sensitivity_mask(df: pd.DataFrame) -> pd.Series:
    """The P4-B01 rows: evidence tier not AUTO_EXACT_VALIDATED, or validation label INCONCLUSIVE (533 rows).
    Used only to compare results; these rows stay in the main analysis."""
    return df["identity_evidence_tier"].ne("AUTO_EXACT_VALIDATED") | df["identity_rs5_validation_label"].eq("INCONCLUSIVE")


# ----------------------------------------------------------------------------- correlation primitives
def pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def ranks(a: np.ndarray) -> np.ndarray:
    return pd.Series(a).rank(method="average").to_numpy()  # average ranks: ties are common in counts


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return pearson(ranks(x), ranks(y))


def partial(rxy: float, rxz: float, ryz: float) -> float:
    """First-order partial correlation of x and y given z, from the three pairwise correlations."""
    den = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return float((rxy - rxz * ryz) / den) if den > 0 else np.nan


def applicable(df: pd.DataFrame, feature: str, register: pd.DataFrame) -> pd.Series:
    return uni.applicable_rows(df, feature, register)


def pair_frame(df: pd.DataFrame, feature: str, register: pd.DataFrame, extra: list[str] = ()) -> pd.DataFrame:
    """Applicable rows with a usable target and a non-null feature value (pairwise-complete; nothing filled)."""
    rows = applicable(df, feature, register) & df["target_usable"]
    cols = list(dict.fromkeys([feature, TARGET, "canonical_player_id", "season", POSITION, *extra]))
    sub = df.loc[rows, cols]
    return sub[sub[feature].notna()]


# ----------------------------------------------------------------------------- feature vs target
def cluster_bootstrap_spearman(df: pd.DataFrame, register: pd.DataFrame, reps: int = BOOT_REPS,
                               seed: int = BOOT_SEED) -> pd.DataFrame:
    """95% percentile intervals for each feature-target Spearman, resampling players (not rows) with replacement,
    so that a player's repeated seasons move together (RS5-11)."""
    rng = np.random.default_rng(seed)
    pairs = {f: pair_frame(df, f, register) for f in FEATURES}
    players = df.loc[df["target_usable"], "canonical_player_id"].unique()
    draws = [rng.choice(players, size=players.size, replace=True) for _ in range(reps)]
    rows = []
    for f, sub in pairs.items():
        if len(sub) < MIN_N:
            rows.append({"feature": f, "spearman_ci_low": np.nan, "spearman_ci_high": np.nan})
            continue
        index = sub.groupby("canonical_player_id").indices
        x, y = sub[f].to_numpy(float), sub[TARGET].to_numpy(float)
        stats = []
        for draw in draws:
            idx = np.concatenate([index[p] for p in draw if p in index])
            stats.append(spearman(x[idx], y[idx]))
        lo, hi = np.nanpercentile(stats, [2.5, 97.5])
        rows.append({"feature": f, "spearman_ci_low": lo, "spearman_ci_high": hi})
    return pd.DataFrame(rows).set_index("feature")


def monotonic_label(rho: float, ci_low: float, ci_high: float) -> str:
    if np.isnan(rho):
        return "n/a (too few rows)"
    if ci_low <= 0 <= ci_high:
        return "no clear monotonic association"
    strength = abs(rho)
    word = "strong" if strength >= 0.5 else "moderate" if strength >= 0.3 else "weak"
    return f"{word} {'positive' if rho > 0 else 'negative'}"


def feature_target_association(df: pd.DataFrame, register: pd.DataFrame, boot: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per feature: sample size, missingness, Pearson (raw and log10 target), Spearman with a
    player-cluster bootstrap interval, the Pearson-Spearman gap, and the Spearman after removing the
    shared dependence on minutes played (partial rank correlation; descriptive only)."""
    reg = register.set_index("feature")
    boot = cluster_bootstrap_spearman(df, register) if boot is None else boot
    rows = []
    for f in FEATURES:
        app_usable = applicable(df, f, register) & df["target_usable"]
        sub = pair_frame(df, f, register, ["m_minutes_played"])
        x, y = sub[f].to_numpy(float), sub[TARGET].to_numpy(float)
        null_rows = df.loc[app_usable & df[f].isna(), TARGET]
        rho = spearman(x, y)
        r_raw, r_log = pearson(x, y), pearson(x, np.log10(y))
        row = {
            "feature": f, "analysis_group": reg.at[f, "analysis_group"], "kind": reg.at[f, "kind"],
            "eligibility_category": reg.at[f, "eligibility_category"],
            "applicable_positions": reg.at[f, "applicable_positions"],
            "applicable_rows_with_target": int(app_usable.sum()), "n_pairs": len(sub),
            "players": int(sub["canonical_player_id"].nunique()),
            "missing_pct_with_target": float(df.loc[app_usable, f].isna().mean() * 100),
            "distinct_values": int(sub[f].nunique()),
            "pearson_raw": r_raw, "pearson_log10": r_log, "spearman": rho,
            "spearman_ci_low": boot.at[f, "spearman_ci_low"], "spearman_ci_high": boot.at[f, "spearman_ci_high"],
            "spearman_minus_pearson_raw": rho - r_raw, "spearman_minus_pearson_log10": rho - r_log,
            "median_target_when_present_eur": float(np.median(y)) if y.size else np.nan,
            "median_target_when_null_eur": float(null_rows.median()) if len(null_rows) else np.nan,
            "null_rows_with_target": len(null_rows),
        }
        # Starts as a second control: goalkeeper minutes are mostly missing (ISS-11), starts are not.
        sub = sub.join(df["m_starts"]) if "m_starts" not in sub else sub
        for control, name in (("m_minutes_played", "minutes"), ("m_starts", "starts")):
            both = sub.dropna(subset=[control])
            if f != control and len(both) >= MIN_N:
                xm, ym, zm = both[f].to_numpy(float), both[TARGET].to_numpy(float), both[control].to_numpy(float)
                rxy, rxz, ryz = spearman(xm, ym), spearman(xm, zm), spearman(ym, zm)
                row.update({f"n_with_{name}": len(both), f"spearman_with_{name}": rxz,
                            f"partial_spearman_given_{name}": partial(rxy, rxz, ryz)})
            else:
                row.update({f"n_with_{name}": len(both), f"spearman_with_{name}": np.nan,
                            f"partial_spearman_given_{name}": np.nan})
        row["association"] = monotonic_label(rho, row["spearman_ci_low"], row["spearman_ci_high"]) if len(sub) >= MIN_N \
            else "n/a (too few rows)"
        flags = []
        if f in uni.RD04:
            flags.append("RD-04 pending")
        if f in SOURCE_REPORTED:
            flags.append("ISS-29 source-reported")
        if f in GK_FEATURES:
            flags.append("GK rows only (ISS-11)")
        if f.endswith("_per90"):
            flags.append("per-90 on small denominators (P4-B05)")
        row["flags"] = "; ".join(flags)
        row["temporal_caveat"] = "RD-03"
        rows.append(row)
    return pd.DataFrame(rows)


def association_by_group(df: pd.DataFrame, register: pd.DataFrame, by: str, groups: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Spearman of each feature with the target inside each group, and the pair count. Groups with fewer than
    MIN_N pairs are left empty (NaN) in the correlation table; their counts are still reported."""
    rho, n = {}, {}
    for f in FEATURES:
        sub = pair_frame(df, f, register)
        rho[f], n[f] = {}, {}
        for g in groups:
            s = sub[sub[by] == g]
            n[f][g] = len(s)
            rho[f][g] = spearman(s[f].to_numpy(float), s[TARGET].to_numpy(float)) if len(s) >= MIN_N else np.nan
    return pd.DataFrame(rho).T[groups], pd.DataFrame(n).T[groups]


def pooled_vs_within(assoc: pd.DataFrame, by_season: pd.DataFrame, by_position: pd.DataFrame) -> pd.DataFrame:
    """Pooled Spearman next to the range of within-season and within-position Spearman values."""
    a = assoc.set_index("feature")
    out = pd.DataFrame({
        "pooled_spearman": a["spearman"],
        "season_min": by_season.min(axis=1), "season_max": by_season.max(axis=1),
        "season_range": by_season.max(axis=1) - by_season.min(axis=1),
        "seasons_reported": by_season.notna().sum(axis=1),
        "position_min": by_position.min(axis=1), "position_max": by_position.max(axis=1),
        "positions_reported": by_position.notna().sum(axis=1),
    })
    out["sign_differs_across_positions"] = (out["position_min"] < -0.1) & (out["position_max"] > 0.1)
    return out


def binned_target(df: pd.DataFrame, register: pd.DataFrame, feature: str, bins: int = 10) -> pd.DataFrame:
    """Target quantiles inside quantile bins of the feature (pairwise-complete rows). Ties in count metrics
    can merge bins, so fewer than `bins` bins may result; the actual bin edges are reported."""
    sub = pair_frame(df, feature, register)
    if len(sub) < MIN_N:
        return pd.DataFrame()
    bins = min(bins, len(sub) // MIN_N)  # at least MIN_N rows per bin (goalkeeper metrics get fewer bins)
    codes = pd.qcut(sub[feature].rank(method="first"), bins, labels=False)  # equal-count bins on ranks
    g = sub.groupby(codes)
    out = pd.DataFrame({
        "feature": feature, "bin": g.size().index + 1, "n": g.size().values,
        "feature_min": g[feature].min().values, "feature_max": g[feature].max().values,
        "feature_median": g[feature].median().values,
        "target_p25_eur": g[TARGET].quantile(0.25).values, "target_median_eur": g[TARGET].median().values,
        "target_p75_eur": g[TARGET].quantile(0.75).values,
    })
    return out


def binned_all(df: pd.DataFrame, register: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([binned_target(df, register, f) for f in FEATURES], ignore_index=True)


def binned_shape(binned: pd.DataFrame) -> pd.DataFrame:
    """Shape of the binned median trend: direction changes and the bin where the median peaks."""
    rows = []
    for f, b in binned.groupby("feature", sort=False):
        med = b["target_median_eur"].to_numpy()
        steps = np.sign(np.diff(med))
        steps = steps[steps != 0]
        changes = int((np.diff(steps) != 0).sum()) if steps.size > 1 else 0
        top = int(np.argmax(med))
        peak = int(b["bin"].iloc[top])
        inner_peak = changes <= 2 and 0 < top < len(med) - 1 and max(med[0], med[-1]) <= 0.7 * med[top]
        if changes == 0:
            trend = "monotonic"
        elif inner_peak:
            trend = f"inverted U (peak in bin {peak})"  # both ends at least 30% below the peak
        elif changes <= 2:
            trend = "mostly monotonic (minor reversals)"
        else:
            trend = "irregular"
        rows.append({"feature": f, "bins": len(b), "median_first_bin_eur": med[0], "median_last_bin_eur": med[-1],
                     "last_to_first_ratio": med[-1] / med[0] if med[0] else np.nan,
                     "direction_changes": changes, "peak_bin": peak, "trend": trend})
    return pd.DataFrame(rows)


def identity_sensitivity(df: pd.DataFrame, register: pd.DataFrame) -> pd.DataFrame:
    """Feature-target Spearman on all rows vs without the 533 P4-B01 rows. Comparison only; no row is removed
    from the main analysis."""
    keep = ~identity_sensitivity_mask(df)
    rows = []
    for f in FEATURES:
        full = pair_frame(df, f, register)
        strict = full[keep.loc[full.index]]
        rows.append({"feature": f, "n_all": len(full), "n_without_p4b01": len(strict),
                     "spearman_all": spearman(full[f].to_numpy(float), full[TARGET].to_numpy(float)),
                     "spearman_without_p4b01": spearman(strict[f].to_numpy(float), strict[TARGET].to_numpy(float))
                     if len(strict) >= MIN_N else np.nan})
    out = pd.DataFrame(rows)
    out["difference"] = out["spearman_without_p4b01"] - out["spearman_all"]
    return out


def identity_subset_profile(df: pd.DataFrame) -> pd.DataFrame:
    """How the P4-B01 rows differ from the rest on the target (they are not a random subset)."""
    m = identity_sensitivity_mask(df)
    u = df.loc[df["target_usable"]]
    g = u.groupby(m.loc[u.index].map({True: "P4-B01 subset", False: "other rows"}))[TARGET]
    out = pd.DataFrame({"rows": m.map({True: "P4-B01 subset", False: "other rows"}).value_counts(),
                        "usable_targets": g.size(), "median_eur": g.median(), "p75_eur": g.quantile(0.75)})
    return out


# ----------------------------------------------------------------------------- categorical vs target
def epsilon_squared(values: pd.Series, groups: pd.Series) -> dict:
    """Kruskal-Wallis H (tie-corrected) and the rank effect size epsilon^2 = H / (N - 1). No p-value is reported:
    rows of the same player are not independent (RS5-11), so the usual test assumptions do not hold."""
    r = values.rank(method="average")
    n = len(r)
    mean_rank = (n + 1) / 2
    h = 12 / (n * (n + 1)) * sum(len(x) * (x.mean() - mean_rank) ** 2 for _, x in r.groupby(groups, observed=True))
    ties = values.value_counts()
    correction = 1 - ((ties ** 3 - ties).sum() / (n ** 3 - n))
    h = h / correction if correction > 0 else np.nan
    return {"n": n, "groups": int(groups.nunique()), "kruskal_h": h, "epsilon_squared": h / (n - 1)}


def target_quantiles_by(df: pd.DataFrame, by, order=None) -> pd.DataFrame:
    u = df.loc[df["target_usable"]]
    g = u.groupby(by, observed=True)[TARGET]
    out = pd.DataFrame({"rows": df.groupby(by, observed=True).size(), "n_target": g.size(),
                        "p10_eur": g.quantile(0.10), "p25_eur": g.quantile(0.25), "median_eur": g.median(),
                        "p75_eur": g.quantile(0.75), "p90_eur": g.quantile(0.90), "mean_eur": g.mean()})
    out["iqr_ratio_p75_p25"] = out["p75_eur"] / out["p25_eur"]
    out["interpretable"] = out["n_target"] >= MIN_N
    return out.reindex(order) if order is not None else out


def age_band(df: pd.DataFrame) -> pd.Series:
    return pd.cut(df["age_at_season_end_years"], AGE_BANDS, labels=AGE_LABELS, right=True)


def minutes_band(df: pd.DataFrame) -> pd.Series:
    """Minutes bands from Phase 4.2; missing minutes stay a separate category (never read as zero)."""
    band = pd.cut(df["m_minutes_played"], uni.MINUTES_BANDS, labels=uni.MINUTES_LABELS).astype(object)
    return band.where(df["m_minutes_played"].notna(), "minutes missing")


def position_season_long(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Target quantiles for every position x season cell, with counts."""
    out = target_quantiles_by(df, [POSITION, "season"])
    idx = pd.MultiIndex.from_product([POSITION_ORDER, list(scope.labels)], names=[POSITION, "season"])
    return out.reindex(idx)


def position_season_spread(cells: pd.DataFrame) -> pd.DataFrame:
    """Per position: how much the season medians move (the RD-03/ISS-21 batch effect shows up here)."""
    med = cells["median_eur"].unstack("season")
    return pd.DataFrame({"min_season_median_eur": med.min(axis=1), "max_season_median_eur": med.max(axis=1),
                         "max_to_min_ratio": med.max(axis=1) / med.min(axis=1),
                         "smallest_cell_n": cells["n_target"].unstack("season").min(axis=1)}).reindex(POSITION_ORDER)


def categorical_effects(df: pd.DataFrame) -> pd.DataFrame:
    """Rank effect sizes of each categorical grouping on the target. Season and position x season are
    descriptive groupings (season is a key, P4-A05), not candidate predictors."""
    u = df.loc[df["target_usable"]]
    t = u[TARGET].astype(float)
    groupings = {
        "position_group_season": u[POSITION],
        "season (grouping key, not a predictor)": u["season"],
        "position x season (grouping)": u[POSITION] + " | " + u["season"],
        "age band (derived from age)": age_band(u).astype(str),
        "minutes band (derived; missing kept separate)": minutes_band(u),
    }
    rows = [{"grouping": name, **epsilon_squared(t, g)} for name, g in groupings.items()]
    within = []
    for pos in POSITION_ORDER:
        s = u[POSITION] == pos
        within.append({"grouping": f"season within {pos}", **epsilon_squared(t[s], u.loc[s, "season"])})
    for season in sorted(u["season"].unique()):
        s = u["season"] == season
        within.append({"grouping": f"position within {season}", **epsilon_squared(t[s], u.loc[s, POSITION])})
    return pd.DataFrame(rows + within)


# ----------------------------------------------------------------------------- feature vs feature
def correlation_matrix(df: pd.DataFrame, features: list[str], rows: pd.Series, method: str = "spearman") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pairwise-complete correlation matrix on the selected rows, and the pair counts behind each cell.
    Cells with fewer than MIN_N pairs are left empty."""
    sub = df.loc[rows, features].astype(float)
    corr = sub.corr(method=method, min_periods=MIN_N)
    present = sub.notna().astype(int)
    n = present.T @ present
    return corr, n


def strong_pairs(corr: pd.DataFrame, n: pd.DataFrame, pearson_corr: pd.DataFrame, register: pd.DataFrame,
                 threshold: float = STRONG) -> pd.DataFrame:
    groups = register.set_index("feature")["analysis_group"]
    rows = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.at[a, b]
            if pd.notna(r) and abs(r) >= threshold:
                rows.append({"feature_a": a, "feature_b": b, "spearman": r, "pearson_raw": pearson_corr.at[a, b],
                             "n_pairs": int(n.at[a, b]), "relation": pair_relation(a, b, groups)})
    out = pd.DataFrame(rows)
    return out.sort_values("spearman", key=np.abs, ascending=False, ignore_index=True) if len(out) else out


def pair_relation(a: str, b: str, groups: pd.Series) -> str:
    """Semantic reading of a correlated pair."""
    base = lambda f: f.removesuffix("_per90")  # noqa: E731
    if base(a) == base(b) or {base(a), base(b)} == {"m_blocked_shots", "m_blocks"}:
        return "same metric: season total and per-90 rate"
    playing_time = set(uni.FEATURE_GROUPS["2 Playing time and participation"])
    if a in playing_time and b in playing_time:
        return "playing-time measures"
    if a in playing_time or b in playing_time:
        return "volume metric scales with playing time"
    for name, family in OVERLAP_FAMILIES.items():
        if a in family and b in family:
            return f"overlapping definition ({name})"
    if groups[a] == groups[b]:
        return f"same metric family ({groups[a][2:]})"
    if not a.endswith("_per90") and not b.endswith("_per90"):
        return "season totals of different actions (shared dependence on playing time)"
    return "different families"


# Metrics built from the same underlying events (xG is computed from shots; xA from passes that lead to shots).
OVERLAP_FAMILIES = {
    "shots, goals and xG": {"m_goals", "m_shots", "m_shots_on_target", "m_expected_goals", "m_non_penalty_xg",
                            "m_expected_goals_on_target"},
    "chance creation and xA": {"m_assists", "m_expected_assists", "m_chances_created", "m_big_chances_created"},
}


def pair_by_season(df: pd.DataFrame, pairs: pd.DataFrame, rows: pd.Series, scope) -> pd.DataFrame:
    """Within-season Spearman of each strong pair; a wide range marks season-dependent behaviour."""
    out = []
    for _, p in pairs.iterrows():
        rec = {"feature_a": p["feature_a"], "feature_b": p["feature_b"], "pooled": p["spearman"]}
        for s in scope.labels:
            sub = df.loc[rows & (df["season"] == s), [p["feature_a"], p["feature_b"]]].dropna()
            rec[prof.short(s)] = spearman(sub.iloc[:, 0].to_numpy(float), sub.iloc[:, 1].to_numpy(float)) \
                if len(sub) >= MIN_N else np.nan
        out.append(rec)
    out = pd.DataFrame(out)
    if len(out):
        seasons = [prof.short(s) for s in scope.labels]
        out["season_min"] = out[seasons].min(axis=1)
        out["season_max"] = out[seasons].max(axis=1)
        out["season_range"] = out["season_max"] - out["season_min"]
    return out


def redundancy_clusters(corr: pd.DataFrame, threshold: float = REDUNDANT) -> pd.DataFrame:
    """Connected groups of features linked by |Spearman| >= threshold (single linkage). A description of
    overlap, not a selection: no feature is dropped or preferred here."""
    cols = list(corr.columns)
    parent = {c: c for c in cols}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.at[a, b]
            if pd.notna(r) and abs(r) >= threshold:
                parent[find(a)] = find(b)
    clusters = {}
    for c in cols:
        clusters.setdefault(find(c), []).append(c)
    rows = []
    k = 0
    for members in sorted(clusters.values(), key=len, reverse=True):
        if len(members) < 2:
            continue
        k += 1
        block = corr.loc[members, members].to_numpy()
        off = block[~np.eye(len(members), dtype=bool)]
        rows.append({"cluster": k, "size": len(members), "members": ", ".join(members),
                     "min_abs_spearman_within": float(np.nanmin(np.abs(off))),
                     "median_abs_spearman_within": float(np.nanmedian(np.abs(off)))})
    return pd.DataFrame(rows)


def per90_vs_total(df: pd.DataFrame) -> pd.DataFrame:
    """Total vs per-90 version of the same metric (outfield rows): rates are much less redundant with their
    totals than totals are with each other, because rates remove most of the playing-time dependence."""
    rows = []
    o = df[POSITION].isin(OUTFIELD)
    for rate in uni.per90_columns():
        total = rate.removesuffix("_per90")
        total = "m_blocked_shots" if total == "m_blocks" else total
        if total not in df.columns:
            continue
        sub = df.loc[o, [total, rate, "m_minutes_played"]].dropna()
        rows.append({"total": total, "rate": rate, "n": len(sub),
                     "spearman_total_rate": spearman(sub[total].to_numpy(float), sub[rate].to_numpy(float)),
                     "spearman_total_minutes": spearman(sub[total].to_numpy(float), sub["m_minutes_played"].to_numpy(float)),
                     "spearman_rate_minutes": spearman(sub[rate].to_numpy(float), sub["m_minutes_played"].to_numpy(float))})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    dictionary, eligibility, reliability = prof.load_metadata()
    register = uni.feature_register(eligibility, reliability)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seasons = list(scope.labels)

    assoc = feature_target_association(df, register)
    rho_season, n_season = association_by_group(df, register, "season", seasons)
    rho_pos, n_pos = association_by_group(df, register, POSITION, POSITION_ORDER)
    binned = binned_all(df, register)
    cells = position_season_long(df, scope)
    outfield_rows = df[POSITION].isin(OUTFIELD)
    gk_rows = df[POSITION].eq("GK")
    s_out, n_out = correlation_matrix(df, OUTFIELD_FEATURES, outfield_rows, "spearman")
    p_out, _ = correlation_matrix(df, OUTFIELD_FEATURES, outfield_rows, "pearson")
    gk_cols = ["age_at_season_end_years", "m_appearances", "m_starts", "m_rating", *GK_FEATURES]
    s_gk, n_gk = correlation_matrix(df, gk_cols, gk_rows, "spearman")
    p_gk, _ = correlation_matrix(df, gk_cols, gk_rows, "pearson")
    pairs = strong_pairs(s_out, n_out, p_out, register)
    pairs_gk = strong_pairs(s_gk, n_gk, p_gk, register)
    pairs_season = pair_by_season(df, pairs, outfield_rows, scope)

    import duckdb
    con = duckdb.connect()
    derived = cells.reset_index()[["season", POSITION, "n_target", "median_eur"]]
    con.register("position_season_table", derived)
    scope_check_derived = check_table(con, "position_season_table", scope, "season", None)

    tables = {
        "feature_target_association.csv": assoc,
        "feature_target_spearman_by_season.csv": rho_season.rename(columns=prof.short),
        "feature_target_n_by_season.csv": n_season.rename(columns=prof.short),
        "feature_target_spearman_by_position.csv": rho_pos,
        "feature_target_n_by_position.csv": n_pos,
        "feature_target_pooled_vs_within.csv": pooled_vs_within(assoc, rho_season, rho_pos),
        "feature_target_binned.csv": binned,
        "feature_target_binned_shape.csv": binned_shape(binned),
        "identity_sensitivity_spearman.csv": identity_sensitivity(df, register),
        "identity_subset_profile.csv": identity_subset_profile(df),
        "target_by_position_43.csv": target_quantiles_by(df, POSITION, POSITION_ORDER),
        "target_by_season_43.csv": target_quantiles_by(df, "season", seasons),
        "target_by_position_season_43.csv": cells,
        "target_position_season_spread.csv": position_season_spread(cells),
        "target_by_age_band.csv": target_quantiles_by(df.assign(age_band=age_band(df)), "age_band", AGE_LABELS),
        "target_by_age_band_position.csv": target_quantiles_by(df.assign(age_band=age_band(df)), [POSITION, "age_band"]),
        "target_by_minutes_band.csv": target_quantiles_by(df.assign(minutes_band=minutes_band(df)), "minutes_band",
                                                          [*uni.MINUTES_LABELS, "minutes missing"]),
        "categorical_effect_sizes.csv": categorical_effects(df),
        "correlation_matrix_spearman_outfield.csv": s_out,
        "correlation_matrix_pearson_outfield.csv": p_out,
        "correlation_matrix_pair_counts_outfield.csv": n_out,
        "correlation_matrix_spearman_goalkeeper.csv": s_gk,
        "correlation_matrix_pair_counts_goalkeeper.csv": n_gk,
        "strong_feature_pairs_outfield.csv": pairs,
        "strong_feature_pairs_goalkeeper.csv": pairs_gk,
        "strong_feature_pairs_by_season.csv": pairs_season,
        "redundancy_clusters_outfield.csv": redundancy_clusters(s_out),
        "per90_vs_total.csv": per90_vs_total(df),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8",
                     float_format="%.6g")
    a = assoc.set_index("feature")
    summary = {
        "dataset": str(prof.DATASET.relative_to(ROOT)).replace("\\", "/"),
        "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_id": scope.scope_id,
        "scope_check": verification["scope_check"],
        "scope_check_derived_position_season_table": scope_check_derived,
        "rows": len(df), "usable_targets": int(df["target_usable"].sum()),
        "features_analysed": len(FEATURES),
        "identity_sensitivity_rows": int(identity_sensitivity_mask(df).sum()),
        "bootstrap": {"replicates": BOOT_REPS, "seed": BOOT_SEED, "unit": "canonical_player_id"},
        "thresholds": {"min_n": MIN_N, "strong_pair": STRONG, "redundancy_cluster": REDUNDANT},
        "top_spearman": a["spearman"].sort_values(ascending=False).head(10).round(4).to_dict(),
        "strong_pairs_outfield": len(pairs), "strong_pairs_goalkeeper": len(pairs_gk),
        "redundancy_clusters_outfield": int(len(tables["redundancy_clusters_outfield.csv"])),
        "max_abs_identity_sensitivity_difference": float(tables["identity_sensitivity_spearman.csv"]["difference"].abs().max()),
        "temporal_caveat": RD03,
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "bivariate_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:6000])
