"""Khung walk-forward DÙNG CHUNG cho mọi mô hình (HAR, GARCH-biến thể, ML, DL...).

Quy tắc chống leakage (được kiểm thử trong tests/test_leakage.py):
  * Origin t = cuối ngày t; feature của origin t chỉ dùng thông tin <= t.
  * Nhãn y_{t'} (h bước) chỉ biết sau ngày t'+h  =>  tại origin t chỉ train trên t' <= t - h.
  * Refit theo block `refit_every` origin; cả block dùng mô hình fit tại origin đầu block.
Giao diện mô hình:  class M(BaseModel): features=[...]; fit(train_df, task); predict(test_df, task)->RV level (>0)
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

from src.features.schema import y_col, ylog_col

FORECAST_COLS = ["asset", "model", "horizon", "origin_date", "target_date", "y_pred", "train_end", "n_train"]


@dataclass(frozen=True)
class Task:
    horizon: int

    @property
    def y_col(self):
        return y_col(self.horizon)

    @property
    def ylog_col(self):
        return ylog_col(self.horizon)


class BaseModel:
    name = "base"
    features: list = []

    def fit(self, train: pd.DataFrame, task: Task):
        raise NotImplementedError

    def predict(self, test: pd.DataFrame, task: Task) -> np.ndarray:
        raise NotImplementedError


def iter_splits(d: pd.DataFrame, task: Task, features, scheme="expanding", min_train=365,
                window=None, refit_every=5, test_start=None, test_end=None):
    """Yield (train_df, test_df). Dùng trực tiếp được cho ML/DL cần vòng lặp riêng."""
    h = task.horizon
    d = d.sort_values("date").reset_index(drop=True)
    assert d["date"].is_unique, "mỗi asset chỉ 1 dòng/ngày"
    feat_ok = d[list(features)].notna().all(axis=1)
    train_ok = feat_ok & d[task.y_col].notna() & d[task.ylog_col].notna()
    in_test = feat_ok.copy()
    if test_start is not None:
        in_test &= d["date"] >= pd.Timestamp(test_start)
    if test_end is not None:
        in_test &= d["date"] <= pd.Timestamp(test_end)
    orig = np.flatnonzero(in_test.values)
    pos = 0
    while pos < len(orig):
        block = orig[pos:pos + refit_every]
        cutoff = d["date"].iloc[block[0]] - pd.Timedelta(days=h)
        tr = d[(d["date"] <= cutoff) & train_ok]
        if scheme == "rolling":
            tr = tr.iloc[-window:]
        if len(tr) < min_train:
            pos += 1          # chưa đủ dữ liệu train -> bỏ origin này, thử origin kế
            continue
        yield tr, d.iloc[block]
        pos += len(block)


def walk_forward(data: pd.DataFrame, model_factory, task: Task, asset: str, **kw) -> pd.DataFrame:
    rows = []
    for tr, te in iter_splits(data, task, model_factory().features, **kw):
        m = model_factory()
        m.fit(tr, task)
        p = np.asarray(m.predict(te, task), float)
        if p.shape != (len(te),) or not np.all(np.isfinite(p)) or np.any(p <= 0):
            raise ValueError(f"{m.name}: dự báo phải hữu hạn và > 0")
        rows.append(pd.DataFrame({
            "asset": asset, "model": m.name, "horizon": task.horizon,
            "origin_date": te["date"].values,
            "target_date": te["date"].values + np.timedelta64(task.horizon, "D"),
            "y_pred": p, "train_end": tr["date"].max(), "n_train": len(tr)}))
    if not rows:
        return pd.DataFrame(columns=FORECAST_COLS)
    return pd.concat(rows, ignore_index=True)[FORECAST_COLS]


def run_all_assets(dataset, model_factory, horizon, assets=None, **kw):
    out = []
    for a in (assets or dataset["asset"].unique()):
        out.append(walk_forward(dataset[dataset["asset"] == a], model_factory, Task(horizon), a, **kw))
    return pd.concat(out, ignore_index=True)
