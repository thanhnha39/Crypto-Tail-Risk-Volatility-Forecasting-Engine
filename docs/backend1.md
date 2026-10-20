# Backend 1 – Feature & Khung đánh giá (Crypto Volatility Forecasting)

Xử lý dữ liệu 5 phút -> dataset point-in-time -> khung walk-forward dùng chung -> bảng/hình/Chương 5.

## Chạy nhanh
```bash
pip install -r requirements.txt
make all            # synth(dữ liệu mô phỏng) -> dataset -> test -> baselines -> aggregate -> report
```
**Dữ liệu thật:** `python -m src.data.binance_download klines --symbol BTCUSDT --start 2019-01 --end 2025-12`
(tương tự ETHUSDT) và `... fred`; đặt `data_source: binance` trong `config/config.yaml`; bỏ bước `synth`; `make dataset test baselines aggregate report`.
> Bộ tải chưa được chạy thử trong môi trường dựng repo (không có mạng). Thử 1 tháng trước khi tải cả giai đoạn.

## Cấu trúc
| Đường dẫn | Nội dung |
|---|---|
| `src/features/` | `intraday.py` (5' -> ngày), `build_features.py`, `regimes.py`, `schema.py` (hợp đồng cột) |
| `src/evaluation/` | `metrics.py` (RMSE/MAE/QLIKE), `dm.py` (DM+HLN), `walkforward.py`, `baselines.py`, `validate.py`, `aggregate.py`, `make_report.py` |
| `tests/test_leakage.py` | 12 test chống leakage + sanity khung (naive, oracle, DM) |
| `data/processed/dataset.parquet` | 1 dòng = asset × ngày; feature + `regime` + nhãn `y_*` |
| `outputs/forecasts/` | file dự báo của mọi mô hình (định dạng: `docs/forecast_format.md`) |
| `outputs/tables`, `outputs/figures` | so sánh mô hình, DM vs HAR-RV, regime; forecast vs actual, rolling QLIKE |
| `paper/chapter5_results.md` | Chương 5 tự sinh từ bảng |
| `docs/leakage_review.md` | phiếu review chéo chống leakage |

## Lưu ý quan trọng
- Mặc định repo chạy trên **dữ liệu mô phỏng** -> kết quả chỉ để kiểm tra pipeline.
- Nếu không có `pyarrow`, code tự ghi `.csv.gz` thay `.parquet` (cùng tên) và đọc lại bình thường.
- Regime là **đề xuất** (`config.regimes`); nhóm cần chốt ngưỡng trước khi chạy kết quả cuối.
