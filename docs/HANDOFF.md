# Bàn giao tích hợp Data → Backend 1 → Backend 2 → Backend 3

Điểm bắt đầu hiện tại là nhánh `main`, đã tích hợp bản `backend-3` gồm Data, Backend 1, Backend 2 và Backend 3. Đã có dataset feature/target, lịch dự báo, regime, HAR-RV/GARCH/GJR-GARCH/XGBoost và Elastic Net. Bảng so sánh đủ bốn mô hình chính nằm tại `outputs/tables/model_comparison.csv`; hợp đồng đầu ra ở `docs/forecast_format.md`.

Bản mô phỏng cũ, script tạo dữ liệu mô phỏng và cấu hình YAML đã ngừng dùng được dọn khỏi cây file hiện tại. Lịch sử Git vẫn giữ các phiên bản trước. Các fixture mô phỏng trong unit test được giữ để kiểm tra công thức và leakage; dữ liệu/kết quả nghiên cứu dùng snapshot thật.

Đọc `docs/backend3.md` để chạy ML/SHAP/ablation; `docs/backend2.md` để dùng volatility đầu vào cho Backend 4. `outputs/tables/robustness.csv` tổng hợp rolling/expanding và h1/h7 từ dự báo thật, cùng ngày khi so sánh hai cửa sổ. `outputs/tables/feature_sets.csv` liệt kê nhóm biến. Macro được xử lý riêng theo `docs/macro_sensitivity.md`, không đưa vào mô hình chính. Holdout 2026 dành cho lượt tích hợp cuối; không chạy để hoàn thiện bảng trung gian.





## Tình trạng

Đã thu thập và chuẩn hóa BTCUSDT/ETHUSDT spot 5 phút từ 01/12/2018 đến 17/10/2026 UTC. Mỗi coin có 828.050 nến; tháng 12/2018 là dữ liệu đệm; warmup 2019–2020, đánh giá 2021–2025, holdout 2026 hiện chỉ đến 17/10/2026. Các nhãn trong bảng QA đã theo quy định nhóm, xem docs/GROUP_PROTOCOL.md. Thống kê giá/return/RV không dùng holdout; ACF chỉ dùng warmup.

Đã chạy kiểm tra trên toàn bộ nến bàn giao và xác minh hash 277 file nguồn, gồm 222 archive dữ liệu chính, 51 archive đối chiếu và 4 snapshot FRED/CoinGecko. Các unit test kiểm tra timestamp, khoảng thiếu, duplicate và tính bất biến return quá khứ đều qua. Đây là kiểm tra dữ liệu, chưa thay thế test leakage của feature/model khi triển khai backend sau.


| Đường dẫn tương đối | Mục đích |
|---|---|
| `data/interim/BTCUSDT_5m_clean.parquet` | Nến BTC chuẩn hóa UTC |
| `data/interim/ETHUSDT_5m_clean.parquet` | Nến ETH chuẩn hóa UTC |
| `data/interim/{coin}_daily_quality.parquet` | Số nến và cờ eligible_rv theo ngày |
| `data/interim/{coin}_daily_reference_qa.parquet` | Return/RV tham chiếu để đối chiếu code; chưa có lag/target |
| `data/interim/{coin}_quarantine.parquet` | Hàng bị cách ly nếu có; snapshot hiện tại không có |
| `docs/data_dictionary.md` | Định nghĩa, đơn vị, kiểu và quy tắc thời gian |
| `docs/source_log.csv` | Nguồn, thời gian tải, hash và độ phủ |
| `docs/data_quality_report.md` | Tất cả kết quả QA và giới hạn |
| `outputs/tables/handoff_validation.json` | Kết quả kiểm tra trên dữ liệu thật |

## Những điểm cần giữ khi tạo feature

1. Return đã nhân 100; RV tham chiếu là %², volatility là %. Không nhân 100 thêm lần nữa và không trộn với variance từ return thập phân.
2. Giữ lưới ngày UTC đầy đủ trước khi lag/rolling. Không drop các ngày thiếu rồi coi hai dòng còn lại là hai ngày liên tiếp.
3. Có 21 ngày thiếu nến/mỗi coin, tổng 814 nến/mỗi coin. RV baseline của các ngày đó để NaN; không thay bằng 0. Ngày đầu snapshot 01/12/2018 thiếu close liền trước cũng không đủ RV.
4. Một ngày đủ RV phải có 288 nến hợp lệ và 288 return đúng khoảng 5 phút. Không dùng return qua một khoảng 10/15 phút như return 5 phút.
5. Đừng suy luận giá trị trong `daily_reference_qa` là target đã shift. Huân đã nhận tiếp phần chuẩn bị feature của Châu ở bước sau. Khi tạo target t+1, gán giai đoạn theo target_date bằng cấu hình chung, không lấy nhãn ngày t. Các file dự báo theo mẫu nhóm chỉ được tạo sau khi có model output.

