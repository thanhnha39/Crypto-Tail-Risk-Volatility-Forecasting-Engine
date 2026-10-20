# Định dạng file dự báo (áp dụng cho MỌI mô hình trong nhóm)

Mỗi mô hình ghi **một file cho mỗi (model, asset, horizon)** vào `outputs/forecasts/`:

    outputs/forecasts/{model}__{asset}__h{horizon}.parquet      # vd har_rv__BTCUSDT__h1.parquet

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `asset` | str | `BTCUSDT`, `ETHUSDT` |
| `model` | str | tên duy nhất, chữ thường (`har_rv`, `xgb`, `lstm`, `garch_t`...) |
| `horizon` | int | 1 hoặc 7 |
| `origin_date` | date | ngày t = thời điểm ra dự báo (cuối ngày t, UTC) |
| `target_date` | date | `origin_date + horizon` ngày |
| `y_pred` | float | dự báo **trung bình RV_{t+1..t+h} ở LEVEL (đơn vị %²), > 0**. Mô hình log phải tự đổi về level (vd `exp(xb + 0.5 s²)`) |
| `train_end` | date | ngày `date` cuối cùng của mẫu train đã dùng. **Phải thoả `train_end <= origin_date - horizon`** |
| `n_train` | int | (tuỳ chọn) số quan sát train |

Quy tắc:
1. **Không ghi `y_true`** (hoặc nếu ghi thì phải khớp dataset). Bộ tổng hợp luôn lấy `y_true` từ `dataset.parquet`.
2. Mỗi `(asset, model, horizon, origin_date)` xuất hiện đúng 1 lần; không NaN/inf; `y_pred > 0`.
3. Bảng so sánh chỉ tính trên **origin chung** của mọi mô hình -> mô hình nào thiếu origin sẽ làm co mẫu của tất cả.
   Hãy dùng `evaluation.test_start` trong config và dự báo đủ các ngày có feature.
4. Chạy `python -m src.evaluation.aggregate` để validate; lỗi (đặc biệt `LEAKAGE`) sẽ dừng pipeline.

## Cách tích hợp mô hình mới (2 cách)

**A. Giao diện `BaseModel`** (khuyến nghị cho ML/GARCH-hybrid):

```python
from src.evaluation.walkforward import BaseModel, Task, run_all_assets
class MyXGB(BaseModel):
    name = "xgb"
    features = ["log_rv_d", "log_rv_w", "log_rv_m", "log_park", "log_turn_rel", "log_vix_l1"]
    def fit(self, train, task):       # train đã lọc: chỉ nhãn đã biết tại origin, không NaN
        ...fit trên train[self.features], train[task.ylog_col]
    def predict(self, test, task):    # trả về RV LEVEL > 0, len = len(test)
        return np.exp(pred_log + 0.5 * self.s2)
fc = run_all_assets(dataset, MyXGB, horizon=1, **eval_kwargs(cfg))   # xem run_baselines.py
```

**B. Vòng lặp riêng** (LSTM/Transformer cần chuỗi): dùng `iter_splits(d, task, features, ...)` để nhận
`(train_df, test_df)` đúng luật chống leakage, rồi tự ghép cột theo bảng trên. Với mô hình chuỗi, cửa sổ lookback
cho origin t chỉ được lấy từ dòng có `date <= t` trong **dataset** (không dùng `y_*`).

## Cột trong `dataset.parquet`
Xem `src/features/schema.py`. Dòng `date = t` chỉ chứa thông tin tới hết ngày t. Cột `y_rv_h{h}` / `y_logrv_h{h}` là **nhãn**
(tương lai) -> không bao giờ đưa vào `features`. `regime` tính point-in-time tại t.
