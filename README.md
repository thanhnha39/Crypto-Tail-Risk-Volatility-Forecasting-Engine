# Crypto-Tail-Risk-Volatility-Forecasting-Engine
A cryptocurrency volatility forecasting and tail-risk analysis engine for BTC and ETH, combining GARCH, HAR-RV, and XGBoost models with VaR/ES backtesting and an interactive Streamlit dashboard.


## Cấu trúc

```text
data/raw/       Dữ liệu gốc, ZIP, checksum, metadata và raw Parquet
data/interim/   Nến sạch, chất lượng theo ngày và tham chiếu QA
data/processed/ Chưa có dataset mô hình; Châu xây ở bước tiếp theo
src/data/       Code của toàn bộ luồng dữ liệu
config/         Cấu hình coin, thời gian và quy tắc kiểm tra
tests/          Kiểm tra dữ liệu
docs/           Source log, dictionary, quality report
outputs/        Bảng, hình và báo cáo HTML
```

Tài liệu mô tả được lưu tại một nơi là `docs/`. Chỉ có một file cài thư viện `requirements.txt`, chứa phiên bản thực tế đã kiểm tra. Bộ này không chứa `.venv`, `.cache`, `.idea` hoặc bytecode.

Đọc `docs/HANDOFF.md`, `docs/data_dictionary.md` và `docs/data_quality_report.md`. Hai file nến chính là `data/interim/BTCUSDT_5m_clean.parquet` và `data/interim/ETHUSDT_5m_clean.parquet`; luôn dùng kèm daily_quality để biết ngày đủ RV. Báo cáo xem bằng trình duyệt: `outputs/BAN_GIAO_DU_LIEU_HUAN.html`.

## Cài và chạy

Dùng Python 3.12. Mở terminal tại thư mục gốc repo:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.data.run
```

Có thể chạy bằng `run_data.ps1` nếu chính sách PowerShell của máy cho phép. Không cần thay đổi execution policy để dùng trực tiếp Python như trên.

Để kiểm tra bộ dữ liệu đã có mà không tải/chạy lại:

```powershell
.\.venv\Scripts\python.exe -m src.data.validate
```

Chạy từng bước bằng các module `src.data.download`, `src.data.clean`, `src.data.audit`, `src.data.report`, `src.data.validate`. Raw có sẵn được kiểm tra hash và tái sử dụng; không sửa file nguồn. Snapshot mới cần cập nhật `config/data.toml` và giữ nguyên snapshot cũ.

## Trạng thái và giới hạn

BTCUSDT/ETHUSDT spot 5 phút từ 01/12/2018 đến 17/10/2026 UTC, 828.050 nến mỗi coin; 12/2018 là warm-up. Mỗi coin có 21 ngày thiếu nến, không tự lấp giá hay RV bằng 0. RV tham chiếu chỉ có ở ngày đủ điều kiện; return qua khoảng trống không được tính như return 5 phút.

VIX/USD đã thu thập và có forward-fill cho mô tả, nhưng chưa xác minh thời điểm công bố/vintage lịch sử, nên chưa dùng làm feature dự báo. CoinGecko đối chiếu 365 ngày; các khác biệt nguồn được ghi trong quality report. Các bảng tham chiếu chưa phải dataset có lag/target/split đã được nhóm duyệt. Chưa chạy mô hình và chưa có `outputs/tables/robustness.csv`; phần này cần kết quả mô hình của nhóm.

Sáu unit test và kiểm tra dữ liệu bàn giao được dùng để xác nhận timestamp, return, điều kiện RV và hash nguồn; chưa thay thế kiểm tra leakage của feature/model.

Nguồn chính thức: [Binance](https://github.com/binance/binance-public-data), [FRED VIX](https://fred.stlouisfed.org/series/VIXCLS), [FRED USD](https://fred.stlouisfed.org/series/DTWEXBGS), [Fed H.10](https://www.federalreserve.gov/releases/h10/about.htm), [CoinGecko](https://docs.coingecko.com/demo/reference/coins-id-market-chart). Chi tiết từng file nguồn có tại `docs/source_log.csv`.
