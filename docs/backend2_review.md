# Kiểm tra kỹ thuật Backend 2

Đây là ghi chú tích hợp code, không phải chương báo cáo học thuật hoặc xác nhận review độc lập bởi thành viên khác.

## Điểm đã sửa khi review khung chung

1. Train của một mô hình supervised nay chỉ chứa target đúng horizon đang fit. Trước đó mô hình h1 còn nhìn thấy cột target h7 chưa chắc đã quan sát đầy đủ. HAR không dùng cột này, nhưng loại bỏ nó giúp adapter mới không vô tình dùng nhãn chưa biết.
2. Fit/forecast thất bại được ghi status và NaN, không âm thầm tái sử dụng fit cũ hoặc thay model khác. Bảng coverage giữ được số lượng thất bại.
3. Trạng thái GARCH tại refit dùng final-parameter backcast giống public forecast của `arch`. Trạng thái conditional volatility lưu từ optimizer có thể khác nhẹ; với beta gần 1, khác biệt vẫn tồn tại sau 730 ngày. Có kiểm tra hồi quy riêng cho trường hợp này.
4. Tổ hợp dùng variance, không trung bình σ; không học trọng số từ evaluation. Thiếu một thành phần thì không tạo prediction.
5. σ h7 không được gắn scale Student-t chính xác. Bản xuất risk-volatility thể hiện giới hạn này rõ ràng.

## Kiểm tra có thể chạy lại

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.models.diagnostics
```

35 unit tests đã qua tại thời điểm triển khai, bao gồm 13 kiểm tra Backend 2: đệ quy khớp `arch`, cập nhật trạng thái giữa refit, beta gần 1, cache tách trạng thái, không dùng return tương lai, thiếu return, không hội tụ, nhãn khác horizon, thất bại không có dự báo giả, scale Student-t, tổ hợp variance và provenance. Fixtures mô phỏng chỉ dùng trong test; kết quả nghiên cứu dùng dữ liệu thật.

Trên dữ liệu thật, từng lần fit có đối chiếu đường variance 7 bước với `arch`; kết quả và độ lệch tối đa nằm trong `outputs/diagnostics/backend2_validation.json`. Bảng fit ghi tham số, hội tụ và residual tests; không coi việc phần mềm chạy xong là bằng chứng mọi mô hình đều phù hợp.

Snapshot 2021–2025 đã chạy: 2.928 fit GARCH/GJR duy nhất, tất cả hội tụ; 15 fit cần khởi tạo lại. Độ lệch đệ quy so với `arch` tối đa 8,53×10⁻¹⁴. Có 1.528 fit persistence gần 1 và 2.635 fit ν≤4, được giữ và gắn cờ trong bảng chẩn đoán. Các cờ này cần được xem xét khi diễn giải tính dừng, robust SE và residual tests; không đổi tham số theo kết quả evaluation để làm mất cờ. HAR và tổ hợp vẫn có ngày không dự báo vì thiếu feature, ghi rõ trong coverage; không lấp dữ liệu để đạt đủ số dòng `ok`.

## Thành viên review độc lập cần làm

- Đọc `src/models/har.py`, `garch.py` và `src/evaluation/walkforward.py`, xác nhận quy ước thời điểm và cửa sổ theo `GROUP_PROTOCOL.md`.
- Chạy test; chọn một origin kiểm tra dữ liệu train chỉ đến refit cutoff và trạng thái chỉ cập nhật đến origin.
- Đối chiếu đơn vị return %, RV %²; h7 là tổng; đọc coverage và các cờ persistence/ν/residual.
- Xác nhận không chạy holdout, không dùng residual tương lai làm pool FHS.

Trạng thái review độc lập vẫn là `pending_team_review`; không đánh dấu hoàn tất chỉ dựa vào kiểm tra tự động.
