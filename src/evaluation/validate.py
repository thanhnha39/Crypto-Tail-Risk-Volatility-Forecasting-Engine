"""Kiểm tra file dự báo của thành viên trước khi đưa vào bảng tổng hợp."""
import numpy as np
import pandas as pd

from src.features.schema import y_col

REQUIRED = ["asset", "model", "horizon", "origin_date", "target_date", "y_pred", "train_end"]


def truth_table(dataset: pd.DataFrame, horizons) -> pd.DataFrame:
    parts = [dataset[["asset", "date", "regime", y_col(h)]].rename(
        columns={"date": "origin_date", y_col(h): "y_true"}).assign(horizon=h) for h in horizons]
    return pd.concat(parts, ignore_index=True)


def validate_forecasts(fc: pd.DataFrame, dataset: pd.DataFrame, name="forecast"):
    """Trả về list lỗi (rỗng = hợp lệ)."""
    errs = []
    miss = [c for c in REQUIRED if c not in fc.columns]
    if miss:
        return [f"{name}: thiếu cột {miss}"]
    if fc.duplicated(["asset", "model", "horizon", "origin_date"]).any():
        errs.append(f"{name}: trùng (asset, model, horizon, origin_date)")
    p = fc["y_pred"].astype(float)
    if (~np.isfinite(p)).any() or (p <= 0).any():
        errs.append(f"{name}: y_pred phải hữu hạn và > 0")
    lag = (pd.to_datetime(fc["origin_date"]) - pd.to_datetime(fc["train_end"])).dt.days
    if (lag < fc["horizon"]).any():
        errs.append(f"{name}: LEAKAGE - train_end phải <= origin_date - horizon (nhãn chưa biết tại origin)")
    td = (pd.to_datetime(fc["target_date"]) - pd.to_datetime(fc["origin_date"])).dt.days
    if (td != fc["horizon"]).any():
        errs.append(f"{name}: target_date phải = origin_date + horizon ngày")
    tt = truth_table(dataset, sorted(fc["horizon"].unique()))
    m = fc.merge(tt, on=["asset", "origin_date", "horizon"], how="left")
    if m["y_true"].notna().sum() == 0:
        errs.append(f"{name}: không khớp được origin_date nào với dataset")
    if "y_true" in fc.columns:
        both = m.dropna(subset=["y_true_x", "y_true_y"]) if "y_true_x" in m else m.iloc[0:0]
        if len(both) and not np.allclose(both["y_true_x"], both["y_true_y"], rtol=1e-6):
            errs.append(f"{name}: y_true trong file khác dataset (harness luôn dùng y_true từ dataset)")
    return errs
