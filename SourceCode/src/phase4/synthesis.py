"""Phase 4.7: cross-phase consistency, research-integrity and notebook checks for the final Phase 4 acceptance.

Read-only. Compares the recorded evidence of Phases 4.0-4.6 with each other and with a fresh recomputation from the
official dataset, rebuilds the Phase 4.0 eligibility register in a temporary folder and compares it byte for byte,
and audits the executed notebook. It changes no data and no earlier evidence.

Usage (evidence): python -I -X utf8 src/phase4/synthesis.py <out_dir>
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
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

EV = ROOT / "reports/phase_04"
NOTEBOOK = ROOT / "FB69_report.ipynb"
ELIGIBILITY_SCRIPT = EV / "step_00/evidence/scripts/p40_eligibility.py"
EXCLUDED_SEASON_PATTERNS = ("2019/2020", "2019/20", "14022")
FORBIDDEN_PREFIXES = ("target_", "temporal_", "identity_", "crosswalk_", "provenance_", "s_")
FORBIDDEN_COLUMNS = {"nationality_profile_present_day", "m_key_passes", "canonical_player_id", "fotmob_player_id",
                     "transfermarkt_player_id", "fotmob_player_name", "fotmob_profile_name", "fotmob_birth_date", "season", "season_id"}
SECTIONS = {"4.1": "fb69-p41-", "4.2": "fb69-p42-", "4.3": "fb69-p43-", "4.4": "fb69-p44-", "4.5": "fb69-p45-", "4.6": "fb69-p46-", "4.7": "fb69-p47-"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, **kw).rename(columns=lambda c: c.lstrip("﻿"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- cross-phase consistency
def consistency_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Key statistics as recorded by each sub-phase, compared with each other and with a fresh recomputation."""
    v40 = _json(EV / "step_00/evidence/phase4_00_verification.json")
    s41 = _json(EV / "step_01/evidence/profiling_summary.json")
    s42 = _json(EV / "step_02/evidence/univariate_summary.json")
    s43 = _json(EV / "step_03/evidence/bivariate_summary.json")
    s44 = _json(EV / "step_04/evidence/multivariate_summary.json")
    s45 = _json(EV / "step_05/evidence/reliability_summary.json")
    t42 = _csv(EV / "step_02/evidence/target_summary.csv", index_col=0)
    pos42 = _csv(EV / "step_02/evidence/target_by_position.csv", index_col=0)
    pos44 = _csv(EV / "step_04/evidence/position_profile.csv", index_col=0)
    sea42 = _csv(EV / "step_02/evidence/target_by_season.csv", index_col=0)
    sea44 = _csv(EV / "step_04/evidence/season_profile.csv", index_col=0)
    sea45 = _csv(EV / "step_05/evidence/identity_season_medians.csv", index_col=0)
    a43 = _csv(EV / "step_03/evidence/feature_target_association.csv").set_index("feature")
    fa46 = _csv(EV / "step_06/evidence/feature_assessment_matrix.csv").set_index("feature")
    ids43 = _csv(EV / "step_03/evidence/identity_sensitivity_spearman.csv").set_index("feature")
    ids45 = _csv(EV / "step_05/evidence/identity_feature_target_sensitivity.csv").set_index("feature")
    sem45 = _csv(EV / "step_05/evidence/status_semantics.csv").set_index("status")
    tf46 = _csv(EV / "step_06/evidence/target_feasibility.csv").set_index("measure")
    ref45 = _csv(EV / "step_05/evidence/temporal_reference_values.csv").set_index("measure")
    u = df["target_usable"]
    k = df.groupby("canonical_player_id").size()
    ku = df[u].groupby("canonical_player_id").size()
    null_statuses = ["MISSING", "UNVERIFIED_POSITION", "UNSUPPORTED", "CONFLICTING"]
    gk_cov = _csv(EV / "step_05/evidence/gk_coverage_by_season.csv")
    rows = [
        ("Rows", {"4.0": v40["rows"], "4.3": s43["rows"], "4.4": s44["rows"], "fresh": len(df)}, ""),
        ("Usable targets", {"4.0": v40["target_usable"], "4.2": t42.at["n", "raw_eur"], "4.3": s43["usable_targets"], "4.4": s44["usable_targets"],
                            "4.6": tf46.at["usable targets", "value"], "fresh": int(u.sum())}, ""),
        ("Players", {"4.0": v40["unique_players"], "fresh": df["canonical_player_id"].nunique()}, ""),
        ("Target median (EUR)", {"4.0": v40["target_eur"]["median"], "4.2": t42.at["p50", "raw_eur"], "fresh": float(df.loc[u, uni.TARGET].median())}, ""),
        ("Null metric cells", {"4.0": v40["metric_null_cells"]["null"], "4.1": s41["missingness"]["metric_null_cells"],
                               "4.5": int(sem45.loc[null_statuses, "cells"].sum()),
                               "fresh": int(df[[c for c in df.columns if c.startswith("m_")]].isna().sum().sum())}, ""),
        ("P4-B01 rows", {"4.0": v40["rows_not_auto_exact_validated_or_inconclusive"], "4.3": s43["identity_sensitivity_rows"],
                         "4.5": s45["identity_sensitivity_rows"], "fresh": int(biv.identity_sensitivity_mask(df).sum())}, ""),
        ("Median valuation age (days)", {"4.0": v40["median_age_days"], "4.5": ref45.at["Median valuation age (days)", "recomputed"],
                                         "fresh": float(df.loc[u, "target_valuation_age_days"].median())}, ""),
        ("Appearances after valuation (%)", {"4.0": v40["appearances_after_valuation"]["pct"],
                                             "4.5": round(ref45.at["Appearances after the valuation date (%)", "recomputed"], 2)}, ""),
        ("Multi-season players (all rows)", {"4.0": v40["multi_season_players"], "fresh": int((k > 1).sum())},
         "4.6 reports 679 players for usable-target rows only (8 multi-season players have a target in one season only)"),
        ("Multi-season players (usable rows)", {"4.6": _json(EV / "step_06/evidence/feasibility_summary.json")["random_split_leakage"]["players_with_multiple_seasons"],
                                                "fresh": int((ku > 1).sum())}, ""),
        ("Goalkeeper rows", {"4.4": int(pos44.at["GK", "rows"]), "4.5": int(gk_cov["gk_rows"].sum()), "fresh": int(df[uni.POSITION].eq("GK").sum())}, ""),
        ("Features analysed", {"4.2": s42["features_analysed"], "4.3": s43["features_analysed"], "4.6": len(fa46), "fresh": len(uni.FEATURES)}, ""),
    ]
    for p in prof.POSITION_ORDER:
        rows.append((f"Median target {p} (EUR)", {"4.2": pos42.at[p, "median_eur"], "4.4": pos44.at[p, "target_median_eur"]}, ""))
    for s in sea42.index:
        rows.append((f"Median target {prof.short(s)} (EUR)", {"4.2": sea42.at[s, "median_eur"], "4.4": sea44.at[s, "target_median_eur"],
                                                              "4.5": sea45.at[s, "median_all_eur"]}, ""))
    rows.append(("Pooled Spearman, all 53 features (max |difference| 4.3 vs 4.6)",
                 {"4.3 vs 4.6": float((a43["spearman"] - fa46["pooled_spearman"]).abs().max())}, "must be 0"))
    rows.append(("Identity sensitivity, all 53 features (max |difference| 4.3 vs 4.5)",
                 {"4.3 vs 4.5": float((ids43["difference"] - ids45["difference"]).abs().max())}, "must be 0"))
    out = []
    for name, values, note in rows:
        vals = [float(v) for v in values.values()]
        consistent = np.allclose(vals, vals[0], rtol=1e-9, atol=1e-9) if not name.startswith(("Pooled", "Identity")) else vals[0] < 1e-9
        out.append({"check": name, **{f"value_{k}": v for k, v in values.items()}, "consistent": bool(consistent), "note": note})
    return pd.DataFrame(out)


