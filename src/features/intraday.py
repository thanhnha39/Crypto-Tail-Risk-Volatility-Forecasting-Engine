"""Recompute strict daily QA from clean bars for verification and leakage tests."""
import numpy as np
import pandas as pd
from src.data.clean import daily_quality, reference_daily

def daily_from_bars(bars, settings):
    b=bars.copy().sort_values("open_time").reset_index(drop=True)
    b["open_time"]=pd.to_datetime(b["open_time"],utc=True)
    if b["open_time"].duplicated().any(): raise ValueError("Duplicate clean bar")
    adjacent=b["open_time"].diff().eq(pd.Timedelta(minutes=5))
    b["return_5m_pct_qa"]=(100*np.log(b["close"]/b["close"].shift(1))).where(adjacent)
    b["zero_volume"]=b["volume"].eq(0)
    b["large_return_review"]=b["return_5m_pct_qa"].abs().gt(settings["large_return_review_threshold_pct"])
    start=b["open_time"].min().floor("D");end=b["open_time"].max().floor("D")
    quality=daily_quality(b,b,start,end,settings)
    return reference_daily(b,quality)
