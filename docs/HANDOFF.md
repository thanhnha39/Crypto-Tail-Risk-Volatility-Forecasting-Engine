



## Tình trạng

Đã thu thập và chuẩn hóa BTCUSDT/ETHUSDT spot 5 phút từ 01/12/2018 đến 17/10/2026 UTC. Mỗi coin có 828.050 nến; tháng 12/2018 là warm-up, dữ liệu từ 2019 là phạm vi chính. Năm 2026 tách khỏi phần hình/thống kê mô tả 2019–2025. Việc này không thay nhóm chốt train/validation/test.

Đã chạy kiểm tra trên toàn bộ nến bàn giao và xác minh hash 277 file nguồn, gồm 222 archive dữ liệu chính, 51 archive đối chiếu và 4 snapshot FRED/CoinGecko. Sáu unit test kiểm tra timestamp, khoảng thiếu, duplicate và tính bất biến return quá khứ đều qua. Đây là kiểm tra dữ liệu, chưa thay thế test leakage của feature/model ở phần Châu.


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
3. Có 21 ngày thiếu nến/mỗi coin, tổng 814 nến/mỗi coin. RV baseline của các ngày đó để NaN; không thay bằng 0. Ngày đầu warm-up thiếu close liền trước cũng không đủ RV.
4. Một ngày đủ RV phải có 288 nến hợp lệ và 288 return đúng khoảng 5 phút. Không dùng return qua một khoảng 10/15 phút như return 5 phút.
5. Đừng suy luận giá trị trong `daily_reference_qa` là target đã shift. Feature/target t+1, split và test leakage do Châu tạo, rồi thống nhất định dạng forecast với các thành viên làm mô hình.

## Vấn đề nguồn đã được ghi nhận

Ngày 21/12/2020 có khác biệt giữa archive tháng và ngày của Binance: daily thiếu hơn monthly 4 timestamp/mỗi coin và có OHLC ở một số timestamp chung khác nhau. Giữ monthly làm nguồn chính, không trộn hoặc sửa raw; ngày đó vốn đã thiếu nến và không đủ RV. Xem `gap_source_audit.csv` và `gap_archive_ohlc_differences.csv`. Không gọi đây là dữ liệu đã được xác minh độc lập hoàn toàn.

Có 4 nến BTC và 6 nến ETH có |return 5 phút| >10%. Cả 10 nến khớp OHLC tổng hợp từ 5 nến 1 phút cùng sàn. Giữ lại, không tự cắt đuôi; xem `large_return_source_audit.csv`.

CoinGecko có 365 ngày đối chiếu/coin. Ngày 22/02/2026 lệch trên 2% với Binance; close Binance tổng hợp 5m đã khớp archive 1d nhưng chênh giữa nguồn chưa xác định nguyên nhân. Giữ giá nguồn, ghi nhận cờ, không sửa theo CoinGecko. Dữ liệu 2026 không có trong phần thống kê mô tả 2019–2025.

## Vĩ mô

VIXCLS/DTWEXBGS đã có bảng observations. Chưa xác minh release/vintage lịch sử nên `available_at` trống, `point_in_time_verified=False`. Không dùng `macro_calendar_DESCRIPTIVE_ONLY.parquet` để huấn luyện; forward-fill ở đó chỉ phục vụ mô tả. H.10/USD có lịch công bố theo tuần, shift một ngày đơn thuần chưa đủ. Đề xuất trước mắt chạy core với OHLCV/volume; chỉ thêm macro khi nhóm xử lý được availability.

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
