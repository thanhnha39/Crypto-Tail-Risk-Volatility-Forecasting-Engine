"""Download immutable source snapshots with provenance and SHA256 checks."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
AGENT = "CryptoRiskAcademicData/1.0 (undergraduate research)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def get(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in (400, 401, 403, 404, 451) or attempt == attempts - 1:
                raise
            time.sleep(min(2 ** (attempt + 1), 12))
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(2 ** (attempt + 1), 12))
    raise RuntimeError(url)


def save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def archive_tasks(start: date, end: date, symbols: list[str]):
    month = start.replace(day=1)
    while month <= end:
        following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = following - timedelta(days=1)
        for symbol in symbols:
            if month >= start and last <= end:
                periods = [("monthly", month.strftime("%Y-%m"))]
            else:
                first_day, last_day = max(start, month), min(end, last)
                periods = [("daily", (first_day + timedelta(days=i)).isoformat())
                           for i in range((last_day - first_day).days + 1)]
            for frequency, period in periods:
                filename = f"{symbol}-5m-{period}.zip"
                relative = Path("data/raw/binance") / symbol / filename
                url = f"https://data.binance.vision/data/spot/{frequency}/klines/{symbol}/5m/{filename}"
                yield {"dataset_id": f"{symbol}_5m_{period}", "symbol": symbol,
                       "frequency": frequency, "period": period, "url": url,
                       "path": relative.as_posix()}
        month = following


def fetch_archive(task: dict) -> dict:
    record = dict(task)
    destination = ROOT / task["path"]
    metadata = destination.with_suffix(".zip.meta.json")
    try:
        if destination.exists() and metadata.exists():
            old = json.loads(metadata.read_text(encoding="utf-8"))
            actual_hash = sha256(destination)
            if old.get("sha256") != actual_hash or old.get("checksum_status") != "verified":
                raise ValueError("Cached raw file changed or has no verified checksum; inspect before retry.")
            return old | {"cache_reused": True}
        if destination.exists() or metadata.exists():
            raise ValueError("Incomplete raw cache pair; inspect source file before replacing it.")
        body = get(task["url"])
        checksum_body = get(task["url"] + ".CHECKSUM")
        expected_hash = checksum_body.decode("utf-8").split()[0].lower()
        actual_hash = hashlib.sha256(body).hexdigest()
        if expected_hash != actual_hash:
            raise ValueError("Remote SHA256 checksum mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(".zip.part")
        partial.write_bytes(body)
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC error")
            csv_files = [x for x in archive.namelist() if x.lower().endswith(".csv")]
            if len(csv_files) != 1:
                raise ValueError(f"Expected one CSV, found {len(csv_files)}")
        partial.replace(destination)
        destination.with_suffix(".zip.CHECKSUM").write_bytes(checksum_body)
        record.update(status="ok", checksum_status="verified", sha256=actual_hash,
                      downloaded_at_utc=now(), byte_count=len(body), cache_reused=False)
        save_json(metadata, record)
    except Exception as error:
        record.update(status="unavailable", downloaded_at_utc=now(),
                      error=f"{type(error).__name__}: {error}")
    return record


def snapshot(dataset_id: str, url: str, destination: Path) -> dict:
    metadata = destination.with_suffix(destination.suffix + ".meta.json")
    if destination.exists() and metadata.exists():
        old = json.loads(metadata.read_text(encoding="utf-8"))
        if old.get("sha256") != sha256(destination):
            raise ValueError(f"Immutable snapshot changed: {destination}")
        return old | {"cache_reused": True}
    if destination.exists():
        raise ValueError(f"Untracked raw snapshot: {destination}")
    record = {"dataset_id": dataset_id, "url": url, "path": destination.relative_to(ROOT).as_posix()}
    try:
        body = get(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        record.update(status="ok", sha256=hashlib.sha256(body).hexdigest(),
                      downloaded_at_utc=now(), byte_count=len(body), checksum_status="local_hash")
        save_json(metadata, record)
    except Exception as error:
        record.update(status="unavailable", downloaded_at_utc=now(),
                      error=f"{type(error).__name__}: {error}")
    return record


def download(config_path: Path, workers: int = 6) -> dict:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    settings = config["data"]
    start, end = date.fromisoformat(settings["start"]), date.fromisoformat(settings["end"])
    if end >= datetime.now(timezone.utc).date():
        raise ValueError("end must be a completed UTC date, not today/future")
    tasks = list(archive_tasks(start, end, settings["symbols"]))
    print(f"Downloading/verifying {len(tasks)} Binance archives, {start} to {end}", flush=True)
    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_archive, task): task for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            records.append(record)
            if i % 20 == 0 or record["status"] != "ok" or i == len(tasks):
                print(f"Binance {i}/{len(tasks)}: {record['dataset_id']} {record['status']}", flush=True)
    stamp = config["snapshot"]["id"]
    for series in ("VIXCLS", "DTWEXBGS"):
        query = urllib.parse.urlencode({"id": series, "cosd": start.isoformat(), "coed": end.isoformat()})
        record = snapshot(series, "https://fred.stlouisfed.org/graph/fredgraph.csv?" + query,
                          ROOT / "data/raw/fred" / stamp / f"{series}.csv")
        records.append(record)
        print("FRED", series, record["status"], flush=True)
    for coin, symbol in (("bitcoin", "BTCUSDT"), ("ethereum", "ETHUSDT")):
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=365&interval=daily"
        record = snapshot(f"coingecko_{symbol}", url,
                          ROOT / "data/raw/coingecko" / stamp / f"{coin}_usd_daily.json")
        record.update(symbol=symbol, purpose="price_crosscheck_only", lookback_limit_days=365)
        records.append(record)
        print("CoinGecko", symbol, record["status"], flush=True)
        time.sleep(1)
    manifest = {"created_at_utc": now(), "snapshot_id": stamp, "start": start.isoformat(),
                "end": end.isoformat(), "config_sha256": sha256(config_path),
                "records": sorted(records, key=lambda x: x["dataset_id"])}
    save_json(ROOT / "data/raw" / f"manifest_{stamp}.json", manifest)
    failures = [r for r in records if r["status"] != "ok"]
    print(f"Download complete: {len(records)-len(failures)} ok, {len(failures)} unavailable", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/data.toml")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    download(args.config.resolve(), max(1, min(args.workers, 8)))


if __name__ == "__main__":
    main()
