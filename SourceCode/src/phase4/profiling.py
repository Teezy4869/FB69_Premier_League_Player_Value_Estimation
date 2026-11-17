"""Phase 4.1: dataset profiling and structural EDA of the official FB69 research release.

Read-only. The notebook (FB69_report.ipynb) and the evidence CLI both call these functions, so every number
has one implementation. Nothing here imputes, filters, corrects or transforms the dataset.

Usage (evidence): python -I -X utf8 src/phase4/profiling.py <out_dir>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.research_scope.scope import check_parquet, check_table, load_scope  # noqa: E402

RELEASE = ROOT / "data/releases/fb69_player_season_integrated_rs5_v1"
DATASET = RELEASE / "player_season_integrated_rs5_v1.parquet"
DATASET_SHA256 = "4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd"
ELIGIBILITY = ROOT / "reports/phase_04/step_00/phase4_feature_eligibility.csv"
KEY = ["canonical_player_id", "season"]

# Status vocabulary of the s_* columns, as documented in reports/research_scope_rs5/step_02/FOTMOB_COVERAGE_REPORT.md
S_STATUS_VOCABULARY = {"OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED",
                       "MISSING", "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING"}
S_OBSERVED = {"OBSERVED", "OBSERVED_ZERO", "OBSERVED_FALLBACK_LEADERBOARD", "OBSERVED_SOURCE_REVISED"}
PERCENT_METRICS = ["m_aerials_won_percent", "m_cross_accuracy", "m_duels_won_percent", "m_long_ball_accuracy",
                   "m_passing_accuracy", "m_save_percentage"]
POSITION_ORDER = ["GK", "DEF", "MID", "FWD"]


# ----------------------------------------------------------------------------- loading
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_verified(path: Path = DATASET, expected: str = DATASET_SHA256):
    """Verify the SHA-256, then load. Raises before reading any row if the file is not the official release."""
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path.name}: {actual} != {expected}. Stop: not the official release.")
    scope = load_scope()
    scope_counts = check_parquet(path, scope, "season", "season_id")
    table = pq.read_table(path)
    return table.to_pandas(), table.schema, scope, {"sha256": actual, "scope_check": scope_counts}


def load_metadata():
    dictionary = pd.read_csv(RELEASE / "data_dictionary.csv")
    eligibility = pd.read_csv(ELIGIBILITY)
    reliability = pd.read_csv(RELEASE / "docs/feature_reliability.csv")
    return dictionary, eligibility, reliability


def metric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("m_")]


def short(label: str) -> str:
    return f"{label[:4]}/{label[-2:]}"


# ----------------------------------------------------------------------------- 4.1.A overview
def overview(df: pd.DataFrame, scope) -> dict:
    usable = int(df["target_usable"].sum())
    return {
        "rows": len(df),
        "columns": df.shape[1],
        "unique_players": int(df["canonical_player_id"].nunique()),
        "player_season_records": int(df[KEY].drop_duplicates().shape[0]),
        "usable_targets": usable,
        "missing_targets": len(df) - usable,
        "target_coverage_pct": round(usable / len(df) * 100, 2),
        "seasons": int(df["season"].nunique()),
        "seasons_equal_scope": sorted(df["season"].unique()) == sorted(scope.labels),
        "duplicated_full_rows": int(df.astype(str).duplicated().sum()),
        "duplicated_primary_keys": int(df.duplicated(KEY).sum()),
        "null_primary_keys": int(df[KEY].isna().any(axis=1).sum()),
    }


# ----------------------------------------------------------------------------- 4.1.B schema
def schema_profile(df: pd.DataFrame, schema, dictionary: pd.DataFrame, eligibility: pd.DataFrame) -> pd.DataFrame:
    meta = dictionary.set_index("column").join(eligibility.set_index("column")[["eligibility_category", "condition_type", "condition_ids"]])
    invalid = invalid_value_counts(df)
    rows = []
    for col in df.columns:
        s = df[col]
        non_null = int(s.notna().sum())
        top_share = float(s.value_counts(dropna=False, normalize=True).iloc[0]) if len(s) else np.nan
        n_unique = int(s.nunique(dropna=True))
        n_states = int(s.nunique(dropna=False))  # distinct values, counting null as one state
        rows.append({
            "column": col,
            "arrow_type": str(schema.field(col).type),
            "dictionary_type": meta.at[col, "type"],
            "role": meta.at[col, "role"],
            "eligibility_category": meta.at[col, "eligibility_category"],
            "condition_type": meta.at[col, "condition_type"],
            "non_null": non_null,
            "null": len(s) - non_null,
            "missing_pct": round((len(s) - non_null) / len(s) * 100, 2),
            "unique": n_unique,
            "top_value_share_pct": round(top_share * 100, 2),
            "constant": n_states <= 1,                              # one value (or all null) on every row
            "single_value_with_nulls": n_unique == 1 and non_null < len(s),
            "near_constant": n_states > 1 and top_share >= 0.99,
            "invalid_values": invalid.get(col, {}).get("count", 0),
            "invalid_rule": invalid.get(col, {}).get("rule", ""),
        })
    return pd.DataFrame(rows)


def invalid_value_counts(df: pd.DataFrame) -> dict:
    """Values outside the domain a column can take. Counted, never changed."""
    rules = {}
    for col in metric_columns(df):
        if col in PERCENT_METRICS:
            rules[col] = ("outside [0, 100]", ~df[col].between(0, 100) & df[col].notna())
        elif col == "m_rating":
            rules[col] = ("outside [0, 10]", ~df[col].between(0, 10) & df[col].notna())
        elif col == "m_goals_prevented":
            continue  # goals prevented can legitimately be negative
        else:
            rules[col] = ("negative", df[col] < 0)
    rules["age_at_season_end_years"] = ("outside [15, 45]", ~df["age_at_season_end_years"].between(15, 45))
    rules["target_market_value"] = ("not positive", df["target_market_value"] <= 0)
    rules["target_valuation_age_days"] = ("negative (after cutoff)", df["target_valuation_age_days"] < 0)
    for col in [c for c in df.columns if c.startswith("temporal_") and c != "temporal_alignment_class"]:
        rules[col] = ("negative", df[col] < 0)
    for col in ["confirmed_appearance_count", "started_match_count", "sub_in_match_count", "unresolved_substitute_count"]:
        rules[col] = ("negative", df[col] < 0)
    return {col: {"rule": rule, "count": int(mask.sum())} for col, (rule, mask) in rules.items()}


def role_summary(profile: pd.DataFrame) -> pd.DataFrame:
    return (profile.groupby("eligibility_category")
            .agg(columns=("column", "size"), mean_missing_pct=("missing_pct", "mean"),
                 constant_columns=("constant", "sum"))
            .round(2).sort_values("columns", ascending=False))


# ----------------------------------------------------------------------------- 4.1.C seasons
def season_distribution(df: pd.DataFrame, scope) -> pd.DataFrame:
    g = df.groupby("season")
    out = pd.DataFrame({
        "rows": g.size(),
        "unique_players": g["canonical_player_id"].nunique(),
        "usable_targets": g["target_usable"].sum().astype(int),
    })
    out["missing_targets"] = out["rows"] - out["usable_targets"]
    out["share_of_rows_pct"] = (out["rows"] / out["rows"].sum() * 100).round(2)
    out["target_coverage_pct"] = (out["usable_targets"] / out["rows"] * 100).round(2)
    out = out.reindex(list(scope.labels))
    # players who also appear in the previous official season
    seasons = list(scope.labels)
    players = {s: set(df.loc[df["season"] == s, "canonical_player_id"]) for s in seasons}
    out["returning_from_previous_season"] = [np.nan] + [len(players[s] & players[p]) for p, s in zip(seasons, seasons[1:])]
    return out


def seasons_per_player(df: pd.DataFrame) -> pd.Series:
    return df.groupby("canonical_player_id")["season"].nunique().value_counts().sort_index().rename("players")


# ----------------------------------------------------------------------------- 4.1.D population
APPEARANCE_BINS = [0, 1, 4, 9, 19, 29, 38]
APPEARANCE_LABELS = ["1", "2-4", "5-9", "10-19", "20-29", "30-38"]
MINUTE_BINS = [0, 89, 449, 899, 1799, 2699, 3420]
MINUTE_LABELS = ["1-89", "90-449", "450-899", "900-1799", "1800-2699", "2700-3420"]


def position_by_season(df: pd.DataFrame, scope) -> pd.DataFrame:
    t = df.pivot_table(index="season", columns="position_group_season", values="canonical_player_id", aggfunc="size", fill_value=0)
    return t.reindex(index=list(scope.labels), columns=[p for p in POSITION_ORDER if p in t.columns])


def appearance_profile(df: pd.DataFrame) -> pd.DataFrame:
    bins = pd.cut(df["confirmed_appearance_count"], APPEARANCE_BINS, labels=APPEARANCE_LABELS)
    return pd.crosstab(bins, df["position_group_season"]).reindex(columns=POSITION_ORDER).rename_axis("confirmed appearances")


def minutes_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Minutes bins; a null minutes value is reported with its source status, never as zero."""
    bins = pd.cut(df["m_minutes_played"], MINUTE_BINS, labels=MINUTE_LABELS).astype(object)
    bins = bins.where(df["m_minutes_played"].notna(), "null (" + df["s_minutes_played"].astype(str) + ")")
    order = MINUTE_LABELS + sorted(set(bins) - set(MINUTE_LABELS))
    return pd.crosstab(bins, df["position_group_season"]).reindex(index=order, columns=POSITION_ORDER, fill_value=0).rename_axis("minutes played")


