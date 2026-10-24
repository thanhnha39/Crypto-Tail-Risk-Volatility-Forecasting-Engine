import io
import unittest

import numpy as np
import pandas as pd
from scipy import stats

from src.backend4 import (
    backtest_tables,
    build_risk_forecasts,
    christoffersen_test,
    empirical_tail,
    kupiec_test,
    student_t_tail,
)


class Backend4Tests(unittest.TestCase):
    def test_student_t_quantile_and_expected_shortfall_use_unit_variance_scale(self):
        alpha, nu = 0.05, 8.0
        quantile, expected_shortfall = student_t_tail(alpha, nu)
        raw_quantile = stats.t.ppf(alpha, df=nu)
        scale = np.sqrt((nu - 2) / nu)
        expected_q = raw_quantile * scale
        expected_es = scale * (
            -(nu + raw_quantile**2) / (nu - 1) * stats.t.pdf(raw_quantile, df=nu) / alpha
        )
        self.assertAlmostEqual(quantile, expected_q)
        self.assertAlmostEqual(expected_shortfall, expected_es)
        self.assertLess(expected_shortfall, quantile)

    def test_empirical_tail_uses_only_observations_at_or_below_quantile(self):
        quantile, expected_shortfall = empirical_tail([-3, -2, -1, 0, 1], 0.4)
        self.assertAlmostEqual(quantile, -1.4)
        self.assertAlmostEqual(expected_shortfall, -2.5)

    def test_kupiec_accepts_exact_expected_breach_rate(self):
        result = kupiec_test([True] * 5 + [False] * 95, 0.05, minimum_observations=100)
        self.assertEqual(result["uc_status"], "ok")
        self.assertAlmostEqual(result["lr_uc"], 0.0)
        self.assertAlmostEqual(result["p_value_uc"], 1.0)

    def test_christoffersen_detects_clustered_exceptions(self):
        clustered = christoffersen_test([False] * 90 + [True] * 10, minimum_observations=20)
        scattered = christoffersen_test(([False] * 9 + [True]) * 10, minimum_observations=20)
        self.assertEqual(clustered["ind_status"], "ok")
        self.assertGreater(clustered["lr_ind"], scattered["lr_ind"])

    def test_fhs_residuals_are_not_available_until_observable_at_origin(self):
        dates = pd.date_range("2021-01-01", periods=5, tz="UTC")
        dataset = pd.DataFrame({
            "symbol": "BTCUSDT", "origin_date": dates, "ret_d": [0.0, -1.0, 2.0, -2.0, 1.0],
            "regime": ["normal", "normal", "crisis", "normal", "normal"],
            "target_segment_h1": "evaluation",
        })
        forecasts = pd.DataFrame([{
            "symbol": "BTCUSDT", "model": "har_rv", "window": "rolling", "horizon_days": 1,
            "origin_date": date, "target_date": date + pd.Timedelta(days=1),
            "forecast_available_at": date + pd.Timedelta(days=1), "status": "ok",
            "mean_forecast_pct": 0.0, "volatility_forecast_pct": 1.0,
            "rv_forecast_pct2": 1.0, "protocol_sha256": "protocol", "dataset_sha256": "dataset",
        } for date in dates[:-1]])
        options = {
            "residual_window_calendar_days": 730, "min_fhs_residuals": 1,
        }
        risk = build_risk_forecasts(forecasts, dataset, options, [0.95])
        self.assertEqual(int(risk.iloc[0]["n_residuals"]), 0)
        self.assertEqual(int(risk.iloc[1]["n_residuals"]), 0)
        self.assertEqual(int(risk.iloc[2]["n_residuals"]), 1)
        self.assertEqual(risk.iloc[2]["risk_status"], "ok")
        self.assertEqual(risk.iloc[2]["regime"], "crisis")
        risk.to_parquet(io.BytesIO(), index=False)

    def test_backtest_ignores_gaps_when_counting_exception_transitions(self):
        dates = pd.to_datetime([
            "2021-01-01", "2021-01-02", "2021-01-04", "2021-01-05",
        ], utc=True)
        risk = pd.DataFrame({
            "symbol": "BTCUSDT", "model": "har_rv", "window": "rolling", "confidence": 0.95,
            "tail_probability": 0.05, "risk_method": "filtered_historical_simulation",
            "risk_status": "ok", "origin_date": dates, "breach": [False, True, True, False],
            "var_loss_pct": [1.0] * 4, "es_loss_pct": [1.5] * 4,
            "regime": ["normal", "crisis", "crisis", "normal"],
        })
        backtests, crisis = backtest_tables(risk, minimum_observations=2)
        self.assertEqual(int(backtests.iloc[0]["n_transitions"]), 2)
        self.assertEqual(int(crisis.loc[crisis.regime.eq("crisis"), "n_breaches"].iloc[0]), 2)


if __name__ == "__main__":
    unittest.main()
