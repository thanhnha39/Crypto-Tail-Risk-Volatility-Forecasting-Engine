"""Point-in-time one-day tail-risk forecasts, shared-sample backtests and RQ5."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.risk.metrics import christoffersen_test, expected_shortfall, kupiec_test, quantile_loss, value_at_risk
from src.utils.config import ROOT, protocol_hash
from src.utils.io import write_table
from src.evaluation.validate import validate_forecasts

ALPHAS = (.05, .01)
MIN_FHS_HISTORY = 20  # Retained from the submitted specification; never tuned on evaluation.
MODELS = ('har_rv','garch','gjr_garch','xgboost','enet','naive_rw','hist_mean','combo_econ','combo_core4')
CRISES = {'covid_crash_2020':('2020-03-12','2020-03-16'),
          'may_2021_selloff':('2021-05-01','2021-05-31'),
          'luna_collapse_2022':('2022-05-07','2022-05-13'),
          'ftx_collapse_2022':('2022-11-06','2022-11-14')}

def _utc(values):
    # Explicit resolution: Parquet may store microseconds, Timestamp.value uses ns.
    return pd.to_datetime(values, utc=True, errors='raise').astype('datetime64[ns, UTC]')

def build_residuals(fc):
    """Own-model OOS errors, with explicit time when the target return is known."""
    valid = fc.status.eq('ok') & np.isfinite(fc.realized_return_pct) & fc.volatility_forecast_pct.gt(0)
    r = fc.loc[valid, ['symbol','model','window','origin_date','target_date',
                      'forecast_available_at','realized_return_pct','volatility_forecast_pct','mean_forecast_pct']].copy()
    r['observable_at'] = _utc(r.target_date) + pd.Timedelta(days=1)
    r['standardized_residual'] = (r.realized_return_pct-r.mean_forecast_pct)/r.volatility_forecast_pct
    return r

def _risk_rows(fc, residuals):
    """Keep every scheduled row, including explicitly unavailable forecasts."""
    fc = fc.copy()
    for c in ('origin_date','target_date','forecast_available_at'):
        fc[c] = _utc(fc[c])
    model, symbol = str(fc.model.iloc[0]), str(fc.symbol.iloc[0])
    method = 'student_t' if model in {'garch','gjr_garch'} else 'fhs'
    pools = {}
    if method == 'fhs' and not residuals.empty:
        r = residuals.loc[residuals.symbol.eq(symbol)&residuals.model.eq(model)].copy()
        for c in ('target_date','observable_at'):
            r[c] = _utc(r[c])
        if (r.observable_at < r.target_date+pd.Timedelta(days=1)).any():
            raise ValueError('Residual observable_at precedes completion of its target')
        if r.duplicated(['symbol','model','window','target_date']).any():
            raise ValueError('Duplicate residual keys')
        for window, part in r.groupby('window'):
            part = part.loc[np.isfinite(part.standardized_residual)].sort_values('observable_at')
            pools[window] = part
    out = []
    for row in fc.itertuples(index=False):
        sigma = np.sqrt(row.rv_forecast_pct2) if np.isfinite(row.rv_forecast_pct2) and row.rv_forecast_pct2>0 else np.nan
        mean = float(getattr(row,'mean_forecast_pct',0.))
        nu = float(getattr(row,'nu',np.nan))
        status = 'ok' if row.status=='ok' and np.isfinite(sigma) and np.isfinite(mean) else 'source_forecast_unavailable'
        z = None; count = 0; last_seen = pd.NaT; last_target = pd.NaT
        if status == 'ok' and method == 'fhs':
            pool = pools.get(row.window, pd.DataFrame())
            if len(pool):
                # Compare UTC datetime values, never mixed integer timestamp units.
                past = pool.loc[pool.observable_at.le(row.forecast_available_at) & pool.target_date.lt(row.target_date)]
                z = past.standardized_residual.to_numpy(float)
                count = len(z)
                if count:
                    last_seen, last_target = past.observable_at.max(), past.target_date.max()
            if count < MIN_FHS_HISTORY:
                status = 'insufficient_fhs_history'
        if status == 'ok' and method=='student_t' and (not np.isfinite(nu) or nu<=2):
            status = 'invalid_student_t_parameters'
        for alpha in ALPHAS:
            var = es = np.nan; tail_count = np.nan
            if status == 'ok':
                var = float(value_at_risk(mean,sigma,alpha,method,nu=nu,residuals=z))
                es = float(expected_shortfall(mean,sigma,alpha,method,nu=nu,residuals=z))
                if z is not None:
                    tail_count = int((z<=np.quantile(z,alpha)).sum())
            record = dict(date=row.target_date,coin=symbol,model=model,window=row.window,alpha=alpha,
                confidence=1-alpha,method=method,var=var,es=es,status=status,origin_date=row.origin_date,
                forecast_available_at=row.forecast_available_at,horizon_days=1,
                sigma_pct=sigma,variance_pct2=row.rv_forecast_pct2,mean_forecast_pct=mean,nu=nu,
                n_fhs_residuals=count if method=='fhs' else np.nan,n_fhs_tail=tail_count,
                last_residual_observable_at=last_seen,last_residual_target_date=last_target)
            for c in ('dataset_sha256','protocol_sha256','selection_sha256','config_sha256','refit_origin'):
                if hasattr(row,c): record[c] = getattr(row,c)
            out.append(record)
    return pd.DataFrame(out)

def comparison_tables(risks, models=MODELS):
    """Primary comparisons use an identical set of valid dates for every model."""
    common = pd.Series(False,index=risks.index)
    coverage=[]
    for (coin,window,alpha), group in risks.groupby(['coin','window','alpha']):
        sets = [set(group.loc[group.model.eq(m)&group.score_valid,'date']) for m in models]
        shared = set.intersection(*sets) if sets else set()
        common.loc[group.index] = group.date.isin(shared)
        for model, part in group.groupby('model'):
            coverage.append(dict(coin=coin,window=window,alpha=alpha,model=model,
                n_scheduled=len(part),n_available=int(part.score_valid.sum()),n_common=len(shared),
                first_available=str(part.loc[part.score_valid,'date'].min()),
                last_available=str(part.loc[part.score_valid,'date'].max()),
                status_counts=json.dumps(part.status.value_counts().to_dict(),sort_keys=True)))
    risks['common_sample'] = common
    def summarize(frame, sample):
        rows=[]
        for key, group in risks.groupby(['coin','model','window','alpha','method']):
            selected=frame.loc[frame.index.isin(group.index)].sort_values('date')
            b=selected.breach.to_numpy(float).astype(bool)
            uc=kupiec_test(b,key[3]);cc=christoffersen_test(b,key[3],dates=selected.date)
            rows.append(dict(zip(['coin','model','window','alpha','method'],key),sample=sample,
                n=len(selected),n_breach=uc['n_breach'],breach_rate=uc['breach_rate'],
                kupiec_p=uc['p_value'],christoffersen_p=cc['p_value'],
                independence_p=cc['p_independence'],cc_status=cc['status'],
                n_adjacent_pairs=cc['n_adjacent_pairs'],n_gaps=cc['n_gaps'],
                quantile_loss=float(quantile_loss(selected['return'],selected['var'],key[3]).mean()) if len(selected) else np.nan,
                observed_es_pct=float(selected.loc[selected.breach.eq(1),'return'].mean()),
                mean_es_on_breach_pct=float(selected.loc[selected.breach.eq(1),'es'].mean())))
        return pd.DataFrame(rows)
    return summarize(risks.loc[common],'common_all_9_models'),summarize(risks.loc[risks.score_valid],'available_per_model'),pd.DataFrame(coverage)

def _plot(group,path,coin,model):
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for ax,alpha in zip(axes,ALPHAS):
        part=group.loc[group.window.eq('rolling')&group.alpha.eq(alpha)].sort_values('date')
        ax.plot(part.date,part['return'],color='#52616b',lw=.55,label='Return')
        ax.plot(part.date,part['var'],color='#d1495b',lw=.7,label=f'VaR {1-alpha:.0%}')
        ax.plot(part.date,part.es,color='#4257a5',lw=.6,alpha=.7,label='ES')
        b=part.breach.eq(1)
        ax.scatter(part.loc[b,'date'],part.loc[b,'return'],s=9,color='#ef912c',label='Breach',zorder=3)
        ax.set_ylabel('Log return (%)');ax.grid(alpha=.2);ax.legend(ncol=4,frameon=False)
    fig.suptitle(f'{coin} | {model} | rolling | h=1 | 2021–2025')
    fig.tight_layout();path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path,dpi=140);plt.close(fig)

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(input_root=None,output_root=None,with_strategy=True):
    source=Path(input_root or ROOT).resolve();dest=Path(output_root or source).resolve()
    cfg=tomllib.loads((source/'config/data.toml').read_text(encoding='utf-8'))
    cfg['backend1']=tomllib.loads((source/'config/backend1.toml').read_text(encoding='utf-8'))
    dataset_path=source/'data/processed/dataset.parquet';dataset=pd.read_parquet(dataset_path)
    digest=_sha(dataset_path);meta=json.loads((source/'data/processed/dataset_meta.json').read_text(encoding='utf-8'))
    if meta['dataset_sha256']!=digest or meta['protocol_sha256']!=protocol_hash(cfg):
        raise ValueError('Dataset/protocol provenance mismatch; rebuild upstream outputs first')
    start=pd.Timestamp(cfg['data']['evaluation_start'],tz='UTC');end=pd.Timestamp(cfg['data']['research_end'],tz='UTC')
    truth=dataset[['symbol','origin_date','ret_d']].rename(columns={'origin_date':'target_date','ret_d':'realized_return_pct'})
    truth['target_date']=_utc(truth.target_date)
    parts=[];inputs={'data/processed/dataset.parquet':digest}
    for coin in cfg['data']['symbols']:
        for model in MODELS:
            rel=f'outputs/forecasts/{coin}_{model}.parquet';path=source/rel
            if not path.exists():raise ValueError(f'Required upstream forecasts missing: {path}')
            fc=pd.read_parquet(path)
            errors=validate_forecasts(fc,dataset,cfg,digest,rel)
            if errors:raise ValueError('\n'.join(errors))
            if set(fc.symbol)!={coin} or set(fc.model)!={model}:raise ValueError(f'Wrong file identity: {rel}')
            for c in ('origin_date','target_date','forecast_available_at'):fc[c]=_utc(fc[c])
            # Exclude final holdout before building any residuals or risk forecasts.
            fc=fc.loc[fc.horizon_days.eq(1)&fc.target_date.between(start,end)].copy()
            if 'mean_forecast_pct' not in fc:fc['mean_forecast_pct']=0.
            # Unavailable forecasts may have missing means. Successful ones may not.
            if (~np.isfinite(fc.loc[fc.status.eq('ok'),'mean_forecast_pct'])).any():raise ValueError(f'Invalid forecast mean: {rel}')
            expected=pd.date_range(start,end,freq='D')
            for window in ('rolling','expanding'):
                if set(fc.loc[fc.window.eq(window),'target_date'])!=set(expected):raise ValueError(f'Incomplete forecast calendar: {rel} {window}')
            fc=fc.merge(truth,on=['symbol','target_date'],how='left',validate='many_to_one')
            residuals=build_residuals(fc)
            risk=_risk_rows(fc,residuals)
            actual=truth.rename(columns={'symbol':'coin','target_date':'date','realized_return_pct':'return'})
            risk=risk.merge(actual,on=['coin','date'],how='left',validate='many_to_one')
            risk['score_valid']=risk.status.eq('ok')&np.isfinite(risk['return'])
            risk['breach']=np.where(risk.score_valid,(risk['return']<risk['var']).astype(float),np.nan)
            parts.append(risk);inputs[rel]=_sha(path)
            print(f'[risk] {coin} {model}: {int(risk.score_valid.sum())}/{len(risk)} scored rows',flush=True)
    risks=pd.concat(parts,ignore_index=True)
    primary,available,coverage=comparison_tables(risks)
    out=dest/'outputs/risk';out.mkdir(parents=True,exist_ok=True)
    for (coin,model),group in risks.groupby(['coin','model']):
        write_table(group.sort_values(['date','window','alpha']),out/f'{coin}_{model}.parquet')
        _plot(group,dest/f'outputs/figures/risk/{coin}_{model}_var_breaches.png',coin,model)
    primary.to_csv(out/'backtest.csv',index=False)
    available.to_csv(out/'backtest_available_sample.csv',index=False)
    coverage.to_csv(out/'coverage.csv',index=False)
    crises=[]
    for name,(lo,hi) in CRISES.items():
        lower,upper=pd.Timestamp(lo,tz='UTC'),pd.Timestamp(hi,tz='UTC')
        for key,group in risks.groupby(['coin','model','window','alpha','method']):
            for sample,mask in [('common_all_9_models',group.common_sample),('available_per_model',group.score_valid)]:
                part=group.loc[mask&group.date.between(lower,upper)]
                status='outside_evaluation' if upper<start or lower>end else ('ok' if len(part) else 'no_valid_forecasts')
                crises.append(dict(zip(['coin','model','window','alpha','method'],key),crisis=name,start=lo,end=hi,
                    sample=sample,status=status,n=len(part),n_breach=int(part.breach.sum()) if len(part) else np.nan,
                    breach_rate=float(part.breach.mean()) if len(part) else np.nan,
                    quantile_loss=float(quantile_loss(part['return'],part['var'],key[3]).mean()) if len(part) else np.nan))
    pd.DataFrame(crises).to_csv(out/'crisis_breaches.csv',index=False)
    from src.risk.simulation import check_simulation
    pd.DataFrame(check_simulation()).to_csv(out/'simulation_checks.csv',index=False)
    if with_strategy:
        from src.risk.strategy import run_all_vol_targeting
        run_all_vol_targeting(root=dest)
    manifest=dict(schema_version=2,evaluation_start=str(start),evaluation_end=str(end),holdout_evaluated=False,
        input_root=str(source),models=list(MODELS),risk_rows=len(risks),valid_rows=int(risks.score_valid.sum()),
        common_rows=int(risks.common_sample.sum()),fhs_min_history=MIN_FHS_HISTORY,
        fhs_history='expanding own-model one-day OOS residuals, observable_at <= forecast_available_at',
        protocol_sha256=protocol_hash(cfg),dataset_sha256=digest,input_sha256=inputs,
        limitations=['Early FHS history can have only one 1% tail observation; see n_fhs_tail.',
          'Christoffersen uses adjacent calendar-day pairs only; gapped sample p-values are asymptotic diagnostics.',
          'Kupiec/Christoffersen assess VaR coverage, not a formal ES calibration test.',
          'Strategy is a frictional simulation at daily close, zero cash yield and 365-day annualization.'])
    manifest['risk_source_sha256']={f'src/risk/{p.name}':_sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    manifest['strategy_parameters']=dict(vol_target_annual_pct=15.,max_leverage=1.,fee_bps=5.,annualization_days=365,
        cost_convention='one-way fee on traded value; exact self-financing initial allocation for both strategies') if with_strategy else None
    manifest['output_sha256']={p.relative_to(dest).as_posix():_sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('run_manifest.json','verification.json','README.md')}
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'README.md').write_text('''# Backend 4 risk outputs (corrected)

`{coin}_{model}.parquet`: all scheduled 2021–2025 h=1 dates, two windows,
alpha .05/.01 (95%/99%). Returns/VaR/ES/sigma in percent; variance in %².
`status` and `score_valid` distinguish missing predictions from zero breaches.
`common_sample` identifies common valid dates across all 9 models per coin/window/alpha.

- backtest.csv: primary common-sample VaR backtests and quantile loss.
- backtest_available_sample.csv: each model's own available sample; not a fair ranking.
- coverage.csv: counts, first/last valid dates, unavailable reasons.
- crisis_breaches.csv: common and available samples; COVID 2020 explicitly outside evaluation.
- simulation_checks.csv: six deterministic checks with known simulated tail rates.
- volatility_targeting.csv and strategy_paths/: optional RQ5 with original sigma and costs.
- run_manifest.json: source/output checksums, protocol and method limitations.

FHS uses own-model OOS residuals only after the return is observable. Minimum
20 past residuals is fixed, not selected on evaluation. The early 99% empirical
tail is sparse; inspect n_fhs_tail. No 2026 final holdout is evaluated.
Christoffersen never joins across missing days; gapped-sample p-values are
asymptotic diagnostics. These tests validate VaR coverage, not ES calibration.
''',encoding='utf-8')
    return risks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root',type=Path);p.add_argument('--output-root',type=Path)
    p.add_argument('--skip-strategy',action='store_true')
    a=p.parse_args();run(a.input_root,a.output_root,not a.skip_strategy)

if __name__=='__main__':main()