def low_playing_time(df: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "1 confirmed appearance": df["confirmed_appearance_count"] == 1,
        "2-4 confirmed appearances": df["confirmed_appearance_count"].between(2, 4),
        "minutes < 90 (reported)": df["m_minutes_played"] < 90,
        "minutes null": df["m_minutes_played"].isna(),
        "all rows": pd.Series(True, index=df.index),
    }
    rows = []
    for name, mask in groups.items():
        sub = df[mask]
        rows.append({"group": name, "rows": int(mask.sum()), "share_pct": round(mask.mean() * 100, 2),
                     "goalkeepers": int((sub["position_group_season"] == "GK").sum()),
                     "target_coverage_pct": round(sub["target_usable"].mean() * 100, 2) if len(sub) else np.nan,
                     "mean_null_metrics": round(sub["missing_feature_count"].mean(), 2) if len(sub) else np.nan})
    return pd.DataFrame(rows).set_index("group")


def gk_vs_outfield(df: pd.DataFrame) -> pd.DataFrame:
    grp = np.where(df["position_group_season"] == "GK", "Goalkeeper", "Outfield")
    g = df.groupby(grp)
    return pd.DataFrame({
        "rows": g.size(),
        "unique_players": g["canonical_player_id"].nunique(),
        "median_confirmed_appearances": g["confirmed_appearance_count"].median(),
        "minutes_null_pct": g["m_minutes_played"].apply(lambda s: round(s.isna().mean() * 100, 2)),
        "target_coverage_pct": g["target_usable"].apply(lambda s: round(s.mean() * 100, 2)),
        "mean_null_metrics": g["missing_feature_count"].mean().round(2),
    })


