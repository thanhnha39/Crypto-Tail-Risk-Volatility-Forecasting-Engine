"""Loss cho dự báo RV (level, >0). Dùng chung cho mọi mô hình."""
import numpy as np
import pandas as pd


def _chk(y, f):
    y, f = np.asarray(y, float), np.asarray(f, float)
    if np.any(~np.isfinite(y)) or np.any(~np.isfinite(f)):
        raise ValueError("y/f chứa NaN hoặc inf")
    if np.any(f <= 0) or np.any(y <= 0):
        raise ValueError("RV và dự báo phải > 0 (QLIKE yêu cầu)")
    return y, f


def se_loss(y, f):
    y, f = np.asarray(y, float), np.asarray(f, float)
    return (y - f) ** 2


def ae_loss(y, f):
    y, f = np.asarray(y, float), np.asarray(f, float)
    return np.abs(y - f)


def qlike_loss(y, f):
    """QLIKE (Patton 2011): y/f - ln(y/f) - 1 >= 0, =0 khi f=y."""
    y, f = _chk(y, f)
    r = y / f
    return r - np.log(r) - 1


LOSSES = {"se": se_loss, "ae": ae_loss, "qlike": qlike_loss}


def add_losses(df: pd.DataFrame) -> pd.DataFrame:
    """df có y_true, y_pred -> thêm cột se, ae, qlike."""
    out = df.copy()
    for k, fn in LOSSES.items():
        out[k] = fn(out["y_true"].values, out["y_pred"].values)
    return out


def summarize(df: pd.DataFrame) -> pd.Series:
    """df đã có cột loss -> RMSE, MAE, QLIKE, n."""
    return pd.Series({"RMSE": float(np.sqrt(df["se"].mean())), "MAE": float(df["ae"].mean()),
                      "QLIKE": float(df["qlike"].mean()), "n": int(len(df))})
