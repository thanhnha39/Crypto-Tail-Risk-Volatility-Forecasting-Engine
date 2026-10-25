# Quy trình đánh giá cuối trên holdout 2026

Lượt chấm cuối dùng snapshot hiện tại từ 01/01 đến 17/10/2026 UTC cho BTCUSDT và ETHUSDT. Dữ liệu đã từng được xem cho QA/mô tả; chưa dùng để chấm mô hình hoặc chọn lại siêu tham số. Không gọi đây là trọn năm 2026 hoặc dữ liệu chưa từng được nhìn thấy.

## Thiết kế khóa trước khi chấm

- Giữ chín model: HAR-RV, GARCH-t, GJR-GARCH-t, XGBoost, Elastic Net, naive RV, historical mean, combo_econ, combo_core4. Giữ cấu hình, features và lựa chọn warmup hiện có.
- Chính: rolling 730 ngày lịch, h1, QLIKE, HAR-RV benchmark. RMSE/MAE bổ sung. So sánh trên cùng ngày hợp lệ của các model; báo cáo coverage riêng.
- Refit mỗi 5 ngày lịch theo mốc origin 31/12/2020, không đặt lại mốc 01/01/2026. Được dùng quan sát/nhãn 2026 đã hoàn tất trước cutoff để refit theo thiết kế; không dùng kết quả holdout để tune.
- Phụ: expanding, tổng RV h7 trên target nằm trọn holdout và đủ dữ liệu, regime theo origin và ngưỡng warmup, volume ablation/SHAP. Không thêm model, macro hoặc stress event mới từ việc nhìn kết quả 2026.
- DM-HLN và HAC theo code hiện có. Họ kiểm định chính là tất cả so sánh QLIKE rolling h1 với HAR của hai coin, điều chỉnh Holm chung; các bảng khác có p danh nghĩa. Chênh loss âm có lợi cho model. Không yêu cầu ML thắng benchmark để nghiệm thu.
- Risk h1: VaR/ES 95%/99%; Student-t cho GARCH/GJR; FHS cho model còn lại. Pool FHS gồm residual OOS riêng model/window của 2021–2025 rồi thêm 2026 khi observable_at <= forecast_available_at, target residual < target forecast. Giữ minimum 20 residual, không đổi quy tắc quantile.
- Kupiec/Christoffersen kiểm tra VaR, không phải hiệu chuẩn ES. Mẫu tối đa 290 ngày chỉ có 2,9 vi phạm kỳ vọng ở 99%, nên công suất kiểm định hạn chế. P-value rủi ro là danh nghĩa.
- RQ5 phụ giữ target 15%/năm, trần tỷ trọng 1, phí một chiều 5 bps, 365 ngày/năm. Đường vốn holdout bắt đầu flat và tính phí ban đầu; không nối trạng thái 2025. Chưa có slippage/latency/cash yield.

## Chạy và truy vết

Chạy `python -B run_tests.py`, rồi `python -B -m src.final_holdout --prepare` để khóa code, cấu hình, dataset, lựa chọn mô hình và các kết quả evaluation. Chỉ sau đó chạy `python -B -u -m src.final_holdout --run`.

Orchestrator gọi từng module dự báo trước khi aggregate đúng một lần. Không chạy tuần tự backend2/backend3 với cờ final-holdout vì cả hai entry point cũ đều gọi aggregate và sẽ đụng khóa chấm. Baseline không viết lại lịch đã khóa.

Kết quả mới dùng forecasts_holdout, volatility_holdout, diagnostics_holdout, ablation_holdout, holdout_tables, holdout_figures và risk_holdout trong outputs. Evaluation 2021–2025 không ghi đè. Plan và pipeline manifest ghi hash, thời điểm, phiên bản môi trường và trạng thái từng bước; kiểm tra lại hash trước/sau mỗi bước.

`--resume` chỉ tiếp tục bước chưa bắt đầu khi các bước trước đã ghi hoàn tất và hash vẫn khớp. Bước failed/started cần điều tra kỹ thuật và biên bản khôi phục riêng; không xóa khóa để thử lại. Hoàn tất rồi không mở lại cùng mẫu để tinh chỉnh.

`python -B -m src.evaluation.verify_holdout` kiểm tra lại lịch/cutoff, tất cả VaR/ES, FHS đầu năm, thay đổi residual tương lai, cùng mẫu, đường vốn và hash. `python -B -m src.reporting.holdout_report` tạo lại báo cáo từ kết quả đã lưu, không fit lại model.

Manifest risk evaluation lưu hash của code tại thời điểm tạo ra kết quả cũ. Sau khi nâng cấp code, đối chiếu bản lịch sử bằng `python -B verify_backend4.py --input-root . --historical-source-ref e226478 --output-report outputs/holdout_evaluation_compatibility.json`; không sửa manifest hoặc báo cáo verification cũ để giả định code mới đã tạo ra kết quả trước đây.

Kết quả số liệu và diễn giải cuối được tổng hợp trong [HOLDOUT_RESULTS.md](HOLDOUT_RESULTS.md). Trạng thái hoàn thành trong outputs/final_holdout_pipeline.json là nguồn xác nhận lượt chấm đã xong.
