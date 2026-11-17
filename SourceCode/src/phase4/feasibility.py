"""Phase 4.6: feature assessment and modeling feasibility for the official FB69 research release.

Assessment only. No feature is engineered, selected, removed or transformed; no model is trained; no split is
executed. The assessment combines the recorded and tested evidence of Phases 4.2-4.5 (each evidence set has a
test asserting that it equals a recomputation from the official dataset) with a few cheap recomputations.
Every rating follows a stated rule; ratings marked "judgment" are subjective and labelled as such.
Eligibility categories are read from the Phase 4.0 register and never changed here.

Usage (evidence): python -I -X utf8 src/phase4/feasibility.py <out_dir>
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
EV = ROOT / "reports/phase_04"
E42, E43, E44, E45 = (EV / f"step_0{k}/evidence" for k in (2, 3, 4, 5))

# Rules (thresholds stated once; used in every rating)
COVERAGE_RULE = "High: <=10% null on applicable rows and values in 5 seasons; Medium: <=30% and 5 seasons; Low: >30% or fewer than 5 seasons"
ASSOCIATION_RULE = "|pooled Spearman| >= 0.5 strong, >= 0.3 moderate, >= 0.1 weak, else none (Phase 4.3)"
BEYOND_PT_RULE = "|partial Spearman given starts| >= 0.25 retained, 0.10-0.25 partly retained, < 0.10 mostly playing time"
REDUNDANCY_RULE = "max |Spearman| with another outfield feature >= 0.9 high, >= 0.8 medium, else low (outfield matrix, Phase 4.3)"
POSITION_RULE = "GK only, or outfield within-position Spearman range >= 0.25: position-specific; else general"
IDENTITY_RULE = "|change in Spearman without P4-B01| >= 0.05 sensitive, else robust"
TAIL_RULE = "values beyond 3 IQR > 2% of observed values: heavy tail; else moderate/none"
# Interpretability is a judgment (subjective): counts and totals high; model-based and rates medium; composite rating low.
INTERPRETABILITY = {"age (years)": "high", "season count/total": "high", "per-90 rate": "medium",
                    "percentage (source-reported)": "medium", "season total (model-based)": "medium",
                    "average rating (0-10)": "low (composite source score)"}


def load_evidence() -> dict[str, pd.DataFrame]:
    rd = lambda p, **k: pd.read_csv(p, **k).rename(columns=lambda c: c.lstrip("﻿"))  # noqa: E731
    return {
        "summary42": rd(E42 / "feature_summary.csv").set_index("feature"),
        "assoc43": rd(E43 / "feature_target_association.csv").set_index("feature"),
        "within43": rd(E43 / "feature_target_pooled_vs_within.csv", index_col=0),
        "corr43": rd(E43 / "correlation_matrix_spearman_outfield.csv", index_col=0),
        "clusters43": rd(E43 / "redundancy_clusters_outfield.csv"),
        "ident43": rd(E43 / "identity_sensitivity_spearman.csv").set_index("feature"),
        "within44": rd(E44 / "within_group_spearman.csv", index_col=0),
        "map45": rd(E45 / "reliability_map.csv").set_index("feature"),
        "fm45": rd(E45 / "feature_missingness.csv").set_index("metric"),
    }


# ----------------------------------------------------------------------------- feature assessment
def _coverage(null_pct, seasons):
    if seasons < 5 or null_pct > 30:
        return "low"
    return "high" if null_pct <= 10 else "medium"


def _association(r):
    a = abs(r)
    return "strong" if a >= 0.5 else "moderate" if a >= 0.3 else "weak" if a >= 0.1 else "none"


def _beyond(p):
    if pd.isna(p):
        return "n/a (is the control)"
    a = abs(p)
    return "retained" if a >= 0.25 else "partly retained" if a >= 0.10 else "mostly playing time"


def feature_assessment(df: pd.DataFrame, register: pd.DataFrame, ev: dict) -> pd.DataFrame:
    s42, a43, w43, c43, i43, w44, m45 = (ev[k] for k in ("summary42", "assoc43", "within43", "corr43", "ident43", "within44", "map45"))
    cluster_of = {m: int(r["cluster"]) for _, r in ev["clusters43"].iterrows() for m in r["members"].split(", ")}
    reg = register.set_index("feature")
    rows = []
    for f in uni.FEATURES:
        gk = f in uni.FEATURE_GROUPS["8 Goalkeeping"]
        null_pct = float(m45.at[f, "null_applicable_pct"])
        seasons = int(m45.at[f, "seasons_with_values"])
        others = c43.loc[f].drop(f).abs() if f in c43.index else pd.Series(dtype=float)
        max_r = float(others.max()) if len(others) else np.nan
        partner = others.idxmax() if len(others) else ""
        outfield_cols = [f"{p} all" for p in ("DEF", "MID", "FWD")]
        reg_cols = ["GK >=19 starts"] if gk else [f"{p} >=19 starts" for p in ("DEF", "MID", "FWD")]  # same population as the feature
        pos_range = (w44.loc[f, outfield_cols].max() - w44.loc[f, outfield_cols].min()) if not gk else np.nan
        regular_max = w44.loc[f, reg_cols].abs().max()
        upper = s42.at[f, "upper_3iqr"] / s42.at[f, "n"] * 100 if s42.at[f, "n"] else np.nan
        rec = {
            "feature": f, "analysis_group": reg.at[f, "analysis_group"][2:],
            "eligibility_category": reg.at[f, "eligibility_category"], "condition_ids": reg.at[f, "condition_ids"],
            # 1-2 coverage and missingness (evidence)
            "null_applicable_pct": null_pct, "seasons_with_values": seasons, "coverage": _coverage(null_pct, seasons),
            "missingness_informative": bool(a43.at[f, "median_target_when_null_eur"] < 0.5 * a43.at[f, "median_target_when_present_eur"])
            if pd.notna(a43.at[f, "median_target_when_null_eur"]) else False,
            # 3 source reliability (evidence, Phase 4.5 class)
            "reliability_class": m45.at[f, "reliability_class"],
            # 4 temporal alignment (evidence)
            "temporal": "RD-03 + incomplete window (RD-04)" if f in uni.RD04 else
                        ("RD-03 + small denominators (P4-B05)" if f.endswith("_per90") else "RD-03 only"),
            # 5 position relevance (evidence)
            "position_relevance": "GK only" if gk else ("position-specific" if pos_range >= 0.25 else "general"),
            "outfield_position_rho_range": pos_range,
            # 6-7 distribution and tails (evidence, Phase 4.2)
            "shape": s42.at[f, "shape"], "skew": s42.at[f, "skew"], "beyond_3iqr_pct": upper,
            "tail": "heavy" if upper > 2 else "moderate/none",
            # 8 redundancy (evidence, Phase 4.3)
            "max_abs_rho_other_feature": max_r, "most_correlated_with": partner,
            "redundancy": "n/a (GK matrix)" if gk else ("high" if max_r >= 0.9 else "medium" if max_r >= 0.8 else "low"),
            "redundancy_cluster": cluster_of.get(f, ""),
            # 9 interpretability (judgment)
            "interpretability_judgment": INTERPRETABILITY[reg.at[f, "kind"]],
            # 10 target association (evidence)
            "pooled_spearman": a43.at[f, "spearman"], "association": _association(a43.at[f, "spearman"]),
            "partial_given_starts": a43.at[f, "partial_spearman_given_starts"],
            "beyond_playing_time": _beyond(a43.at[f, "partial_spearman_given_starts"]),
            "max_abs_rho_within_regulars": regular_max,
            # 11 identity sensitivity (evidence)
            "identity_change": i43.at[f, "difference"],
            "identity_sensitivity": "sensitive" if abs(i43.at[f, "difference"]) >= 0.05 else "robust",
        }
        rec["usefulness_judgment"], rec["phase5_recommendation"] = usefulness(rec, f)
        rows.append(rec)
    return pd.DataFrame(rows)


def usefulness(rec: dict, f: str) -> tuple[str, str]:
    """12th dimension (judgment, built from the evidence ratings by explicit rules)."""
    if f in uni.RD04:
        return "unknown until RD-04 is decided", "conditional: owner decision (RD-04)"
    if rec["eligibility_category"] == "CONDITIONAL_PREDICTOR":  # ISS-29 reliability-conditional features
        base = "conditional: reliability assessment (ISS-29)"
        if f in ("m_save_percentage", "m_goals_conceded_per90"):
            base = "conditional: ISS-29, internal consistency shown (owner may reclassify)"
        return ("promising" if rec["association"] in ("strong", "moderate") or rec["max_abs_rho_within_regulars"] >= 0.3 else "limited"), base
    if f.startswith("m_") and rec["position_relevance"] == "GK only":
        return ("promising for goalkeepers" if rec["association"] in ("strong", "moderate") else "limited"), "consider in a goalkeeper-specific design"
    strong_signal = rec["beyond_playing_time"] == "retained" or rec["max_abs_rho_within_regulars"] >= 0.3
    if f == "age_at_season_end_years":
        return "promising (non-monotonic; interacts with playing time)", "consider; needs a non-linear representation"
    if rec["analysis_group"].startswith("Playing time"):
        return "promising as the playing-time axis; highly redundant within the group", "consider one representation of playing time"
    if strong_signal and rec["coverage"] != "low":
        return "promising", "consider (core candidate)"
    if strong_signal:
        return "promising but incomplete", "consider with missingness handling (P4-B07)"
    if rec["association"] in ("strong", "moderate"):
        return "mostly a playing-time proxy", "consider only with playing-time context"
    return "limited descriptive association", "low expected value; keep available, do not prioritise"


def matrix_counts(fa: pd.DataFrame) -> pd.DataFrame:
    dims = ["coverage", "reliability_class", "temporal", "position_relevance", "tail", "redundancy", "interpretability_judgment",
            "association", "beyond_playing_time", "identity_sensitivity", "usefulness_judgment", "phase5_recommendation"]
    return pd.concat({d: fa[d].value_counts() for d in dims}).rename("features").to_frame()


def group_recommendations(fa: pd.DataFrame) -> pd.DataFrame:
    """Candidate feature groups for Phase 5 consideration (not a selection)."""
    rows = [
        ("Playing time", "m_appearances, m_starts, m_minutes_played",
         "Strongest grouping axis (4.4) and Spearman ~0.53; the three are near-duplicates (0.92-0.995); GK minutes missing (P4-D05)",
         "Consider; choose one primary representation; starts are complete for GK"),
        ("Age", "age_at_season_end_years", "Inverted U; interacts with playing time; -0.34 to -0.59 within regulars",
         "Consider with a non-linear form; ISS-07 for 4 birth dates"),
        ("Position context", "position_group_season", "Distinct sub-populations; metric meaning differs by position; whole-season modal (P4-B04)",
         "Consider as context or for position-specific models"),
        ("Attacking output and xG", "m_goals, m_shots, m_shots_on_target, m_expected_goals, m_non_penalty_xg, m_shots_per90, m_shots_on_target_per90",
         "Retained beyond playing time (partial 0.28-0.33); strong for MID/FWD regulars; high internal redundancy (cluster 2)",
         "Consider; resolve redundancy by design (totals vs rates)"),
        ("Chance creation and xA", "m_assists, m_expected_assists, m_chances_created, m_big_chances_created",
         "xA 0.56 pooled, 0.33 given starts; xA/chances 0.93", "Consider; big chances has 44% nulls"),
        ("Passing quality", "m_accurate_passes_per90, m_passing_accuracy, m_long_ball_accuracy, m_accurate_long_passes(_per90)",
         "Retained for defenders (0.48-0.51); accuracy rates source-reported (ISS-29); passing accuracy drifts (P4-B09)",
         "Consider position-specifically; ISS-29 decision needed for accuracy rates"),
        ("Possession volume", "m_touches, m_accurate_passes, m_dribbles_succeeded, m_successful_crosses",
         "Mostly playing time (touches 0.47 -> 0.16 given starts); in playing-time cluster", "Consider only with playing-time context"),
        ("Defensive actions", "m_tackles, m_interceptions, m_recoveries, m_blocked_shots, m_aerials_won, m_duels_won and rates",
         "Positive pooled associations are playing time; negative given playing time (P4-B08); rates drift (P4-B09)",
         "Low expected value as direct signals; possible team-context confounding (RS5-12)"),
        ("Discipline and fouls", "m_yellow_cards, m_red_cards, m_fouls_committed, m_fouls_won",
         "Mostly playing time; fouls won retains 0.20", "Low priority"),
        ("Overall rating", "m_rating", "Strongest single association (0.58; 0.41 given starts); composite source score; 17 conflicting, 58 revised cells",
         "Consider; interpret as a composite, not independent evidence"),
        ("Goalkeeping", "m_saves, m_save_percentage, m_clean_sheets, m_goals_conceded(_per90), m_penalty_saves",
         "206 rows; clean sheets 0.67; saves reverse given starts; two rates internally consistent", "Consider only in a goalkeeper-specific design"),
        ("RD-04 metrics", ", ".join(uni.RD04), "Incomplete window or season coverage (4.5)", "Pending owner decision RD-04"),
        ("Club context", "8 RS5-12 columns", "Complete but temporally ambiguous; possible strong proxy", "Pending owner decision RS5-12"),
        ("Status columns", "52 s_* (excluding s_key_passes)", "Encode why a value is null (4.5)", "Not numeric features; role decided in preprocessing design (P4-D01)"),
    ]
    return pd.DataFrame(rows, columns=["group", "features", "evidence", "recommendation_for_phase5_consideration"])


def eligibility_review(eligibility: pd.DataFrame, fa: pd.DataFrame) -> pd.DataFrame:
    """Current eligibility categories (unchanged) with the Phase 4.6 reading."""
    e = eligibility.copy()
    e["subtype"] = e["eligibility_category"]
    cond = e["eligibility_category"].eq("CONDITIONAL_PREDICTOR")
    e.loc[cond & e["column"].isin(uni.RD04), "subtype"] = "CONDITIONAL_PREDICTOR: owner decision (RD-04)"
    e.loc[cond & e["condition_ids"].astype(str).str.contains("RS5-12"), "subtype"] = "CONDITIONAL_PREDICTOR: owner decision (RS5-12)"
    e.loc[cond & e["column"].isin(biv.SOURCE_REPORTED), "subtype"] = "CONDITIONAL_PREDICTOR: reliability assessment (ISS-29)"
    notes = {
        "CANDIDATE_PREDICTOR": "Candidates with warnings; assessed in the matrix; no change",
        "CONDITIONAL_PREDICTOR: owner decision (RD-04)": "Remain pending; 4.5 evidence summarised for the owner",
        "CONDITIONAL_PREDICTOR: owner decision (RS5-12)": "Remain pending; temporally ambiguous (4.5)",
        "CONDITIONAL_PREDICTOR: reliability assessment (ISS-29)": "Assessed in 4.5: 2 internally consistent, 6 unverifiable; classification unchanged",
        "EXCLUDED_PREDICTOR": "m_key_passes, s_key_passes, nationality_profile_present_day: remain excluded",
        "TARGET": "Never predictors", "IDENTITY_METADATA": "Never predictors (group keys and sensitivity grouping only)",
        "TEMPORAL_AUDIT": "Never predictors (audit only; see P4-D05)",
        "STATUS_MISSINGNESS": "Not numeric performance features; possible role as missingness indicators (P4-D01)",
    }
    out = e.groupby("subtype").agg(columns=("column", "size"), examples=("column", lambda s: ", ".join(s.head(4))))
    out["phase_4_6_reading"] = out.index.map(notes)
    return out


def status_role(df: pd.DataFrame) -> pd.DataFrame:
    """Possible future roles of the s_* columns (assessment, not a decision)."""
    s = [c for c in df.columns if c.startswith("s_")]
    vals = pd.Series(df[s].to_numpy().ravel()).value_counts()
    constant = [c for c in s if df[c].nunique() <= 1]
    rows = [
        ("Interpret nulls in EDA and audits", "Distinguishes unavailable, not applicable, unsupported and conflicting nulls", "Used throughout Phase 4", "none"),
        ("Missingness indicators for preprocessing", "MISSING is informative (fringe players, lower values; 4.3 and 4.5)", "Possible; one indicator per metric family or per block, not per status value", "P4-D01 decision"),
        ("Applicability masks", "UNVERIFIED_POSITION marks GK-only metrics on outfield rows", "Possible for position-specific designs", "P4-D01, P4-B10"),
        ("Exclusion of unusable cells", "CONFLICTING (36 cells) and UNSUPPORTED (key_passes)", "Keep null; never zero", "none"),
        ("Numeric performance features", "Statuses are categorical source codes", "Not appropriate", "n/a"),
    ]
    out = pd.DataFrame(rows, columns=["possible_role", "basis", "assessment", "decision_needed"])
    out.attrs["status_cells"] = vals.to_dict()
    out.attrs["constant_status_columns"] = constant
    return out


# ----------------------------------------------------------------------------- regression feasibility
def target_feasibility(df: pd.DataFrame) -> pd.DataFrame:
    t = df.loc[df["target_usable"], TARGET].astype(float)
    lt = np.log10(t)
    rows = [("usable targets", len(t), ""), ("players with a usable target", df.loc[df["target_usable"], "canonical_player_id"].nunique(), ""),
            ("distinct target values", t.nunique(), "coarse, rounded valuations"),
            ("skewness raw / log10", f"{t.skew():.2f} / {lt.skew():.2f}", "log over-corrects slightly"),
            ("max / median", f"{t.max() / t.median():.1f}", "heavy upper tail"),
            ("share of total value in top 5% of rows", f"{t.nlargest(int(len(t) * 0.05)).sum() / t.sum() * 100:.1f}%", "raw-scale errors dominated by the tail"),
            ("rows beyond 3 IQR (raw)", int((t > t.quantile(.75) + 3 * (t.quantile(.75) - t.quantile(.25))).sum()), "genuine elite players (4.2)")]
    return pd.DataFrame(rows, columns=["measure", "value", "note"])


def spread_vs_level(df: pd.DataFrame) -> pd.DataFrame:
    """Within position x role cells: median, IQR and IQR/median on raw and log scales (heteroscedasticity check)."""
    d = df.join(mvt.groups(df))
    d = d[d["target_usable"]]
    g = d.groupby([POSITION, "starts_group"], observed=True)[TARGET]
    out = pd.DataFrame({"n": g.size(), "median_eur": g.median(), "iqr_eur": g.quantile(.75) - g.quantile(.25),
                        "p75_to_p25": g.quantile(.75) / g.quantile(.25),
                        "iqr_log10": d.assign(l=np.log10(d[TARGET].astype(float))).groupby([POSITION, "starts_group"], observed=True)["l"]
                        .apply(lambda s: s.quantile(.75) - s.quantile(.25))})
    return out[out["n"] >= biv.MIN_N]


def population_feasibility(df: pd.DataFrame, scope) -> pd.DataFrame:
    u = df[df["target_usable"]]
    rows = []
    for name, sub in [("all", u)] + [(p, u[u[POSITION] == p]) for p in prof.POSITION_ORDER] + [(prof.short(s), u[u["season"] == s]) for s in scope.labels]:
        rows.append({"population": name, "usable_rows": len(sub), "players": sub["canonical_player_id"].nunique(),
                     "rows_per_player": len(sub) / sub["canonical_player_id"].nunique(),
                     "target_median_eur": sub[TARGET].median()})
    return pd.DataFrame(rows).set_index("population")


def complete_case(df: pd.DataFrame, features: list[str]) -> pd.Series:
    """Share of usable outfield rows that have every listed feature (what a complete-case analysis would keep)."""
    u = df[df["target_usable"] & df[POSITION].ne("GK")]
    keep = u[features].notna().all(axis=1)
    groups = {"all": keep, **{p: keep[u[POSITION] == p] for p in biv.OUTFIELD},
              **{prof.short(s): keep[u["season"] == s] for s in sorted(u["season"].unique())}}
    return pd.Series({k: v.mean() * 100 for k, v in groups.items()}, name="complete_case_core_outfield_pct")


# ----------------------------------------------------------------------------- split feasibility
def player_structure(df: pd.DataFrame) -> pd.DataFrame:
    u = df[df["target_usable"]]
    k = u.groupby("canonical_player_id").size()
    return pd.DataFrame({"players": k.value_counts().sort_index(), "rows": (k.value_counts().sort_index() * k.value_counts().sort_index().index)}).rename_axis("seasons_per_player")


def random_split_leakage(df: pd.DataFrame, test_share: float = 0.2) -> dict:
    """Expected share of test rows whose player also has a row in training under a random row split
    (analytic; no split is executed): for a player with k rows, P = 1 - test_share^(k-1)."""
    u = df[df["target_usable"]]
    k = u.groupby("canonical_player_id").size()
    rows_k = u["canonical_player_id"].map(k)
    p = 1 - test_share ** (rows_k - 1)
    return {"test_share": test_share, "expected_test_rows_with_player_in_train_pct": float(p.mean() * 100),
            "players_with_multiple_seasons": int((k > 1).sum()), "rows_of_multi_season_players": int(rows_k[rows_k > 1].size)}


def temporal_holdout(df: pd.DataFrame, scope) -> pd.DataFrame:
    """Feasibility of season hold-outs: for each season as a hypothetical test season with all earlier seasons as
    training, report sizes, player overlap and distribution shift. Descriptive; nothing is split or saved."""
    seasons = list(scope.labels)
    u = df[df["target_usable"]]
    rows = []
    for i, s in enumerate(seasons[1:], start=1):
        train, test = u[u["season"].isin(seasons[:i])], u[u["season"] == s]
        seen = test["canonical_player_id"].isin(train["canonical_player_id"])
        rows.append({"test_season": s, "train_seasons": i, "train_rows": len(train), "test_rows": len(test),
                     "test_rows_player_seen_in_train_pct": seen.mean() * 100, "test_new_player_rows": int((~seen).sum()),
                     "train_target_median_eur": train[TARGET].median(), "test_target_median_eur": test[TARGET].median(),
                     "test_median_valuation_age_days": test["target_valuation_age_days"].median(),
                     "clearances_coverage_train_pct": train["m_clearances"].notna().mean() * 100,
                     "clearances_coverage_test_pct": test["m_clearances"].notna().mean() * 100})
    return pd.DataFrame(rows)


def split_comparison() -> pd.DataFrame:
    rows = [
        ("Random row split", "Not allowed (RS5-11)", "Same player in train and test; inflated scores", "-", "Prohibited"),
        ("Grouped by player (K-fold, players kept together)", "Every player-season belongs to one fold",
         "No identity leakage; uses all five seasons; folds mix seasons, so the season batch effect is shared between train and test",
         "Stratify or report by season and position; report a P4-B01 sensitivity run", "Primary evaluation"),
        ("Temporal hold-out (train earlier seasons, test 2024/25)", "Train 2020/21-2023/24, test 2024/25",
         "Matches the use case 'estimate this season's values from past seasons'; tests generalisation to a new batch; "
         "74.7% of test rows belong to players seen in earlier seasons (138 new-player rows); shift in level, batch timing and clearances coverage",
         "Report returning and new players separately; consider excluding test players from training as a stricter variant", "Secondary evaluation"),
        ("Rolling origin (expanding window)", "Test 2021/22 ... 2024/25 in turn with earlier seasons as training",
         "Several temporal estimates; first folds are small (515 training rows)", "Use if temporal stability matters", "Optional"),
        ("Combined grouped + temporal", "Temporal hold-out where test players are removed from training",
         "Strictest; smallest training set; answers 'new player, new season'", "Owner choice", "Optional stricter variant"),
    ]
    return pd.DataFrame(rows, columns=["strategy", "definition", "properties", "requirements", "recommendation"])


# ----------------------------------------------------------------------------- risk register
def risk_register() -> pd.DataFrame:
    rows = [
        ("R01", "Identity leakage through repeated players", "687 players in 2+ seasons; an 80/20 random row split would leave the player of about 76% of test rows in training (analytic expectation)", "High", "All", "Inflated evaluation", "Grouped-by-player and/or temporal split; never random rows (RS5-11)", "No", "Fix split before any evaluation (P4-D02)"),
        ("R02", "Temporal construct mismatch", "Mostly mid-season label; 44% of appearances after valuation; 25-55% by season", "High", "All m_*", "Weaker label-feature correspondence; misleading causal readings", "Report RD-03; season-aware evaluation; keep D4/D6 unless owner changes", "Yes (RD-03 decision)", "State in every result"),
        ("R03", "Season batch effects and level shift", "Valuation age 66-206 days by season; medians 10-17m; stratified x1.2-1.75", "High", "Target", "Season-dependent bias; poor temporal generalisation", "Season-aware evaluation and reporting; do not use season as a free predictor without design", "No", "Evaluation design"),
        ("R04", "Heavy-tailed, coarse target", "Skew 2.31; 32 rows beyond 3 IQR; 84 distinct values", "High", "Target", "Raw-scale losses dominated by elite players", "Consider log-scale training with raw-scale reporting; robust metrics", "No", "Target transformation decision"),
        ("R05", "Informative, non-random missingness", "Fringe rows 72% MISSING; null rows lower-valued for 51/52 features", "High", "Count and rate metrics", "Biased complete-case models; wrong zero-fill", "Status-aware missingness plan; no blind imputation (ISS-25, ISS-27, P4-B07)", "No", "Preprocessing design (P4-D01)"),
        ("R06", "Playing-time confounding and redundancy", "Most volume associations vanish given starts; 54 strong pairs; 4 clusters", "Medium", "Volume totals", "Unstable coefficients, spurious importance", "Choose representations deliberately; check multicollinearity", "No", "Feature design (P4-D03)"),
        ("R07", "Position heterogeneity", "Different levels and metric meanings; GK 206 rows", "Medium", "All", "Pooled model fits outfield; poor GK estimates", "Position context or position-specific models; separate GK reporting", "No", "Model design"),
        ("R08", "Goalkeeper data limits", "Minutes 7/206; outfield metrics MISSING; ~40 GK rows per season", "Medium", "GK metrics", "Unstable GK estimates", "GK-specific handling; P4-D05 decision on lineup minutes", "Yes (P4-D05)", "Feature design"),
        ("R09", "Identity mappings not human-validated", "Lower bound 98.73% (< 99% SOP); 533 P4-B01 rows, lower-valued", "Medium", "Target", "Small wrong-target risk; fringe sensitivity", "P4-B01 sensitivity run for every result; owner labelling (ISS-01)", "Yes (labels)", "Before final results"),
        ("R10", "RD-04 metrics", "clearances one season; touches in box disagrees before 2024/25; goals prevented weak", "Medium", "5 metrics", "Season-dependent artefacts", "Owner decides exclude or season-aware use", "Yes (RD-04)", "Before feature selection"),
        ("R11", "Club context temporal ambiguity", "73 multi-club rows; no transfer dates", "Medium", "8 columns", "Post-valuation information or strong proxy", "Keep conditional; owner decision", "Yes (RS5-12)", "Before feature selection"),
        ("R12", "Source-reported rates", "6 of 8 unverifiable", "Low", "8 metrics", "Unknown measurement error", "Flag; owner may reclassify the 2 consistent GK rates", "Yes (P4-D03)", "Feature decision"),
        ("R13", "Rate-metric drift across seasons", "Recoveries/90 -23%, interceptions/90 -29% (regulars)", "Medium", "Defensive rates, passing accuracy", "Temporal hold-out shift", "Season-aware evaluation; monitor per-season errors", "No", "Evaluation"),
        ("R14", "Small-denominator per-90 rates", "40 rows under 90 minutes with rates; extremes 60 tackles/90", "Medium", "10 per-90 rates", "Outlier-driven fits", "Owner decides minimum-minutes rule, or robust handling (P4-B05)", "Yes (P4-B05)", "Preprocessing"),
        ("R15", "Old and pre-season labels", "12 targets > 365 days; 18 before first match", "Low", "Target", "Weak labels", "Keep; sensitivity analysis; owner decision RD-01", "Yes (RD-01)", "Before final dataset"),
        ("R16", "Retrospective collection and source revisions", "95 revised, 36 conflicting cells", "Low", "rating, xG, goals_prevented", "Values differ from season-end view", "Document; keep nulls", "No", "Reporting"),
        ("R17", "Effective sample size", "2,697 rows but 1,196 players; GK 206 rows", "Medium", "All", "Overfitting with many features", "Limit model complexity; grouped CV; report uncertainty", "No", "Model design"),
        ("R18", "Environment and full-suite tests", "ENV-P4-02/03: full suite not re-run during 4.1-4.6; .venv314 used", "Low", "Reproducibility", "Undetected regressions", "Run the protected full suite in 4.7 and before Phase 5", "No", "4.7"),
    ]
    return pd.DataFrame(rows, columns=["id", "risk", "evidence", "severity", "affected", "potential_impact", "mitigation",
                                       "owner_approval_required", "phase5_action"])


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    dictionary, eligibility, reliability = prof.load_metadata()
    register = uni.feature_register(eligibility, reliability)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ev = load_evidence()
    fa = feature_assessment(df, register, ev)
    th = temporal_holdout(df, scope)
    core = fa.loc[fa["phase5_recommendation"].eq("consider (core candidate)") & ~fa["position_relevance"].eq("GK only"), "feature"].tolist()

    import duckdb
    con = duckdb.connect()
    # The hold-out table has no first season by construction; the scope check runs on the usable-target rows behind it.
    con.register("usable_rows", df.loc[df["target_usable"], ["season"]])
    scope_check_derived = check_table(con, "usable_rows", scope, "season", None)

    sr = status_role(df)
    tables = {
        "feature_assessment_matrix.csv": fa,
        "feature_assessment_counts.csv": matrix_counts(fa),
        "candidate_feature_groups.csv": group_recommendations(fa),
        "eligibility_review.csv": eligibility_review(eligibility, fa),
        "status_column_role.csv": sr,
        "target_feasibility.csv": target_feasibility(df),
        "target_spread_vs_level.csv": spread_vs_level(df),
        "population_feasibility.csv": population_feasibility(df, scope).join(complete_case(df, core)),
        "player_structure.csv": player_structure(df),
        "temporal_holdout_feasibility.csv": th,
        "split_strategy_comparison.csv": split_comparison(),
        "modeling_risk_register.csv": risk_register(),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8", float_format="%.6g")
    rules = {"coverage": COVERAGE_RULE, "association": ASSOCIATION_RULE, "beyond_playing_time": BEYOND_PT_RULE,
             "redundancy": REDUNDANCY_RULE, "position": POSITION_RULE, "identity": IDENTITY_RULE, "tail": TAIL_RULE,
             "interpretability": "judgment: " + json.dumps(INTERPRETABILITY), "usefulness": "judgment by explicit rules in feasibility.usefulness()"}
    summary = {
        "dataset": str(prof.DATASET.relative_to(ROOT)).replace("\\", "/"),
        "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_id": scope.scope_id, "scope_check": verification["scope_check"],
        "scope_check_derived_usable_rows": scope_check_derived,
        "evidence_inputs": [str(p.relative_to(ROOT)).replace("\\", "/") for p in (E42, E43, E44, E45)],
        "rules": rules,
        "recommendations": fa["phase5_recommendation"].value_counts().to_dict(),
        "random_split_leakage": random_split_leakage(df),
        "status_cells": sr.attrs["status_cells"], "constant_status_columns": sr.attrs["constant_status_columns"],
        "no_model_trained": True, "no_feature_engineered": True, "no_split_executed": True,
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "feasibility_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:5000])