def definitional_differences() -> pd.DataFrame:
    """Counts that differ across sub-phases because they are defined differently (documented, not errors)."""
    rows = [
        ("Limited-coverage features", "4.2: 21 (> 20% null on applicable rows or a season below 50% coverage, all features incl. RD-04 and ISS-29)",
         "4.5: 15 in class 'reliable values, limited coverage' (RD-04 and ISS-29 features have their own classes)", "Different definitions"),
        ("Multi-season players", "4.0/4.1: 687 players, 2,206 rows (all rows)", "4.6: 679 players, 2,180 rows (rows with a usable target)", "Different populations"),
        ("Players", "4.0/4.1: 1,228 (all rows)", "4.3/4.6: 1,196 (rows with a usable target)", "Different populations"),
        ("Rows without detailed statistics", "4.2: 317 outfield rows with minutes but no detailed statistics", "4.5: 317 outfield rows with 0 starts, all without detailed statistics", "Same rows, two descriptions"),
        ("Association labels", "4.3: strength from |Spearman| plus a bootstrap interval ('no clear association' when it contains 0)", "4.6: strength from |Spearman| only ('none' below 0.1)", "Different rules; both give 9 strong; weak/none counts differ"),
    ]
    return pd.DataFrame(rows, columns=["topic", "source_a", "source_b", "explanation"])


