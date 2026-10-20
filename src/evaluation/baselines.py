"""Mô hình baseline: naive (kiểm tra khung), hist-mean, HAR-RV (benchmark chính), HAR-RV-log."""
import numpy as np

from src.evaluation.walkforward import BaseModel, Task
from src.features.schema import HAR_COLS, HAR_LOG_COLS


class NaiveRW(BaseModel):
    """Dự báo RV_{t+1..t+h} = RV_t (no-change)."""
    name = "naive_rw"
    features = ["rv_d"]

    def fit(self, train, task):
        return self

    def predict(self, test, task):
        return test["rv_d"].values


class HistMean(BaseModel):
    """Trung bình y trên cửa sổ train (unconditional)."""
    name = "hist_mean"
    features = ["rv_d"]

    def fit(self, train, task):
        self.mu = float(train[task.y_col].mean())
        return self

    def predict(self, test, task):
        return np.full(len(test), self.mu)


def _ols(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return beta, X1


class HARRV(BaseModel):
    """Corsi (2009): y = b0 + bd*RV_t + bw*RV5_t + bm*RV22_t (OLS, level). Sàn dự báo = min(y_train)."""
    name = "har_rv"
    features = HAR_COLS

    def fit(self, train, task):
        y = train[task.y_col].values
        self.beta, _ = _ols(train[self.features].values, y)
        self.floor = float(y.min())
        return self

    def predict(self, test, task):
        X1 = np.column_stack([np.ones(len(test)), test[self.features].values])
        return np.maximum(X1 @ self.beta, self.floor)


class HARRVLog(BaseModel):
    """HAR trên log RV; chuyển về level bằng exp(xb + 0.5*s2) (hiệu chỉnh lognormal)."""
    name = "har_rv_log"
    features = HAR_LOG_COLS

    def fit(self, train, task):
        y = train[task.ylog_col].values
        self.beta, X1 = _ols(train[self.features].values, y)
        res = y - X1 @ self.beta
        self.s2 = float(res.var(ddof=X1.shape[1]))
        return self

    def predict(self, test, task):
        X1 = np.column_stack([np.ones(len(test)), test[self.features].values])
        return np.exp(X1 @ self.beta + 0.5 * self.s2)


BASELINES = {m.name: m for m in (NaiveRW, HistMean, HARRV, HARRVLog)}
