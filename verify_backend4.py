"""Verify delivered risk outputs against source forecasts and causal residual cutoffs."""
from pathlib import Path
import hashlib
import json
import sys
import subprocess
import numpy as np
import pandas as pd

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-root',type=Path,required=True)
parser.add_argument('--historical-source-ref',help='Git revision that generated the preserved evaluation artifacts')
parser.add_argument('--output-report',type=Path,help='Separate verification report; do not overwrite historical evidence')
args=parser.parse_args()
BASE=args.input_root.resolve()
SUB=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
import src
src.__path__.insert(0,str(SUB/'src'))
from src.risk.run import _risk_rows,build_residuals
from src.risk.metrics import christoffersen_test

out=SUB/'outputs/risk'
files=sorted(out.glob('*.parquet'))
assert len(files)==18
all_risk=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
assert len(all_risk)==2*9*2*2*1826
assert not all_risk.duplicated(['coin','model','window','alpha','date']).any()
assert all_risk.date.min()==pd.Timestamp('2021-01-01',tz='UTC')
assert all_risk.date.max()==pd.Timestamp('2025-12-31',tz='UTC')
valid=all_risk.loc[all_risk.score_valid]
assert np.isfinite(valid[['var','es','return','sigma_pct']].to_numpy()).all()
assert valid.es.le(valid['var']+1e-12).all()
assert (valid.breach==(valid['return']<valid['var']).astype(float)).all()
assert all_risk.loc[~all_risk.score_valid,'breach'].isna().all()
fhs=valid.loc[valid.method.eq('fhs')]
assert fhs.n_fhs_residuals.ge(20).all()
assert fhs.last_residual_observable_at.le(fhs.forecast_available_at).all()
assert fhs.last_residual_target_date.lt(fhs.date).all()
summary=pd.read_csv(out/'backtest.csv')
assert len(summary)==72
assert summary.groupby(['coin','window','alpha']).n.nunique().eq(1).all()
for key,g in all_risk.groupby(['coin','window','alpha']):
    common=g.loc[g.common_sample]
    date_sets=[set(p.date) for _,p in common.groupby('model')]
    assert all(d==date_sets[0] for d in date_sets)
    for model,p in common.groupby('model'):
        p=p.sort_values('date')
        actual=christoffersen_test(p.breach,key[2],dates=p.date)
        row=summary.loc[summary.coin.eq(key[0])&summary.window.eq(key[1])&summary.alpha.eq(key[2])&summary.model.eq(model)].iloc[0]
        assert row.n_adjacent_pairs==actual['n_adjacent_pairs']
        assert row.n_gaps==actual['n_gaps']

# Recompute the first 50 actual HAR forecasts; change future residuals only.
fc=pd.read_parquet(BASE/'outputs/forecasts/BTCUSDT_har_rv.parquet')
fc=fc.loc[fc.horizon_days.eq(1)&fc.window.eq('rolling')].sort_values('target_date')
truth=pd.read_parquet(BASE/'data/processed/dataset.parquet',columns=['symbol','origin_date','ret_d'])
truth=truth.rename(columns={'origin_date':'target_date','ret_d':'realized_return_pct'})
fc=fc.merge(truth,on=['symbol','target_date'],how='left',validate='many_to_one')
if 'mean_forecast_pct' not in fc:fc['mean_forecast_pct']=0.
pool=build_residuals(fc)
check=fc.head(100)
expected=_risk_rows(check,pool)
changed=pool.copy();changed.loc[changed.observable_at.gt(check.forecast_available_at.max()),'standardized_residual']=-10000
mutated=_risk_rows(check,changed)
np.testing.assert_allclose(expected['var'],mutated['var'],equal_nan=True,rtol=0,atol=0)
np.testing.assert_allclose(expected.es,mutated.es,equal_nan=True,rtol=0,atol=0)
for c in ('target_date','observable_at'):changed[c]=changed[c].astype('datetime64[ns, UTC]')
again=_risk_rows(check,changed)
np.testing.assert_allclose(expected['var'],again['var'],equal_nan=True,rtol=0,atol=0)
delivered=all_risk.loc[all_risk.coin.eq('BTCUSDT')&all_risk.model.eq('har_rv')&all_risk.window.eq('rolling')]
merged=expected.merge(delivered,on=['coin','model','window','alpha','date'],suffixes=('_check','_delivered'),validate='one_to_one')
np.testing.assert_allclose(merged.var_check,merged.var_delivered,equal_nan=True,rtol=0,atol=0)
paths=sorted((out/'strategy_paths').glob('*.parquet'))
assert len(paths)==36
for p in paths:
    curve=pd.read_parquet(p)
    assert len(curve)==1826 and curve.date.diff().iloc[1:].eq(pd.Timedelta(days=1)).all()
    np.testing.assert_allclose(curve.strategy_cum,100*((1+curve.strategy_return/100).cumprod()-1),atol=1e-10)
    np.testing.assert_allclose(curve.bh_cum,100*((1+curve.bh_return/100).cumprod()-1),atol=1e-10)
    assert (curve.cost_pct>=-1e-12).all()
    assert curve.loc[~curve.forecast_used,'cost_pct'].abs().le(1e-12).all()
assert len(list((SUB/'outputs/figures/risk').glob('*.png')))==18
manifest=json.loads((out/'run_manifest.json').read_text(encoding='utf-8'))
for rel,sha in manifest['input_sha256'].items():assert hashlib.sha256((BASE/rel).read_bytes()).hexdigest()==sha
for rel,sha in manifest['output_sha256'].items():assert hashlib.sha256((SUB/rel).read_bytes()).hexdigest()==sha
for rel,sha in manifest.get('risk_source_sha256',{}).items():
    code=(subprocess.check_output(['git','show',f'{args.historical_source_ref}:{rel}'],cwd=SUB)
          if args.historical_source_ref else (SUB/rel).read_bytes())
    assert hashlib.sha256(code).hexdigest()==sha
assert manifest['holdout_evaluated'] is False
result=dict(check='passed',risk_files=len(files),scheduled_risk_rows=len(all_risk),valid_risk_rows=len(valid),
    common_risk_rows=int(all_risk.common_sample.sum()),backtest_rows=len(summary),strategy_paths=len(paths),
    first_valid_har=str(delivered.loc[delivered.score_valid,'date'].min()),
    har_fhs_count_range=[int(delivered.n_fhs_residuals.min()),int(delivered.n_fhs_residuals.max())],
    real_data_future_mutation_test='passed',timestamp_resolution_invariance='passed',
    source_and_output_checksums='passed',holdout_evaluated=False,
    unit_tests=json.loads((out/'test_results.json').read_text(encoding='utf-8')) if (out/'test_results.json').exists() else None,
    risk_source_sha256={p.relative_to(SUB).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((SUB/'src/risk').glob('*.py'))})
result['historical_source_ref']=args.historical_source_ref
(args.output_report or out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
