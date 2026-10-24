# VIX/USD: dữ liệu vintage và sensitivity riêng

## Nguồn và thời điểm thông tin

Bộ dữ liệu bổ sung dùng ALFRED cho `VIXCLS` và `DTWEXBGS`. Danh sách ngày vintage được lấy từ form download của từng chuỗi; mỗi cột CSV phải mang đúng mã chuỗi và ngày vintage đã yêu cầu. Mỗi snapshot giữ giá trị của ngày quan sát gần nhất có số liệu ở chính vintage đó. Không lấy giá trị FRED tải hiện tại rồi gán lùi ngày công bố.

ALFRED cung cấp thông tin theo ngày, không chứng minh thời điểm công bố chính xác trong ngày. Quy tắc bảo thủ: `available_at = vintage_date + 2 ngày UTC`; feature tại ngày origin t chỉ dùng snapshot có `available_at <= 00:00 UTC ngày t`. Quy tắc này còn chậm hơn dùng thông tin đến cuối t, nhằm tránh suy diễn giờ công bố từ ngày vintage ở Mỹ. Việc công bố H.10 theo tuần và ngày nghỉ đã phản ánh qua ngày vintage thực tế; không giả định mọi quan sát USD đều xuất hiện vào ngày kế tiếp.

Tên cột `log_vix_l1`/`log_usd_l1` kế thừa schema đã khai báo; thời điểm thực tế được quyết định bằng `available_at` và as-of ở trên, không phải phép shift một hàng hoặc đúng một ngày quan sát. Cần đọc kèm các cột `_available_at` khi kiểm tra dataset macro.

Nối as-of backward, không backfill đầu chuỗi. Giữa hai vintage, giữ thông tin mới nhất đã được phép biết. Phiên bản sửa đổi sau này chỉ ảnh hưởng feature sau thời điểm khả dụng của phiên bản đó. Không dùng trường kết thúc vintage trong tương lai làm predictor. Có thể có độ trễ lưu trữ tại ALFRED so với nguồn; thiết kế chấp nhận chậm hơn và không khẳng định là phản ứng theo thời gian thực của Cboe/Fed.

Kiểm tra nguồn phát hiện một số snapshot có giá trị cho ngày quan sát sau chính ngày vintage (ví dụ VIX vintage 27/05/2022 chứa ngày 30/05/2022). Những quan sát này bị loại trước khi chọn giá trị gần nhất; số lượng được lưu ở `excluded_future_observations`. Raw được giữ nguyên để đối chiếu, không coi ngày vintage là đủ để bỏ qua kiểm tra ngày quan sát.

Chỉ tải vintage 01/11/2018–31/12/2025. Chuỗi USD này bắt đầu có vintage từ 04/02/2019; không gán dữ liệu được công bố hồi tố cho các ngày trước đó. Không tải/chấm holdout 2026 trong bước này. Dataset chính và raw FRED cũ được giữ nguyên; bộ macro mới nằm riêng.

## Thí nghiệm có/không biến phụ

Mỗi Elastic Net/XGBoost có bốn biến thể:

| Tên | Predictors |
|---|---|
| `macro_base` | Năm core + hai volume; không macro |
| `vix` | Baseline + log VIX |
| `usd` | Baseline + log USD |
| `vix_usd` | Baseline + cả hai macro |

Cả bốn biến thể dùng điều kiện đủ dữ liệu của toàn bộ chín biến; kiểm tra hash cùng dòng train, cùng số dòng và cùng lịch refit. Khi chấm, dùng giao ngày hợp lệ của tám model/biến thể cho từng coin/window/horizon. Vì tập đủ dữ liệu khác, baseline này không được thay bằng file dự báo chính rồi coi là so sánh cùng mẫu.

Giữ nguyên siêu tham số và seed đã khóa trên warmup của mô hình chính; không tune lại theo macro/evaluation. Scaler và smearing chỉ fit trên train hiện tại. Lịch rolling 730 ngày, expanding, refit mỗi 5 ngày, h1/h7 giữ nguyên. Kết quả trả lời giá trị bổ sung của macro trong thiết kế với tham số cố định, không khẳng định đây là mô hình macro đã được tối ưu riêng.

Macro chỉ dùng sensitivity theo GROUP_PROTOCOL. Các file mới không được đưa vào `outputs/forecasts/` để tránh làm thay đổi bảng xếp hạng mô hình chính.

## File và lệnh chạy

| File | Công dụng |
|---|---|
| `data/raw/alfred/manifest.json` và CSV/HTML đi kèm | URL nguồn, ngày vintage, hash và provenance |
| `data/interim/macro_vintages.parquet` | Snapshot gần nhất đã biết theo mỗi vintage, thời điểm khả dụng bảo thủ |
| `outputs/sensitivity/macro/forecasts/` | 16 file dự báo của hai coin × tám biến thể |
| `outputs/sensitivity/macro/fit_diagnostics.csv` | Cùng dòng train, scaler và trạng thái fit |
| `outputs/sensitivity/macro/coverage.csv`, `validation.json` | Coverage, hash và kiểm tra bàn giao |
| `outputs/tables/backend3_macro_ablation.csv` | QLIKE/RMSE/MAE và DM-HLN so với baseline không macro |

```powershell
python -m src.data.macro_vintages
python -m src.models.macro_sensitivity
python -m src.models.ml_analysis
python -m src.evaluation.robustness
```

Hai lệnh đầu tải bộ macro/chạy sensitivity riêng. `src.backend3` mặc định vẫn chạy các mô hình chính và cập nhật thống kê, không tự tải lại vintage hay fit macro. Các file đã commit đủ để thành viên đọc kết quả không cần tải lại.

Có thể chia tác vụ theo `--symbol BTCUSDT --model enet` (tương tự cho ETHUSDT/XGBoost) trong các terminal riêng, hoặc thêm `--variant vix`/`usd`/`vix_usd`/`macro_base` để chạy từng nhóm biến. Mỗi tác vụ ghi file forecast và refit riêng, không dùng chung estimator. Khi đủ tác vụ hoàn tất, chạy `python -m src.models.macro_sensitivity --analyze-only` để kiểm tra đủ 16 file, ghép diagnostics và xuất bảng. Tham số/seed giữ nguyên; không chạy hai tác vụ có phạm vi trùng nhau đồng thời.

## Nguồn phương pháp và dữ liệu

Snapshot đã chạy: 1.790 vintage VIX, 361 vintage USD; 23 ô nguồn có ngày quan sát sau vintage bị loại khỏi bước chọn feature. Có 23.360 fit thành công, 16 file dự báo, 64 dòng so sánh; đủ lịch evaluation và cùng mẫu train được validator đối chiếu. Bản kiểm tra sensitivity tại thời điểm triển khai có 53 kiểm tra qua (trước khi bổ sung risk), gồm availability, revision, bất biến với thông tin tương lai và cùng mẫu. Không chấm holdout hoặc chọn lại siêu tham số. Số quan sát chấm điểm và trạng thái DM phải đọc kèm từng dòng bảng; không suy luận hiệu quả tăng chỉ vì thêm macro.

- [ALFRED: định nghĩa vintage và định dạng dữ liệu](https://alfred.stlouisfed.org/help/downloaddata).
- [FRED/ALFRED: real-time periods và dữ liệu sửa đổi](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).
- [Fed H.10: lịch công bố hàng tuần](https://www.federalreserve.gov/releases/h10/).
- [ALFRED VIXCLS](https://alfred.stlouisfed.org/series?seid=VIXCLS), [ALFRED DTWEXBGS](https://alfred.stlouisfed.org/series?seid=DTWEXBGS).
