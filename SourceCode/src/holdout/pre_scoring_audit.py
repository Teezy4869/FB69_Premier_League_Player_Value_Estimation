"""Holdout pre-scoring leakage audit. Prints booleans, counts and dates only; never a holdout target, value or prediction."""
import sys,json,os,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT)); os.chdir(ROOT)
import pandas as pd, lightgbm as lgb, duckdb
from src.phase5.final_model import verify_freeze
from src.phase3.tm_common import file_hash
from src.phase5 import features as fx
from src.phase3.season_targets import select_target, HISTORY
from src.phase5.season_start_prev_value import decide
from src.holdout import build_holdout as bh
R={}
m=verify_freeze(); R['freeze_hashes_ok']=True
M=Path('data/phase_05/final_model/final_model_v1'); fm=json.load(open(M/'manifest.json'))
R['model_sha_ok']=file_hash(M/'final_model.txt')==fm['model_sha256']
mt=lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p),dt.timezone.utc).isoformat(timespec='seconds')
raw=[os.path.join(d,f) for d,_,fs in os.walk('data/holdout_2025_26/fotmob/raw') for f in fs]
R['times_utc']={'freeze_signed':m['signed_utc'],'model_fitted':fm['generated_utc'],'model_file_mtime':mt(M/'final_model.txt'),
 'first_holdout_raw_file':min(mt(p) for p in raw),'holdout_input_v1':mt('data/holdout_2025_26/model_input/holdout_model_input_v1.parquet'),'holdout_input_v2':mt('data/holdout_2025_26/model_input/holdout_model_input_v2.parquet')}
dev=pd.read_parquet(fx.OUTPUT/'model_input.parquet'); cfg=fx.load_config(); feats=fx.feature_columns(cfg)
R['dev']={'rows':len(dev),'seasons':sorted(dev.season.unique()),'model_training_rows':fm['training_rows'],'best_params':fm['best_params']}
bst=lgb.Booster(model_file=str(M/'final_model.txt'))
R['booster_features_equal_config']=bst.feature_name()==feats and fm['feature_order']==feats
R['features']=feats
R['non_feature_columns_in_model']=[f for f in feats if f.startswith(('target','s_','temporal','identity','season')) or f in ('canonical_player_id','transfermarkt_player_id')]
d=duckdb.sql("select target_valuation_date, target_season_end_date from 'data/releases/fb69_player_season_integrated_rs5_v1/player_season_integrated_rs5_v1.parquet'").df()
R['dev_target_after_cutoff']=int((pd.to_datetime(d.target_valuation_date)>pd.to_datetime(d.target_season_end_date)).sum())
p=pd.read_parquet('data/phase_05/previous_value/season_start_prev_value_v1/season_start_prev_value.parquet')
R['dev_prev_on_or_after_first_match']=int((p.prev_valuation_date.notna()&(p.prev_valuation_date>=p.first_match_date)).sum())
R['dev_latest_target_valuation_date']=str(pd.to_datetime(d.target_valuation_date).max().date())
h=pd.read_parquet('data/holdout_2025_26/model_input/holdout_model_input_v2.parquet')
R['holdout']={'rows':len(h),'season':sorted(h.season.unique()),'key_overlap_with_dev':int(h.set_index(fx.KEY).index.isin(dev.set_index(fx.KEY).index).sum()),
 'feature_columns_present':all(f in h for f in feats),'categories_equal':list(h.position_group_season.cat.categories)==list(dev.position_group_season.cat.categories),
 'dtypes_equal':all(str(h[f].dtype)==str(dev[f].dtype) for f in feats)}
# temporal checks on holdout: dates only, no values printed
cw,_=bh.apply_labels(pd.read_parquet('data/holdout_2025_26/entity_resolution/matching_v2_1__reviews_none/player_crosswalk.parquet').set_index('fotmob_player_id'))
hist={}
for tid,day,v,s,rid in duckdb.sql(f"select tm_player_id,valuation_date,market_value,quality_status,source_record_id from '{HISTORY.as_posix()}'").fetchall():
    hist.setdefault(tid,[]).append({'valuation_date':day,'market_value':v,'quality_status':s,'source_record_id':rid})
late=prev_bad=0
for t in h.transfermarkt_player_id:
    sel=select_target(hist.get(t,[]),bh.END,90)['selected_valuation_date']; late+=sel is None or sel>bh.END
    pv=decide(hist.get(t,[]),bh.FIRST)['prev_valuation_date']; prev_bad+=pv is not None and pv>=bh.FIRST
R['holdout_target_after_cutoff_or_missing']=late; R['holdout_prev_on_or_after_first_match']=prev_bad
R['holdout_labelling_file_value_columns']=[c for c in pd.read_csv('reports/phase_05/holdout/iss01_holdout_labeling.csv',nrows=0).columns if any(w in c.lower() for w in ('value','market','target','eur'))]
R['scoring_outputs_exist']=[str(p) for p in Path('data').rglob('*') if 'holdout' in str(p).lower() and any(w in p.name.lower() for w in ('pred','score','metric','lock'))]
print(json.dumps(R,indent=1,default=str))