## Vấn đề nguồn đã được ghi nhận

Ngày 21/12/2020 có khác biệt giữa archive tháng và ngày của Binance: daily thiếu hơn monthly 4 timestamp/mỗi coin và có OHLC ở một số timestamp chung khác nhau. Giữ monthly làm nguồn chính, không trộn hoặc sửa raw; ngày đó vốn đã thiếu nến và không đủ RV. Xem `gap_source_audit.csv` và `gap_archive_ohlc_differences.csv`. Không gọi đây là dữ liệu đã được xác minh độc lập hoàn toàn.

Có 4 nến BTC và 6 nến ETH có |return 5 phút| >10%. Cả 10 nến khớp OHLC tổng hợp từ 5 nến 1 phút cùng sàn. Giữ lại, không tự cắt đuôi; xem `large_return_source_audit.csv`.

CoinGecko có 365 ngày đối chiếu/coin. Ngày 22/02/2026 lệch trên 2% với Binance; close Binance tổng hợp 5m đã khớp archive 1d nhưng chênh giữa nguồn chưa xác định nguyên nhân. Giữ giá nguồn, ghi nhận cờ, không sửa theo CoinGecko. Dữ liệu 2026 không có trong phần thống kê mô tả 2019–2025.

## Vĩ mô

Các bảng FRED observations cũ vẫn chưa xác minh vintage; không dùng `macro_calendar_DESCRIPTIVE_ONLY.parquet` để huấn luyện. Bộ bổ sung `data/interim/macro_vintages.parquet` lấy từ snapshot ALFRED lịch sử, có manifest/hash và quy tắc khả dụng bảo thủ riêng. Sensitivity có/không VIX/USD nằm trong `outputs/sensitivity/macro/` và `outputs/tables/backend3_macro_ablation.csv`; xem `docs/macro_sensitivity.md`. Macro không nằm trong mô hình chính.

## Cách mở nhanh

```python
from pathlib import Path
import pandas as pd

root = Path.cwd()  # Chạy từ thư mục gốc repo
bars = pd.read_parquet(root / "data/interim/BTCUSDT_5m_clean.parquet")
quality = pd.read_parquet(root / "data/interim/BTCUSDT_daily_quality.parquet")
reference = pd.read_parquet(root / "data/interim/BTCUSDT_daily_reference_qa.parquet")
```

Khi nhận, xác nhận đọc được hai coin, timezone UTC, đủ khoảng nghiên cứu, và hiểu các cờ thiếu/nguồn. Báo cáo xem nhanh tại `outputs/BAN_GIAO_DU_LIEU_HUAN.html`. Pipeline chạy lại bằng `.venv\Scripts\python.exe -m src.data.run` từ thư mục gốc; không tự gửi dữ liệu lên GitHub/Drive.

## Cập nhật offline và kiểm tra

Chạy `python -m src.data.refresh` từ gốc repo trong môi trường đã cài requirements để đồng bộ nhãn ngày, bảng và báo cáo. Không tải/chỉnh sửa raw hoặc nến sạch. Cửa sổ, horizon và mô hình được ghi ở config/data.toml để dùng chung cho bước backend; phần dữ liệu hiện chưa thực thi các cấu hình model.

## Bốn quy ước đã chốt

- Cửa sổ: 730 ngày lịch, từ t−729 đến t; giữ ngày thiếu trên lịch.
- Refit: cách 5 ngày lịch, neo ngày dự báo 01/01/2021 (origin 31/12/2020); dự báo hằng ngày, tiếp tục cùng lịch sang holdout.
- Target 7 ngày: tổng RV của t+1 đến t+7 (%²), yêu cầu đủ bảy ngày; chỉ fit nhãn đã quan sát đầy đủ.
- Crisis: phân vị 90% của RV trung bình 22 ngày trong warmup 2019–2020, riêng từng coin, cố định sau warmup; regime dự báo chỉ dùng dữ liệu đến origin.

Chi tiết và ví dụ: `docs/GROUP_PROTOCOL.md`. Dataset feature/target, lịch chạy và ngưỡng crisis cụ thể đã có trong `data/processed/`. Bước tiếp theo là Backend 4 (VaR/ES và backtesting), sử dụng dự báo/volatility hiện có.
