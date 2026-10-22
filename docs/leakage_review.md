# Kiểm tra chống leakage và review chéo

Tự động: `python run_tests.py`. Các test thử bỏ/phá dữ liệu sau T, kiểm tra feature quá khứ không đổi; target 7 ngày là tổng và thiếu một ngày thì NaN; target cross-segment; nhãn crisis warmup cố định; lịch refit không dịch khi mất feature; cửa sổ theo ngày lịch; nhãn train hoàn tất trước refit; predict/history không được nhận target; đơn vị naive h7; validator bắt metadata sai; common sample; DM-HLN và giữ khoảng trống theo ngày lịch.

Review độc lập theo yêu cầu nhóm **chưa được ký xác nhận**. Người review: __________; ngày: __________; commit: __________.

- [ ] Đối chiếu RV với 288 return từ nến gốc, giữ return lớn và không scale ngày thiếu.
- [ ] Tất cả feature rolling trailing; không bfill, không chuẩn hóa bằng toàn mẫu.
- [ ] Crisis threshold chỉ dùng warmup từng coin; không dùng threshold hoàn chỉnh cho origin trước warmup end.
- [ ] Macro không nằm trong features; không coi shift một ngày là đã xác minh historical availability.
- [ ] Target 7 ngày chưa quan sát hết không vào train; giữ lịch trước khi lag/rolling.
- [ ] Đúng refit clock, train_start/train_end và thứ tự cập nhật state của adapter GARCH.
- [ ] Kiểm tra file thành viên bằng validate_forecasts; so sánh cùng mẫu và đọc coverage.
- [ ] Không dùng holdout chọn siêu tham số; không gọi final-holdout khi chưa chốt mô hình.

Kết luận reviewer: __________.
