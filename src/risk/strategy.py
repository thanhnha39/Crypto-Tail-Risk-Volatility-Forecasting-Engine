"""Optional RQ5: daily volatility targeting with costs and calendar preservation."""
from pathlib import Path
import numpy as np
import pandas as pd
from src.utils.config import ROOT
from src.utils.io import write_table

def _sharpe(daily_returns_pct,periods=365):
    r=np.asarray(daily_returns_pct,float)
    sd=r.std(ddof=1) if len(r)>1 else np.nan
    return float(np.sqrt(periods)*r.mean()/sd) if sd>0 else np.nan

def _max_drawdown(cumulative_pct):
    """Percentage wealth drawdown, including the initial wealth of one."""
    wealth=1+np.asarray(cumulative_pct,float)/100
    if not len(wealth):return np.nan
    peak=np.maximum.accumulate(np.r_[1.,wealth])[1:]
    return float(100*np.min(wealth/peak-1))

def run_strategy(dates,returns,sigma_forecast,vol_target_annual_pct=15.,max_leverage=1.,fee_bps=5.):
    """sigma dated t is known at start of target day t; returns are percent log returns.

    Fixed default parameters are illustrative, never optimized on test data.
    Missing forecast: keep existing holdings without trading. Missing return:
    raise rather than compress the calendar or invent zero P&L.
    Target weights apply after paying proportional one-way trading costs.
    Turnover is measured against the pre-trade weight after market drift.
    """
    d=pd.DatetimeIndex(pd.to_datetime(dates,utc=True));r=np.asarray(returns,float);sigma=np.asarray(sigma_forecast,float)
    if not len(r) or not (len(d)==len(r)==len(sigma)):raise ValueError('Nonempty aligned arrays required')
    if not d.is_monotonic_increasing or d.has_duplicates or (len(d)>1 and not (d[1:]-d[:-1]==pd.Timedelta(days=1)).all()):
        raise ValueError('Strategy requires a full consecutive daily calendar')
    if not np.isfinite(r).all():raise ValueError('Missing realized return: cannot compute a continuous wealth path')
    if vol_target_annual_pct<=0 or not 0<max_leverage<=1 or not 0<=fee_bps<10000:
        raise ValueError('Positive target, 0 < max_leverage <= 1 and 0 <= fee < 10000 bps required')
    simple=np.expm1(r/100);fee=fee_bps/10000;target=vol_target_annual_pct/np.sqrt(365)
    rows=[];drift_weight=0.;wealth=bhwealth=1.
    for i in range(len(r)):
        valid=np.isfinite(sigma[i]) and sigma[i]>0
        w=min(max_leverage,target/sigma[i]) if valid else drift_weight
        # Solve cost = fee * |w*(1-cost) - old_weight|, as fraction of pretrade NAV.
        delta=w-drift_weight
        cost=fee*delta/(1+fee*w) if delta>=0 else fee*(-delta)/(1-fee*w)
        net=(1-cost)*(1+w*simple[i])-1
        # Full initial allocation pays the same trade-value fee convention as w=1 above.
        bh=(1/(1+fee) if i==0 else 1.)*(1+simple[i])-1
        wealth*=1+net;bhwealth*=1+bh
        rows.append(dict(date=d[i],return_log_pct=r[i],sigma_pct=sigma[i],forecast_used=valid,
            missing_forecast_policy='hold_existing_position',pretrade_weight=drift_weight,weight=w,
            turnover=abs(w*(1-cost)-drift_weight),cost_pct=100*cost,
            strategy_return=100*net,bh_return=100*bh,
            strategy_cum=100*(wealth-1),bh_cum=100*(bhwealth-1)))
        drift_weight=w*(1+simple[i])/(1+w*simple[i])
    return pd.DataFrame(rows)

def _summarise(coin,model,window,vol_target,max_leverage,fee_bps,df):
    n=len(df);sr=df.strategy_return.to_numpy();bh=df.bh_return.to_numpy()
    return dict(coin=coin,model=model,window=window,vol_target_pct=vol_target,max_leverage=max_leverage,
        fee_bps=fee_bps,annualization_days=365,n_days=n,n_missing_forecast=int((~df.forecast_used).sum()),
        strategy_ann_return_pct=100*((1+df.strategy_cum.iloc[-1]/100)**(365/n)-1),
        bh_ann_return_pct=100*((1+df.bh_cum.iloc[-1]/100)**(365/n)-1),
        strategy_sharpe=_sharpe(sr),bh_sharpe=_sharpe(bh),
        strategy_max_drawdown_pct=_max_drawdown(df.strategy_cum),bh_max_drawdown_pct=_max_drawdown(df.bh_cum),
        mean_weight=float(df.weight.mean()),total_cost_pct_of_daily_nav=float(df.cost_pct.sum()))

def run_all_vol_targeting(vol_target_annual_pct=15.,max_leverage=1.,fee_bps=5.,root=None):
    dest=Path(root or ROOT);risk_dir=dest/'outputs/risk';summaries=[]
    for path in sorted(risk_dir.glob('*.parquet')):
        frame=pd.read_parquet(path)
        for window,part in frame.loc[frame.alpha.eq(.05)].groupby('window'):
            part=part.sort_values('date')
            # Original forecast sigma remains usable before FHS has 20 OOS errors.
            curve=run_strategy(part.date,part['return'].to_numpy(float),part.sigma_pct.to_numpy(float),
                vol_target_annual_pct,max_leverage,fee_bps)
            coin,model=str(part.coin.iloc[0]),str(part.model.iloc[0])
            for c in ('coin','model','window','dataset_sha256','protocol_sha256'):
                curve[c]=part[c].iloc[0] if c in part else str(window)
            write_table(curve,risk_dir/f'strategy_paths/{coin}_{model}_{window}.parquet')
            summaries.append(_summarise(coin,model,str(window),vol_target_annual_pct,max_leverage,fee_bps,curve))
    result=pd.DataFrame(summaries)
    if result.empty:raise ValueError('No corrected risk outputs found')
    result.to_csv(risk_dir/'volatility_targeting.csv',index=False)
    return result

if __name__=='__main__':run_all_vol_targeting()
