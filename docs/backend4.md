# Backend 4 — VaR, ES và backtesting

Backend 4 tạo forecast risk một ngày cho các mô hình có trong `outputs/forecasts/`; mặc định chỉ đánh giá evaluation 2021–2025, không chấm holdout. Chạy sau Backend 1–3:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_backend4 -v
.\.venv\Scripts\python.exe -m src.backend4
```

Đầu ra:

| File | Nội dung |
|---|---|
| `outputs/risk/{symbol}_{model}_risk.parquet` | VaR, ES, return thực, breach và trạng thái theo origin/confidence |
| `outputs/tables/backend4_backtesting.csv` | VaR/ES trung bình, breach rate, Kupiec UC, Christoffersen independence và conditional coverage |
| `outputs/tables/backend4_crisis_breaches.csv` | Số lần vi phạm và tỷ lệ theo regime |
| `outputs/figures/backend4_{symbol}_rolling_h1_var_q95.png` | Loss thực tế, VaR và breach trên cửa sổ rolling |
| `outputs/figures/backend4_{symbol}_rolling_h1_var_q99.png` | Như trên ở mức 99% |
| `outputs/diagnostics/backend4_validation.json` | Trạng thái, hash dữ liệu/cấu hình/forecast và thông tin phương pháp |

## Quy ước phương pháp

- Chỉ dùng horizon 1 ngày: VaR/ES là đuôi trái của return một ngày, đơn vị phần trăm. `var_loss_pct` và `es_loss_pct` là số dương theo quy ước loss; breach xảy ra khi return thực thấp hơn `return_quantile_pct`.
- GARCH/GJR-GARCH dùng Student-t chuẩn hóa về phương sai 1, với `nu` tại từng forecast và mean/σ forecast của mô hình. Không áp dụng Student-t cho các tổ hợp.
- HAR, Elastic Net, XGBoost, baseline và các tổ hợp dùng filtered historical simulation từ standardized out-of-sample return residuals của đúng model/window. Residual chỉ được đưa vào pool nếu `observable_at <= origin_date`; cửa sổ pool tối đa 730 ngày lịch. Pool dưới 500 residual được ghi `insufficient_residual_history`, không tạo risk forecast giả.
- Kupiec UC kiểm tra tỷ lệ vi phạm vô điều kiện; Christoffersen independence kiểm tra sự phụ thuộc nối tiếp; conditional coverage là tổng hai thống kê. Chuyển tiếp chỉ tính giữa các ngày lịch liên tiếp, không nối qua ngày thiếu. P-value cần diễn giải thận trọng, nhất là VaR 99% với ít breach.
- Breach theo regime dùng nhãn tại origin, được xác định bằng thông tin đã biết đến origin. Báo cáo cần xem số lượng mẫu/breach cùng với tỷ lệ.
- Bảng backtest gộp từng coin/model/window/confidence, vì vậy không gộp rolling với expanding khi diễn giải kết quả chính. Hình mặc định thể hiện rolling h1.

Thiết lập nằm trong `config/backend4.toml`. Backend 4 hiện chưa triển khai volatility targeting (RQ5 tùy chọn); không diễn giải backtest VaR/ES thành lợi nhuận chiến lược.
