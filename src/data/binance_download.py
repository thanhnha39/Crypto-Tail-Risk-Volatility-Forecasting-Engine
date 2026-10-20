"""Tải dữ liệu thật (CHƯA kiểm thử trong sandbox vì không có mạng - hãy chạy thử 1 tháng trước).

  python -m src.data.binance_download klines --symbol BTCUSDT --start 2019-01 --end 2025-12
  python -m src.data.binance_download fred
Kết quả: data/raw/{SYMBOL}_5m.parquet  và  data/raw/macro.parquet

Lưu ý: dữ liệu spot trên data.binance.vision từ 2025-01-01 dùng timestamp micro-giây
(trước đó mili-giây) -> được chuẩn hoá bên dưới. Mọi timestamp là UTC, bar-open time.
"""
import argparse
import io
import urllib.request
import zipfile
import pandas as pd

from src.utils.config import ROOT
from src.utils.io import write_table

COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "n_trades", "taker_base", "taker_quote", "ignore"]
BASE = "https://data.binance.vision/data/spot/monthly/klines/{s}/{i}/{s}-{i}-{ym}.zip"


def _to_ts(s: pd.Series) -> pd.Series:
    unit = "us" if s.iloc[0] > 1e14 else "ms"
    return pd.to_datetime(s, unit=unit)


def download_klines(symbol, start, end, interval="5m"):
    frames = []
    for ym in pd.period_range(start, end, freq="M").astype(str):
        url = BASE.format(s=symbol, i=interval, ym=ym)
        try:
            raw = urllib.request.urlopen(url, timeout=60).read()
        except Exception as e:  # noqa: BLE001
            print("skip", ym, e)
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            df = pd.read_csv(z.open(z.namelist()[0]), header=None, names=COLS)
        if df["open_time"].iloc[0] == "open_time":      # một số file có header
            df = df.iloc[1:].astype(float)
        df["timestamp"] = _to_ts(df["open_time"].astype("int64"))
        frames.append(df[["timestamp", "open", "high", "low", "close", "volume", "quote_volume"]])
    out = pd.concat(frames).drop_duplicates("timestamp").sort_values("timestamp")
    return out.reset_index(drop=True)


def download_fred(series={"VIXCLS": "vix", "DTWEXBGS": "usd"}):
    out = None
    for sid, name in series.items():
        df = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
        df.columns = ["date", name]
        df["date"] = pd.to_datetime(df["date"])
        df[name] = pd.to_numeric(df[name], errors="coerce")
        out = df if out is None else out.merge(df, on="date", how="outer")
    return out.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("klines")
    k.add_argument("--symbol", required=True)
    k.add_argument("--start", required=True)
    k.add_argument("--end", required=True)
    sub.add_parser("fred")
    a = ap.parse_args()
    if a.cmd == "klines":
        print(write_table(download_klines(a.symbol, a.start, a.end), ROOT / f"data/raw/{a.symbol}_5m.parquet"))
    else:
        print(write_table(download_fred(), ROOT / "data/raw/macro.parquet"))
