# Từ điển dữ liệu bàn giao 

Schema nến sạch dùng chung ở data/interim. Raw ZIP là bản nguồn nguyên gốc; raw Parquet tổng hợp giữ token gốc dưới dạng chuỗi để tránh làm tròn và giữ dấu vết. Nhãn giai đoạn theo config/data.toml; dataset feature/target hiện đã có ở data/processed, được mô tả thêm trong docs/TECHNICAL_GUIDE.md.

| Cột | Kiểu | Định nghĩa | Đơn vị / lưu ý |
| --- | --- | --- | --- |
| symbol | string | Mã cặp spot | BTCUSDT/ETHUSDT |
| open_time | timestamp UTC | Đầu nến 5 phút; khóa cùng symbol | datetime64 UTC, không phải giờ VN |
| open/high/low/close | float64 | Giá OHLC | USDT/coin |
| volume | float64 | Khối lượng giao dịch | coin |
| quote_volume | float64 | Khối lượng theo đồng định giá | USDT; không phải tỷ lệ turnover |
| n_trades | int64 | Số giao dịch | count |
| taker_buy_base/quote | float64 | Khối lượng mua chủ động | coin / USDT |
| source_file | string | Đường dẫn archive gốc | relative path |
| timestamp_unit | string | Đơn vị timestamp gốc đã nhận diện | ms/us |
| quality_flag | string | ok hoặc cờ cần xem xét | Không đồng nghĩa đã xác minh nguyên nhân |
| zero_volume | bool | Nến volume bằng 0; giữ và gắn cờ | Không tự xóa |
| return_5m_pct_qa | float64 | 100*ln(close/close trước), chỉ khi cách đúng 5 phút | % log return; NaN sau khoảng thiếu |
| return_gap_before | bool | Không có nến liền trước cách đúng 5 phút | Bao gồm quan sát đầu snapshot |
| large_return_review | bool | /return 5 phút/ > 10% | Cờ xem xét, không tự winsorize |
| eligible_rv | bool | Đủ 288 nến hợp lệ và 288 return liền nhau | Baseline RV đầy đủ |
| rv_reference_pct2 | float64 | Tổng bình phương 288 return 5 phút hợp lệ | %²; chỉ là tham chiếu QA |
| volatility_reference_pct | float64 | Căn RV tham chiếu | %/ngày; không annualize |
| return_daily_pct_qa | float64 | 100*ln(close cuối ngày/close cuối ngày trước) | % log return; giữ lưới ngày |
| sample_segment | string | pre_sample / warmup / evaluation / holdout | 12/2018 / 2019–2020 / 2021–2025 / 2026; theo ngày quan sát |
| quarantine_reason | string | Lý do loại khỏi nến sạch | Raw vẫn giữ nguyên |
| observation_date | timestamp UTC | Ngày quan sát FRED | Không phải ngày công bố |
| available_at | timestamp UTC | Thời điểm lịch sử có thể dùng | Để NaT khi chưa xác minh; không dùng predict |
| retrieved_at_utc | timestamp UTC | Thời điểm tải snapshot | Không gán thay cho historical availability |
| descriptive_ffill_value | float64 | Giá trị lấp tiếp theo ngày quan sát | CHỈ MÔ TẢ; predictive_use_allowed=False |

RV được tính bằng return đã nhân 100, nên phương sai có đơn vị %². Không so với variance từ return dạng số thập phân nếu chưa đổi đơn vị. Ngày chứa nến mở 00:00–23:55 UTC; nến cuối kết thúc tại biên 00:00 ngày sau.

CoinGecko có giá USD tại 00:00 UTC, được ghép với close Binance của NGÀY TRƯỚC; bỏ điểm cập nhật intraday cuối chuỗi. Chênh lệch còn phản ánh USDT/USD và giá tổng hợp nhiều sàn.

## Bộ macro vintage bổ sung

`data/interim/macro_vintages.parquet` tách khỏi observations/calendar FRED gốc:

| Cột | Ý nghĩa |
|---|---|
| `series_id` | VIXCLS hoặc DTWEXBGS |
| `vintage_date` | Ngày snapshot lịch sử tại ALFRED |
| `observation_date` | Ngày quan sát gần nhất có giá trị, không sau vintage |
| `value` | Chỉ số tại đúng vintage, chưa lấy log |
| `available_at` | Vintage + 2 ngày UTC, quy tắc khả dụng bảo thủ |
| `point_in_time_verified` | Snapshot đã qua kiểm tra mã chuỗi/ngày vintage; không khẳng định giờ công bố chính xác |
| `excluded_future_observations` | Số ô nguồn có ngày quan sát sau vintage, đã loại khỏi feature |

Nhánh sensitivity nối as-of tại đầu ngày UTC của origin, tạo `log_vix_l1`, `log_usd_l1` và các cột `_available_at`. Tên l1 kế thừa schema; độ trễ thực tế theo availability, không phải shift một hàng. Dataset macro được tạo trong bộ nhớ, không ghi đè dataset chính. Manifest/hash nguồn và chi tiết ở `docs/macro_sensitivity.md`.
