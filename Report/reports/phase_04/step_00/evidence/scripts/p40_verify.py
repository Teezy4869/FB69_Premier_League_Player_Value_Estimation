"""Phase 4.0 read-only verification of the FB69 rs5 release. Writes JSON evidence to argv[2]. Never writes into the repo data."""
import hashlib, json, sys, csv, re
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT))
import duckdb, pyarrow.parquet as pq
from src.research_scope.scope import load_scope, check_parquet

REL = ROOT / "data/releases/fb69_player_season_integrated_rs5_v1"
DS = REL / "player_season_integrated_rs5_v1.parquet"
EXPECTED = "4d94ec73cfb9d72421fb2bbb1d7976bcf29f8a4f6cc985435955e574b072eedd"
r = {}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

# --- identity
r["dataset_path"] = DS.relative_to(ROOT).as_posix()
r["dataset_sha256"] = sha(DS)
r["dataset_sha256_matches_expected"] = r["dataset_sha256"] == EXPECTED
man = json.loads((REL / "release_manifest.json").read_text(encoding="utf-8"))
mf = []
for f in man["files"]:
    p = REL / f["path"]
    ok = p.exists() and sha(p) == f["sha256"] and p.stat().st_size == f["bytes"]
    mf.append({"path": f["path"], "ok": ok})
listed = {f["path"] for f in man["files"]}
on_disk = {p.relative_to(REL).as_posix() for p in REL.rglob("*") if p.is_file()} - {"release_manifest.json"}
r["manifest"] = {"files_listed": len(mf), "files_verified": sum(x["ok"] for x in mf), "failed": [x["path"] for x in mf if not x["ok"]],
                 "unlisted_files_on_disk": sorted(on_disk - listed), "listed_missing": sorted(listed - on_disk),
                 "manifest_dataset_sha256": next(f["sha256"] for f in man["files"] if f["path"] == DS.name),
                 "manifest_dataset_rows": next(f.get("rows") for f in man["files"] if f["path"] == DS.name),
                 "seasons": man["seasons"], "excluded_seasons": man["excluded_seasons"], "scope_id": man["scope_id"]}
im = json.loads((REL / "integration_manifest.json").read_text(encoding="utf-8"))
r["integration_manifest_mentions_dataset_sha"] = EXPECTED in json.dumps(im)
r["scope_snapshot_identical_to_config"] = sha(REL / "research_scope.yaml") == sha(ROOT / "configs/research_scope.yaml")
r["research_scope_yaml_sha256"] = sha(ROOT / "configs/research_scope.yaml")
for a, b in [("docs/PHASE4_CONDITIONS.md", "reports/research_scope_rs5/step_04/PHASE4_CONDITIONS.md"), ("docs/ISSUE_TRACKER.md", "reports/research_scope_rs5/step_04/ISSUE_TRACKER.md"),
             ("docs/DATA_CONTRACT_RS5.md", "reports/research_scope_rs5/DATA_CONTRACT_RS5.md"), ("docs/LEAKAGE_AUDIT.md", "reports/research_scope_rs5/step_04/LEAKAGE_AUDIT.md")]:
    r.setdefault("release_doc_copies_identical", {})[a] = sha(REL / a) == sha(ROOT / b)

