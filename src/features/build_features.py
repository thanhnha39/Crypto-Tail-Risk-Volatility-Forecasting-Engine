"""Daily stats + macro -> bảng feature/target point-in-time cho 1 asset."""
import numpy as np
import pandas as pd

from src.features.intraday import daily_from_bars
from src.features.regimes import label_regimes
from src.features.schema import FEATURE_COLS, y_col, ylog_col


def macro_lagged(macro: pd.DataFrame, calendar: pd.DatetimeIndex, lag_days: int) -> pd.DataFrame:
    """macro: cột date, vix, usd (chỉ ngày giao dịch; có thể NaN ngày lễ).
    Dòng t nhận giá trị MỚI NHẤT có ngày <= t - lag_days (ffill chỉ lấy từ quá khứ)."""
    m = macro.set_index("date").sort_index()[["vix", "usd"]]
    m = m.reindex(m.index.union(calendar)).ffill().reindex(calendar)
    m = m.shift(lag_days)
    return pd.DataFrame({"log_vix_l1": np.log(m["vix"]), "log_usd_l1": np.log(m["usd"])})


def build_features(bars: pd.DataFrame, macro: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    d = daily_from_bars(bars, cfg["intraday"])
    fw, fm = cfg["features"]["har_windows"]["week"], cfg["features"]["har_windows"]["month"]
    tw = cfg["features"]["turnover_window"]

    f = pd.DataFrame(index=d.index)
    f["close"], f["n_ret"] = d["close"], d["n_ret"]
    f["rv_d"] = d["rv"]
    f["rv_w"] = d["rv"].rolling(fw, min_periods=fw).mean()       # trailing, gồm cả ngày t
    f["rv_m"] = d["rv"].rolling(fm, min_periods=fm).mean()
    for c in ("rv_d", "rv_w", "rv_m"):
        f["log_" + c] = np.log(f[c])
    f["park"] = d["park"]
    f["log_park"] = np.log(d["park"])
    f["ret_d"] = d["ret_d"]
    f["log_qv"] = np.log(d["qv"])
    f["log_turn_rel"] = np.log(d["qv"] / d["qv"].rolling(tw, min_periods=tw).mean())
    f = f.join(macro_lagged(macro, d.index, cfg["features"]["macro_lag_days"]))

    f["regime"] = label_regimes(d["close"], f["rv_m"], cfg["regimes"])

    # ---- targets: nhìn VỀ PHÍA TRƯỚC, chỉ dùng để làm nhãn, không bao giờ là feature ----
    for h in cfg["horizons"]:
        y = d["rv"].rolling(h, min_periods=h).mean().shift(-h)    # TB RV_{t+1..t+h}
        f[y_col(h)] = y
        f[ylog_col(h)] = np.log(y)
    f.index.name = "date"
    return f


def build_dataset(bars_by_asset: dict, macro: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    parts = []
    for asset, bars in bars_by_asset.items():
        f = build_features(bars, macro, cfg).reset_index()
        f.insert(0, "asset", asset)
        parts.append(f)
    ds = pd.concat(parts, ignore_index=True)
    front = ["asset", "date", "close", "n_ret", "regime"]
    rest = [c for c in ds.columns if c not in front]
    ds = ds[front + [c for c in FEATURE_COLS if c in rest] + [c for c in rest if c not in FEATURE_COLS]]
    return ds
