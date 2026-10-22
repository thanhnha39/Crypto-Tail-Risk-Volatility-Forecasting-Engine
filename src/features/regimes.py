"""Fixed warmup calibration; evaluation regime uses information through the origin only."""
import numpy as np
import pandas as pd

def label_regimes(daily, config):
    r=config["study"]["regime"]
    rv=daily["rv_reference_pct2"]
    mean=rv.rolling(r["rv_average_days"],min_periods=r["rv_average_min_valid_days"]).mean()
    warm=daily["sample_segment"].eq("warmup")
    calibration=mean.loc[warm].dropna()
    if calibration.empty: raise ValueError("No complete warmup observations for crisis threshold")
    threshold=float(calibration.quantile(r["crisis_quantile"],interpolation="linear"))
    trend=100*np.log(daily["close"]/daily["close"].shift(r["log_return_days"]))
    labels=pd.Series(r["missing_history_label"],index=daily.index,dtype="str")
    ready=(mean.notna() & trend.notna() & daily["date"].ge(pd.Timestamp(config["data"]["warmup_end"],tz="UTC")))
    labels.loc[ready]="normal"
    labels.loc[ready & trend.ge(r["bull_threshold_pct"]) ]="bull"
    labels.loc[ready & trend.le(r["bear_threshold_pct"]) ]="bear"
    labels.loc[ready & mean.gt(threshold)]="crisis"
    return labels, mean, trend, {"symbol":str(daily["symbol"].iloc[0]),"crisis_threshold_pct2":threshold,
        "quantile":r["crisis_quantile"],"quantile_interpolation":"linear","calibration_start":config["data"]["research_start"],
        "calibration_end":config["data"]["warmup_end"],"n_calibration":len(calibration),"frozen":True}