def appearance_evidence_agreement(df: pd.DataFrame) -> pd.DataFrame:
    """FotMob-reported counts versus lineup-confirmed counts (two derivations of the same quantity)."""
    rows = []
    for reported, confirmed in (("m_appearances", "confirmed_appearance_count"), ("m_starts", "started_match_count")):
        diff = df[reported] - df[confirmed]
        rows.append({"reported": reported, "lineup_evidence": confirmed, "compared": int(diff.notna().sum()),
                     "equal": int((diff == 0).sum()), "reported_higher": int((diff > 0).sum()),
                     "reported_lower": int((diff < 0).sum()), "reported_null": int(df[reported].isna().sum())})
    return pd.DataFrame(rows)


def population_context() -> dict:
    """Unverified player-seasons are outside the dataset; their counts come from the FotMob rs5 release summary."""
    summary = json.loads((ROOT / "data/releases/fotmob_epl_2020_2025_rs5_v1/metadata/canonical_summary_rs5.json").read_text(encoding="utf-8"))
    total = next(r for r in summary["population_by_season"] if r["season_label"] == "TOTAL_RS5")
    return {k: total[k] for k in ("player_seasons", "confirmed_appeared", "unverified", "unknown_player_matches")}


# ----------------------------------------------------------------------------- 4.1.E missingness
def missingness_by_column(df: pd.DataFrame, reliability: pd.DataFrame) -> pd.DataFrame:
    rel = reliability.set_index("feature")
    rows = []
    for col in metric_columns(df):
        applies_gk_only = rel.at[col, "applicable_positions"] == "GK_ONLY"
        applicable = df["position_group_season"] == "GK" if applies_gk_only else pd.Series(True, index=df.index)
        status = df["s_" + col[2:]].value_counts()
        rows.append({"metric": col, "family": rel.at[col, "metric_family"],
                     "applies_to": "GK" if applies_gk_only else "ALL",
                     "null_pct_all_rows": round(df[col].isna().mean() * 100, 2),
                     "null_pct_applicable_rows": round(df.loc[applicable, col].isna().mean() * 100, 2),
                     **{f"status_{k}": int(status.get(k, 0)) for k in ("MISSING", "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING", "OBSERVED_ZERO")}})
    return pd.DataFrame(rows).sort_values("null_pct_applicable_rows", ascending=False).reset_index(drop=True)


