"""Window sensitivity must not compare forecasts on unequal dates."""
import unittest
import pandas as pd
from src.evaluation.robustness import robustness_table
from src.evaluation.metrics import add_losses
from src.utils.config import load_config


class RobustnessTests(unittest.TestCase):
    def test_pairs_windows_and_models_on_identical_dates(self):
        records = []
        for day in pd.date_range("2021-01-01", periods=40, tz="UTC"):
            for model in ["har_rv", "enet"]:
                for window in ["rolling", "expanding"]:
                    if day.day == 5 and window == "expanding" and model == "enet":
                        continue
                    records.append(dict(symbol="BTCUSDT", horizon_days=1, origin_date=day,
                        model=model, window=window, y_true=2., rv_forecast_pct2=2. if window == "rolling" else 3.))
        result = robustness_table(add_losses(pd.DataFrame(records)), load_config())
        self.assertEqual(set(result.n), {38.})
        self.assertTrue(result.loc[result.window.eq("expanding"), "QLIKE_minus_rolling_same_horizon"].gt(0).all())
        self.assertTrue(result.loc[result.window.eq("rolling"), "QLIKE_minus_rolling_same_horizon"].eq(0).all())

    def test_rejects_missing_window(self):
        rows = pd.DataFrame([dict(symbol="BTCUSDT", horizon_days=1, origin_date=pd.Timestamp("2021-01-01", tz="UTC"),
            model="enet", window="rolling", y_true=2., rv_forecast_pct2=2.)])
        with self.assertRaises(ValueError):
            robustness_table(add_losses(rows), load_config())


if __name__ == "__main__":
    unittest.main()
