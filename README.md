# Crypto Tail Risk and Volatility Forecasting Engine

Repo nghiên cứu dự báo realized variance và rủi ro đuôi BTC/ETH. **main đã tích
hợp Data và Backend 1–4**, kèm code, dữ liệu và kết quả evaluation thật.

## Bắt đầu từ đây

**Trạng thái backend hiện tại và thứ tự đọc:** [BACKEND_STATUS.md](docs/BACKEND_STATUS.md).


| Viết luận, lấy số liệu và diễn giải kết quả | **[Bàn giao viết luận](docs/BAN_GIAO_VIET_LUAN.md)** |
| Kết quả đánh giá cuối năm 2026 | **[Kết quả holdout](docs/HOLDOUT_RESULTS.md)** và [quy trình đã khóa](docs/HOLDOUT_PROTOCOL.md) |
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
- 12/2018 là đệm, warmup 2019–2020, evaluation **2021–2025**; holdout riêng **01/01–17/10/2026**, theo kế hoạch đã khóa và trạng thái trong `outputs/final_holdout_pipeline.json`.
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

Dashboard và biên soạn luận là các phần tiếp theo. Kết quả holdout được bàn giao
riêng trong `docs/HOLDOUT_RESULTS.md`; không dùng để chọn lại siêu tham số hoặc làm đẹp kết quả.
Mọi ngày thiếu giữ trạng thái rõ; không biến NaN thành dự báo/rủi ro bằng 0.

## Đánh giá cuối trên holdout

Đọc [HOLDOUT_RESULTS.md](docs/HOLDOUT_RESULTS.md) để lấy bảng dự báo, DM có
điều chỉnh Holm cho họ kiểm định chính, đối chiếu 2021–2025/2026 và VaR/ES.
`outputs/holdout_verification.json` ghi kết quả đối chiếu độc lập với file đã lưu;
`outputs/final_holdout_pipeline.json` xác nhận trạng thái từng bước.
Các kiểm tra được thực hiện tự động bởi cùng bộ code của nhóm, không thay phản biện độc lập của thành viên.
Kết quả toàn bộ 108 kiểm thử trước lượt chấm ở `outputs/holdout_unit_tests.json`.
Giới hạn QA giữa nguồn ngày 22/02/2026 vẫn giữ theo tài liệu dữ liệu; không sửa
giá Binance để khớp CoinGecko và không dùng chênh lệch này để tune.

Không chạy lại model khi chỉ cần đọc báo cáo. Lệnh tạo lại báo cáo từ kết quả:
`python -B -m src.reporting.holdout_report`. Luồng chạy mới và cơ chế khóa ở
[HOLDOUT_PROTOCOL.md](docs/HOLDOUT_PROTOCOL.md).

File `BAN_GIAO_VIET_LUAN.md` và manifest tương ứng được giữ nguyên như bản bàn
giao ngày 24/10, phạm vi số liệu 2021–2025; các câu “holdout chưa chấm” trong
bản đó mô tả trạng thái tại thời điểm bàn giao cũ. Dùng thêm `HOLDOUT_RESULTS.md`
cho trạng thái và kết quả 2026 hiện tại.

Sau khi lượt chấm hoàn tất, tiêu đề cố định “2021–2025” trong hàm vẽ hình được
sửa để lấy ngày thực tế. Bản plan/code gốc được lưu tại
`outputs/holdout_plan_original.json` và `outputs/holdout_source_original/`;
`outputs/holdout_presentation_amendment.json` đối chiếu trước/sau và xác nhận
toàn bộ file số liệu không đổi. Hash từng stage là dấu vết lịch sử; các hash
hình đã sửa nằm ở phần final_deliverable trong pipeline manifest.
