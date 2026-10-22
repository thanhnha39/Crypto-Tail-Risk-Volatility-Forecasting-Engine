"""Point-in-time features and explicitly forward targets on a complete UTC daily grid."""
import numpy as np
import pandas as pd
from src.data.protocol import sample_segments
from src.features.regimes import label_regimes
from src.features.schema import y_col, ylog_col

def safe_log(values):
    return np.log(values.where(values.gt(0)))

def build_features(daily, config):
    d=daily.copy().sort_values("date").reset_index(drop=True)
    d["date"]=pd.to_datetime(d["date"],utc=True)
    if d["date"].duplicated().any() or not d["date"].diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError("Daily input must retain a unique, complete UTC calendar")
    d["sample_segment"]=sample_segments(d["date"],config["data"])
    if d.loc[~d["eligible_rv"],"rv_reference_pct2"].notna().any(): raise ValueError("Ineligible RV must be missing")
    f=pd.DataFrame({"symbol":d["symbol"],"origin_date":d["date"],"origin_segment":d["sample_segment"],
        "feature_available_at":d["date"]+pd.Timedelta(days=1),"close":d["close"],
        "n_ret":d["valid_adjacent_returns"],"eligible_rv":d["eligible_rv"]})
    options=config["backend1"]["features"]
    f["rv_d"]=d["rv_reference_pct2"]
    f["rv_w"]=f["rv_d"].rolling(options["har_week_days"],min_periods=options["har_week_days"]).mean()
    f["rv_m"]=f["rv_d"].rolling(options["har_month_days"],min_periods=options["har_month_days"]).mean()
    for col in ["rv_d","rv_w","rv_m"]: f["log_"+col]=safe_log(f[col])
    full=d["valid_bars"].eq(config["data"]["expected_bars_per_day"])
    f["park"]=((100*np.log(d["high"]/d["low"]))**2/(4*np.log(2))).where(full)
    f["log_park"]=safe_log(f["park"])
    f["ret_d"]=d["return_daily_pct_qa"]
    qv=d["quote_volume"].where(full)
    f["log_qv"]=safe_log(qv)
    n=options["relative_volume_days"]
    f["log_turn_rel"]=safe_log(qv/qv.rolling(n,min_periods=n).mean())
    f["regime"],f["regime_rv22_pct2"],f["ret_90d_pct"],threshold=label_regimes(d,config)
    for h in [config["study"]["main_horizon_days"],*config["study"]["sensitivity_horizon_days"]]:
        f[y_col(h)]=f["rv_d"].rolling(h,min_periods=h).sum().shift(-h)
        f[ylog_col(h)]=safe_log(f[y_col(h)])
        start=d["date"]+pd.Timedelta(days=1);end=d["date"]+pd.Timedelta(days=h)
        f[f"target_start_h{h}"]=start;f[f"target_end_h{h}"]=end
        # Do not pass out-of-design future dates into the period label function.
        limit=pd.Timestamp(config["data"]["holdout_end"],tz="UTC")
        start_segment=sample_segments(start.clip(upper=limit),config["data"])
        end_segment=sample_segments(end.clip(upper=limit),config["data"])
        segment=np.where(start_segment==end_segment,end_segment,"cross_segment")
        f[f"target_segment_h{h}"]=np.where(end.le(limit),segment,"out_of_scope")
        f[f"target_valid_h{h}"]=f[y_col(h)].notna()
    return f,threshold
