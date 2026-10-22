"""Validate the actual data handoff without fitting or selecting models."""
from datetime import datetime, timezone
import json
import tomllib

import numpy as np
import pandas as pd

from .download import ROOT, sha256, save_json
from .protocol import sample_segments


def validate():
    summary = json.loads((ROOT / "outputs/tables/data_quality_summary.json").read_text(encoding="utf-8"))
    config_path = ROOT / "config/data.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert summary["config_sha256"] == sha256(config_path), "Refresh stale data handoff after config changes"
    checks = []
    for item in summary["symbols"]:
        symbol = item["symbol"]
        bars = pd.read_parquet(ROOT / f"data/interim/{symbol}_5m_clean.parquet")
        quality = pd.read_parquet(ROOT / f"data/interim/{symbol}_daily_quality.parquet")
        daily = pd.read_parquet(ROOT / f"data/interim/{symbol}_daily_reference_qa.parquet")
        assert bars["open_time"].is_monotonic_increasing
        assert not bars["open_time"].duplicated().any()
        assert bars["symbol"].eq(symbol).all()
        assert str(bars["open_time"].dt.tz) == "UTC"
        assert bars["open_time"].eq(bars["open_time"].dt.floor("5min")).all()
        assert (bars[["open", "high", "low", "close"]] > 0).all().all()
        assert (bars["high"] >= bars[["open", "low", "close"]].max(axis=1)).all()
        assert (bars["low"] <= bars[["open", "high", "close"]].min(axis=1)).all()
        adjacent = bars["open_time"].diff().eq(pd.Timedelta(minutes=5))
        manual_returns = (100 * np.log(bars["close"] / bars["close"].shift(1))).where(adjacent)
        np.testing.assert_allclose(manual_returns, bars["return_5m_pct_qa"], rtol=1e-12, atol=1e-12, equal_nan=True)
        assert bars.loc[~adjacent, "return_5m_pct_qa"].isna().all()
        assert len(bars) == item["clean_rows"]
        assert int(quality["missing_bars"].sum()) == 288 * len(quality) - len(bars)
        assert daily.loc[~daily["eligible_rv"], "rv_reference_pct2"].isna().all()
        np.testing.assert_allclose(daily["volatility_reference_pct"] ** 2, daily["rv_reference_pct2"], rtol=1e-12, atol=1e-12, equal_nan=True)
        expected_dates = pd.date_range(config["data"]["start"], config["data"]["end"], tz="UTC", freq="D")
        pd.testing.assert_index_equal(pd.DatetimeIndex(quality["date"]), expected_dates, check_names=False)
        assert quality["sample_segment"].eq(sample_segments(quality["date"], config["data"])).all()
        pd.testing.assert_frame_equal(quality, daily[quality.columns])
        counts = bars.groupby(bars["open_time"].dt.floor("D")).size().reindex(expected_dates, fill_value=0)
        np.testing.assert_array_equal(counts, quality["valid_bars"])
        eligible = quality["valid_bars"].eq(288) & quality["valid_adjacent_returns"].eq(288)
        np.testing.assert_array_equal(eligible, quality["eligible_rv"])
        manual_rv = manual_returns.pow(2).groupby(bars["open_time"].dt.floor("D")).sum(min_count=288)
        manual_rv = manual_rv.reindex(expected_dates).where(eligible.to_numpy())
        np.testing.assert_allclose(manual_rv, daily["rv_reference_pct2"], rtol=1e-12, atol=1e-12, equal_nan=True)
        csv_quality = pd.read_csv(ROOT / f"outputs/tables/{symbol}_daily_quality.csv", parse_dates=["date"])
        pd.testing.assert_frame_equal(quality, csv_quality, check_dtype=False)
        # Every raw 2025+ timestamp must have been converted to the right actual date.
        assert bars.loc[bars["open_time"].ge(pd.Timestamp("2025-01-01", tz="UTC")), "timestamp_unit"].eq("us").all()
        assert bars.loc[bars["open_time"].lt(pd.Timestamp("2025-01-01", tz="UTC")), "timestamp_unit"].eq("ms").all()
        cross = pd.read_csv(ROOT / f"outputs/tables/{symbol}_coingecko_crosscheck.csv")
        assert (pd.to_datetime(cross["timestamp_utc"], utc=True) - pd.to_datetime(cross["date"], utc=True)).eq(pd.Timedelta(days=1)).all()
        assert cross["sample_segment"].eq(sample_segments(cross["date"], config["data"])).all()
        checks.append({"symbol": symbol, "rows_validated": len(bars), "calendar_days": len(quality), "status": "passed"})
    stats = pd.read_csv(ROOT / "outputs/tables/descriptive_statistics.csv")
    assert set(stats["sample_segment"]) == {"warmup", "evaluation"}
    acf = pd.read_csv(ROOT / "outputs/tables/acf_rv.csv")
    assert pd.to_datetime(acf["segment_start"], utc=True).ge(pd.Timestamp(config["data"]["research_start"], tz="UTC")).all()
    assert pd.to_datetime(acf["segment_end"], utc=True).le(pd.Timestamp(config["data"]["warmup_end"], tz="UTC")).all()
    log = pd.read_csv(ROOT / "docs/source_log.csv")
    assert not log["dataset_id"].duplicated().any()
    for row in log.itertuples():
        assert row.status == "ok", row.dataset_id
        assert sha256(ROOT / row.local_path) == row.sha256, row.local_path
    for name in ("VIXCLS", "DTWEXBGS"):
        macro = pd.read_parquet(ROOT / f"data/interim/{name}_observations.parquet")
        assert macro["available_at"].isna().all()
        assert not macro["point_in_time_verified"].any()
    calendar = pd.read_parquet(ROOT / "data/interim/macro_calendar_DESCRIPTIVE_ONLY.parquet")
    assert not calendar["predictive_use_allowed"].any()
    for _, part in calendar.groupby("series_id", sort=False):
        np.testing.assert_allclose(part["observed_value"].ffill(), part["descriptive_ffill_value"], equal_nan=True)
    result = {"validated_at_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "source_files_hash_checked": len(log), "macro_predictive_use_blocked": True,
              "period_labels_verified": True, "rv_units_and_completeness_verified": True,
              "holdout_excluded_from_descriptive_statistics": True,
              "status": "passed_with_documented_source_gaps_and_reviews",
              "limitations": ["macro_release_vintage_unverified", "archive_disagreement_2020_12_21", "coingecko_difference_2026_02_22"]}
    save_json(ROOT / "outputs/tables/handoff_validation.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    validate()