# --- structure
t = pq.read_table(DS)
con = duckdb.connect()
con.register("d", t)
q = lambda s: con.execute(s).fetchall()
r["rows"] = t.num_rows
r["columns"] = t.num_columns
r["unique_players"] = q("select count(distinct canonical_player_id) from d")[0][0]
r["unique_fotmob_ids"] = q("select count(distinct fotmob_player_id) from d")[0][0]
r["season_distribution"] = {k: v for k, v in q("select season, count(*) from d group by 1 order by 1")}
r["season_label_id_pairs"] = [list(x) for x in q("select distinct season, season_id from d order by 1")]
r["pk_duplicates"] = q("select count(*) from (select canonical_player_id, season from d group by 1,2 having count(*)>1)")[0][0]
r["pk_nulls"] = q("select count(*) from d where canonical_player_id is null or season is null")[0][0]
r["fotmob_key_duplicates"] = q("select count(*) from (select fotmob_player_id, season_id from d group by 1,2 having count(*)>1)")[0][0]
r["duplicate_full_rows"] = t.num_rows - q("select count(*) from (select distinct * from d)")[0][0]
r["target_usable"] = q("select count(*) from d where target_usable")[0][0]
r["target_value_nonnull"] = q("select count(*) from d where target_market_value is not null")[0][0]
r["target_missing"] = q("select count(*) from d where not target_usable or target_usable is null")[0][0]
r["usable_iff_value"] = q("select count(*) from d where (target_usable) <> (target_market_value is not null)")[0][0]
r["target_coverage_pct"] = round(100 * r["target_usable"] / r["rows"], 2)
r["target_missing_reasons"] = {str(k): v for k, v in q("select target_missing_reason, count(*) from d where not target_usable group by 1 order by 2 desc")}
r["target_status"] = {str(k): v for k, v in q("select target_status, count(*) from d group by 1 order by 2 desc")}
r["target_eur"] = dict(zip(["median", "mean", "max", "min"], q("select median(target_market_value), avg(target_market_value), max(target_market_value), min(target_market_value) from d where target_usable")[0]))
r["target_currency"] = {str(k): v for k, v in q("select target_currency, count(*) from d group by 1")}
r["usable_by_season"] = {k: v for k, v in q("select season, count(*) from d where target_usable group by 1 order by 1")}

# dictionary vs schema
dic = list(csv.DictReader(open(REL / "data_dictionary.csv", encoding="utf-8-sig")))
dmap = {x["column"]: x for x in dic}
r["dictionary_rows"] = len(dic)
r["dictionary_columns_equal_schema_order"] = [x["column"] for x in dic] == t.column_names
r["dictionary_type_mismatches"] = [c for c in t.column_names if c in dmap and dmap[c]["type"] != str(t.schema.field(c).type)]
r["dtype_counts"] = {}
for f in t.schema:
    r["dtype_counts"][str(f.type)] = r["dtype_counts"].get(str(f.type), 0) + 1
roles = {}
for x in dic:
    roles[x["role"]] = roles.get(x["role"], 0) + 1
r["role_counts"] = roles
r["candidate_predictor_true"] = sum(x["candidate_predictor"] == "True" for x in dic)
r["candidate_predictor_roles"] = sorted({x["role"] for x in dic if x["candidate_predictor"] == "True"})
bad = [x["column"] for x in dic if x["candidate_predictor"] == "True" and (x["column"].startswith(("target_", "temporal_", "identity_")) or x["role"] in ("KEY", "IDENTITY_LINK", "IDENTITY_CONTEXT", "CLUB_CONTEXT"))]
r["forbidden_columns_flagged_candidate"] = bad

# --- scope
sc = load_scope()
r["scope_labels"] = list(sc.labels)
r["scope_ids"] = list(sc.season_ids)
r["scope_excluded"] = list(sc.excluded_labels)
r["scope_cutoffs"] = {s.season: s.season_end_date.isoformat() for s in sc.seasons}
r["scope_check_dataset"] = check_parquet(DS, sc, "season", "season_id")
r["rows_2019_20"] = q("select count(*) from d where season='2019/2020' or season_id='14022'")[0][0]
r["research_scope_id_values"] = {str(k): v for k, v in q("select research_scope_id, count(*) from d group by 1")}
r["dataset_version_values"] = {str(k): v for k, v in q("select dataset_version, count(*) from d group by 1")}
r["cutoff_by_season"] = {k: str(v) for k, v in q("select season, min(target_season_end_date) from d group by 1 order by 1")}
r["cutoff_consistent"] = all(str(q(f"select count(distinct target_season_end_date) from d where season='{s.season}' and target_season_end_date is not null")[0][0]) == "1"
                             and r["cutoff_by_season"][s.season] == s.season_end_date.isoformat() for s in sc.seasons)
r["valuations_after_cutoff"] = q("select count(*) from d where target_valuation_date > target_season_end_date")[0][0]

