"""Corroborate source gaps and flagged bars using additional source archives."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import zipfile

import numpy as np
import pandas as pd

from .download import ROOT, fetch_archive, save_json, now
from .clean import COLS, normalize_timestamps


def task(symbol, interval, period, purpose):
    filename = f"{symbol}-{interval}-{period}.zip"
    frequency = "monthly" if len(period) == 7 else "daily"
    return {"dataset_id": f"audit_{symbol}_{interval}_{period}", "symbol": symbol,
            "interval": interval, "period": period, "purpose": purpose, "frequency": frequency,
            "path": f"data/raw/audit/{symbol}/{filename}",
            "url": f"https://data.binance.vision/data/spot/{frequency}/klines/{symbol}/{interval}/{filename}"}


def read(record):
    with zipfile.ZipFile(ROOT / record["path"]) as archive:
        name = next(x for x in archive.namelist() if x.endswith(".csv"))
        with archive.open(name) as stream:
            frame = pd.read_csv(stream, header=None, names=COLS, dtype="str")
    frame["open_time"], _ = normalize_timestamps(frame["open_time_raw"])
    for col in ("open", "high", "low", "close", "volume", "n_trades"):
        frame[col] = pd.to_numeric(frame[col])
    return frame


def audit():
    summary_path = ROOT / "outputs/tables/data_quality_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    tasks = []
    missing_info = {}
    large_info = {}
    cross_info = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        quality = pd.read_parquet(ROOT / f"data/interim/{symbol}_daily_quality.parquet")
        for row in quality.loc[quality["missing_bars"].gt(0)].itertuples():
            period = row.date.strftime("%Y-%m-%d")
            record = task(symbol, "5m", period, "missing_day_source_check")
            tasks.append(record)
            missing_info[record["dataset_id"]] = row
        flags = pd.read_csv(ROOT / f"outputs/tables/{symbol}_review_bars.csv")
        large = flags.loc[flags["large_return_review"]].copy()
        large["day"] = pd.to_datetime(large["open_time"], utc=True).dt.strftime("%Y-%m-%d")
        for period, part in large.groupby("day"):
            record = task(symbol, "1m", period, "large_return_1m_corrob")
            tasks.append(record)
            large_info[record["dataset_id"]] = part
        compared = pd.read_csv(ROOT / f"outputs/tables/{symbol}_coingecko_crosscheck.csv")
        unusual = compared.loc[compared["review_required"]].copy()
        unusual["month"] = pd.to_datetime(unusual["date"], utc=True).dt.strftime("%Y-%m")
        for period, part in unusual.groupby("month"):
            record = task(symbol, "1d", period, "crosscheck_binance_1d_corrob")
            tasks.append(record)
            cross_info[record["dataset_id"]] = part
    records = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for future in as_completed([pool.submit(fetch_archive, t) for t in tasks]):
            records.append(future.result())
    gap_rows, return_rows, cross_rows, bar_differences = [], [], [], []
    for record in records:
        key = record["dataset_id"]
        if record["status"] != "ok":
            continue
        frame = read(record)
        record.update(row_count=len(frame), coverage_start=str(frame["open_time"].min()),
                      coverage_end=str(frame["open_time"].max()))
        if key in missing_info:
            original = missing_info[key]
            clean = pd.read_parquet(ROOT / f"data/interim/{record['symbol']}_5m_clean.parquet", columns=["open_time", "open", "high", "low", "close", "volume"])
            monthly_day = clean.loc[clean["open_time"].dt.floor("D").eq(original.date)].set_index("open_time")
            monthly_times = pd.DatetimeIndex(monthly_day.index)
            daily_times = pd.DatetimeIndex(frame["open_time"])
            extra = daily_times.difference(monthly_times)
            missing_in_daily = monthly_times.difference(daily_times)
            shared = monthly_times.intersection(daily_times)
            cols = ["open", "high", "low", "close"]
            shared_matches = bool(np.isclose(monthly_day.reindex(shared)[cols].to_numpy(),
                                             frame.set_index("open_time").reindex(shared)[cols].to_numpy(),
                                             rtol=1e-9, atol=1e-8).all())
            if not shared_matches:
                main_shared = monthly_day.reindex(shared)[cols]
                daily_shared = frame.set_index("open_time").reindex(shared)[cols]
                different = ~np.isclose(main_shared.to_numpy(), daily_shared.to_numpy(), rtol=1e-9, atol=1e-8).all(axis=1)
                for ts in shared[different]:
                    row = {"symbol": record["symbol"], "open_time": ts}
                    for col in cols:
                        row[f"monthly_{col}"] = float(main_shared.loc[ts, col])
                        row[f"daily_{col}"] = float(daily_shared.loc[ts, col])
                    bar_differences.append(row)
            status = "same_source_gap_confirmed" if len(extra) == len(missing_in_daily) == 0 and shared_matches else (
                "daily_subset_monthly_priority" if len(extra) == 0 and shared_matches else "archive_disagreement_review")
            gap_rows.append({"symbol": record["symbol"], "date": original.date, "monthly_clean_bars": original.valid_bars,
                             "daily_archive_bars": len(frame), "daily_extra_bars": len(extra),
                             "daily_missing_vs_monthly": len(missing_in_daily),
                             "shared_ohlc_match": shared_matches,
                             "monthly_only_bar_times_utc": "|".join(map(str, missing_in_daily)),
                             "daily_only_bar_times_utc": "|".join(map(str, extra)), "status": status,
                             "source_file": record["path"]})
        elif key in large_info:
            frame["bar5"] = frame["open_time"].dt.floor("5min")
            grouped = frame.groupby("bar5").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                               close=("close", "last"), volume=("volume", "sum"), n_1m=("open_time", "size"))
            for row in large_info[key].itertuples():
                timestamp = pd.Timestamp(row.open_time)
                if timestamp not in grouped.index:
                    status = "missing_1m_reference"
                    n = 0
                else:
                    other = grouped.loc[timestamp]
                    matched = all(np.isclose(getattr(row, col), other[col], rtol=1e-9, atol=1e-8) for col in ("open", "high", "low", "close"))
                    n = int(other["n_1m"])
                    status = "ohlc_confirmed_by_5x1m_same_exchange" if matched and n == 5 else "aggregation_disagreement_review"
                return_rows.append({"symbol": record["symbol"], "open_time": row.open_time,
                                    "return_5m_pct": row.return_5m_pct_qa, "status": status,
                                    "n_1m": n, "source_file": record["path"]})
        elif key in cross_info:
            by_day = frame.set_index(frame["open_time"].dt.floor("D"))
            for row in cross_info[key].itertuples():
                ts = pd.Timestamp(row.date)
                source_close = float(by_day.loc[ts, "close"]) if ts in by_day.index else np.nan
                matched = bool(np.isclose(source_close, row.close, rtol=0, atol=1e-8))
                cross_rows.append({"symbol": record["symbol"], "date": row.date, "close_from_5m": row.close,
                                   "close_from_1d_archive": source_close, "coingecko_price_usd": row.price_usd,
                                   "signed_difference_pct": row.signed_difference_pct,
                                   "binance_close_confirmed": matched,
                                   "status": "binance_aggregation_confirmed_cross_source_difference_unresolved" if matched else "binance_archive_disagreement",
                                   "source_file": record["path"]})
    pd.DataFrame(gap_rows).sort_values(["symbol", "date"]).to_csv(ROOT / "outputs/tables/gap_source_audit.csv", index=False)
    pd.DataFrame(return_rows).sort_values(["symbol", "open_time"]).to_csv(ROOT / "outputs/tables/large_return_source_audit.csv", index=False)
    pd.DataFrame(cross_rows).to_csv(ROOT / "outputs/tables/crosscheck_source_audit.csv", index=False)
    pd.DataFrame(bar_differences).to_csv(ROOT / "outputs/tables/gap_archive_ohlc_differences.csv", index=False)
    audit_summary = {"generated_at_utc": now(), "archives_requested": len(tasks),
                     "archives_ok": sum(r["status"] == "ok" for r in records),
                     "gap_days_checked": len(gap_rows),
                     "gap_days_matching_daily_source": sum(r["status"] == "same_source_gap_confirmed" for r in gap_rows),
                     "gap_days_daily_subset_monthly_priority": sum(r["status"] == "daily_subset_monthly_priority" for r in gap_rows),
                     "gap_archive_disagreements": [r for r in gap_rows if r["status"] != "same_source_gap_confirmed"],
                     "shared_bar_ohlc_disagreement_count": len(bar_differences),
                     "large_return_bars_checked": len(return_rows),
                     "large_return_bars_ohlc_confirmed": sum(r["status"] == "ohlc_confirmed_by_5x1m_same_exchange" for r in return_rows),
                     "cross_source_discrepancies": cross_rows,
                     "failures": [r for r in records if r["status"] != "ok"]}
    save_json(ROOT / "data/raw" / f"audit_manifest_{summary['snapshot_id']}.json", {"records": records})
    # Dates serialized explicitly for JSON reproducibility.
    for row in audit_summary["gap_archive_disagreements"]:
        row["date"] = str(row["date"])
    save_json(ROOT / "outputs/tables/source_audit_summary.json", audit_summary)
    # Keep main and supplemental sources together in the source log, without duplicates on rerun.
    source_log = pd.read_csv(ROOT / "docs/source_log.csv")
    base = source_log.loc[~source_log["dataset_id"].astype(str).str.startswith("audit_")]
    audit_log = pd.DataFrame(records).rename(columns={"path": "local_path", "url": "source_url"})
    full = pd.concat([base, audit_log], ignore_index=True)
    full.to_csv(ROOT / "docs/source_log.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(audit_summary, ensure_ascii=False, indent=2), flush=True)
    return audit_summary


if __name__ == "__main__":
    audit()
