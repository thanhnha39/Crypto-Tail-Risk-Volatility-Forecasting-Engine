# Crypto Tail Risk and Volatility Forecasting Engine

Repo nghiên cứu dự báo realized variance và rủi ro đuôi BTC/ETH. **main đã tích
hợp Data và Backend 1–4**, kèm code, dữ liệu và kết quả evaluation thật.

## Bắt đầu từ đây

| Bạn cần làm gì | Đọc file này |
|---|---|
| Viết luận, lấy số liệu và diễn giải kết quả | **[Bàn giao viết luận](docs/BAN_GIAO_VIET_LUAN.md)** |
| Chạy code hoặc làm tiếp dashboard | **[Hướng dẫn kỹ thuật](docs/TECHNICAL_GUIDE.md)** |
| Kiểm tra quy định nghiên cứu | [GROUP_PROTOCOL.md](docs/GROUP_PROTOCOL.md) |
| Hiểu biến và dữ liệu thiếu | [data_dictionary.md](docs/data_dictionary.md), [data_quality_report.md](docs/data_quality_report.md) |
| Kiểm tra nguồn | [source_log.md](docs/source_log.md), [source_log.csv](docs/source_log.csv) |
| Nhận schema forecast và risk | [forecast_format.md](docs/forecast_format.md) |
| Hiểu availability VIX/USD | [macro_sensitivity.md](docs/macro_sensitivity.md) |

File bàn giao luận có các bảng số liệu, DM, regime, ablation volume/macro,
VaR/ES và stress, chiến lược, hình nên trích và giới hạn cần giữ khi diễn giải.
Các ghi chú Backend 1–4 và checklist review cũ đã được gom vào hướng dẫn kỹ thuật;
lịch sử Git vẫn giữ bản trước.

## Phạm vi hiện tại

- Binance **spot BTCUSDT/ETHUSDT**, nến 5 phút UTC, snapshot đến **17/10/2026**.
- 12/2018 là đệm, warmup 2019–2020, evaluation **2021–2025**; holdout 2026 chưa chấm mô hình.
- Daily RV %²; rolling 730 ngày lịch, refit mỗi 5 ngày; h1 chính, h7 sensitivity.
- Bốn model chính: HAR-RV, GARCH-t, GJR-GARCH-t, XGBoost. Bổ sung Elastic Net,
  naive, historical mean và hai tổ hợp; GRU tùy chọn chưa triển khai.
- Macro chỉ nằm trong sensitivity ALFRED riêng, không trong model chính.
- Risk h1: VaR/ES 95%/99%, kiểm định, stress windows và volatility targeting có phí.

Đây là kết quả nghiên cứu/mô phỏng. Unit test đạt không có nghĩa mọi model vượt
benchmark hay ES đã được kiểm định hiệu chuẩn. Kết luận thống kê nằm trong file bàn giao.

## Chạy từ gốc repo

Python 3.12 và môi trường đã cài requirements:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B run_tests.py
.\.venv\Scripts\python.exe -B -X utf8 verify_backend4.py --input-root .
```

Kết quả đã được lưu sẵn. Không cần chạy fit lại để viết luận.

| Thư mục | Nội dung |
|---|---|
| `data/raw/` | ZIP/CSV nguồn, checksum và metadata |
| `data/interim/` | Nến sạch, daily QA, nguồn macro |
| `data/processed/` | Dataset daily, target, lịch và regime |
| `outputs/forecasts/` | 18 file dự báo variance chính, gồm h1/h7 và rolling/expanding |
| `outputs/tables/` | So sánh cùng mẫu, DM, regime, robustness, SHAP và ablation |
| `outputs/diagnostics/` | Tham số, hội tụ, residual, kiểm tra handoff |
| `outputs/sensitivity/macro/` | Forecast và kiểm tra macro riêng |
| `outputs/risk/` | VaR/ES, coverage/backtest, crisis, daily strategy paths |
| `outputs/figures/` | Hình dữ liệu, forecast, regime, SHAP và risk |
| `outputs/reporting/` | Manifest truy nguồn file bàn giao luận |

Chạy lại pipeline theo thứ tự khi cần: `python -m src.backend1`,
`python -m src.backend2`, `python -m src.backend3`, `python -m src.backend4`.
Lệnh fit không cần thiết cho người chỉ đọc số liệu. Lệnh tạo lại bàn giao từ
kết quả có sẵn: `python -m src.reporting.build_handoff`.

## Trạng thái tiếp theo

Dashboard, biên soạn luận và lượt holdout cuối được thực hiện sau khi nhóm chốt
thiết kế. Không dùng holdout để chọn lại siêu tham số hoặc làm đẹp kết quả.
Mọi ngày thiếu giữ trạng thái rõ; không biến NaN thành dự báo/rủi ro bằng 0.
