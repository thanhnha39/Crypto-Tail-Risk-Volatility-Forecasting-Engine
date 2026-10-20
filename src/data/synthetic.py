"""Dữ liệu mô phỏng 5 phút + macro, để kiểm thử pipeline khi chưa có dữ liệu Binance thật.

DGP: log-vol ngày = tổng 2 thành phần AR(1) (bộ nhớ ngắn + dài, kiểu HAR) + cú sốc crisis;
drift chậm (tạo bull/bear); return 5' ~ Student-t(5) nhân U-shape intraday.
Có chủ ý chèn: bar bị thiếu ngẫu nhiên, 1 ngày mất hẳn, 1 khoảng 6 giờ mất, 1 bad tick.
KHÔNG dùng kết quả trên dữ liệu này để kết luận gì về thị trường thật.
"""
import numpy as np
import pandas as pd

BPD = 288


def _ar1(n, phi, sd_innov, rng):
    x = np.zeros(n)
    e = rng.normal(0, sd_innov, n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


def simulate_asset(start, end, seed, base_vol=3.0, p0=10000.0, vol0=3e4,
                   missing_frac=0.002, inject_defects=True):
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    n = len(days)
    jumps = (rng.random(n) < 0.004) * rng.exponential(0.8, n)
    shock = np.zeros(n)
    for t in range(1, n):
        shock[t] = 0.9 * shock[t - 1] + jumps[t]
    x = _ar1(n, 0.55, 0.20, rng) + _ar1(n, 0.985, 0.075, rng) + shock
    sigma_d = base_vol * np.exp(x - 0.5)                       # % / ngày
    drift = _ar1(n, 0.995, 0.012, rng)                         # % / ngày, chậm

    j = np.arange(BPD)
    w = 1 + 0.4 * np.cos(2 * np.pi * (j / BPD - 0.6))
    w = w / w.sum()
    z = rng.standard_t(5, size=(n, BPD)) / np.sqrt(5 / 3)
    r = drift[:, None] / BPD + sigma_d[:, None] * np.sqrt(w)[None, :] * z    # %
    logp = np.log(p0) + np.cumsum(r.ravel()) / 100
    close = np.exp(logp)
    open_ = np.concatenate([[p0], close[:-1]])
    sig_bar = (sigma_d[:, None] * np.sqrt(w)[None, :]).ravel()
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.5 * sig_bar / 100)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.5 * sig_bar / 100)))
    vol = vol0 * np.exp(0.6 * (x - 0.5))[:, None] * (w * BPD)[None, :] * rng.lognormal(0, 0.3, (n, BPD))
    vol = vol.ravel()

    ts = pd.date_range(days[0], periods=n * BPD, freq="5min")
    bars = pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": vol, "quote_volume": vol * close})
    if inject_defects:
        keep = rng.random(len(bars)) > missing_frac
        if n > 400:
            d_gap = 300 * BPD
            keep[d_gap:d_gap + BPD] = False                    # mất cả 1 ngày
            keep[(350 * BPD + 60):(350 * BPD + 132)] = False   # mất 6 giờ
            k = 200 * BPD + 100                                # bad tick
            bars.loc[k, ["close", "high"]] = bars.loc[k, "close"] * 1.5
        bars = bars[keep].reset_index(drop=True)
    return bars, x


def simulate_macro(days, btc_logvol, seed):
    """VIX/USD chỉ có ngày làm việc (T2-T6) -> kiểm thử logic ffill + lag."""
    rng = np.random.default_rng(seed)
    n = len(days)
    sm = pd.Series(btc_logvol).rolling(10, min_periods=1).mean().values
    logvix = np.log(18) + 0.35 * sm + _ar1(n, 0.9, 0.04, rng)
    usd = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    m = pd.DataFrame({"date": days, "vix": np.exp(logvix), "usd": usd})
    return m[m["date"].dt.dayofweek < 5].reset_index(drop=True)


def simulate_universe(assets, start="2019-01-01", end="2025-12-31", seed=42):
    bars, xs = {}, []
    for i, a in enumerate(assets):
        b, x = simulate_asset(start, end, seed + i, base_vol=3.0 if i == 0 else 3.8,
                              p0=10000.0 / (1 + 5 * i), vol0=3e4 * (1 + 20 * i))
        bars[a] = b
        xs.append(x)
    days = pd.date_range(start, end, freq="D")
    macro = simulate_macro(days, np.mean(xs, axis=0), seed + 99)
    return bars, macro


if __name__ == "__main__":
    import argparse
    from src.utils.config import load_config, ROOT
    from src.utils.io import write_table
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2025-12-31")
    a = ap.parse_args()
    cfg = load_config()
    bars, macro = simulate_universe(cfg["assets"], a.start, a.end)
    for k, b in bars.items():
        print("wrote", write_table(b, ROOT / "data/raw" / f"{k}_5m.parquet"), len(b))
    print("wrote", write_table(macro, ROOT / "data/raw/macro.parquet"))
