"""Public ALFRED vintage snapshots; conservative availability, never revised-current backfill."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import io
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler
import numpy as np
import pandas as pd
from src.data.download import sha256, save_json
from src.utils.config import ROOT

RAW = ROOT/"data/raw/alfred"
OUTPUT = ROOT/"data/interim/macro_vintages.parquet"
MANIFEST = RAW/"manifest.json"
SOURCES = {
    "downloads": "https://alfred.stlouisfed.org/help/downloaddata",
    "realtime": "https://fred.stlouisfed.org/docs/api/fred/realtime_period.html",
    "h10": "https://www.federalreserve.gov/releases/h10/",
}


def fetch(url):
    # Direct HTTPS avoids a stale local desktop proxy; no authentication is used.
    error = None
    for _ in range(3):
        try:
            with build_opener(ProxyHandler({})).open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=35) as response:
                return response.read()
        except OSError as exc:
            error = exc
    raise error


def parse_snapshot(raw, series, vintages):
    table = pd.read_csv(io.BytesIO(raw), na_values=["."])
    expected = [series+"_"+date.replace("-", "") for date in vintages]
    if list(table.columns) != ["observation_date", *expected]:
        raise ValueError("ALFRED returned different vintage identities")
    dates = pd.to_datetime(table.observation_date, utc=True)
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Invalid observation calendar")
    records = []
    for vintage, column in zip(vintages, expected):
        day = pd.Timestamp(vintage, tz="UTC")
        values = pd.to_numeric(table[column], errors="raise")
        # Some source vintages contain a populated holiday observation dated
        # after the vintage itself. Never use it; preserve the raw snapshot and
        # record the anomaly rather than trusting observation availability.
        future_count = int((values.notna() & dates.gt(day)).sum())
        valid = values.notna() & dates.le(day)
        if not valid.any():
            continue
        index = values.loc[valid].index[-1]
        value = float(values.loc[index])
        if not np.isfinite(value) or value <= 0:
            raise ValueError("Macro index must be finite and positive")
        records.append(dict(series_id=series, vintage_date=day, observation_date=dates.loc[index],
            value=value, available_at=day+pd.Timedelta(days=2), point_in_time_verified=True,
            excluded_future_observations=future_count))
    return records


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    jobs, listings = [], []
    for series in ["VIXCLS", "DTWEXBGS"]:
        url = "https://alfred.stlouisfed.org/series/downloaddata?seid="+series
        path = RAW/(series+"_vintage_listing.html")
        page = path.read_bytes() if path.exists() else fetch(url)
        if not path.exists():
            path.write_bytes(page)
        select = page.decode().split('id="form_selected_vintage_dates"', 1)[1].split("</select>", 1)[0]
        dates = sorted(set(d for d in re.findall(r'value="(\d{4}-\d{2}-\d{2})"', select)
            if "2018-11-01" <= d <= "2025-12-31"))
        if not dates:
            raise ValueError("No historical vintages: "+series)
        listings.append(dict(series_id=series, url=url, path=path.relative_to(ROOT).as_posix(),
            sha256=sha256(path), vintage_count=len(dates), first=dates[0], last=dates[-1]))
        # The graph service truncates requests above twelve lines.
        for start in range(0, len(dates), 10):
            batch = dates[start:start+10]
            lower = (pd.Timestamp(batch[0])-pd.Timedelta(days=45)).strftime("%Y-%m-%d")
            query = urlencode(dict(id=",".join([series]*len(batch)), vintage_date=",".join(batch),
                cosd=",".join([lower]*len(batch)), coed=",".join([batch[-1]]*len(batch))))
            url = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?"+query
            path = RAW/f"{series}_{batch[0]}_{batch[-1]}.csv"
            jobs.append((series, batch, url, path))
    def worker(job):
        series, dates, url, path = job
        raw = path.read_bytes() if path.exists() else fetch(url)
        rows = parse_snapshot(raw, series, dates)
        path.write_bytes(raw)
        return rows, dict(series_id=series, vintage_dates=dates, url=url,
            path=path.relative_to(ROOT).as_posix(), sha256=sha256(path), rows=len(rows))
    rows, records = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, future in enumerate(as_completed([pool.submit(worker, job) for job in jobs]), 1):
            part, record = future.result()
            rows.extend(part); records.append(record)
            if i % 8 == 0 or i == len(jobs):
                print(f"ALFRED {i}/{len(jobs)} batches verified", flush=True)
    table = pd.DataFrame(rows).sort_values(["series_id", "vintage_date"]).reset_index(drop=True)
    if table.duplicated(["series_id", "vintage_date"]).any():
        raise ValueError("Duplicate vintage snapshots")
    table.to_parquet(OUTPUT, index=False)
    save_json(MANIFEST, dict(status="verified_alfred_vintage_snapshots", retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
        source_references=SOURCES, listings=listings, records=sorted(records, key=lambda x: x["path"]),
        derived_path=OUTPUT.relative_to(ROOT).as_posix(), derived_sha256=sha256(OUTPUT),
        availability_rule="vintage_date_plus_two_UTC_days_then_origin_start_asof",
        observation_policy="latest_nonmissing_observation_in_each_historical_snapshot",
        requested_last_vintage="2025-12-31", holdout_downloaded=False))
    print(table.groupby("series_id").size().to_string(), flush=True)


def attach_macro(dataset, vintages):
    if not vintages.point_in_time_verified.eq(True).all():
        raise ValueError("Unverified macro input")
    result = dataset.copy()
    for series, feature in [("VIXCLS", "log_vix_l1"), ("DTWEXBGS", "log_usd_l1")]:
        right = vintages.loc[vintages.series_id.eq(series)].sort_values("available_at")
        if right.empty or right.available_at.duplicated().any():
            raise ValueError("Missing/duplicate macro vintage availability")
        if not right.available_at.eq(right.vintage_date+pd.Timedelta(days=2)).all():
            raise ValueError("Unexpected availability rule")
        values = pd.merge_asof(result[["origin_date"]].sort_values("origin_date"),
            right[["available_at", "value", "observation_date"]], left_on="origin_date", right_on="available_at", direction="backward")
        values.index = result.sort_values("origin_date").index
        result[feature] = np.log(values.value.reindex(result.index))
        result[feature+"_available_at"] = values.available_at.reindex(result.index)
        if result[feature+"_available_at"].gt(result.origin_date).any():
            raise ValueError("Future macro availability")
    result.attrs["verified_macro_features"] = True
    return result


def load_verified_macro(dataset):
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if meta["derived_sha256"] != sha256(OUTPUT):
        raise ValueError("Changed macro data")
    for record in meta["records"]+meta["listings"]:
        if sha256(ROOT/record["path"]) != record["sha256"]:
            raise ValueError("Changed ALFRED source")
    result = attach_macro(dataset, pd.read_parquet(OUTPUT))
    result.attrs["macro_dataset_sha256"] = sha256(OUTPUT)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    download()