def missingness_overview(df: pd.DataFrame) -> dict:
    m = df[metric_columns(df)]
    all_cells = df.size
    return {"metric_null_cells": int(m.isna().sum().sum()), "metric_cells": int(m.size),
            "metric_null_pct": round(m.isna().sum().sum() / m.size * 100, 2),
            "all_null_cells": int(df.isna().sum().sum()), "all_cells": int(all_cells),
            "all_null_pct": round(df.isna().sum().sum() / all_cells * 100, 2),
            "columns_with_nulls": int((df.isna().sum() > 0).sum()),
            "metrics_with_nulls": int((m.isna().sum() > 0).sum())}


def missingness_by_family(df: pd.DataFrame, reliability: pd.DataFrame) -> pd.DataFrame:
    fam = reliability.set_index("feature")["metric_family"]
    m = df[metric_columns(df)]
    rows = []
    for family, cols in fam[fam.index.isin(m.columns)].groupby(fam[fam.index.isin(m.columns)]):
        block = m[cols.index]
        rows.append({"family": family, "metrics": len(cols), "null_pct": round(block.isna().mean().mean() * 100, 2)})
    return pd.DataFrame(rows).set_index("family").sort_values("null_pct")


def missingness_by_group(df: pd.DataFrame, group: str, order=None) -> pd.DataFrame:
    m = df[metric_columns(df)].isna()
    out = m.groupby(df[group]).mean().mean(axis=1).mul(100).round(2).rename("metric_null_pct").to_frame()
    out["mean_null_metrics_per_row"] = df.groupby(group)["missing_feature_count"].mean().round(2)
    return out.reindex(order) if order is not None else out


def status_by_position(df: pd.DataFrame, reliability: pd.DataFrame) -> pd.DataFrame:
    """s_* status cells split by row position and by whether the metric is GK-only."""
    gk_only = set(reliability.loc[reliability["applicable_positions"] == "GK_ONLY", "feature"])
    s_cols = [c for c in df.columns if c.startswith("s_")]
    long = df[["position_group_season"] + s_cols].melt(id_vars="position_group_season", var_name="status_column", value_name="status")
    long["metric_scope"] = np.where(("m_" + long["status_column"].str[2:]).isin(gk_only), "GK-only metric", "all-position metric")
    long["row_group"] = np.where(long["position_group_season"] == "GK", "GK rows", "outfield rows")
    return long.pivot_table(index=["row_group", "metric_scope"], columns="status", values="status_column", aggfunc="size", fill_value=0)


def status_by_season(df: pd.DataFrame, scope) -> pd.DataFrame:
    s_cols = [c for c in df.columns if c.startswith("s_")]
    long = df[["season"] + s_cols].melt(id_vars="season", value_name="status")
    return long.pivot_table(index="season", columns="status", values="variable", aggfunc="size", fill_value=0).reindex(list(scope.labels))


