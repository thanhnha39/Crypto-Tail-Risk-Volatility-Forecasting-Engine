# Backend 1 — feature và khung đánh giá dùng dữ liệu thật

## Đầu vào và cấu hình

Nhánh này ghép nhánh `data` vào `backend-1`. Nguồn chính: `data/interim/{symbol}_daily_reference_qa.parquet`, được tạo từ 828.050 nến thật/mỗi coin. Code tải/làm sạch và snapshot hash từ nhánh data được giữ nguyên. Cấu hình nghiên cứu ở `config/data.toml`; cấu hình feature/đánh giá bổ sung ở `config/backend1.toml`. YAML cũ đã ngừng dùng.

## Chạy trên máy thành viên

Python 3.12, mở terminal ở gốc repo:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_tests.py
.\.venv\Scripts\python.exe -m src.backend1
```

Chạy từng bước: `src.features.build_dataset`, `src.evaluation.run_baselines`, `src.evaluation.aggregate`.
Mặc định chỉ chấm điểm evaluation 2021–2025. Pipeline không tạo chương báo cáo và không tự tải dữ liệu thay thế.

## Các file bàn giao

| File/thư mục | Vai trò |
|---|---|
| `data/processed/dataset.parquet` | Một symbol × ngày origin UTC; feature, nhãn target 1/7 ngày, trạng thái giai đoạn |
| `data/processed/dataset_meta.json` | Nguồn thật, schema feature, hash input/dataset/protocol, giới hạn |
| `data/processed/forecast_schedule.parquet` | Lịch chung cho rolling/expanding, horizon 1/7, evaluation/holdout; không phải file dự báo |
| `data/processed/regime_thresholds.json` | Ngưỡng crisis cố định từng coin và số quan sát hiệu chuẩn |
| `data/processed/regime_labels.csv` | Nhãn regime tại origin, RV trung bình 22 ngày, return 90 ngày |
| `outputs/tables/regime_labels.csv` | Bản nhãn gọn cho ghép kết quả |
| `outputs/forecasts/{symbol}_{model}.parquet` | Dự báo baseline/thành viên; chứa cả horizon/window |
| `outputs/tables/model_comparison.csv` | RMSE, MAE, QLIKE trên cùng ngày hợp lệ giữa các model trong mỗi tác vụ |
| `outputs/tables/dm_vs_benchmark.csv` | DM-HLN so với HAR-RV, tách coin/horizon/window/loss |
| `outputs/tables/regime_performance.csv`, `dm_by_regime.csv` | Hiệu quả và DM theo regime |
| `outputs/tables/forecast_coverage.csv` | Số ngày yêu cầu, dự báo thành công, target hợp lệ và mẫu chung |
| `outputs/tables/model_availability.csv` | Mô hình đã có hoặc còn chờ thành viên |
| `outputs/tables/backend1_validation.json` | Kết quả xác minh luồng thật và provenance |
| `outputs/figures/backend1_*.png` | Forecast/actual RV và căn RV, rolling QLIKE, so sánh theo regime |
| `outputs/legacy_synthetic/` | Các ví dụ mô phỏng cũ kế thừa từ main, không được đọc vào tổng hợp hiện tại |

## Định nghĩa feature/target

- `rv_d`: RV ngày origin t, là RV “hôm qua” khi xét ngày cần dự báo t+1. `rv_w`, `rv_m`: trung bình 5 và 22 ngày lịch đến t; yêu cầu đủ các ngày.
- `park`: Parkinson variance `(100*ln(high/low))² / (4*ln(2))`; chỉ dùng high/low của ngày đủ 288 nến. Đây là estimator theo giả định mô hình giá, không thay RV quan sát.
- `ret_d`: return log close-to-close (%). `log_qv`: log quote volume ngày đầy đủ.
- `log_turn_rel`: log tỷ số quote volume hiện tại/trung bình quote volume 22 ngày. **Chỉ là proxy hoạt động giao dịch**, không phải turnover/market capitalization vì chưa có market cap lịch sử đồng nhất.
- `y_rv_h1=RV(t+1)`; `y_rv_h7=sum(RV(t+1)..RV(t+7))`, đơn vị %². `y_logrv_h*` là log target cho ML. Thiếu bất kỳ RV trong target thì để NaN; log chỉ xác định khi RV dương.
- Nhãn giai đoạn theo toàn bộ khoảng target; target băng qua hai giai đoạn được gắn `cross_segment` và không dùng để đánh giá riêng giai đoạn đó.
- Macro không nằm trong `FEATURE_COLS`. FRED observations/calendar cũ chưa được xác minh release/vintage; lag một ngày không làm chúng đủ điều kiện dự báo. Sensitivity macro đang chờ dữ liệu point-in-time được xác minh.

## Lịch và cách fit

Cửa sổ rolling gồm 730 ngày lịch đến refit origin; expanding bắt đầu từ 01/01/2019. Nhãn nhiều ngày phải nằm trọn cửa sổ và đã hoàn tất tại refit origin. Chỉ sau khi chọn khoảng thời gian mới lọc feature/nhãn thiếu; không lùi cửa sổ để bù đủ dòng.

Refit neo origin 31/12/2020 (ngày dự báo đầu 01/01/2021), mỗi 5 ngày lịch. Ngày thiếu feature không làm dịch lịch. Giữa các refit, tham số cố định nhưng feature/trạng thái được cập nhật hằng ngày. `predict()` nhận một ngày mỗi lần để GARCH có thể cập nhật state đúng; tham số không được fit lại ngoài lịch.

`min_train_rows=365` là kiểm tra tối thiểu dòng hợp lệ sau lọc, không thay độ dài cửa sổ 730 ngày. Mô hình quan sát return như GARCH có thể khai báo `requires_target=False`; khung sẽ dùng các quan sát đến refit origin và không đưa nhãn tương lai vào fit.

## Regime

Ngưỡng là phân vị 90% của RV trung bình 22 ngày, lấy các giá trị kết thúc trong warmup 2019–2020, riêng từng coin. Cần đủ 22 RV liên tiếp; dùng interpolation linear, đóng băng sau warmup. Không dùng ngưỡng này để gán nhãn các origin trước khi warmup kết thúc. Các origin thiếu RV22/return90 được gắn `unclassified`. Thứ tự crisis > bear > bull > normal. Nhãn gắn với thông tin tại origin, không lấy RV thực tế của ngày target để phân loại.

## Baseline và khả năng so sánh

Đã có naive `h*RV_t`, historical mean target và HAR-RV OLS tham chiếu. HAR trả variance mức dương, sàn kỹ thuật 1e-10. Các mô hình này kiểm tra luồng đánh giá; không giả lập đầu ra GARCH/GJR/XGBoost. Bảng so sánh bốn mô hình chính chỉ hoàn chỉnh sau khi các thành viên đưa file hợp lệ vào. `model_availability.csv` và `core_models_complete` công khai trạng thái này.

So sánh trên giao các ngày mà tất cả model hiện có trong một tác vụ đều dự báo thành công và target dương hợp lệ. Luôn đọc kèm coverage vì mẫu giao có thể nhỏ hơn lịch gốc. QLIKE chuẩn hóa = y/f − ln(y/f) − 1; RMSE/MAE trên RV %². DM dùng d = loss(model) − loss(HAR), âm là model có loss thấp hơn; Bartlett HAC đến lag h−1 **theo ngày lịch**, hiệu chỉnh HLN và p-value Student-t(n−1). Mẫu ít hơn 30 hoặc phương sai loss sai khác bằng 0 có trạng thái rõ ràng, không gán p giả. Lag h−1 là quy ước kiểm định; dependence dài hơn do refit/regime vẫn là hạn chế cần kiểm tra khi có mô hình cuối.

## Holdout

Dataset và lịch có 2026 đến 17/10/2026, nhưng default không chạy/chấm điểm holdout. Sau khi nhóm khóa mô hình và siêu tham số mới dùng `python -m src.evaluation.run_baselines --final-holdout`, rồi `python -m src.evaluation.aggregate --final-holdout`. Các lệnh tạo file đánh dấu để không vô tình chạy/chấm lại; lỗi giữa chừng cần kiểm tra trạng thái trước khi tiếp tục. Không dùng các lệnh final để tuning.

## Nguồn phương pháp

Parkinson (1980): https://www.cmegroup.com/trading/fx/files/michael_parkinson.pdf

Harvey, Leybourne & Newbold (1997), DOI: https://doi.org/10.1016/S0169-2070(96)00719-4

Đối chiếu HLN/Bartlett với implementation gốc của forecast: https://github.com/robjhyndman/forecast/blob/master/R/DM2.R

SciPy Student-t: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html
