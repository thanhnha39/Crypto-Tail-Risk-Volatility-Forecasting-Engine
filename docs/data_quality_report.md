

# Snapshot 2026-10-18; tạo báo cáo 2026-10-18T08:10:16.085519+00:00.

## Phạm vi và tình trạng

BTCUSDT và ETHUSDT spot 5 phút, 01/12/2018–17/10/2026 UTC. Tháng 12/2018 là warm-up; số liệu mô tả chính 2019–2025; năm 2026 được ghi riêng. Không tự chốt train/validation/test. Đã tải VIXCLS, DTWEXBGS và giá CoinGecko trong phạm vi 365 ngày được API cung cấp. Không thu thập order-book/phái sinh và không chạy mô hình.

Archive Binance đã khớp SHA256 từ nguồn: **222**. Số nguồn/file tải lỗi: **0**. Mỗi archive có URL, thời điểm tải, hash và row count trong source_log.csv.

## Kết quả kiểm tra nến

| Coin | Raw rows | Clean rows | Quarantine | Ngày thiếu | Nến thiếu | Volume 0 | Return >10% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT | 828,050 | 828,050 | 0 | 21 | 814 | 56 | 4 |
| ETHUSDT | 828,050 | 828,050 | 0 | 21 | 814 | 56 | 6 |

Ngày đủ nến nhưng thiếu close liền trước cũng không đủ điều kiện RV; kiểm tra eligible_rv trong daily_quality. Các ngày thiếu được giữ trên lưới ngày; RV tham chiếu để NaN. Không ghép return qua khoảng trống, không nội suy hoặc backfill. Nến zero-volume và return lớn được giữ, gắn cờ và có bảng riêng; cờ không khẳng định đó là lỗi dữ liệu.

Đối chiếu bổ sung: 51/51 archive tải/khớp checksum; 40/42 ngày thiếu trùng khớp giữa monthly và daily; 10/10 nến return lớn có OHLC khớp tổng hợp từ 5 nến 1 phút cùng sàn. Đây là đối chiếu hai độ phân giải của cùng nguồn, không phải xác minh độc lập toàn thị trường. Chi tiết tại gap_source_audit.csv và large_return_source_audit.csv.

Có 0 trường hợp daily là tập con của monthly: bảng gap_source_audit ghi các timestamp khác biệt. Giữ monthly làm nguồn chính, không bỏ nến monthly chỉ vì daily thiếu hơn; cả ngày vẫn được đánh dấu không đủ điều kiện RV. Các OHLC ở timestamp chung được đối chiếu riêng.

**Còn 2 trường hợp archive khác biệt chưa xác định nguyên nhân**, gồm BTCUSDT ngày 2020-12-21; ETHUSDT ngày 2020-12-21. Giữ monthly làm nguồn chính; 14 nến có OHLC khác nhau được ghi ở gap_archive_ohlc_differences.csv. Không kết luận dữ liệu hai archive đồng nhất; ngày này đã bị loại khỏi RV baseline do thiếu nến.

## Đối chiếu CoinGecko

| Coin | Ngày khớp | Median lệch tuyệt đối | Max lệch tuyệt đối | Ngày >2% |
| --- | --- | --- | --- | --- |
| BTCUSDT | 365 | 0.0604% | 3.7600% | 1 |
| ETHUSDT | 365 | 0.0595% | 4.5147% | 1 |

Ghép sample CoinGecko 00:00 UTC với close Binance của ngày vừa kết thúc; bỏ điểm intraday. USD khác USDT và giá tổng hợp khác giá một sàn, nên không yêu cầu lệch bằng 0. Giới hạn một năm khiến việc đối chiếu không bao phủ toàn mẫu. Chi tiết tại *_coingecko_crosscheck.csv.

Ngày lệch trên 2% đã được đối chiếu thêm với archive Binance 1 ngày. Xem crosscheck_source_audit.csv: nếu close 1d khớp close tổng hợp 5m, ghi nhận chênh lệch giữa nguồn vẫn chưa có kết luận nguyên nhân; giữ giá gốc, không thay giá Binance bằng CoinGecko.

## Dữ liệu vĩ mô và tính khả dụng

| Chuỗi | Dòng quan sát | Giá trị không thiếu | Ngày cuối có giá trị |
| --- | --- | --- | --- |
| DTWEXBGS | 2050 | 1961 | 2026-10-09 00:00:00+00:00 |
| VIXCLS | 2054 | 2010 | 2026-10-15 00:00:00+00:00 |

**Đã thu thập, chưa đủ xác minh point-in-time để đưa vào feature dự báo.** FRED tải hiện tại có thể chứa sửa đổi; ngày quan sát không phải thời điểm công bố. H.10/USD được công bố theo tuần, vì vậy shift một ngày đơn thuần chưa đủ. Bảng observations để available_at trống và point_in_time_verified=False. Bản calendar forward-fill chỉ dành cho mô tả, tên file DESCRIPTIVE_ONLY và predictive_use_allowed=False; không backfill đầu chuỗi. Khi có lịch release/vintage kiểm chứng được, Châu/Huân mới ghép as-of để làm feature. Phần lõi có thể dùng OHLCV và volume trong lúc này.

## Bảng và hình dùng cho chương 3

Bảng nguồn: source_log.csv; từ điển biến: docs/data_dictionary.md; thống kê: descriptive_statistics.csv. Hình 3.1 giá và Hình 3.2 RV dùng mẫu mô tả 2019–2025. Hình 3.3 ACF chỉ tính trên đoạn lịch liên tục dài nhất có RV đủ điều kiện của từng coin, không nối qua ngày thiếu; đoạn và N nằm trong acf_rv.csv. Dải ±1.96/sqrt(N) chỉ là tham chiếu xấp xỉ dưới giả định nhiễu trắng. Các hình là kết quả tính từ dữ liệu thật, không phải hình minh họa trong brief.


## Nguồn và giới hạn

Binance Public Data: https://github.com/binance/binance-public-data

FRED: https://fred.stlouisfed.org/series/VIXCLS và https://fred.stlouisfed.org/series/DTWEXBGS

Fed H.10: https://www.federalreserve.gov/releases/h10/about.htm

CoinGecko API: https://docs.coingecko.com/demo/reference/coins-id-market-chart

Số liệu trong báo cáo do nhóm tính từ các snapshot có hash; không khẳng định lịch sử Binance là toàn thị trường. Outlier chưa có bằng chứng độc lập không bị tự loại. Macro chưa được chứng minh availability/vintage nên bị chặn khỏi predictive core.
