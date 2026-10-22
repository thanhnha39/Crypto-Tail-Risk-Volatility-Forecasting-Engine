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
| 9 | Độ dài cửa sổ | 730 ngày |
| 10 | Ước lượng lại | Mỗi 5 ngày, cùng lịch cho bốn mô hình |
| 11 | Horizon | 1 ngày chính; 7 ngày kiểm tra độ nhạy |
| 12 | Giai đoạn | Warmup 2019–2020; đánh giá 2021–2025; holdout 2026 chỉ đánh giá mô hình một lần cuối |
| 13 | XGBoost | Chọn siêu tham số một lần trên warmup, không tinh chỉnh lại |
| 14 | Thông tin | Dự báo t+1 chỉ dùng dữ liệu đến hết ngày t UTC |
| 15 | Đánh giá | QLIKE chính, RMSE, MAE; so sánh Diebold–Mariano |
| 16 | Regime | Crisis: RV trung bình 22 ngày trên phân vị 90%; bull/bear: log return 90 ngày ≥ +10% / ≤ −10%; crisis > bear > bull > normal |
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

## Những chi tiết cần chốt khi làm backend sau

Bảng nhóm chưa chỉ rõ 730 ngày lịch hay 730 quan sát hợp lệ, mốc neo lịch refit 5 ngày, mục tiêu horizon 7 ngày là tổng hay trung bình RV, tập hiệu chuẩn phân vị crisis, và schema cột của file dự báo. Cần chốt trước khi triển khai; không suy diễn từ việc bỏ ngày RV thiếu. Năm 2019–2020 có 731 ngày lịch, khác độ dài cửa sổ 730 ngày. Ngưỡng regime, scaler và mọi bước hiệu chuẩn không được dùng dữ liệu tương lai/holdout.

Macro observations hiện chưa có release/vintage được xác minh; calendar forward-fill chỉ mô tả. Không đổi cờ `predictive_use_allowed=False` thành True để chạy sensitivity cho đủ bảng.
