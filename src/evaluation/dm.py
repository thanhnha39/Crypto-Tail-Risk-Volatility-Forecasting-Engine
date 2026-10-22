"""HLN-corrected DM with Bartlett HAC over actual calendar lags (do not compress gaps)."""
import numpy as np
import pandas as pd
from scipy import stats

def dm_test(loss_a,loss_b,h=1,hln=True,dates=None,min_n=30):
    if h not in [1,7]: raise ValueError("Supported forecast horizons are 1 and 7 days")
    a,b=np.asarray(loss_a,float),np.asarray(loss_b,float)
    if a.shape!=b.shape: raise ValueError("Paired losses required")
    index=pd.DatetimeIndex(pd.to_datetime(dates,utc=True)) if dates is not None else pd.date_range("2000-01-01",periods=len(a),tz="UTC")
    if index.has_duplicates: raise ValueError("Duplicate DM dates")
    series=pd.Series(a-b,index=index).replace([np.inf,-np.inf],np.nan).sort_index()
    n=int(series.notna().sum())
    result={"n":n,"mean_diff":float(series.mean()),"stat":np.nan,"p_value":np.nan,"status":"insufficient_n"}
    if n<max(min_n,2*h): return result
    series=series.reindex(pd.date_range(series.index.min(),series.index.max(),tz="UTC",freq="D"))
    centered=series-series.mean()
    lrv=float(centered.pow(2).sum()/n)
    for lag in range(1,h):
        covariance=float((centered*centered.shift(lag)).sum()/n)
        lrv+=2*(1-lag/h)*covariance
    if not np.isfinite(lrv) or lrv<=1e-18: result["status"]="degenerate_loss_difference";return result
    statistic=float(series.mean()/np.sqrt(lrv/n))
    if hln:
        statistic*=np.sqrt((n+1-2*h+h*(h-1)/n)/n)
        p=2*stats.t.sf(abs(statistic),df=n-1)
    else: p=2*stats.norm.sf(abs(statistic))
    result.update(stat=float(statistic),p_value=float(p),status="ok")
    return result

def stars(p):
    return "" if not np.isfinite(p) else "***" if p<.01 else "**" if p<.05 else "*" if p<.1 else ""
