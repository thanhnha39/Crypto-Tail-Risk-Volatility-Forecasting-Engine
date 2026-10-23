"""Causal log-RV models, train-only smearing and shared ablation eligibility."""
import hashlib
import json
import tomllib
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from src.evaluation.walkforward import BaseModel, ModelFitError, ModelForecastError
from src.features.schema import FEATURE_COLS
from src.utils.config import ROOT


def load_ml_config():
    options = tomllib.loads((ROOT / "config/backend3.toml").read_text(encoding="utf-8"))
    names = options["features"]["core"] + options["features"]["volume"]
    if not set(names).issubset(FEATURE_COLS) or len(set(names)) != len(names):
        raise ValueError("ML requires distinct declared causal features")
    if options["features"]["macro_predictive_use"]:
        raise ValueError("Macro historical release/vintage availability is not verified")
    if not options["features"]["matched_ablation_training_rows"]:
        raise ValueError("Volume ablation must retain identical training eligibility")
    if options["general"]["retransformation"] != "training_residual_mean_exp":
        raise ValueError("Unsupported log-to-variance retransformation")
    if options["general"]["gru_enabled"]:
        raise ValueError("GRU is excluded by the user's current scope")
    return options


def ml_config_hash():
    return hashlib.sha256((ROOT / "config/backend3.toml").read_bytes()).hexdigest()


def smearing_log_factor(log_target, fitted_log):
    residual = np.asarray(log_target, float) - np.asarray(fitted_log, float)
    if not len(residual) or not np.isfinite(residual).all():
        raise ModelFitError("Invalid training residuals for smearing")
    return float(logsumexp(residual) - np.log(len(residual)))


def variance_from_log(log_prediction, log_smear, floor):
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        try:
            output = np.maximum(np.exp(np.asarray(log_prediction, float) + log_smear), floor)
        except FloatingPointError as error:
            raise ModelForecastError("Nonfinite log-to-variance prediction") from error
    if not np.isfinite(output).all():
        raise ModelForecastError("Nonfinite variance prediction")
    return output


class LogRVModel(BaseModel):
    requires_target = True
    needs_history = False

    def __init__(self, settings, options=None, core_only=False, diagnostics=None, shap_records=None):
        self.options = options or load_ml_config()
        self.settings = dict(settings)
        self.core_only = core_only
        # Both ablation variants use the full feature availability mask. Only
        # predictors enter the estimator, scaler and SHAP calculations.
        self.features = self.options["features"]["core"] + self.options["features"]["volume"]
        self.predictors = self.options["features"]["core"] if core_only else self.features
        self.diagnostics = diagnostics
        self.shap_records = shap_records

    def fit(self, train, task):
        context = getattr(self, "context", {})
        record = {key: context.get(key) for key in ["symbol", "window", "refit_origin", "train_start", "train_end"]}
        record.update(model=self.name, horizon_days=task.horizon, n_train=len(train),
                      predictors=json.dumps(self.predictors), eligibility_features=json.dumps(self.features),
                      train_feature_end=train.origin_date.max(),
                      train_rows_sha256=hashlib.sha256(train.origin_date.array.asi8.tobytes()).hexdigest())
        try:
            values = train[self.predictors].to_numpy(float)
            target = train[task.ylog_col].to_numpy(float)
            if not len(train) or not np.isfinite(values).all() or not np.isfinite(target).all():
                raise ModelFitError("ML fit requires observed finite features and log targets")
            self._fit_log(values, target)
            fitted = self._predict_log(values)
            self.log_smear = smearing_log_factor(target, fitted)
            self.fit_signature = hashlib.sha256(values.tobytes() + target.tobytes() +
                json.dumps(self.settings, sort_keys=True).encode() + self.name.encode()).hexdigest()
            record.update(fit_status="ok", log_smear=self.log_smear,
                          train_log_rmse=float(np.sqrt(np.mean((target-fitted)**2))),
                          fit_signature=self.fit_signature, **getattr(self, "fit_info", {}))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError, ModelFitError) as error:
            record.update(fit_status="failed", error_message=str(error))
            if self.diagnostics is not None:
                self.diagnostics.append(record)
            raise ModelFitError(str(error)) from error
        if self.diagnostics is not None:
            self.diagnostics.append(record)
        return self

    def predict(self, test, task, history=None):
        values = test[self.predictors].to_numpy(float)
        raw = self._predict_log(values)
        self.last_test = test.copy()
        self.last_raw = np.asarray(raw, float)
        self.last_prediction = variance_from_log(raw, self.log_smear, self.options["general"]["variance_floor"])
        return self.last_prediction

    def forecast_metadata(self, task):
        return {"mean_forecast_pct": 0., "nu": np.nan, "student_t_scale_pct": np.nan,
                "innovation_distribution": "FHS_required", "fit_signature": self.fit_signature,
                "raw_log_rv_forecast": float(self.last_raw[0]), "log_smearing_factor": self.log_smear,
                "predictors": json.dumps(self.predictors), "mean_convention": "zero_for_FHS_handoff"}
