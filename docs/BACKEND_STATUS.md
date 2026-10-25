# Bàn giao backend hoàn chỉnh

Trạng thái đối chiếu ngày 25/10/2026: Data và Backend 1–4 đã có code, dữ liệu,
kết quả evaluation 2021–2025 và kết quả holdout 01/01–17/10/2026 UTC.

## Đọc và lấy số liệu

| Mục đích | Tài liệu / kết quả |
|---|---|
| Viết phần thực nghiệm 2021–2025 | [Bàn giao viết luận](BAN_GIAO_VIET_LUAN.md) |
| Viết đánh giá cuối 2026 | [Kết quả holdout](HOLDOUT_RESULTS.md) |
| Quy tắc và phương pháp | [Quy định nhóm](GROUP_PROTOCOL.md), [hướng dẫn kỹ thuật](TECHNICAL_GUIDE.md) |
| Tích hợp dashboard | [Schema forecast/risk](forecast_format.md) |
| Bảng và hình 2021–2025 | `outputs/tables/`, `outputs/figures/`, `outputs/risk/` |
| Bảng và hình 2026 | `outputs/holdout_tables/`, `outputs/holdout_figures/`, `outputs/risk_holdout/` |

File bàn giao viết luận cũ là bản ghi nhận ngày 24/10. Những câu “holdout chưa
chấm” trong bản đó đã được cập nhật bằng tài liệu holdout riêng; không dùng
chúng để suy ra trạng thái hiện tại. Hai bộ số liệu phải ghi đúng giai đoạn.

## Phạm vi đã hoàn thành

- Data: BTC/ETH spot 5 phút, UTC, kiểm tra chất lượng và nhật ký nguồn.
- Backend 1: feature/target, lịch refit, regime, chống leakage, đánh giá cùng mẫu.
- Backend 2: HAR-RV, GARCH-t, GJR-GARCH-t, diagnostics và tổ hợp.
- Backend 3: Elastic Net, XGBoost, SHAP, volume ablation; macro sensitivity riêng.
- Backend 4: VaR/ES 95%/99%, Kupiec/Christoffersen, coverage, stress evaluation
  và volatility targeting có phí.
- Holdout: giữ thiết kế đã khóa, tiếp tục lịch refit và residual lịch sử đúng
  thời điểm; có forecast, rủi ro, bảng so sánh, hình và báo cáo kết quả riêng.

GRU là tùy chọn đã hoãn theo phạm vi nhóm chốt. Dashboard và biên soạn luận
là công việc tích hợp tiếp theo. Không cần bổ sung GRU để nghiệm thu backend
trong phạm vi này.

## Kiểm tra bản bàn giao

- Toàn bộ 108 kiểm thử code đạt trong lần kiểm tra lại ngày 25/10/2026.
- Kiểm tra forecast/holdout: [holdout_verification.json](../outputs/holdout_verification.json).
- Đối chiếu risk evaluation với nguồn lịch sử:
  [backend_completion_evaluation_check.json](../outputs/backend_completion_evaluation_check.json).
- Trạng thái từng bước chấm: [final_holdout_pipeline.json](../outputs/final_holdout_pipeline.json).
- Tổng hợp nghiệm thu: [backend_completion.json](../outputs/backend_completion.json).

Từ thư mục gốc repo, dùng Python đã cài `requirements.txt`:

```powershell
python -B run_tests.py
python -B -m src.evaluation.verify_holdout
python -B verify_backend4.py --input-root . --historical-source-ref e226478 --output-report outputs/backend_completion_evaluation_check.json
```

Các lệnh trên kiểm tra kết quả đã lưu. Không chạy lại lượt fit/chấm holdout
đã hoàn thành hoặc xóa khóa để tinh chỉnh theo kết quả.

Đạt kiểm tra kỹ thuật không có nghĩa mọi mô hình vượt benchmark. ES chưa có
kiểm định hiệu chuẩn riêng; mẫu holdout chỉ là một phần năm 2026. Giữ các
giới hạn dữ liệu và diễn giải thống kê trong hai tài liệu kết quả.
