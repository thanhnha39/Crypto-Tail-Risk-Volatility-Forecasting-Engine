# Báo cáo chất lượng dữ liệu và bàn giao thống nhất

Người chuẩn bị: Huân. Snapshot 2026-10-18; tạo báo cáo 2026-10-22T14:57:01.477019+00:00.

## Phạm vi và tình trạng

BTCUSDT và ETHUSDT spot 5 phút, 01/12/2018–17/10/2026 UTC. Tháng 12/2018 là dữ liệu đệm (pre_sample); warmup 2019–2020; đánh giá 2021–2025; holdout 2026. Snapshot hiện chỉ đến 17/10/2026. Các thống kê giá/return/RV và hình mô tả không dùng holdout; kiểm tra chất lượng nguồn vẫn bao phủ toàn bộ snapshot. Đã tải VIXCLS, DTWEXBGS và giá CoinGecko trong phạm vi 365 ngày được API cung cấp. Không thu thập order-book/phái sinh và không chạy mô hình.

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

**Bộ FRED snapshot gốc chỉ dành cho mô tả.** Bộ ALFRED vintage bổ sung được mô tả riêng ở docs/macro_sensitivity.md; các giới hạn dưới đây vẫn áp dụng cho observations/calendar FRED cũ. FRED tải hiện tại có thể chứa sửa đổi; ngày quan sát không phải thời điểm công bố. H.10/USD được công bố theo tuần, vì vậy shift một ngày đơn thuần chưa đủ. Bảng observations để available_at trống và point_in_time_verified=False. Bản calendar forward-fill chỉ dành cho mô tả, tên file DESCRIPTIVE_ONLY và predictive_use_allowed=False; không backfill đầu chuỗi. Khi có lịch release/vintage kiểm chứng được, Châu/Huân mới ghép as-of để làm feature. Theo quy định nhóm, macro bị loại khỏi mô hình chính; chỉ dùng kiểm tra độ nhạy sau khi xác minh release/vintage.

## Bốn quy ước đã thống nhất

| Hạng mục | Quy ước |
| --- | --- |
| Cửa sổ | 730 ngày lịch; t−729 đến t; giữ ngày thiếu |
| Refit | Mỗi 5 ngày lịch; neo ngày dự báo 2021-01-01; dự báo hằng ngày |
| Target 7 ngày | Tổng RV(t+1)...RV(t+7), %²; yêu cầu đủ 7 RV; chỉ fit target đã quan sát đầy đủ |
| Crisis | Phân vị 90% của RV trung bình 22 ngày; hiệu chuẩn warmup riêng coin rồi cố định; chỉ dùng thông tin đến origin |

Chi tiết: docs/GROUP_PROTOCOL.md. Tài liệu này mô tả bước Data; trạng thái tích hợp feature/target, regime và mô hình hiện tại xem docs/HANDOFF.md.

## Bảng và hình dùng cho chương 3

Bảng nguồn: source_log.csv; từ điển biến: docs/data_dictionary.md; thống kê: descriptive_statistics.csv. Hình 3.1 giá và Hình 3.2 RV dùng mẫu mô tả 2019–2025. Hình 3.3 ACF chỉ tính trên đoạn lịch liên tục dài nhất có RV đủ điều kiện trong warmup 2019–2020 của từng coin, không nối qua ngày thiếu; đoạn và N nằm trong acf_rv.csv. Dải ±1.96/sqrt(N) chỉ là tham chiếu xấp xỉ dưới giả định nhiễu trắng. Các hình là kết quả tính từ dữ liệu thật, không phải hình minh họa trong brief.

## Bộ bàn giao và bước tiếp theo

Nhận *_5m_clean.parquet, *_daily_quality.parquet, *_quarantine.parquet, QA daily reference, source log, dictionary, bảng thiếu/outlier và báo cáo này. Huân phụ trách tiếp phần chuẩn bị feature của Châu ở bước sau. Giữ ngày thiếu trên lịch, tạo feature đến hết ngày t UTC và target t+1; gán split của dataset mô hình theo target_date bằng cùng cấu hình giai đoạn. QA reference đã có nhãn ngày quan sát, chưa phải dataset feature/target và không có lệnh train. Quy định nhóm: HAR-RV, GARCH(1,1), GJR-GARCH, XGBoost; rolling 730 ngày, expanding để kiểm tra độ nhạy; ước lượng lại mỗi 5 ngày; horizon chính 1 ngày và kiểm tra độ nhạy 7 ngày; chỉ chọn siêu tham số XGBoost trên warmup. Xem docs/GROUP_PROTOCOL.md. Robustness của các mô hình đã tích hợp được xuất riêng ở outputs/tables/robustness.csv; các chương học thuật không nằm trong đợt triển khai code.

## Nguồn và giới hạn

Binance Public Data: https://github.com/binance/binance-public-data

FRED: https://fred.stlouisfed.org/series/VIXCLS và https://fred.stlouisfed.org/series/DTWEXBGS

Fed H.10: https://www.federalreserve.gov/releases/h10/about.htm

CoinGecko API: https://docs.coingecko.com/demo/reference/coins-id-market-chart

Số liệu trong báo cáo do nhóm tính từ các snapshot có hash; không khẳng định lịch sử Binance là toàn thị trường. Outlier chưa có bằng chứng độc lập không bị tự loại. Bộ FRED cũ không dùng dự báo; bộ ALFRED vintage bổ sung chỉ dùng sensitivity theo docs/macro_sensitivity.md, không đưa vào predictive core.