# ----------------------------------------------------------------------------- integrity
def scope_scan() -> pd.DataFrame:
    """Search every Phase 4 evidence table for the excluded season."""
    rows = []
    for path in sorted(EV.glob("step_0[1-6]/evidence/*")):
        if path.suffix not in (".csv", ".json"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = {p: text.count(p) for p in EXCLUDED_SEASON_PATTERNS if p in text}
        if hits:
            rows.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "hits": json.dumps(hits)})
    return pd.DataFrame(rows, columns=["file", "hits"])


def predictor_integrity() -> pd.DataFrame:
    """No forbidden column was analysed as a predictor or recommended for consideration."""
    fa = _csv(EV / "step_06/evidence/feature_assessment_matrix.csv")
    analysed = set(uni.FEATURES)
    recommended = set(fa.loc[fa["phase5_recommendation"].str.startswith("consider"), "feature"])
    checks = []
    for name, cols in (("analysed predictors (4.2-4.6)", analysed), ("recommended for consideration (4.6)", recommended)):
        bad = sorted(c for c in cols if c.startswith(FORBIDDEN_PREFIXES) or c in FORBIDDEN_COLUMNS)
        club = sorted(c for c in cols if c in {"confirmed_team_ids", "confirmed_team_count", "associated_team_count", "associated_team_ids",
                                                "associated_team_names", "is_multi_club", "multi_club_status", "multi_club_class"})
        rd04 = sorted(c for c in cols & set(uni.RD04)) if "recommended" in name else []
        checks.append({"set": name, "columns": len(cols), "forbidden": ", ".join(bad), "club_context": ", ".join(club),
                       "rd04_recommended": ", ".join(rd04), "ok": not bad and not club and not rd04})
    return pd.DataFrame(checks)


def eligibility_rebuild() -> dict:
    """Rebuild the Phase 4.0 eligibility register with its own script and compare it byte for byte."""
    registered = EV / "step_00/phase4_feature_eligibility.csv"
    with tempfile.TemporaryDirectory(prefix="fb69_elig_") as folder:
        out = Path(folder) / "rebuilt.csv"
        subprocess.run([sys.executable, "-I", str(ELIGIBILITY_SCRIPT), str(ROOT), str(out)], check=True, capture_output=True)
        rebuilt = out.read_bytes()
    return {"registered_sha256": sha256(registered), "rebuilt_sha256": hashlib.sha256(rebuilt).hexdigest(),
            "identical": registered.read_bytes() == rebuilt,
            "category_counts": _csv(registered)["eligibility_category"].value_counts().to_dict()}


