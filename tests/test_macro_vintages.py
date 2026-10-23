"""Vintage revisions and delayed availability cannot change earlier macro features."""
import unittest
import numpy as np
import pandas as pd
from src.data.macro_vintages import parse_snapshot, attach_macro
from src.evaluation.walkforward import select_training, Task
from src.utils.config import load_config
from src.models.macro_sensitivity import make_model
from src.models.enet import ElasticNetRV
from src.models.ml_common import load_ml_config
from test_leakage import dataset


class MacroVintageTests(unittest.TestCase):
    def sample(self):
        records = []
        for series in ["VIXCLS", "DTWEXBGS"]:
            for day, value in [("2020-01-01", 10.), ("2020-01-04", 20.)]:
                date = pd.Timestamp(day, tz="UTC")
                records.append(dict(series_id=series, vintage_date=date, observation_date=date,
                    value=value, available_at=date+pd.Timedelta(days=2), point_in_time_verified=True))
        return pd.DataFrame(records)

    def test_asof_respects_delay_no_backfill_and_future_invariance(self):
        data = pd.DataFrame(dict(origin_date=pd.date_range("2020-01-01", periods=8, tz="UTC")))
        vintages = self.sample()
        before = attach_macro(data, vintages)
        self.assertTrue(before.log_vix_l1.iloc[:2].isna().all())
        np.testing.assert_allclose(before.log_vix_l1.iloc[2:5], np.log(10.))
        vintages.loc[vintages.vintage_date.eq(pd.Timestamp("2020-01-04", tz="UTC")), "value"] = 999.
        after = attach_macro(data, vintages)
        pd.testing.assert_series_equal(before.log_vix_l1.iloc[:5], after.log_vix_l1.iloc[:5])
        self.assertNotEqual(before.log_vix_l1.iloc[5], after.log_vix_l1.iloc[5])

    def test_snapshot_identity_and_no_future_observation(self):
        raw = b"observation_date,VIXCLS_20200103,VIXCLS_20200106\n2020-01-02,12,14\n2020-01-03,13,15\n"
        rows = parse_snapshot(raw, "VIXCLS", ["2020-01-03", "2020-01-06"])
        self.assertEqual([row["value"] for row in rows], [13., 15.])
        with self.assertRaises(ValueError):
            parse_snapshot(raw, "VIXCLS", ["2020-01-03"])
        filtered = parse_snapshot(b"observation_date,VIXCLS_20200103\n2020-01-02,12\n2020-01-04,99\n", "VIXCLS", ["2020-01-03"])
        self.assertEqual(filtered[0]["value"], 12.)
        self.assertEqual(filtered[0]["excluded_future_observations"], 1)

    def test_reject_unverified_availability_and_default_framework_macro(self):
        bad = self.sample()
        bad.loc[0, "point_in_time_verified"] = False
        with self.assertRaises(ValueError):
            attach_macro(pd.DataFrame(dict(origin_date=pd.date_range("2020-01-01", periods=3, tz="UTC"))), bad)
        with self.assertRaises(ValueError):
            select_training(pd.DataFrame(), Task(1), ["log_vix_l1"], pd.Timestamp("2021-01-01", tz="UTC"), load_config())
        with self.assertRaises(ValueError):
            select_training(pd.DataFrame(), Task(1), ["log_vix_l1"], pd.Timestamp("2021-01-01", tz="UTC"), load_config(), verified_macro=True)

    def test_macro_adapters_match_training_rows_and_ignore_future_values(self):
        data = dataset().copy()
        for name, value in [("log_vix_l1", 3.), ("log_usd_l1", 4.)]:
            data[name] = value + np.sin(np.arange(len(data))/30)*.1
            data[name+"_available_at"] = data.origin_date-pd.Timedelta(days=1)
        data.attrs.update(verified_macro_features=True, macro_dataset_sha256="fixture")
        cutoff = pd.Timestamp("2020-12-31", tz="UTC")
        options = load_ml_config()
        settings = dict(alpha=.01, l1_ratio=.5)
        models = [make_model(ElasticNetRV, settings, options, v) for v in ["macro_base", "vix_usd"]]
        samples = []
        for model in models:
            train, _, _ = select_training(data, Task(1), model.features, cutoff, load_config(), verified_macro=True)
            samples.append(train.origin_date)
        pd.testing.assert_series_equal(*samples)
        modified = data.copy()
        modified.loc[modified.origin_date.gt(cutoff), "log_vix_l1"] = 999.
        left, _, _ = select_training(data, Task(1), models[1].features, cutoff, load_config(), verified_macro=True)
        right, _, _ = select_training(modified, Task(1), models[1].features, cutoff, load_config(), verified_macro=True)
        pd.testing.assert_frame_equal(left, right)
        models[1].fit(left, Task(1))
        self.assertEqual(len(models[1].predictors), 9)


if __name__ == "__main__":
    unittest.main()
