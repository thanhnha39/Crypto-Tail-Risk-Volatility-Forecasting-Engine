"""ML time boundaries, train-only transforms, seeded models and exact TreeSHAP."""
import contextlib
import copy
import io
import json
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.evaluation.walkforward import Task, select_training, walk_forward, ModelForecastError
from src.models.enet import ElasticNetRV, ElasticNetCore
from src.models.xgb import XGBoostRV, XGBoostCore
from src.models.ml_common import load_ml_config, ml_config_hash, smearing_log_factor, variance_from_log
from src.models.tune_ml import tune, warmup_splits, warmup_fingerprint, prepare_selection
from src.utils.config import load_config, protocol_hash
from test_leakage import dataset


def setup():
    config = copy.deepcopy(load_config())
    config["data"]["symbols"] = ["BTCUSDT"]
    options = copy.deepcopy(load_ml_config())
    options["enet"].update(alpha_grid=[.01], l1_ratio_grid=[.5])
    options["xgboost"].update(max_depth_grid=[2], learning_rate_grid=[.1], num_boost_round_grid=[8])
    return dataset().copy(), config, options


def fitted(cls=ElasticNetRV, data=None, options=None, shap_records=None):
    data = dataset().copy() if data is None else data
    options = options or load_ml_config()
    settings = {"alpha": .01, "l1_ratio": .5} if "Elastic" in cls.__name__ else {
        "max_depth": 2, "learning_rate": .1, "num_boost_round": 8}
    model = cls(settings=settings, options=options, shap_records=shap_records)
    task = Task(1)
    cutoff = pd.Timestamp("2020-12-31", tz="UTC")
    train, lower, end = select_training(data, task, model.features, cutoff, load_config())
    model.set_context({"symbol": "BTCUSDT", "window": "rolling", "refit_origin": cutoff,
                       "train_start": lower, "train_end": end})
    model.fit(train, task)
    test = data.loc[data.origin_date.eq(cutoff), ["symbol", "origin_date", *model.features]]
    return model, train, test


