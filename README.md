# Crypto-Tail-Risk-Volatility-Forecasting-Engine
A cryptocurrency volatility forecasting and tail-risk analysis engine for BTC and ETH, combining GARCH, GJR-GARCH, HAR-RV, and XGBoost models with VaR/ES backtesting and an interactive Streamlit dashboard.


## Cấu trúc

```text
data/raw/       Dữ liệu gốc, ZIP, checksum, metadata và raw Parquet
data/interim/   Nến sạch, chất lượng theo ngày và tham chiếu QA
data/processed/ Dataset feature/target, regime và lịch chạy Backend 1
src/data/       Code của toàn bộ luồng dữ liệu
src/features/   Feature và target point-in-time
src/models/     HAR-RV, GARCH/GJR Student-t, tổ hợp
src/evaluation/ Walk-forward, metrics, DM và tổng hợp
config/         Cấu hình coin, thời gian và quy tắc kiểm tra
tests/          Kiểm tra dữ liệu, leakage và mô hình
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

BTCUSDT/ETHUSDT spot 5 phút từ 01/12/2018 đến 17/10/2026 UTC, 828.050 nến mỗi coin; 12/2018 là dữ liệu đệm; warmup 2019–2020, đánh giá 2021–2025, holdout 2026 (hiện đến 17/10/2026). Mỗi coin có 21 ngày thiếu nến, không tự lấp giá hay RV bằng 0. RV tham chiếu chỉ có ở ngày đủ điều kiện; return qua khoảng trống không được tính như return 5 phút.

VIX/USD đã thu thập và có forward-fill cho mô tả, nhưng chưa xác minh thời điểm công bố/vintage lịch sử. Theo quy định nhóm, macro chỉ dành cho kiểm tra độ nhạy sau khi xác minh; không đưa vào mô hình chính. CoinGecko đối chiếu 365 ngày; các khác biệt nguồn được ghi trong quality report. QA ngày và dataset feature/target được lưu riêng. Chi tiết tại `docs/GROUP_PROTOCOL.md`. Backend 3 bổ sung Elastic Net và XGBoost vào HAR/GARCH/GJR; xem trạng thái và giới hạn hiện tại trong `docs/backend3.md`.

Unit test và kiểm tra dữ liệu bàn giao được dùng để xác nhận timestamp, return, điều kiện RV và hash nguồn; chưa thay thế kiểm tra leakage của feature/model.

Nguồn chính thức: [Binance](https://github.com/binance/binance-public-data), [FRED VIX](https://fred.stlouisfed.org/series/VIXCLS), [FRED USD](https://fred.stlouisfed.org/series/DTWEXBGS), [Fed H.10](https://www.federalreserve.gov/releases/h10/about.htm), [CoinGecko](https://docs.coingecko.com/demo/reference/coins-id-market-chart). Chi tiết từng file nguồn có tại `docs/source_log.csv`.

## Cập nhật thống nhất quy định nhóm

Repo đang áp dụng `pre_sample` (12/2018), `warmup` (2019–2020), `evaluation` (2021–2025), `holdout` (2026). Cấu hình chung ở `config/data.toml`; quy định và giới hạn ở `docs/GROUP_PROTOCOL.md`. Backend 1 đã có feature/target, regime, khung walk-forward và baseline tham chiếu; hướng dẫn tại `docs/backend1.md`.

Cập nhật nhãn, bảng, hình và tài liệu từ dữ liệu đã có, không tải lại nguồn:

```powershell
.\.venv\Scripts\python.exe -m src.data.refresh
```

Lệnh này giữ nguyên raw và nến sạch, kiểm tra giá/return/RV không đổi, tạo lại báo cáo rồi xác minh toàn bộ bộ bàn giao. `outputs/tables/sample_period_summary.csv` thống kê độ phủ và ngày đủ RV theo từng giai đoạn. Thống kê giá/return/RV không dùng holdout; ACF chỉ dùng warmup.

## Bốn quy ước đã chốt

- Cửa sổ: 730 ngày lịch, từ t−729 đến t; giữ ngày thiếu trên lịch.
- Refit: cách 5 ngày lịch, neo ngày dự báo 01/01/2021 (origin 31/12/2020); dự báo hằng ngày, tiếp tục cùng lịch sang holdout.
- Target 7 ngày: tổng RV của t+1 đến t+7 (%²), yêu cầu đủ bảy ngày; chỉ fit nhãn đã quan sát đầy đủ.
- Crisis: phân vị 90% của RV trung bình 22 ngày trong warmup 2019–2020, riêng từng coin, cố định sau warmup; regime dự báo chỉ dùng dữ liệu đến origin.

Chi tiết và ví dụ: `docs/GROUP_PROTOCOL.md`. Trên backend-1, dataset feature/target, lịch chạy và ngưỡng crisis đã được triển khai; xem docs/backend1.md.

## Backend 1 trên dữ liệu thật

Đã ghép nhánh data và thống nhất toàn bộ theo quy định nhóm. Xem **docs/backend1.md** và **docs/forecast_format.md** để chạy/nhận đầu vào và tích hợp model.

```powershell
.\.venv\Scripts\python.exe run_tests.py
.\.venv\Scripts\python.exe -m src.backend1
```

Luồng: daily QA thật → feature/target/regime → lịch walk-forward → naive/historical mean/HAR OLS tham chiếu → bảng và hình đánh giá 2021–2025. Không sinh chương báo cáo và không mặc định chấm điểm holdout 2026. Các trạng thái cũ trong tài liệu bàn giao data mô tả thời điểm trước khi Backend 1 được xây; trạng thái Backend 1 nằm trong docs/backend1.md và outputs/tables/backend1_validation.json.

## Backend 2: đọc từ đây

Hướng dẫn chính: **[docs/backend2.md](docs/backend2.md)**. Chạy sau khi đã có dataset Backend 1:

```powershell
.\.venv\Scripts\python.exe -m src.backend2
```

Đã có HAR-RV OLS, GARCH(1,1)-t, GJR-GARCH-t, tổ hợp ba mô hình, chẩn đoán tham số/residual và bản xuất σ cho risk backend. Kết quả thật 2021–2025 ở `outputs/forecasts/`, `outputs/volatility/`, `outputs/diagnostics/`; bảng/hình đánh giá dùng chung với Backend 1. XGBoost và VaR/ES thuộc phần tiếp theo. Holdout 2026 chưa chấm điểm. Review độc lập của thành viên nhóm còn chờ; ghi chú tại `docs/backend2_review.md`.

## Backend 3: điểm bắt đầu hiện tại

Đọc **[docs/backend3.md](docs/backend3.md)** → **[docs/GROUP_PROTOCOL.md](docs/GROUP_PROTOCOL.md)** → **[docs/forecast_format.md](docs/forecast_format.md)**.

```powershell
.\.venv\Scripts\python.exe -m src.backend3
```

Có Elastic Net, XGBoost với cấu hình khóa từ warmup, TreeSHAP tại các origin ngoài mẫu, ablation volume trên cùng dòng train và tổ hợp HAR/GARCH/GJR/XGBoost. File dự báo/σ dùng chung hợp đồng với Backend 2; bản ablation nằm riêng. Kết quả VIX/USD chưa được tạo vì chưa xác minh historical release/vintage. GRU tùy chọn được hoãn theo lựa chọn của người dùng. Phần tiếp theo là Backend 4: VaR/ES và backtesting; holdout 2026 vẫn giữ cho bước cuối. Không viết chương báo cáo học thuật.
