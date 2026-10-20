"""Regime point-in-time (ĐỀ XUẤT, mọi tham số nằm trong config.regimes -> nhóm cần chốt).

Tại ngày t, chỉ dùng thông tin tới hết ngày t:
  crisis : RV TB 22 ngày > phân vị `crisis_quantile` EXPANDING (tính trên lịch sử tới t) của chính nó
  bear   : return log `trend_window` ngày <= bear_threshold (%)   (nếu không crisis)
  bull   : return log `trend_window` ngày >= bull_threshold (%)   (nếu không crisis/bear)
  normal : còn lại.     'na' khi chưa đủ lịch sử.
"""
import numpy as np
import pandas as pd


def label_regimes(close: pd.Series, rv_m: pd.Series, cfg_reg: dict) -> pd.Series:
    thr = rv_m.expanding(min_periods=cfg_reg["min_history"]).quantile(cfg_reg["crisis_quantile"])
    ret_trend = 100 * np.log(close / close.shift(cfg_reg["trend_window"]))
    reg = pd.Series("normal", index=close.index, dtype=object)
    reg[ret_trend >= cfg_reg["bull_threshold"]] = "bull"
    reg[ret_trend <= cfg_reg["bear_threshold"]] = "bear"
    reg[rv_m > thr] = "crisis"
    reg[thr.isna() | ret_trend.isna() | rv_m.isna()] = "na"
    return reg