class Backend3Tests(unittest.TestCase):
    def test_scaler_uses_training_rows_only(self):
        model, train, test = fitted()
        scaler = model.estimator.steps[0][1]
        np.testing.assert_allclose(scaler.mean_, train[model.predictors].mean().to_numpy())
        before = scaler.mean_.copy()
        future = test.copy()
        future[model.predictors] = future[model.predictors]+2
        model.predict(future, Task(1))
        np.testing.assert_array_equal(before, scaler.mean_)

    def test_log_to_variance_units_and_smearing(self):
        log_factor = smearing_log_factor(np.log([2., 8.]), np.log([1., 2.]))
        self.assertAlmostEqual(np.exp(log_factor), 3.)
        np.testing.assert_allclose(variance_from_log(np.log([4.]), log_factor, 1e-10), [12.])
        self.assertAlmostEqual(np.sqrt(12.)**2, 12.)

    def test_exponential_overflow_is_reported_not_replaced_by_a_fake_forecast(self):
        with self.assertRaises(ModelForecastError):
            variance_from_log([1000.], 0., 1e-10)

    def test_seeded_enet_and_xgb_are_repeatable(self):
        for cls in [ElasticNetRV, XGBoostRV]:
            first, _, test = fitted(cls)
            second, _, _ = fitted(cls)
            np.testing.assert_array_equal(first.predict(test, Task(1)), second.predict(test, Task(1)))

    def test_core_estimators_do_not_use_volume_values(self):
        original = dataset().copy()
        altered = original.copy()
        altered[["log_qv", "log_turn_rel"]] += 1000
        for cls in [ElasticNetCore, XGBoostCore]:
            first, _, test = fitted(cls, original)
            second, _, other_test = fitted(cls, altered)
            self.assertFalse(set(first.predictors) & {"log_qv", "log_turn_rel"})
            np.testing.assert_array_equal(first.predict(test, Task(1)), second.predict(other_test, Task(1)))

    def test_ablation_uses_identical_training_eligibility(self):
        data = dataset().copy()
        data.loc[data.index[500], "log_qv"] = np.nan
        for full_cls, core_cls in [(ElasticNetRV, ElasticNetCore), (XGBoostRV, XGBoostCore)]:
            full, train, _ = fitted(full_cls, data)
            core, core_train, _ = fitted(core_cls, data)
            np.testing.assert_array_equal(train.origin_date, core_train.origin_date)
            self.assertEqual(full.features, core.features)
            self.assertFalse(500 in train.index)

    def test_warmup_tuning_cannot_see_evaluation_or_holdout(self):
        data, config, options = setup()
        future = data.origin_date.gt(pd.Timestamp("2020-12-31", tz="UTC"))
        altered = data.copy()
        columns = [c for c in data if c.startswith("y_")] + options["features"]["core"] + options["features"]["volume"]
        altered.loc[future, columns] = 100000.
        with contextlib.redirect_stdout(io.StringIO()):
            first, scores = tune(data, config, options)
            second, other_scores = tune(altered, config, options)
        self.assertEqual(first, second)
        pd.testing.assert_frame_equal(scores, other_scores)
        self.assertEqual(warmup_fingerprint(data, config, options), warmup_fingerprint(altered, config, options))

    def test_validation_split_purges_unfinished_h7_training_labels(self):
        data, config, options = setup()
        for horizon in [1, 7]:
            train, validation, _ = warmup_splits(data, "BTCUSDT", Task(horizon), config, options)
            self.assertTrue(train[f"target_end_h{horizon}"].le(pd.Timestamp("2020-06-30", tz="UTC")).all())
            self.assertTrue(validation[f"target_start_h{horizon}"].ge(pd.Timestamp("2020-07-01", tz="UTC")).all())
            self.assertTrue(validation[f"target_end_h{horizon}"].le(pd.Timestamp("2020-12-31", tz="UTC")).all())

    def test_tuning_rejects_validation_into_evaluation(self):
        data, config, options = setup()
        options["tuning"]["validation_target_end"] = "2021-01-01"
        with self.assertRaises(ValueError):
            warmup_splits(data, "BTCUSDT", Task(1), config, options)

    def test_frozen_selection_is_reused_without_retuning(self):
        data, config, options = setup()
        locked = {"ml_config_sha256": ml_config_hash(), "protocol_sha256": protocol_hash(config),
                  "dataset_sha256": "test_hash", "warmup_fingerprint": warmup_fingerprint(data, config, options)}
        with patch("src.models.tune_ml.LOCK") as lock, patch("src.models.tune_ml.tune") as tuner:
            lock.exists.return_value = True
            lock.read_text.return_value = json.dumps(locked)
            self.assertEqual(prepare_selection(data, {"dataset_sha256": "test_hash"}, config, options), locked)
            tuner.assert_not_called()
            with self.assertRaises(ValueError):
                prepare_selection(data, {"dataset_sha256": "other_hash"}, config, options)

    def test_native_shap_reconstructs_current_origin_prediction(self):
        records = []
        model, _, test = fitted(XGBoostRV, shap_records=records)
        value = model.predict(test, Task(1))[0]
        model.forecast_metadata(Task(1))
        row = records[0]
        reconstructed = row["base_value"] + sum(row["shap_"+name] for name in model.predictors)
        self.assertAlmostEqual(reconstructed, row["raw_log_prediction"], places=5)
        self.assertAlmostEqual(np.exp(reconstructed+row["log_smearing_factor"]), value, places=4)
        self.assertEqual(row["fit_signature"], model.fit_signature)
        self.assertEqual(row["origin_date"], test.origin_date.iloc[0])

    def test_forecasts_ignore_future_targets_and_features(self):
        data, config, options = setup()
        cutoff = pd.Timestamp("2021-01-05", tz="UTC")
        data.loc[data.origin_date.gt(cutoff), "target_segment_h1"] = "out_of_scope"
        altered = data.copy()
        future = data.origin_date.gt(cutoff)
        altered.loc[future, options["features"]["core"]+options["features"]["volume"]] = 100000.
        altered.loc[altered.target_end_h1.gt(cutoff), "y_rv_h1"] = 1e7
        altered.loc[altered.target_end_h1.gt(cutoff), "y_logrv_h1"] = np.log(1e7)
        for cls in [ElasticNetRV, XGBoostRV]:
            settings = {"alpha": .01, "l1_ratio": .5} if cls==ElasticNetRV else {
                "max_depth": 2, "learning_rate": .1, "num_boost_round": 8}
            def factory():
                return cls(settings=settings, options=options)
            first = walk_forward(data, factory, Task(1), config)
            second = walk_forward(altered, factory, Task(1), config)
            np.testing.assert_array_equal(first.rv_forecast_pct2, second.rv_forecast_pct2)


if __name__ == "__main__":
    unittest.main()
