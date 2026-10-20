"""Bar 5 phút (UTC, bar-open time) -> thống kê ngày. Không backfill, không nội suy."""
import numpy as np
import pandas as pd


def daily_from_bars(bars: pd.DataFrame, cfg_intraday: dict) -> pd.DataFrame:
    """bars: cột timestamp, open, high, low, close, volume, quote_volume.
    Trả về DataFrame index = ngày UTC (liên tục, ngày thiếu = NaN)."""
    bpd = cfg_intraday["bars_per_day"]
    cov_min = cfg_intraday["min_bar_coverage"]
    b = bars.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")

    first_day = b.index[0].normalize()
    last_day = b.index[-1].normalize()
    grid = pd.date_range(first_day, last_day + pd.Timedelta(days=1) - pd.Timedelta(minutes=cfg_intraday["bar_minutes"]),
                         freq=f"{cfg_intraday['bar_minutes']}min")
    close = b["close"].reindex(grid)

    # log return 5 phút (%). Bar thiếu -> return thiếu (cả bar đó và bar kế tiếp), KHÔNG nối qua khoảng trống.
    r5_raw = 100 * np.log(close).diff()
    bad_into = (r5_raw.abs() > cfg_intraday["max_abs_r5"]).reindex(b.index, fill_value=False)
    r5 = r5_raw.where(r5_raw.abs() <= cfg_intraday["max_abs_r5"])   # bad tick -> bỏ return
    day = grid.normalize()

    n_ret = r5.notna().groupby(day).sum()
    rv_raw = (r5 ** 2).groupby(day).sum()
    cov = n_ret / bpd
    rv = rv_raw * (bpd / n_ret.where(n_ret > 0)) if cfg_intraday["scale_for_missing"] else rv_raw
    rv = rv.where(cov >= cov_min)

    cnt = b["close"].resample("1D").count().reindex(n_ret.index, fill_value=0)
    ok = (cnt / bpd) >= cov_min
    # bar có bước nhảy > max_abs_r5 so với bar trước bị loại khỏi High/Low (tránh bad tick làm hỏng Parkinson)
    b = b.copy()
    b.loc[bad_into.values, ["high", "low"]] = np.nan
    agg = b.resample("1D").agg({"high": "max", "low": "min", "volume": "sum", "quote_volume": "sum"})
    agg = agg.reindex(n_ret.index)
    agg = agg.where(ok, np.nan)
    park = (100 * np.log(agg["high"] / agg["low"])) ** 2 / (4 * np.log(2))

    close_last = close.groupby(day).last()                           # last valid close của ngày
    out = pd.DataFrame({
        "close": close_last, "n_ret": n_ret.astype(int), "rv": rv,
        "park": park, "qv": agg["quote_volume"],
    })
    out.index.name = "date"
    out["ret_d"] = 100 * np.log(out["close"]).diff()                 # cần calendar liên tục (đã đảm bảo)
    return out
