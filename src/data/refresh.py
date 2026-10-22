"""Refresh data handoff labels/reports offline, preserving source files and clean bars."""
from datetime import datetime, timezone
import json
import tomllib

import pandas as pd

from .download import ROOT, save_json, sha256
from .clean import reference_daily
from .protocol import sample_segments
from .report import report
from .validate import validate


def refresh():
    config_path = ROOT / "config/data.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    summary_path = ROOT / "outputs/tables/data_quality_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["snapshot_id"] != config["snapshot"]["id"]:
        raise ValueError("Snapshot mismatch; refresh requires existing data from the configured snapshot")
    segment_rows = []
    for item in summary["symbols"]:
        symbol = item["symbol"]
        bars = pd.read_parquet(ROOT / f"data/interim/{symbol}_5m_clean.parquet")
        qpath = ROOT / f"data/interim/{symbol}_daily_quality.parquet"
        dpath = ROOT / f"data/interim/{symbol}_daily_reference_qa.parquet"
        quality = pd.read_parquet(qpath)
        previous = pd.read_parquet(dpath)
        quality["sample_segment"] = sample_segments(quality["date"], config["data"])
        daily = reference_daily(bars, quality)
        # Relabelling must never change prices, returns, RV or the retained calendar.
        pd.testing.assert_frame_equal(previous.drop(columns="sample_segment"),
                                      daily.drop(columns="sample_segment"))
        quality.to_parquet(qpath, index=False)
        daily.to_parquet(dpath, index=False)
        quality.to_csv(ROOT / f"outputs/tables/{symbol}_daily_quality.csv", index=False)
        quality.loc[quality["day_status"].ne("complete")].to_csv(
            ROOT / f"outputs/tables/{symbol}_incomplete_days.csv", index=False)
        cross_path = ROOT / f"outputs/tables/{symbol}_coingecko_crosscheck.csv"
        cross = pd.read_csv(cross_path)
        cross["sample_segment"] = sample_segments(cross["date"], config["data"])
        cross.to_csv(cross_path, index=False)
        item["daily_quality_by_segment"] = quality.groupby("sample_segment").agg(
            days=("date", "size"), eligible_rv=("eligible_rv", "sum"),
            missing_bars=("missing_bars", "sum")).reset_index().to_dict("records")
        for row in item["daily_quality_by_segment"]:
            segment_rows.append({"symbol": symbol, **row})
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["config_sha256"] = sha256(config_path)
    summary["period_labels"] = "pre_sample / warmup / evaluation / holdout; observation dates"
    save_json(summary_path, summary)
    pd.DataFrame(segment_rows).to_csv(ROOT / "outputs/tables/sample_period_summary.csv", index=False)
    report()
    return validate()


if __name__ == "__main__":
    refresh()
