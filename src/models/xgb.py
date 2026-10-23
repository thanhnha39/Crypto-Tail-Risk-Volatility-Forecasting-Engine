"""Seeded CPU XGBoost log-RV with native exact TreeSHAP at OOS origins."""
import numpy as np
import pandas as pd
import xgboost as xgb
from src.evaluation.walkforward import ModelFitError, ModelForecastError
from src.models.ml_common import LogRVModel


class XGBoostRV(LogRVModel):
    name = "xgboost"

    def _matrix(self, values, target=None):
        return xgb.DMatrix(values, label=target, feature_names=self.predictors,
                           nthread=self.options["xgboost"]["nthread"])

    def _fit_log(self, values, target):
        options = self.options["xgboost"]
        params = {"objective": "reg:squarederror", "tree_method": options["tree_method"],
                  "seed": self.options["general"]["seed"], "nthread": options["nthread"],
                  "max_depth": self.settings["max_depth"], "eta": self.settings["learning_rate"],
                  "min_child_weight": options["min_child_weight"], "lambda": options["reg_lambda"],
                  "subsample": options["subsample"], "colsample_bytree": options["colsample_bytree"],
                  "verbosity": 0}
        try:
            self.estimator = xgb.train(params, self._matrix(values, target),
                num_boost_round=self.settings["num_boost_round"], verbose_eval=False)
        except xgb.core.XGBoostError as error:
            raise ModelFitError(str(error)) from error
        self.fit_info = {"boosting_rounds": int(self.estimator.num_boosted_rounds()),
                         "nthread": options["nthread"], "seed": params["seed"]}

    def _predict_log(self, values):
        return self.estimator.predict(self._matrix(values)).astype(float)

    def forecast_metadata(self, task):
        extra = super().forecast_metadata(task)
        if self.shap_records is not None:
            contributions = self.estimator.predict(self._matrix(self.last_test[self.predictors].to_numpy(float)),
                pred_contribs=True, approx_contribs=False).astype(float)[0]
            identity_error = float(abs(contributions.sum() - self.last_raw[0]))
            if not np.isfinite(contributions).all() or not np.isfinite(identity_error) or identity_error > 5e-5:
                raise ModelForecastError("Native TreeSHAP does not reconstruct the raw prediction")
            row = self.last_test.iloc[0]
            entry = {"symbol": row.symbol, "model": self.name, "window": self.context["window"],
                     "horizon_days": task.horizon, "origin_date": row.origin_date,
                     "target_date": row.origin_date+pd.Timedelta(days=task.horizon),
                     "refit_origin": self.context["refit_origin"], "fit_signature": self.fit_signature,
                     "base_value": float(contributions[-1]), "raw_log_prediction": float(self.last_raw[0]),
                     "log_smearing_factor": self.log_smear, "rv_forecast_pct2": float(self.last_prediction[0]),
                     "shap_identity_error": identity_error}
            for name, value in zip(self.predictors, contributions[:-1]):
                entry["shap_"+name] = float(value)
                entry["value_"+name] = float(row[name])
            self.shap_records.append(entry)
            extra["shap_identity_error"] = identity_error
        return extra


class XGBoostCore(XGBoostRV):
    name = "xgboost_core"

    def __init__(self, **kwargs):
        super().__init__(core_only=True, **kwargs)
