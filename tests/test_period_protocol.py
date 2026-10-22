"""Regression checks for agreed date boundaries, RV units and holdout isolation."""
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.data.protocol import sample_segments
from src.data.report import descriptive
from src.data.clean import clean_klines, daily_quality, reference_daily
from test_data_quality import bars


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.settings = tomllib.loads((Path(__file__).resolve().parents[1] / "config/data.toml").read_text(encoding="utf-8"))["data"]

    def test_calendar_boundaries(self):
        dates = ["2018-12-31", "2019-01-01", "2020-12-31", "2021-01-01", "2025-12-31", "2026-01-01", "2026-10-17"]
        self.assertEqual(sample_segments(dates, self.settings).tolist(),
                         ["pre_sample", "warmup", "warmup", "evaluation", "evaluation", "holdout", "holdout"])

    def test_period_gap_is_rejected(self):
        settings = dict(self.settings, evaluation_start="2021-01-02")
        with self.assertRaises(ValueError):
            sample_segments(["2021-01-01"], settings)

    def test_rv_percent_squared_and_sqrt_units(self):
        times = pd.date_range("2019-12-31T23:55:00Z", periods=289, freq="5min")
        prices = (100 * np.exp(np.arange(289) * .001)).tolist()
        raw = bars([x.isoformat() for x in times], prices)
        start, end = pd.Timestamp("2019-12-31", tz="UTC"), pd.Timestamp("2020-01-01", tz="UTC")
        clean, _, normalized = clean_klines(raw, start, end)
        quality = daily_quality(clean, normalized, start, end, self.settings)
        day = reference_daily(clean, quality).iloc[1]
        self.assertTrue(day["eligible_rv"])
        self.assertAlmostEqual(day["rv_reference_pct2"], 288 * .1**2)
        self.assertAlmostEqual(day["volatility_reference_pct"], np.sqrt(288 * .1**2))

    def test_holdout_cannot_change_descriptive_statistics(self):
        frame = pd.DataFrame({"sample_segment":["warmup", "evaluation", "holdout"],
            **{key:[1., 2., 3.] for key in ["close", "return_daily_pct_qa", "rv_reference_pct2", "volatility_reference_pct", "quote_volume"]}})
        with patch("pandas.DataFrame.to_csv"):
            before = descriptive({"BTCUSDT":frame})
            frame.loc[frame["sample_segment"].eq("holdout"), "rv_reference_pct2"] = 1e12
            after = descriptive({"BTCUSDT":frame})
        pd.testing.assert_frame_equal(before, after)
        self.assertEqual(set(after["sample_segment"]), {"warmup", "evaluation"})


if __name__ == "__main__":
    unittest.main()
