"""Tests for time units, gaps, quarantine and information timing."""
import unittest

import numpy as np
import pandas as pd

from src.data.clean import COLS, clean_klines, daily_quality, reference_daily


def bars(times, prices=None):
    prices = prices or [100.0] * len(times)
    rows = []
    for time, price in zip(times, prices):
        ts = pd.Timestamp(time)
        micros = ts >= pd.Timestamp("2025-01-01", tz="UTC")
        raw_time = ts.value // (1000 if micros else 1_000_000)
        row = [str(raw_time), "100", "200", "50", str(price), "10", str(raw_time),
               "1000", "5", "4", "400", "0"]
        rows.append(row)
    result = pd.DataFrame(rows, columns=COLS)
    result["symbol"] = "BTCUSDT"
    result["source_file"] = "fixture_only"
    return result


class QualityTests(unittest.TestCase):
    def clean(self, raw, start="2024-12-31", end="2025-01-02"):
        return clean_klines(raw, pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"))

    def test_millisecond_microsecond_transition_and_scale(self):
        raw = bars(["2024-12-31T23:55:00Z", "2025-01-01T00:00:00Z"], [100, 101])
        clean, quarantine, _ = self.clean(raw)
        self.assertEqual(len(quarantine), 0)
        self.assertEqual(clean["timestamp_unit"].tolist(), ["ms", "us"])
        self.assertEqual(clean["open_time"].diff().iloc[1], pd.Timedelta(minutes=5))
        self.assertAlmostEqual(clean["return_5m_pct_qa"].iloc[1], 100 * np.log(1.01))

    def test_gap_is_not_a_five_minute_return(self):
        clean, _, _ = self.clean(bars(["2025-01-01T00:00:00Z", "2025-01-01T00:10:00Z"], [100, 110]))
        self.assertTrue(clean["return_5m_pct_qa"].isna().all())
        self.assertTrue(clean["return_gap_before"].all())

    def test_conflicting_duplicates_are_quarantined(self):
        clean, quarantine, _ = self.clean(bars(["2025-01-01T00:00:00Z"] * 2, [100, 101]))
        self.assertEqual(len(clean), 0)
        self.assertEqual(len(quarantine), 2)
        self.assertTrue(quarantine["quarantine_reason"].str.contains("conflicting_duplicate").all())

    def test_identical_duplicate_is_logged_and_removed(self):
        clean, quarantine, _ = self.clean(bars(["2025-01-01T00:00:00Z"] * 2))
        self.assertEqual(len(clean), 1)
        self.assertEqual(len(quarantine), 1)
        self.assertIn("identical_duplicate_removed", quarantine["quarantine_reason"].iloc[0])

    def test_future_bars_do_not_change_past_returns(self):
        raw = bars(["2025-01-01T00:00:00Z", "2025-01-01T00:05:00Z"], [100, 101])
        first, _, _ = self.clean(raw)
        extended = pd.concat([raw, bars(["2025-01-02T00:00:00Z"], [150])], ignore_index=True)
        second, _, _ = self.clean(extended)
        pd.testing.assert_frame_equal(first, second.iloc[:2].reset_index(drop=True))

    def test_daily_rv_requires_all_288_adjacent_returns(self):
        times = pd.date_range("2024-12-31T23:55:00Z", periods=289, freq="5min")
        raw = bars([x.isoformat() for x in times])
        clean, _, normalized = self.clean(raw)
        settings = {"expected_bars_per_day": 288, "max_missing_fraction_for_review": 0.05,
                    "research_start": "2019-01-01", "research_end": "2025-12-31",
                    "warmup_end": "2020-12-31", "evaluation_start": "2021-01-01",
                    "holdout_start": "2026-01-01", "holdout_end": "2026-12-31"}
        quality = daily_quality(clean, normalized, pd.Timestamp("2024-12-31", tz="UTC"),
                                pd.Timestamp("2025-01-01", tz="UTC"), settings)
        self.assertTrue(quality["eligible_rv"].iloc[1])
        reference = reference_daily(clean, quality)
        self.assertEqual(reference["rv_reference_pct2"].iloc[1], 0)
        incomplete_raw = raw.drop(index=100).reset_index(drop=True)
        incomplete, _, normalized2 = self.clean(incomplete_raw)
        q2 = daily_quality(incomplete, normalized2, pd.Timestamp("2024-12-31", tz="UTC"),
                           pd.Timestamp("2025-01-01", tz="UTC"), settings)
        self.assertFalse(q2["eligible_rv"].iloc[1])
        self.assertTrue(pd.isna(reference_daily(incomplete, q2)["rv_reference_pct2"].iloc[1]))


if __name__ == "__main__":
    unittest.main()
