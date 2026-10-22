"""Normalize spot bars, quarantine invalid rows and create the data handoff."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tomllib
import zipfile

import numpy as np
import pandas as pd

from .download import ROOT, save_json, sha256
from .protocol import sample_segments

COLS = ["open_time_raw", "open", "high", "low", "close", "volume", "close_time_raw",
        "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote", "ignore"]
PRICE = ["open", "high", "low", "close"]
AMOUNTS = ["volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]
NUMERIC = PRICE + AMOUNTS + ["n_trades"]


def normalize_timestamps(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    numbers = pd.to_numeric(values, errors="coerce")
    units = pd.Series(np.where(numbers.abs() >= 1e14, "us", "ms"), index=values.index)
    result = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    for unit in ("ms", "us"):
        mask = units.eq(unit) & numbers.notna()
        result.loc[mask] = pd.to_datetime(numbers.loc[mask], unit=unit, utc=True, errors="coerce")
    return result, units


def clean_klines(raw: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                  large_return_threshold: float = 10.0):
    frame = raw.copy()
    frame["open_time"], frame["timestamp_unit"] = normalize_timestamps(frame["open_time_raw"])
    for name in NUMERIC:
        frame[name] = pd.to_numeric(frame[name], errors="coerce").astype("float64")
    reason = pd.Series("", index=frame.index, dtype="str")

    def flag(mask, label):
        nonlocal reason
        mask = mask.fillna(True)
        reason.loc[mask] = reason.loc[mask].map(lambda text: f"{text}|{label}".strip("|"))

    flag(frame["open_time"].isna(), "invalid_timestamp")
    flag(frame["open_time"].notna() &
         ~frame["open_time"].eq(frame["open_time"].dt.floor("5min")), "off_grid_timestamp")
    flag(frame["open_time"].notna() &
         ((frame["open_time"] < start) | (frame["open_time"] >= end + pd.Timedelta(days=1))), "outside_requested_range")
    flag(~np.isfinite(frame[NUMERIC]).all(axis=1), "invalid_numeric")
    flag((frame[PRICE] <= 0).any(axis=1), "nonpositive_price")
    flag((frame[AMOUNTS] < 0).any(axis=1) | (frame["n_trades"] < 0), "negative_volume_or_trades")
    flag(frame["n_trades"].notna() & frame["n_trades"].mod(1).ne(0), "noninteger_trades")
    flag((frame["high"] < frame[["open", "close", "low"]].max(axis=1)) |
         (frame["low"] > frame[["open", "close", "high"]].min(axis=1)), "invalid_ohlc")
    tolerance_base = np.maximum(1e-8, frame["volume"].abs() * 1e-8)
    tolerance_quote = np.maximum(1e-6, frame["quote_volume"].abs() * 1e-8)
    flag((frame["taker_buy_base"] > frame["volume"] + tolerance_base) |
         (frame["taker_buy_quote"] > frame["quote_volume"] + tolerance_quote), "taker_exceeds_volume")

    duplicates = frame["open_time"].notna() & frame["open_time"].duplicated(keep=False)
    duplicate_rows = frame.loc[duplicates]
    conflicting_times = pd.DatetimeIndex([])
    if not duplicate_rows.empty:
        distinct = duplicate_rows.groupby("open_time")[NUMERIC].nunique(dropna=False)
        conflicting_times = distinct.index[distinct.gt(1).any(axis=1)]
        flag(frame["open_time"].isin(conflicting_times), "conflicting_duplicate")
    identical_later = frame["open_time"].notna() & frame["open_time"].duplicated(keep="first") & ~frame["open_time"].isin(conflicting_times)
    flag(identical_later, "identical_duplicate_removed")
    frame["quarantine_reason"] = reason
    quarantine = frame.loc[reason.ne("")].copy()
    cleaned = frame.loc[reason.eq("")].copy().sort_values("open_time").reset_index(drop=True)
    cleaned["n_trades"] = cleaned["n_trades"].astype("int64")
    adjacent = cleaned["open_time"].diff().eq(pd.Timedelta(minutes=5))
    cleaned["return_5m_pct_qa"] = (100 * np.log(cleaned["close"] / cleaned["close"].shift(1))).where(adjacent)
    cleaned["return_gap_before"] = ~adjacent
    cleaned["zero_volume"] = cleaned["volume"].eq(0)
    cleaned["large_return_review"] = cleaned["return_5m_pct_qa"].abs().gt(large_return_threshold)
    cleaned["quality_flag"] = np.select(
        [cleaned["zero_volume"] & cleaned["large_return_review"], cleaned["zero_volume"], cleaned["large_return_review"]],
        ["zero_volume|large_return_review", "zero_volume", "large_return_review"], default="ok")
    # A QA reference return is not a lag/target modeling dataset.
    keep = ["symbol", "open_time"] + NUMERIC + ["source_file", "timestamp_unit", "quality_flag",
            "zero_volume", "large_return_review", "return_gap_before", "return_5m_pct_qa"]
    return cleaned[keep], quarantine, frame


def daily_quality(cleaned: pd.DataFrame, normalized_raw: pd.DataFrame,
                  start: pd.Timestamp, end: pd.Timestamp, settings: dict):
    days = pd.date_range(start, end, freq="D", tz="UTC", name="date")
    result = pd.DataFrame(index=days)
    raw_counts = normalized_raw.groupby(normalized_raw["open_time"].dt.floor("D")).size()
    result["raw_rows"] = raw_counts.reindex(days, fill_value=0)
    times = cleaned["open_time"]
    day_values = times.dt.floor("D")
    grouped = cleaned.groupby(day_values)
    result["valid_bars"] = grouped.size().reindex(days, fill_value=0)
    result["expected_bars"] = settings["expected_bars_per_day"]
    result["missing_bars"] = (result["expected_bars"] - result["valid_bars"]).clip(lower=0)
    result["missing_fraction"] = result["missing_bars"] / result["expected_bars"]
    result["valid_adjacent_returns"] = grouped["return_5m_pct_qa"].count().reindex(days, fill_value=0)
    result["zero_volume_bars"] = grouped["zero_volume"].sum().reindex(days, fill_value=0)
    result["large_return_bars"] = grouped["large_return_review"].sum().reindex(days, fill_value=0)
    result["eligible_rv"] = result["valid_bars"].eq(288) & result["valid_adjacent_returns"].eq(288)
    result["day_status"] = np.select(
        [result["valid_bars"].eq(0), result["missing_fraction"].gt(settings["max_missing_fraction_for_review"]),
         result["missing_bars"].gt(0), ~result["eligible_rv"]],
        ["no_data", "more_than_5pct_missing", "incomplete", "missing_previous_close"], default="complete")
    result["sample_segment"] = sample_segments(days, settings)
    result["symbol"] = cleaned["symbol"].iloc[0]
    return result.reset_index()


def reference_daily(cleaned: pd.DataFrame, quality: pd.DataFrame) -> pd.DataFrame:
    work = cleaned.assign(date=cleaned["open_time"].dt.floor("D"))
    grouped = work.groupby("date")
    summary = grouped.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                          close=("close", "last"), volume=("volume", "sum"), quote_volume=("quote_volume", "sum"),
                          n_trades=("n_trades", "sum"))
    # Only actual boundary bars define calendar daily open/close.
    opened = work.loc[work["open_time"].dt.hour.eq(0) & work["open_time"].dt.minute.eq(0)].set_index("date")["open"]
    closed = work.loc[work["open_time"].dt.hour.eq(23) & work["open_time"].dt.minute.eq(55)].set_index("date")["close"]
    summary["open"], summary["close"] = opened, closed
    rv_sums = work.assign(squared=work["return_5m_pct_qa"].pow(2)).groupby("date")["squared"].sum(min_count=288)
    summary["rv_reference_pct2"] = rv_sums
    merged = quality.merge(summary.reset_index(), on="date", how="left", validate="one_to_one")
    merged.loc[~merged["eligible_rv"], "rv_reference_pct2"] = np.nan
    merged["volatility_reference_pct"] = np.sqrt(merged["rv_reference_pct2"])
    merged["return_daily_pct_qa"] = 100 * np.log(merged["close"] / merged["close"].shift(1))
    return merged


def missing_intervals(cleaned: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
    expected = pd.date_range(start, end + pd.Timedelta(days=1), freq="5min", inclusive="left", tz="UTC")
    missing = expected.difference(pd.DatetimeIndex(cleaned["open_time"]))
    if missing.empty:
        return pd.DataFrame(columns=["symbol", "start_utc", "end_utc", "missing_bars", "duration_minutes"])
    series = pd.Series(missing)
    groups = series.diff().ne(pd.Timedelta(minutes=5)).cumsum()
    gaps = series.groupby(groups).agg(["min", "max", "size"]).reset_index(drop=True)
    gaps = gaps.rename(columns={"min": "start_utc", "max": "end_utc", "size": "missing_bars"})
    gaps["duration_minutes"] = gaps["missing_bars"] * 5
    gaps.insert(0, "symbol", cleaned["symbol"].iloc[0])
    return gaps


def clean_symbol(records: list[dict], symbol: str, config: dict, source_log: list[dict]):
    settings = config["data"]
    parts = []
    for record in records:
        if record.get("symbol") != symbol or "frequency" not in record:
            continue
        enriched = dict(record)
        if record["status"] != "ok":
            source_log.append(enriched)
            continue
        file = ROOT / record["path"]
        if sha256(file) != record["sha256"]:
            raise ValueError(f"Raw SHA256 changed: {file}")
        with zipfile.ZipFile(file) as archive:
            filename = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
            with archive.open(filename) as stream:
                frame = pd.read_csv(stream, header=None, names=COLS, dtype="str", keep_default_na=False)
        # Exact original bytes remain in ZIP. Parquet keeps source tokens without rounding.
        frame["symbol"] = symbol
        frame["source_file"] = record["path"]
        observed, units = normalize_timestamps(frame["open_time_raw"])
        enriched.update(row_count=len(frame), coverage_start=str(observed.min()), coverage_end=str(observed.max()),
                        timestamp_units="|".join(sorted(units.unique())))
        source_log.append(enriched)
        parts.append(frame)
    if not parts:
        raise ValueError(f"No usable source data for {symbol}")
    raw = pd.concat(parts, ignore_index=True)
    raw.to_parquet(ROOT / f"data/raw/{symbol}_5m.parquet", index=False, compression="zstd")
    start, end = pd.Timestamp(settings["start"], tz="UTC"), pd.Timestamp(settings["end"], tz="UTC")
    clean, quarantine, normalized = clean_klines(raw, start, end, settings["large_return_review_threshold_pct"])
    clean.to_parquet(ROOT / f"data/interim/{symbol}_5m_clean.parquet", index=False, compression="zstd")
    quarantine.to_parquet(ROOT / f"data/interim/{symbol}_quarantine.parquet", index=False, compression="zstd")
    quality = daily_quality(clean, normalized, start, end, settings)
    daily = reference_daily(clean, quality)
    quality.to_parquet(ROOT / f"data/interim/{symbol}_daily_quality.parquet", index=False)
    daily.to_parquet(ROOT / f"data/interim/{symbol}_daily_reference_qa.parquet", index=False)
    gaps = missing_intervals(clean, start, end)
    gaps.to_csv(ROOT / f"outputs/tables/{symbol}_missing_intervals.csv", index=False)
    quality.loc[quality["day_status"].ne("complete")].to_csv(ROOT / f"outputs/tables/{symbol}_incomplete_days.csv", index=False)
    reviews = clean.loc[clean["zero_volume"] | clean["large_return_review"]]
    reviews.to_csv(ROOT / f"outputs/tables/{symbol}_review_bars.csv", index=False)
    quality.to_csv(ROOT / f"outputs/tables/{symbol}_daily_quality.csv", index=False)
    reasons = quarantine["quarantine_reason"].value_counts().to_dict()
    result = {"symbol": symbol, "raw_rows": len(raw), "clean_rows": len(clean),
              "quarantined_rows": len(quarantine), "quarantine_reasons": reasons,
              "coverage_start_utc": str(clean["open_time"].min()), "coverage_end_utc": str(clean["open_time"].max()),
              "expected_days": len(quality), "days_complete_bars": int(quality["valid_bars"].eq(288).sum()),
              "days_eligible_rv": int(quality["eligible_rv"].sum()), "incomplete_days": int(quality["valid_bars"].lt(288).sum()),
              "missing_bars": int(quality["missing_bars"].sum()), "zero_volume_bars": int(clean["zero_volume"].sum()),
              "large_return_bars": int(clean["large_return_review"].sum()),
              "timestamp_units": clean["timestamp_unit"].value_counts().to_dict(),
              "daily_quality_by_segment": quality.groupby("sample_segment").agg(days=("date", "size"), eligible_rv=("eligible_rv", "sum"), missing_bars=("missing_bars", "sum")).reset_index().to_dict("records")}
    print(f"{symbol}: raw={len(raw):,}, clean={len(clean):,}, quarantine={len(quarantine):,}, incomplete days={result['incomplete_days']}", flush=True)
    return result, daily


def clean_macro(manifest: dict, source_log: list[dict]):
    tables = []
    summaries = []
    for record in manifest["records"]:
        if record["dataset_id"] not in ("VIXCLS", "DTWEXBGS"):
            continue
        enriched = dict(record)
        if record["status"] != "ok":
            source_log.append(enriched)
            summaries.append({"series_id": record["dataset_id"], "status": record["status"]})
            continue
        file = ROOT / record["path"]
        if sha256(file) != record["sha256"]:
            raise ValueError(f"Macro raw hash mismatch: {file}")
        frame = pd.read_csv(file, dtype="str")
        series = record["dataset_id"]
        table = pd.DataFrame({"observation_date": pd.to_datetime(frame.iloc[:, 0], utc=True),
                              "value": pd.to_numeric(frame[series], errors="coerce")})
        if table["observation_date"].duplicated().any():
            raise ValueError(f"Duplicate macro observations: {series}")
        table["series_id"] = series
        table["source_file"] = record["path"]
        table["retrieved_at_utc"] = pd.Timestamp(record["downloaded_at_utc"])
        table["available_at"] = pd.Series(pd.NaT, index=table.index, dtype="datetime64[ns, UTC]")
        table["point_in_time_verified"] = False
        table.to_parquet(ROOT / f"data/interim/{series}_observations.parquet", index=False)
        valid = table.loc[table["value"].notna()]
        enriched.update(row_count=len(table), coverage_start=str(table["observation_date"].min()), coverage_end=str(table["observation_date"].max()))
        source_log.append(enriched)
        summaries.append({"series_id": series, "status": "collected_not_verified_point_in_time", "rows": len(table),
                          "nonmissing_values": len(valid), "last_observation_with_value": str(valid["observation_date"].max())})
        # This calendar view is ONLY for descriptive work; missing values are not bfilled.
        index = pd.date_range(manifest["start"], manifest["end"], freq="D", tz="UTC")
        observed = table.set_index("observation_date")["value"].reindex(index)
        calendar = pd.DataFrame({"date": index, "series_id": series, "observed_value": observed.to_numpy(),
                                 "descriptive_ffill_value": observed.ffill().to_numpy(),
                                 "predictive_use_allowed": False})
        tables.append(calendar)
    if tables:
        pd.concat(tables, ignore_index=True).to_parquet(ROOT / "data/interim/macro_calendar_DESCRIPTIVE_ONLY.parquet", index=False)
    return summaries


def crosscheck(manifest: dict, daily_frames: dict[str, pd.DataFrame], source_log: list[dict], threshold: float):
    summaries = []
    for record in manifest["records"]:
        if not record["dataset_id"].startswith("coingecko_"):
            continue
        enriched = dict(record)
        symbol = record["symbol"]
        if record["status"] != "ok":
            source_log.append(enriched)
            summaries.append({"symbol": symbol, "status": "unavailable"})
            continue
        file = ROOT / record["path"]
        if sha256(file) != record["sha256"]:
            raise ValueError(f"CoinGecko raw hash mismatch: {file}")
        body = json.loads(file.read_text(encoding="utf-8"))
        if "prices" not in body:
            raise ValueError(f"CoinGecko returned no prices: {body}")
        cg = pd.DataFrame(body["prices"], columns=["timestamp_ms", "price_usd"])
        cg["timestamp_utc"] = pd.to_datetime(cg["timestamp_ms"], unit="ms", utc=True)
        cg["midnight_sample"] = cg["timestamp_utc"].eq(cg["timestamp_utc"].dt.floor("D"))
        cg.to_parquet(ROOT / f"data/interim/{symbol}_coingecko_daily.parquet", index=False)
        enriched.update(row_count=len(cg), coverage_start=str(cg["timestamp_utc"].min()), coverage_end=str(cg["timestamp_utc"].max()))
        source_log.append(enriched)
        aligned = cg.loc[cg["midnight_sample"]].copy()
        aligned["date"] = aligned["timestamp_utc"] - pd.Timedelta(days=1)
        # CoinGecko 00:00 belongs to the preceding Binance completed-day close.
        compared = daily_frames[symbol][["date", "close", "sample_segment"]].merge(aligned, on="date", how="inner", validate="one_to_one")
        compared = compared.loc[compared["close"].notna()].copy()
        compared["symbol"] = symbol
        compared["signed_difference_pct"] = 100 * (compared["close"] / compared["price_usd"] - 1)
        compared["absolute_difference_pct"] = compared["signed_difference_pct"].abs()
        compared["review_required"] = compared["absolute_difference_pct"].gt(threshold)
        compared.to_csv(ROOT / f"outputs/tables/{symbol}_coingecko_crosscheck.csv", index=False)
        summaries.append({"symbol": symbol, "status": "compared", "matched_days": len(compared),
                          "date_start": str(compared["date"].min()), "date_end": str(compared["date"].max()),
                          "median_absolute_difference_pct": float(compared["absolute_difference_pct"].median()),
                          "max_absolute_difference_pct": float(compared["absolute_difference_pct"].max()),
                          "days_above_review_threshold": int(compared["review_required"].sum()),
                          "current_nonmidnight_points_excluded": int((~cg["midnight_sample"]).sum())})
    return summaries


def clean(config_path: Path) -> dict:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    manifest_path = ROOT / "data/raw" / f"manifest_{config['snapshot']['id']}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("data/interim", "outputs/tables", "outputs/figures", "docs"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    source_log = []
    symbols = []
    daily_frames = {}
    for symbol in config["data"]["symbols"]:
        result, daily = clean_symbol(manifest["records"], symbol, config, source_log)
        symbols.append(result)
        daily_frames[symbol] = daily
    macro = clean_macro(manifest, source_log)
    comparisons = crosscheck(manifest, daily_frames, source_log, config["data"]["crosscheck_review_threshold_pct"])
    log = pd.DataFrame(source_log)
    log = log.rename(columns={"url": "source_url", "path": "local_path"})
    log.to_csv(ROOT / "docs/source_log.csv", index=False, encoding="utf-8-sig")
    summary = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
               "snapshot_id": config["snapshot"]["id"], "config_sha256": sha256(config_path),
               "symbols": symbols, "macro": macro, "crosscheck": comparisons,
               "download_failures": [r for r in manifest["records"] if r["status"] != "ok"],
               "scope": "source acquisition, normalization, QA references; no modeling dataset, lags, tuning or forecasts"}
    save_json(ROOT / "outputs/tables/data_quality_summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/data.toml")
    args = parser.parse_args()
    clean(args.config.resolve())


if __name__ == "__main__":
    main()
