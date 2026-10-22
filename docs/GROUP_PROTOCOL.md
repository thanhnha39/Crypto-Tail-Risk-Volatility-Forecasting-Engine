# Quy định thống nhất của nhóm

Áp dụng cho phần dữ liệu từ yêu cầu nhóm do Huân cung cấp ngày 22/10/2026.
Nguồn cấu hình máy đọc: `config/data.toml`. Các mục model/risk dưới đây là quy định bàn giao cho bước sau.

| # | Hạng mục | Quy định |
|---|---|---|
| 1 | Nguồn | Binance spot, nến 5 phút, UTC, 288 nến/ngày |
| 2 | Tài sản | BTCUSDT, ETHUSDT |
| 3 | Mục tiêu | Realized variance ngày (RV), %²; báo cáo thêm căn RV (%) |
| 4 | RV hợp lệ | Đủ 288 nến và 288 return 5 phút liên tục; không bù thiếu |
| 5 | Return lớn | Giữ, gắn cờ, không winsorize |
| 6 | Vĩ mô | Loại khỏi mô hình chính; chỉ kiểm tra độ nhạy sau khi xác minh point-in-time |
| 7 | Mô hình | HAR-RV, GARCH(1,1), GJR-GARCH, XGBoost |
| 8 | Cửa sổ | Rolling chính; expanding kiểm tra độ nhạy |
| 9 | Độ dài cửa sổ | 730 ngày lịch, từ t−729 đến t (bao gồm hai đầu) |
| 10 | Ước lượng lại | Mỗi 5 ngày lịch, neo ngày dự báo 01/01/2021; dự báo hằng ngày |
| 11 | Horizon | 1 ngày chính; 7 ngày kiểm tra độ nhạy với target là tổng RV của 7 ngày tiếp theo |
| 12 | Giai đoạn | Warmup 2019–2020; đánh giá 2021–2025; holdout 2026 chỉ đánh giá mô hình một lần cuối |
| 13 | XGBoost | Chọn siêu tham số một lần trên warmup, không tinh chỉnh lại |
| 14 | Thông tin | Dự báo t+1 chỉ dùng dữ liệu đến hết ngày t UTC |
| 15 | Đánh giá | QLIKE chính, RMSE, MAE; so sánh Diebold–Mariano |
| 16 | Regime | Crisis: RV trung bình 22 ngày trên ngưỡng phân vị 90% hiệu chuẩn riêng từng coin từ warmup rồi cố định; bull/bear: log return 90 ngày ≥ +10% / ≤ −10%; crisis > bear > bull > normal |
| 17 | VaR/ES | 95%, 99%; GARCH/GJR dùng Student-t; HAR/XGBoost dùng filtered historical simulation; Kupiec và Christoffersen |
| 18 | File dự báo | `{symbol}_{model}.parquet` và `{symbol}_{model}_risk.parquet` |

## Nhãn dữ liệu ngày

| sample_segment | Từ ngày | Đến ngày | Vai trò |
|---|---|---|---|
| pre_sample | 01/12/2018 | 31/12/2018 | Dữ liệu đệm để lấy close liền trước và tạo lịch sử |
| warmup | 01/01/2019 | 31/12/2020 | Chuẩn bị mô hình và chọn siêu tham số |
| evaluation | 01/01/2021 | 31/12/2025 | Đánh giá ngoài mẫu theo lịch thống nhất |
| holdout | 01/01/2026 | 31/12/2026 theo thiết kế | Snapshot hiện chỉ có đến 17/10/2026 |

`sample_segment` trong bảng QA là nhãn **ngày quan sát**. Khi xây dataset dự báo, phân chia theo **target_date**, không sao chép nhãn ngày t sang target t+1. Ví dụ feature đến 31/12/2025 dự báo 01/01/2026 thuộc holdout. Ngày không đủ RV được giữ trên lịch và để RV NaN; không drop ngày trước khi tạo lag/rolling.

RV = tổng bình phương các return `100*ln(P_j/P_{j-1})`. Nến mở 00:00–23:55 UTC thuộc ngày t; close của nến cuối có sẵn khi ngày t kết thúc. Return tại 00:00 cần close nến 23:55 của ngày trước. Biến căn RV chỉ dùng báo cáo volatility, không đổi mục tiêu thành volatility.

Holdout được kiểm tra chất lượng dữ liệu nguồn, nhưng không dùng chọn mô hình/siêu tham số. Báo cáo mô tả mới chỉ thống kê giá/return/RV theo warmup và evaluation; ACF chỉ dùng warmup. Các báo cáo cũ từng có thống kê mô tả 2026; không khẳng định rằng dữ liệu 2026 chưa từng được xem. Chưa chạy đánh giá mô hình holdout trong phần bàn giao này.

