"""Diebold-Mariano (1995) với hiệu chỉnh Harvey-Leybourne-Newbold (1997).

d_t = L_A,t - L_B,t.  H0: E[d_t] = 0.   stat < 0  => mô hình A có loss thấp hơn (A tốt hơn B).
Phương sai dài hạn dùng autocovariance tới lag h-1 (dự báo h bước => d_t tự tương quan MA(h-1)).
HLN: nhân sqrt((n + 1 - 2h + h(h-1)/n) / n) và so với t(n-1).
"""
import numpy as np
from scipy import stats


def dm_test(loss_a, loss_b, h=1, hln=True):
    a, b = np.asarray(loss_a, float), np.asarray(loss_b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    d = (a - b)[ok]
    n = len(d)
    res = {"n": n, "mean_diff": float(d.mean()) if n else np.nan, "stat": np.nan, "p_value": np.nan}
    if n < max(10, 2 * h):
        return res
    dbar = d.mean()
    dc = d - dbar
    lrv = float(np.dot(dc, dc) / n)
    for k in range(1, h):
        lrv += 2 * float(np.dot(dc[k:], dc[:-k]) / n)
    if not np.isfinite(lrv) or lrv <= 1e-18:     # forecast trùng nhau hoặc lrv âm (mẫu nhỏ)
        return res
    stat = dbar / np.sqrt(lrv / n)
    if hln:
        stat *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
        p = 2 * stats.t.sf(abs(stat), df=n - 1)
    else:
        p = 2 * stats.norm.sf(abs(stat))
    res.update(stat=float(stat), p_value=float(p))
    return res


def stars(p):
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