# ----------------------------------------------------------------------------- 4.1.F structural quality
def categorical_domains(df: pd.DataFrame, scope) -> pd.DataFrame:
    expected = {
        "season": set(scope.labels),
        "season_id": set(scope.season_ids),
        "position_group_season": set(POSITION_ORDER),
        "target_status": {"VALID", "STALE_TARGET", "TARGET_MISSING"},
        "target_missing_reason": {"ONLY_VALUATIONS_AFTER_CUTOFF", "NO_VALUATION_HISTORY", "NO_ELIGIBLE_IDENTITY_MATCH"},
        "target_staleness_bucket": {"0-30", "31-60", "61-90", "91-180", ">180"},
        "target_currency": {"EUR"},
        "crosswalk_status": {"AUTO_EXACT", "AUTO_ADJUDICATED", "REVIEW_REQUIRED"},
        "identity_rs5_validation_label": {"CONFIRMED_MATCH", "INCONCLUSIVE", "CONFIRMED_NON_MATCH"},
        "population_status": {"APPEARED"},
        "multi_club_class": {"SINGLE_CLUB", "MULTI_CLUB_CONFIRMED_APPEARANCES", "MULTI_CLUB_SQUAD_ONLY"},
        "research_scope_id": {scope.scope_id},
    }
    for col in [c for c in df.columns if c.startswith("s_")]:
        expected[col] = S_STATUS_VOCABULARY
    rows = []
    for col, allowed in expected.items():
        observed = set(df[col].dropna().astype(str))
        rows.append({"column": col, "observed_values": len(observed), "unexpected_values": sorted(observed - allowed),
                     "nulls": int(df[col].isna().sum())})
    return pd.DataFrame(rows)


def metric_status_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """A metric value and its s_* status must agree: observed statuses carry a value, the others are null."""
    rows = []
    for col in metric_columns(df):
        status = df["s_" + col[2:]]
        observed = status.isin(S_OBSERVED)
        rows.append({"metric": col,
                     "null_with_observed_status": int((df[col].isna() & observed).sum()),
                     "value_with_non_observed_status": int((df[col].notna() & ~observed).sum()),
                     "observed_zero_not_zero": int(((status == "OBSERVED_ZERO") & (df[col] != 0)).sum())})
    return pd.DataFrame(rows)


def logical_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-column rules. A failure is reported and preserved, never corrected."""
    m = df
    checks = {
        "m_starts > m_appearances": m["m_starts"] > m["m_appearances"],
        "m_shots_on_target > m_shots": m["m_shots_on_target"] > m["m_shots"],
        "m_goals > m_shots": m["m_goals"] > m["m_shots"],
        "m_minutes_played > 90 x m_appearances": m["m_minutes_played"] > 90 * m["m_appearances"],
        "m_appearances > 38": m["m_appearances"] > 38,
        "started + sub_in != confirmed appearances": (m["started_match_count"] + m["sub_in_match_count"]) != m["confirmed_appearance_count"],
        "confirmed_appearance_count < 1": m["confirmed_appearance_count"] < 1,
        "target_usable differs from target value present": m["target_usable"] != m["target_market_value"].notna(),
        "VALID target older than 90 days": (m["target_status"] == "VALID") & (m["target_valuation_age_days"] > 90),
        "STALE_TARGET not older than 90 days": (m["target_status"] == "STALE_TARGET") & (m["target_valuation_age_days"] <= 90),
        "missing_feature_count differs from null m_* count": m["missing_feature_count"] != m[metric_columns(m)].isna().sum(axis=1),
        "temporal games after valuation > games in season": m["temporal_player_games_after_valuation"] > m["temporal_player_games_in_season"],
        "per90 rate reported with minutes < 90": (m["m_minutes_played"] < 90) & m[[c for c in metric_columns(m) if c.endswith("_per90")]].notna().any(axis=1),
    }
    return pd.DataFrame([{"check": k, "rows": int(v.sum())} for k, v in checks.items()]).set_index("check")


def starts_gt_appearances(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["canonical_player_id", "season", "fotmob_player_name", "m_appearances", "m_starts", "s_starts",
            "confirmed_appearance_count", "started_match_count"]
    return df.loc[df["m_starts"] > df["m_appearances"], cols].reset_index(drop=True)


def column_patterns(df: pd.DataFrame, dictionary: pd.DataFrame) -> dict:
    m = {c[2:] for c in df.columns if c.startswith("m_")}
    s = {c[2:] for c in df.columns if c.startswith("s_")}
    known_prefixes = ("m_", "s_", "target_", "temporal_", "identity_")
    return {"dictionary_order_equals_schema": dictionary["column"].tolist() == df.columns.tolist(),
            "metrics_without_status": sorted(m - s), "statuses_without_metric": sorted(s - m),
            "non_snake_case_columns": [c for c in df.columns if c != c.lower() or " " in c],
            "prefixed_columns": {p: sum(c.startswith(p) for c in df.columns) for p in known_prefixes}}


def type_checks(schema, dictionary: pd.DataFrame) -> list[str]:
    types = dictionary.set_index("column")["type"]
    return [f"{f.name}: {f.type} != {types[f.name]}" for f in schema if str(f.type) != types[f.name]]


def extreme_rate_rows(df: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Highest per90 values; shown to explain small-denominator rates, not to remove them."""
    cols = ["fotmob_player_name", "season", "position_group_season", "m_minutes_played", "m_tackles_per90", "m_accurate_passes_per90"]
    return df.sort_values("m_tackles_per90", ascending=False)[cols].head(top).reset_index(drop=True)