## Bốn quyết định đã thống nhất

### 1. Cửa sổ là 730 ngày lịch

Tại cuối ngày t UTC, cửa sổ từ t−729 đến t, tính cả hai đầu. Không kéo cửa sổ lùi thêm để bù đủ 730 dòng hợp lệ. Giữ lịch đầy đủ và RV NaN khi không đủ điều kiện; chỉ lọc dòng huấn luyện không hợp lệ sau khi tạo lag/target. Feature có thể cần dữ liệu lịch sử trước đầu cửa sổ, nhưng dòng target dùng để fit phải thuộc cửa sổ và đã quan sát được tại t. Năm 2019–2020 có 731 ngày lịch, không đồng nhất với cửa sổ 730 ngày.

### 2. Lịch refit chung, neo ngày dự báo 01/01/2021

Refit cho ngày dự báo 01/01/2021 bằng dữ liệu đến hết 31/12/2020; các lần tiếp theo là ngày dự báo 06/01/2021, 11/01/2021,... với origin tương ứng 05/01 và 10/01. Dùng lịch cách 5 ngày lịch cho cả hai coin, bốn mô hình và cả hai horizon. Tiếp tục lịch này sang 2026, không đặt lại mốc ở đầu holdout.

Vẫn phát hành dự báo hằng ngày. Giữa hai lần refit, giữ tham số đã fit và cập nhật feature/trạng thái có điều kiện bằng dữ liệu mới đến origin. Refit tham số không phải chọn lại siêu tham số XGBoost; siêu tham số chỉ chọn một lần trên warmup. Cùng lịch không có nghĩa dùng dữ liệu đến ngày target.

### 3. Target 7 ngày là tổng RV tương lai

`RV_7d(t) = RV(t+1) + ... + RV(t+7)`, đơn vị %² cho giai đoạn 7 ngày; volatility 7 ngày là `sqrt(RV_7d(t))`, đơn vị %. Không lấy trung bình và không coi `sqrt(RV_7d)` là target variance. Trung bình RV lịch sử dùng làm feature HAR là phép tính khác.

Target chỉ hợp lệ khi cả bảy ngày có RV hợp lệ; thiếu bất kỳ ngày nào thì để target NaN. Khi fit tại origin t, chỉ dùng nhãn có ngày kết thúc target ≤ t. Khi chia giai đoạn, lưu đủ ngày bắt đầu/kết thúc target; cửa sổ target băng qua hai giai đoạn được loại khỏi tập đánh giá riêng của từng giai đoạn để không trộn warmup/evaluation/holdout.

### 4. Ngưỡng crisis hiệu chuẩn trên warmup, riêng từng coin

Tính trung bình RV trên 22 ngày lịch liên tiếp, yêu cầu đủ 22 RV hợp lệ. Với mỗi coin, lấy phân vị 90% của các trung bình có ngày kết thúc trong warmup 01/01/2019–31/12/2020, sau đó cố định ngưỡng cho evaluation và holdout. Khi triển khai, lưu giá trị ngưỡng, coin và giai đoạn hiệu chuẩn để tái lập.

Regime đi kèm dự báo t+1 dùng thông tin đến hết origin t: crisis nếu trung bình RV 22 ngày tại t > ngưỡng cố định; nếu không thì bear khi `100*ln(close_t/close_(t−90)) ≤ −10`, bull khi ≥ +10, còn lại normal. Thứ tự ưu tiên crisis > bear > bull > normal. Thiếu lịch sử cần thiết thì gắn `unclassified`, không ép thành normal. Ngưỡng sau warmup chưa được dùng để phân loại tại các origin trước khi warmup kết thúc.

## Phạm vi triển khai hiện tại

Bốn quyết định trên đã được ghi vào cấu hình và tài liệu bàn giao. Chưa tạo dataset feature/target 7 ngày, lịch dự báo, giá trị ngưỡng crisis hay backend/model. Bước tiếp theo triển khai theo các quy ước này và thống nhất schema cột của file dự báo với các thành viên. Ngưỡng regime, scaler và mọi bước hiệu chuẩn không được dùng dữ liệu tương lai/holdout.

Macro observations hiện chưa có release/vintage được xác minh; calendar forward-fill chỉ mô tả. Không đổi cờ `predictive_use_allowed=False` thành True để chạy sensitivity cho đủ bảng.
