"""Common variance metrics; target/prediction units are percent squared."""
import numpy as np
import pandas as pd

def qlike_loss(y,f):
    y,f=np.asarray(y,float),np.asarray(f,float)
    if not np.isfinite(y).all() or not np.isfinite(f).all() or (y<=0).any() or (f<=0).any():
        raise ValueError("Normalized QLIKE requires positive finite truth and forecast")
    ratio=y/f
    return ratio-np.log(ratio)-1

def add_losses(frame):
    out=frame.copy();out["se"]=(out["y_true"]-out["rv_forecast_pct2"])**2
    out["ae"]=(out["y_true"]-out["rv_forecast_pct2"]).abs()
    out["qlike"]=qlike_loss(out["y_true"],out["rv_forecast_pct2"])
    return out

def summarize(frame):
    return pd.Series({"RMSE":float(np.sqrt(frame["se"].mean())),"MAE":float(frame["ae"].mean()),
        "QLIKE":float(frame["qlike"].mean()),"n":int(len(frame))})