# ----------------------------------------------------------------------------- evidence CLI
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = load_verified()
    dictionary, eligibility, reliability = load_metadata()
    profile = schema_profile(df, schema, dictionary, eligibility)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "schema_profile.csv": profile,
        "season_distribution.csv": season_distribution(df, scope),
        "seasons_per_player.csv": seasons_per_player(df).to_frame(),
        "position_by_season.csv": position_by_season(df, scope),
        "appearance_profile.csv": appearance_profile(df),
        "minutes_profile.csv": minutes_profile(df),
        "low_playing_time.csv": low_playing_time(df),
        "gk_vs_outfield.csv": gk_vs_outfield(df),
        "appearance_evidence_agreement.csv": appearance_evidence_agreement(df),
        "missingness_by_metric.csv": missingness_by_column(df, reliability),
        "missingness_by_family.csv": missingness_by_family(df, reliability),
        "missingness_by_season.csv": missingness_by_group(df, "season", list(scope.labels)),
        "missingness_by_position.csv": missingness_by_group(df, "position_group_season", POSITION_ORDER),
        "missingness_by_target_availability.csv": missingness_by_group(df, "target_usable"),
        "status_by_season.csv": status_by_season(df, scope),
        "status_by_position.csv": status_by_position(df, reliability),
        "extreme_per90_rows.csv": extreme_rate_rows(df),
        "categorical_domains.csv": categorical_domains(df, scope),
        "metric_status_consistency.csv": metric_status_consistency(df),
        "logical_checks.csv": logical_checks(df),
        "starts_gt_appearances.csv": starts_gt_appearances(df),
        "role_summary.csv": role_summary(profile),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=not isinstance(table.index, pd.RangeIndex), encoding="utf-8")
    import duckdb
    con = duckdb.connect()
    con.register("season_table", tables["season_distribution.csv"].reset_index())
    scope_check_derived = check_table(con, "season_table", scope, "season", None)
    summary = {
        "dataset": DATASET.relative_to(ROOT).as_posix(), **verification,
        "scope_check_derived_season_table": scope_check_derived,
        "overview": overview(df, scope),
        "missingness": missingness_overview(df),
        "population_context_outside_dataset": population_context(),
        "type_mismatches_vs_dictionary": type_checks(schema, dictionary),
        "column_patterns": column_patterns(df, dictionary),
        "constant_columns": profile.loc[profile["constant"], "column"].tolist(),
        "single_value_with_nulls_columns": profile.loc[profile["single_value_with_nulls"], "column"].tolist(),
        "near_constant_columns": profile.loc[profile["near_constant"], "column"].tolist(),
        "columns_with_invalid_values": profile.loc[profile["invalid_values"] > 0, ["column", "invalid_values", "invalid_rule"]].to_dict("records"),
        "unexpected_categorical_values": categorical_domains(df, scope).query("unexpected_values.str.len() > 0", engine="python").to_dict("records"),
        "environment": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__,
                        "pyarrow": __import__("pyarrow").__version__, "duckdb": duckdb.__version__},
    }
    (out_dir / "profiling_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:6000])