# scope check on every rs5 parquet with a recognisable season column
scan = []
for p in sorted(list((ROOT / "data/research_rs5").rglob("*.parquet")) + list((ROOT / "data/releases").glob("*rs5*/**/*.parquet"))):
    try:
        cols = pq.read_schema(p).names
    except Exception as e:
        scan.append({"path": p.relative_to(ROOT).as_posix(), "error": str(e)}); continue
    lab = next((c for c in ("season", "season_label") if c in cols), None)
    sid = "season_id" if "season_id" in cols else None
    entry = {"path": p.relative_to(ROOT).as_posix(), "label_col": lab, "id_col": sid}
    if lab or sid:
        try:
            check_parquet(p, sc, lab, sid, require_all=False); entry["scope_ok"] = True
        except Exception as e:
            entry["scope_ok"] = False; entry["error"] = str(e)[:300]
    else:
        entry["scope_ok"] = None
    scan.append(entry)
r["rs5_parquet_scope_scan"] = {"files": len(scan), "checked": sum(e.get("scope_ok") is not None for e in scan), "ok": sum(e.get("scope_ok") is True for e in scan),
                               "failed": [e for e in scan if e.get("scope_ok") is False], "no_season_column": [e["path"] for e in scan if e.get("scope_ok") is None]}
# excluded-season strings in rs5 CSV files (data rows)
hits = []
for p in sorted((ROOT / "data/research_rs5").rglob("*.csv")) + sorted(REL.rglob("*.csv")):
    txt = p.read_text(encoding="utf-8", errors="replace")
    n = len(re.findall(r"2019/2020|2019/20\b|\b14022\b", txt))
    if n:
        hits.append({"path": p.relative_to(ROOT).as_posix(), "matches": n})
r["excluded_season_string_hits_in_rs5_csv"] = hits

# --- conditions evidence
r["multi_season_players"] = q("select count(*) from (select canonical_player_id from d group by 1 having count(*)>1)")[0][0]
r["rows_of_multi_season_players"] = q("select count(*) from d where canonical_player_id in (select canonical_player_id from d group by 1 having count(*)>1)")[0][0]
r["crosswalk_status"] = {str(k): v for k, v in q("select crosswalk_status, count(*) from d group by 1 order by 2 desc")}
r["identity_evidence_tier"] = {str(k): v for k, v in q("select identity_evidence_tier, count(*) from d group by 1 order by 2 desc")}
r["identity_rs5_validation_label"] = {str(k): v for k, v in q("select identity_rs5_validation_label, count(*) from d group by 1 order by 2 desc")}
r["identity_human_reviewed"] = {str(k): v for k, v in q("select identity_human_reviewed, count(*) from d group by 1")}
r["players_by_crosswalk_status"] = {str(k): v for k, v in q("select crosswalk_status, count(distinct canonical_player_id) from d group by 1 order by 2 desc")}
r["rows_not_auto_exact_validated_or_inconclusive"] = q("select count(*) from d where identity_evidence_tier is distinct from 'AUTO_EXACT_VALIDATED' or identity_rs5_validation_label = 'INCONCLUSIVE'")[0][0]
r["rd02_rows"] = [dict(zip(["fotmob_player_id", "name", "season", "tm_id", "crosswalk_status", "tier", "label", "adjudicator", "target_usable"], x)) for x in
                  q("select fotmob_player_id, fotmob_player_name, season, transfermarkt_player_id, crosswalk_status, identity_evidence_tier, identity_rs5_validation_label, identity_adjudicator, target_usable from d where fotmob_player_id in ('111930','656562') order by 1,3")]
