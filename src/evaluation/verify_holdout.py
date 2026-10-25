"""Verify every delivered holdout forecast, causal risk pool and unchanged evaluation."""
import json
import numpy as np
import pandas as pd
from src.final_holdout import PLAN, check_frozen, save, sha
from src.utils.config import ROOT, load_config
from src.evaluation.validate import validate_forecasts
from src.evaluation.walkforward import make_schedule
from src.risk.run import MODELS, risk_forecast_input, _risk_rows, comparison_tables
from src.risk.strategy import run_strategy

def verify():
    plan=json.loads(PLAN.read_text(encoding='utf-8'));check_frozen(plan['frozen_sha256'])
    cfg=load_config();ds=pd.read_parquet(ROOT/'data/processed/dataset.parquet')
    digest=sha(ROOT/'data/processed/dataset.parquet')
    schedule=make_schedule(ds,cfg);schedule=schedule.loc[schedule.target_segment.eq('holdout')]
    start,end=pd.Timestamp(plan['start'],tz='UTC'),pd.Timestamp(plan['end'],tz='UTC')
    truth=ds[['symbol','origin_date','ret_d']].rename(columns={'origin_date':'target_date','ret_d':'realized_return_pct'})
    forecasts=[];risk_frames=[];inputs={};future_checks=0
    keys=['symbol','window','horizon_days','origin_date','target_date']
    for coin in cfg['data']['symbols']:
        expected=schedule.loc[schedule.symbol.eq(coin),keys]
        for model in MODELS:
            rel=f'outputs/forecasts_holdout/{coin}_{model}.parquet';p=ROOT/rel
            fc=pd.read_parquet(p);errors=validate_forecasts(fc,ds,cfg,digest,rel)
            if errors:raise ValueError(errors)
            if set(map(tuple,fc[keys].to_numpy()))!=set(map(tuple,expected.to_numpy())):
                raise ValueError('Incomplete holdout schedule: '+rel)
            assert fc.model.eq(model).all() and fc.symbol.eq(coin).all()
            assert fc.target_start.ge(start).all() and fc.target_date.le(end).all()
            inputs[rel]=sha(p);forecasts.append(fc)
            seed=pd.read_parquet(ROOT/f'outputs/forecasts/{coin}_{model}.parquet')
            scored,pool=risk_forecast_input(fc.merge(truth,on=['symbol','target_date'],validate='many_to_one'),
                seed.merge(truth,on=['symbol','target_date'],validate='many_to_one'),start,end)
            risk=pd.read_parquet(ROOT/f'outputs/risk_holdout/{coin}_{model}.parquet')
            assert len(risk)==(end-start).days*4+4
            assert not risk.duplicated(['coin','model','window','alpha','date']).any()
            rebuilt=_risk_rows(scored,pool)
            compare=['coin','model','window','alpha','date']
            both=rebuilt.merge(risk,on=compare,suffixes=('_new','_saved'),validate='one_to_one')
            assert len(both)==len(risk)
            for c in ('var','es','sigma_pct','n_fhs_residuals','n_fhs_tail'):
                np.testing.assert_allclose(both[c+'_new'],both[c+'_saved'],equal_nan=True,rtol=0,atol=0)
            assert both.status_new.eq(both.status_saved).all()
            valid=risk.loc[risk.score_valid]
            assert np.isfinite(valid[['var','es','return','sigma_pct']]).all().all()
            assert valid.es.le(valid['var']+1e-12).all()
            assert valid.breach.eq((valid['return']<valid['var']).astype(float)).all()
            assert risk.loc[~risk.score_valid,'breach'].isna().all()
            fhs=valid.loc[valid.method.eq('fhs')]
            assert fhs.last_residual_observable_at.le(fhs.forecast_available_at).all()
            assert fhs.last_residual_target_date.lt(fhs.date).all()
            assert fhs.n_fhs_residuals.ge(20).all()
            if model not in ('garch','gjr_garch'):
                first=scored.loc[scored.target_date.eq(start)]
                early=_risk_rows(first,pool)
                assert early.n_fhs_residuals.ge(20).all(), 'Historical seed lost at year boundary'
                early_horizon=scored.loc[scored.target_date.le(start+pd.Timedelta(days=29))]
                before=_risk_rows(early_horizon,pool)
                altered=pool.copy()
                altered.loc[altered.observable_at.gt(early_horizon.forecast_available_at.max()),'standardized_residual']=-1e9
                after=_risk_rows(early_horizon,altered)
                np.testing.assert_allclose(before['var'],after['var'],equal_nan=True,rtol=0,atol=0)
                np.testing.assert_allclose(before.es,after.es,equal_nan=True,rtol=0,atol=0)
                future_checks+=1
            for window in ('rolling','expanding'):
                part=risk.loc[risk.window.eq(window)&risk.alpha.eq(.05)].sort_values('date')
                curve=pd.read_parquet(ROOT/f'outputs/risk_holdout/strategy_paths/{coin}_{model}_{window}.parquet')
                rebuilt_curve=run_strategy(part.date,part['return'],part.sigma_pct)
                for c in ('weight','cost_pct','strategy_cum','bh_cum'):
                    np.testing.assert_allclose(curve[c],rebuilt_curve[c],rtol=0,atol=1e-10)
            risk_frames.append(risk)
    allrisk=pd.concat(risk_frames,ignore_index=True)
    primary,available,coverage=comparison_tables(allrisk)
    saved=pd.read_csv(ROOT/'outputs/risk_holdout/backtest.csv')
    pd.testing.assert_frame_equal(primary,saved,check_dtype=False,atol=1e-12,rtol=1e-10)
    assert len(primary)==72 and len(list((ROOT/'outputs/holdout_figures/risk').glob('*.png')))==18
    manifest=json.loads((ROOT/'outputs/risk_holdout/run_manifest.json').read_text(encoding='utf-8'))
    assert manifest['holdout_evaluated'] and manifest['segment']=='holdout'
    check_frozen(manifest['input_sha256']);check_frozen(manifest['output_sha256']);check_frozen(manifest['risk_source_sha256'])
    check_frozen(plan['frozen_sha256'])
    result=dict(status='passed',start=plan['start'],end=plan['end'],forecast_files=18,
        forecast_rows=sum(len(f) for f in forecasts),risk_rows=len(allrisk),valid_risk_rows=int(allrisk.score_valid.sum()),
        common_risk_rows=int(allrisk.common_sample.sum()),risk_backtest_rows=len(primary),strategy_paths=36,
        future_residual_mutation_checks=future_checks,all_risk_values_recomputed=True,
        original_evaluation_unchanged=True,all_forecast_schedules_and_cutoffs_checked=True,
        plan_sha256=sha(PLAN),forecast_sha256=inputs)
    save(ROOT/'outputs/holdout_verification.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':verify()
