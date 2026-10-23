"""Elastic Net log-RV, scaler fit separately inside each training window."""
import json
import warnings
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from src.evaluation.walkforward import ModelFitError
from src.models.ml_common import LogRVModel


class ElasticNetRV(LogRVModel):
    name = "enet"

    def _fit_log(self, values, target):
        options = self.options["enet"]
        converged = False
        for attempts, limit in enumerate([options["max_iterations"], options["retry_max_iterations"]], 1):
            self.estimator = make_pipeline(StandardScaler(), ElasticNet(
                alpha=self.settings["alpha"], l1_ratio=self.settings["l1_ratio"],
                max_iter=limit, tol=options["tolerance"], selection="cyclic",
                random_state=self.options["general"]["seed"]))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ConvergenceWarning)
                self.estimator.fit(values, target)
            converged = not any(issubclass(item.category, ConvergenceWarning) for item in caught)
            if converged:
                break
        if not converged:
            raise ModelFitError("Elastic Net failed convergence after deterministic retry")
        scaler, model = self.estimator.steps[0][1], self.estimator.steps[1][1]
        self.fit_info = {"attempts": attempts, "iterations": int(model.n_iter_),
                         "dual_gap": float(model.dual_gap_),
                         "scaler_mean": json.dumps(scaler.mean_.tolist()),
                         "scaler_scale": json.dumps(scaler.scale_.tolist()),
                         "coefficients": json.dumps(model.coef_.tolist()),
                         "intercept": float(model.intercept_)}

    def _predict_log(self, values):
        return self.estimator.predict(values)


class ElasticNetCore(ElasticNetRV):
    name = "enet_core"

    def __init__(self, **kwargs):
        super().__init__(core_only=True, **kwargs)