r["adjudicated_inconclusive_rows"] = [list(x) for x in q("select fotmob_player_name, season, crosswalk_status, identity_rs5_validation_label from d where crosswalk_status='AUTO_ADJUDICATED' and identity_rs5_validation_label='INCONCLUSIVE' order by 1,2")]
r["unresolved_rows"] = [list(x) for x in q("select fotmob_player_id, fotmob_player_name, season, crosswalk_status, target_missing_reason from d where transfermarkt_player_id is null")]
# temporal
r["median_age_days"] = q("select median(target_valuation_age_days) from d where target_usable")[0][0]
r["pct_over_90"] = round(100 * q("select avg(case when target_valuation_age_days>90 then 1.0 else 0 end) from d where target_usable")[0][0], 2)
a = q("select sum(temporal_player_games_after_valuation), sum(temporal_player_games_in_season), sum(temporal_minutes_after_valuation), sum(temporal_minutes_after_valuation)+sum(temporal_minutes_before_or_on_valuation) from d where target_usable")[0]
r["appearances_after_valuation"] = {"after": a[0], "total": a[1], "pct": round(100 * a[0] / a[1], 2)}
r["minutes_after_valuation_pct"] = round(100 * a[2] / a[3], 2)
r["staleness_bucket"] = {str(k): v for k, v in q("select target_staleness_bucket, count(*) from d where target_usable group by 1 order by 1")}
r["rd01_over_365"] = [list(map(str, x)) for x in q("select fotmob_player_name, season, target_valuation_date, target_valuation_age_days from d where target_usable and target_valuation_age_days>365 order by 4 desc")]
r["min_valuation_date"] = [list(map(str, x)) for x in q("select season, fotmob_player_name, target_valuation_date, target_valuation_age_days from d where target_usable order by target_valuation_date limit 3")]
r["valuations_before_first_match"] = q("select count(*) from d join (select * from (values " + ",".join(f"('{s.season}', DATE '{s.first_match_date}')" for s in sc.seasons) + ") v(season, fm)) using(season) where target_usable and target_valuation_date < fm")[0][0]
# features
mcols = [c for c in t.column_names if c.startswith("m_")]
scols = [c for c in t.column_names if c.startswith("s_")]
r["n_m"], r["n_s"] = len(mcols), len(scols)
r["m_s_pairing_complete"] = sorted(c[2:] for c in mcols) == sorted(c[2:] for c in scols)
r["key_passes_nonnull"] = q("select count(m_key_passes) from d")[0][0]
r["key_passes_status"] = {str(k): v for k, v in q("select s_key_passes, count(*) from d group by 1")}
r["clearances_nonnull_by_season"] = {k: v for k, v in q("select season, count(m_clearances) from d group by 1 order by 1")}
r["clearances_per90_nonnull_by_season"] = {k: v for k, v in q("select season, count(m_clearances_per90) from d group by 1 order by 1")}
r["goals_prevented_nonnull_by_season"] = {k: v for k, v in q("select season, count(m_goals_prevented) from d group by 1 order by 1")}
r["xgot_nonnull_by_season"] = {k: v for k, v in q("select season, count(m_expected_goals_on_target) from d group by 1 order by 1")}
r["touches_box_nonnull_by_season"] = {k: v for k, v in q("select season, count(m_touches_opposition_box) from d group by 1 order by 1")}
sv = {}
for c in scols:
    for k, v in q(f'select "{c}", count(*) from d group by 1 order by 1'):
        sv[str(k)] = sv.get(str(k), 0) + v
r["s_status_values_all_columns"] = dict(sorted(sv.items()))
r["s_types"] = sorted({str(t.schema.field(c).type) for c in scols})
nulls_total = sum(q(f'select count(*) - count("{c}") from d')[0][0] for c in mcols)
r["metric_null_cells"] = {"null": nulls_total, "total": len(mcols) * t.num_rows, "pct": round(100 * nulls_total / (len(mcols) * t.num_rows), 2)}
# null m_ whose s_ says observed
obs_null = {}
for c in mcols:
    n = q(f'select count(*) from d where "{c}" is null and "s_{c[2:]}" = \'OBSERVED\'')[0][0]
    if n:
        obs_null[c] = n
r["null_metric_with_OBSERVED_status"] = obs_null
r["mean_null_metrics_usable_vs_missing"] = [list(x) for x in q("select target_usable, round(avg(missing_feature_count),2), count(*) from d group by 1 order by 1")]
r["mean_null_metrics_by_position"] = [list(x) for x in q("select position_group_season, round(avg(missing_feature_count),2), count(*) from d group by 1 order by 1")]
r["starts_gt_appearances"] = q("select count(*) from d where m_starts > m_appearances")[0][0]
r["multi_club_rows"] = q("select count(*) from d where is_multi_club")[0][0]
r["nationality_nonnull"] = q("select count(nationality_profile_present_day) from d")[0][0]
r["age_nulls"] = q("select count(*) - count(age_at_season_end_years) from d")[0][0]
r["position_group_values"] = {str(k): v for k, v in q("select position_group_season, count(*) from d group by 1 order by 1")}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "phase4_00_verification.json").write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
print(json.dumps(r, indent=1, default=str))
