# Hợp đồng file dự báo cho các backend

Tên: `outputs/forecasts/{symbol}_{model}.parquet`, ví dụ `BTCUSDT_garch.parquet`. Một file chứa cả horizon 1/7 và rolling/expanding. Model chính: `har_rv`, `garch`, `gjr_garch`, `xgboost`. File risk `{symbol}_{model}_risk.parquet` được module tổng hợp volatility bỏ qua; schema VaR/ES thuộc phần risk của nhóm.

| Cột | Kiểu / quy tắc |
|---|---|
| symbol, model | string |
| horizon_days | int 1 hoặc 7 |
| window | rolling / expanding |
| origin_date | Ngày t, timestamp UTC tại đầu ngày; thông tin dùng đến hết ngày này |
| target_start | t+1 |
| target_date | t+h, ngày kết thúc target |
| forecast_available_at | t+1 lúc 00:00 UTC, khi toàn bộ nến ngày t đã kết thúc |
| rv_forecast_pct2 | Dự báo tổng RV h ngày (%²), hữu hạn và >0 khi status=ok |
| volatility_forecast_pct | Căn dự báo RV (%) |
| refit_origin | Origin refit gần nhất theo neo 31/12/2020, cách 5 ngày |
| train_start | Biên dưới cửa sổ ngày lịch, không phải dòng hợp lệ đầu tiên |
| train_end | Ngày kết thúc nhãn/quan sát cuối đã dùng fit, phải ≤ refit_origin |
| train_feature_end | Ngày origin cuối của dòng train; với supervised phải ≤ refit_origin−h |
| n_train | Số dòng thực dùng sau lọc |
| training_kind | supervised / observations / combination |
| status | ok / missing_features / insufficient_train / fit_failed / forecast_failed / component_unavailable |
| protocol_sha256, dataset_sha256 | Đọc từ dataset_meta.json, không thay khi chưa rebuild dữ liệu |

Khóa duy nhất: symbol, model, horizon_days, window, origin_date. Dòng không dự báo được vẫn ghi vào file với status rõ và prediction NaN; không dùng 0 làm thay thế. Không cần gửi y_true; tổng hợp luôn lấy target chuẩn từ dataset. Cùng một lịch, coin và horizon/window phải có timestamp UTC nhất quán.

## Adapter khuyến nghị

```python
import json
import numpy as np
import pandas as pd
from src.evaluation.walkforward import BaseModel, Task, walk_forward
from src.utils.config import ROOT, load_config

class MyModel(BaseModel):
    name = "xgboost"
    features = ["log_rv_d", "log_rv_w", "log_rv_m", "log_park", "log_turn_rel"]
    requires_target = True
    def fit(self, train, task):
        # fit bằng train[self.features], train[task.ylog_col]
        # scaler chỉ fit train; siêu tham số đã khóa từ warmup.
        ...
    def predict(self, test, task, history=None):
        # Một origin mỗi lần; không có target tương lai trong test/history.
        # Chuyển dự báo log về variance mức; ghi rõ cách hiệu chỉnh retransformation.
        return np.array([positive_variance_forecast])

cfg = load_config()
dataset = pd.read_parquet(ROOT / "data/processed/dataset.parquet")
meta = json.loads((ROOT / "data/processed/dataset_meta.json").read_text())
parts = []
for window in ["rolling", "expanding"]:
    for h in [1, 7]:
        parts.append(walk_forward(dataset[dataset.symbol.eq("BTCUSDT")], MyModel, Task(h), cfg, window))
fc = pd.concat(parts, ignore_index=True)
fc["protocol_sha256"] = meta["protocol_sha256"]
fc["dataset_sha256"] = meta["dataset_sha256"]
fc.to_parquet(ROOT / "outputs/forecasts/BTCUSDT_xgboost.parquet", index=False)
```

GARCH/GJR có thể dùng `features=["ret_d"]`, `requires_target=False`. Phần fit dùng return quan sát trong cửa sổ; phần predict cập nhật conditional state bằng history đã biết sau refit và trả tổng variance h bước. Không mặc định nhân 7 nếu mô hình có cấu trúc dự báo nhiều bước.

Sau khi có file mới chạy `python -m src.evaluation.aggregate`; kiểm tra model_comparison, coverage, DM và availability. Tác giả model vẫn chịu trách nhiệm ghi metadata đúng dữ liệu thực đã dùng; validator không chứng minh nội bộ một model ngoại bộ không dùng nguồn khác.

## Phần bổ sung Backend 2

Backend 2 đã triển khai `har_rv`, `garch`, `gjr_garch` và tổ hợp trung bình phương sai `combo_econ`. Cột tùy chọn gồm `error_message`, `mean_forecast_pct`, `nu`, `innovation_distribution`, `student_t_scale_pct`, `variance_path_pct2`, `fit_signature`, `model_config_sha256`; tổ hợp thêm danh sách thành phần/trọng số. Hash model config được lưu riêng, không làm thay đổi hash shared dataset/protocol.

`fit_failed` là ước lượng thất bại, `forecast_failed` là trạng thái dự báo không hợp lệ, `component_unavailable` là tổ hợp thiếu ít nhất một thành phần hợp lệ. Các dòng này không có prediction. `training_kind=combination` dùng metadata thời gian của các thành phần đã được validator kiểm tra riêng.

Bản xuất σ nằm ở `outputs/volatility/{symbol}_{model}.parquet`, có `variance_pct2`, `sigma_pct`, μ và ν khi phù hợp. Đây chưa phải file VaR/ES. Với Student-t h1, scale của Student-t thông thường là `sigma_pct * sqrt((nu-2)/nu)`; h7 không gắn nhãn phân phối Student-t chính xác và scale để trống. Hướng dẫn đầy đủ ở `docs/backend2.md`.
