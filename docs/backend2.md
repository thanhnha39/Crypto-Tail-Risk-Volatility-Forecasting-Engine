# Backend 2 — mô hình kinh tế lượng

## Chạy và nhận bàn giao

Dùng Python 3.12 và `requirements.txt` tại gốc repo. Backend 2 đọc dataset Backend 1 đã có; không tải lại raw và không thay đổi cách xây feature.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.backend2
```

Luồng: dataset → HAR/GARCH/GJR → tổ hợp → đánh giá chung → chẩn đoán. Lệnh mặc định chỉ dự báo và đánh giá 2021–2025. Không tạo chương báo cáo học thuật.

| Nơi đọc | Công dụng |
|---|---|
| `config/backend2.toml` | Cấu hình ước lượng, chẩn đoán và thành phần tổ hợp |
| `src/models/har.py`, `garch.py` | HAR-RV OLS, GARCH(1,1)-t và GJR-GARCH(1,1)-t |
| `src/models/combine.py` | Tổ hợp phương sai với trọng số cố định |
| `outputs/forecasts/{symbol}_{model}.parquet` | Dự báo theo hợp đồng chung, gồm h1/h7 và rolling/expanding |
| `outputs/volatility/{symbol}_{model}.parquet` | σ, phương sai, μ, ν và thông tin bàn giao cho phần risk |
| `outputs/diagnostics/backend2_validation.json` | Kết quả kiểm tra bàn giao và hash các dự báo |
| `outputs/diagnostics/garch_diagnostic_summary.csv` | Tóm tắt hội tụ, persistence, đuôi và residual tests |
| `outputs/diagnostics/garch_fit_diagnostics.csv`, `garch_parameters.csv` | Chẩn đoán và tham số/robust SE từng lần refit |
| `outputs/diagnostics/har_fit_diagnostics.csv` | Hệ số, rank, condition number và sai số trong mẫu của HAR |
| `outputs/diagnostics/oos_standardized_residuals.parquet` | Residual một bước ngoài mẫu, chỉ quan sát được sau ngày target |
| `outputs/tables/`, `outputs/figures/` | So sánh, coverage, DM-HLN, regime và hình chẩn đoán |

Các tên model là `har_rv`, `garch`, `gjr_garch`, `combo_econ`. Chưa có XGBoost trong phần bàn giao này; bảng availability ghi riêng trạng thái đó.

## Quy tắc mô hình

- Giữ nguyên quy định trong `docs/GROUP_PROTOCOL.md`: rolling 730 ngày lịch, expanding kiểm tra độ nhạy, refit cách 5 ngày từ origin 31/12/2020, dự báo hằng ngày. Không đổi hash dataset/protocol khi chỉ bổ sung model.
- HAR dùng OLS với intercept và RV ngày, trung bình 5 ngày, trung bình 22 ngày. Fit riêng target h1 và tổng RV h7. Dự báo không dương được chặn ở floor cố định; không chọn floor theo kết quả evaluation.
- GARCH/GJR dùng `arch`, constant mean, Student-t chuẩn hóa có variance bằng 1, `rescale=False`. Return đầu vào đã là phần trăm: không nhân thêm 100. Phương sai đầu ra có đơn vị %², cùng đơn vị RV.
- Tại refit, trạng thái được lọc bằng residual và backcast từ tham số cuối cùng, giống phương thức `forecast` của `arch`. Không lấy trực tiếp trạng thái còn lưu backcast ban đầu của optimizer. Mỗi fit đối chiếu đường variance 7 bước với thư viện.
- Giữa hai lần refit, giữ tham số và cập nhật trạng thái bằng return mới đã biết. Các return sau origin không được truyền vào trạng thái. Chuỗi thiếu ngày không được nén hay lấp; thất bại được giữ trong file với prediction NaN và lý do.
- GARCH/GJR h7 là tổng 7 conditional variance theo đệ quy, không phải lấy variance ngày đầu nhân 7. HAR h7 là dự báo trực tiếp tổng RV, không phải mô hình lặp 7 lần.
- Optimizer có một lần thử lại theo giới hạn iterations đã cấu hình, từ điểm khởi tạo khả thi cố định: μ=mean train, ω=0,05×variance train, α=0,05, β=0,85, γ=0,05 nếu là GJR, ν=8. Đây là biện pháp số chỉ dùng train, không chọn theo loss evaluation. Không hội tụ/vi phạm điều kiện mô hình thì ghi `fit_failed`; không thay ngầm bằng naive. Cùng một fit hoặc lỗi fit GARCH được dùng cho h1/h7 qua cache, nhưng mỗi lượt có trạng thái riêng.
- Persistence gần 1 được gắn cờ. Dự báo hữu hạn nhiều bước vẫn có thể dùng; không diễn giải unconditional variance tại persistence ≥1. ν≤4 nghĩa là Student-t không có moment bậc bốn hữu hạn; diễn giải kiểm định residual thận trọng.

## Tổ hợp và tích hợp XGBoost sau này

`combo_econ` dùng trung bình đều **phương sai** HAR/GARCH/GJR, sau đó mới lấy căn để có σ. Trọng số chốt trước, không tối ưu trên evaluation/holdout. Tại mỗi origin phải có đủ ba thành phần `status=ok`; nếu thiếu thì ghi `component_unavailable`, không đổi trọng số theo ngày.

Không cần XGBoost để tổ hợp ba mô hình này. Khi có file XGBoost hợp lệ, có thể dùng `combine_forecasts` với danh sách thành phần mở rộng và tên tổ hợp mới, hoặc cập nhật cấu hình rồi chạy lại. Phải lưu rõ phiên bản, thành phần và trọng số; không thay nội dung một kết quả cũ mà không cập nhật provenance. File đầu vào phải cùng dataset, protocol, lịch, horizon và window.

## Bàn giao cho VaR/ES

Phần này xuất volatility và tham số; chưa tạo VaR/ES hoặc backtest risk.

- `variance_pct2`: tổng conditional variance h ngày; `sigma_pct` là căn của nó.
- GARCH/GJR có `mean_forecast_pct`, `nu`. Với h1, `student_t_scale_pct = sigma_pct * sqrt((nu-2)/nu)` là scale để dùng với Student-t thông thường. Không dùng trực tiếp σ làm scale của một Student-t chưa chuẩn hóa.
- Với h7, tổng return GARCH không có phân phối Student-t chính xác chỉ vì innovation ngày là Student-t. Do đó `student_t_scale_pct` để trống và distribution ghi `aggregate_not_exact_student_t`. Phần risk cần mô phỏng đường đi hoặc một phương pháp xấp xỉ được ghi rõ.
- HAR dự kiến dùng filtered historical simulation; μ=0 là quy ước bàn giao hiện tại, không phải ước lượng từ dữ liệu tương lai. Tổ hợp chưa có phân phối risk riêng. Risk backend phải xây residual pool point-in-time từ thông tin đã biết ở từng origin.
- File residual ngoài mẫu có `observable_at = target_date + 1 ngày UTC`. Không dùng nguyên bảng residual của toàn giai đoạn làm pool cho mọi origin, vì sẽ chứa thông tin tương lai.
- File `_risk.parquet` thuộc backend risk sau này; không đặt bản xuất σ vào tên risk để tránh hiểu lầm đã có VaR/ES.

## Đọc chẩn đoán và đánh giá

Loglikelihood/AIC/BIC, robust SE, Ljung–Box cho z/z², ARCH-LM và KS statistic được lưu theo từng fit. P-value residual là xấp xỉ; ước lượng tham số và đuôi dày ảnh hưởng phân phối kiểm định. KS chỉ lưu statistic mô tả, không khẳng định p-value chuẩn khi tham số đã được ước lượng. Hình PIT dùng Student-t chuẩn hóa với ν theo từng origin.

Khung chung chỉ chấm target RV thực hợp lệ. Bảng điểm trên mẫu chung yêu cầu tất cả model đã nạp có dự báo hợp lệ; đọc thêm coverage và điểm trên mẫu riêng để thấy số ngày bị loại. Khả năng dự báo daily return variance và RV đo từ intraday không hoàn toàn đồng nhất; đây là benchmark so sánh trên cùng proxy RV, không phải khẳng định hai đại lượng bằng nhau cho từng ngày.

Chỉ chạy lại phần đánh giá/chẩn đoán, không fit lại:

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.aggregate
.\.venv\Scripts\python.exe -m src.models.diagnostics
```

Holdout 2026 được giữ riêng. Lệnh `--final-holdout` là hành động cuối sau khi nhóm khóa toàn bộ model và lựa chọn nghiên cứu; nó ghi lock bắt đầu/kết thúc, không tự chạy trong bàn giao mặc định. Không xóa lock để tinh chỉnh rồi chấm lại. Kiểm tra kỹ thuật đã làm không thay thế review độc lập của một thành viên khác; xem `docs/backend2_review.md`.

Nguồn triển khai: [arch volatility models](https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html), [arch forecasting](https://arch.readthedocs.io/en/latest/univariate/forecasting.html), [arch standardized Student-t](https://arch.readthedocs.io/en/latest/univariate/generated/arch.univariate.StudentsT.html), [statsmodels Ljung–Box](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html), [ARCH-LM](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_arch.html).