# ----------------------------------------------------------------------------- notebook audit
def notebook_audit(path: Path = NOTEBOOK) -> tuple[pd.DataFrame, dict]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = nb["cells"]
    code = [c for c in cells if c["cell_type"] == "code"]
    counts = [c.get("execution_count") for c in code]
    errors = [c["id"] for c in code for o in c.get("outputs", []) if o.get("output_type") == "error"]
    big = []
    for c in code:
        size = sum(len("".join(o.get("text", ""))) + len("".join(o.get("data", {}).get("text/plain", ""))) for o in c.get("outputs", []))
        if size > 20_000:
            big.append((c["id"], size))
    rows = []
    for sec, prefix in SECTIONS.items():
        sc = [c for c in cells if c["id"].startswith(prefix)]
        if not sc:
            continue
        md = ["".join(c["source"]) for c in sc if c["cell_type"] == "markdown"]
        cc = [c for c in sc if c["cell_type"] == "code"]
        figs = sum(1 for c in cc for o in c.get("outputs", []) if "image/png" in o.get("data", {}))
        text = "\n".join(md)
        rows.append({"section": sec, "cells": len(sc), "code_cells": len(cc), "markdown_cells": len(md), "figures": figs,
                     "markdown_before_first_code": sc[0]["cell_type"] == "markdown",
                     "interpretation_blocks": text.count("**Interpretation") + text.count("Interpretation of Important") + text.count("Conclusion"),
                     "rd03_mentions": text.count("RD-03"), "objective_stated": "Objective" in text,
                     "limitations_section": "Limitations" in text, "conclusion_section": "Conclusion" in text,
                     "causal_disclaimer": bool(re.search(r"(not|no|never|none of this)[^.]{0,80}caus", text, re.I))})
    summary = {"cells": len(cells), "code_cells": len(code), "executed_in_order": counts == list(range(1, len(code) + 1)),
               "error_outputs": errors, "large_text_outputs": big,
               "absolute_paths_in_source": sorted({m for c in cells for m in re.findall(r"[A-Z]:\\\\[A-Za-z]", "".join(c["source"]))})}
    return pd.DataFrame(rows), summary


# ----------------------------------------------------------------------------- evidence
def run_all(out_dir: Path) -> dict:
    df, schema, scope, verification = prof.load_verified()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cons = consistency_checks(df)
    nb_sections, nb_summary = notebook_audit()
    elig = eligibility_rebuild()
    tables = {"cross_phase_consistency.csv": cons, "definitional_differences.csv": definitional_differences(),
              "scope_scan_excluded_season.csv": scope_scan(), "predictor_integrity.csv": predictor_integrity(),
              "notebook_section_audit.csv": nb_sections}
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False, encoding="utf-8", float_format="%.6g")
    summary = {
        "dataset_sha256": verification["sha256"], "sha256_verified": verification["sha256"] == prof.DATASET_SHA256,
        "scope_id": scope.scope_id, "scope_check": verification["scope_check"], "rows_excluded_season": int(df["season"].isin(scope.excluded_labels).sum()),
        "consistency_all": bool(cons["consistent"].all()), "consistency_failures": cons.loc[~cons["consistent"], "check"].tolist(),
        "excluded_season_hits_in_evidence": len(tables["scope_scan_excluded_season.csv"]),
        "predictor_integrity_ok": bool(tables["predictor_integrity.csv"]["ok"].all()),
        "eligibility_rebuild": elig, "notebook": nb_summary,
        "dataset_sha256_after": prof.sha256_file(prof.DATASET),
        "versions": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
    }
    (out_dir / "synthesis_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_all(Path(sys.argv[1])), indent=1, default=str)[:6000])
